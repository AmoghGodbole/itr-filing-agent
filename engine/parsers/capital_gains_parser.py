"""
Capital gains parser — extracts realized P&L from broker tax P&L PDFs.

Supports: Zerodha Tax P&L, Groww P&L, Upstox P&L, CAMS / KFintech consolidated
account statement, and any broker that produces a readable tax P&L PDF.

Budget 2024 split (Jul 23, 2024): the parser attempts to extract pre/post split
if the broker report shows it (Zerodha does from FY 2024-25). When the split is
not available in the document, enter the full gain in the post-Jul 23 bucket
(the more common / larger portion of the year) and note the limitation in CA review.
"""

import base64
import io
import json
from pathlib import Path

import anthropic
import pdfplumber

from engine.parsers._claude_utils import get_model_and_thinking_kwargs, safe_text_block
from engine.models_capital_gains import (
    CapitalGainsSummary,
    EquityGainsSplit,
    OtherGains,
    PropertyGains,
)

EXTRACTION_PROMPT = """You are an expert Indian tax document parser. Extract capital gains figures from this broker tax P&L report.

FY 2024-25 has a critical mid-year tax rate change on July 23, 2024 (Budget 2024):
- Listed equity / equity-oriented MF STCG (< 12 months, STT paid, Sec 111A): 15% before Jul 23 → 20% after
- Listed equity / equity-oriented MF LTCG (≥ 12 months, STT paid, Sec 112A): 10% before Jul 23 → 12.5% after; exemption ₹1L → ₹1.25L
- Other LTCG (Sec 112): 20% with indexation before Jul 23 → 12.5% without indexation after

Asset classification:
- "Equity" = listed shares, equity-oriented MF (>65% equity), ETFs on equity indices — these qualify for Sec 111A/112A rates when STT is paid
- "Debt / Other" = debt MF (units purchased after Apr 1, 2023), bond ETFs, gold ETFs backed by physical gold, unlisted shares — these do NOT qualify for 111A/112A; short-term at slab, long-term at 20%/12.5%
- "Property" = immovable property — always entered manually, leave at 0 unless explicitly shown

Return ONLY a valid JSON object matching exactly this structure. Use 0 for missing or inapplicable figures.
Net gains/losses: enter the net realized P&L for each bucket (sale proceeds minus cost of acquisition).
Negative values mean a net loss for that bucket — enter them as negative numbers.

{
  "equity": {
    "stcg_pre_jul23": 0,
    "stcg_post_jul23": 0,
    "ltcg_pre_jul23": 0,
    "ltcg_post_jul23": 0
  },
  "other": {
    "stcg_at_slab": 0,
    "ltcg_20pct_with_indexation": 0,
    "ltcg_125pct_without_indexation": 0
  },
  "property": {
    "stcg": 0,
    "ltcg_with_indexation": 0,
    "ltcg_without_indexation": 0
  },
  "tds_on_gains": 0
}

Important extraction notes:
1. If the report does NOT show a pre/post Jul 23 split, place the full STCG in stcg_post_jul23 and full LTCG in ltcg_post_jul23 (this is conservative; CA will verify).
2. Do NOT include unrealized gains. Only extract realized (sold) positions.
3. For equity MF: confirm it is equity-oriented (>65% equity allocation) before using 111A/112A buckets. If unclear, put in "other".
4. TDS on gains appears as TDS deducted at source by the broker (on dividends, on MF redemptions, etc.) — use Form 26AS or the broker's TDS certificate for this figure; if not shown, use 0.
5. Zerodha Tax P&L shows "Short term" and "Long term" sections with pre/post budget splits — use those directly.
6. CAMS/KFintech shows individual redemption rows with purchase/sale dates and gain — classify by holding period (< 12 months = STCG, ≥ 12 months = LTCG) and date vs Jul 23, 2024.
"""


def _read_pdf(pdf_path: Path) -> tuple[str, str]:
    raw_bytes = pdf_path.read_bytes()
    text_parts = []
    with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    raw_text = "\n\n--- PAGE BREAK ---\n\n".join(text_parts)
    pdf_b64 = base64.standard_b64encode(raw_bytes).decode("utf-8")
    return raw_text, pdf_b64


_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "equity": {
            "type": "object",
            "properties": {
                "stcg_pre_jul23": {"type": "number"},
                "stcg_post_jul23": {"type": "number"},
                "ltcg_pre_jul23": {"type": "number"},
                "ltcg_post_jul23": {"type": "number"},
            },
            "required": ["stcg_pre_jul23", "stcg_post_jul23", "ltcg_pre_jul23", "ltcg_post_jul23"],
            "additionalProperties": False,
        },
        "other": {
            "type": "object",
            "properties": {
                "stcg_at_slab": {"type": "number"},
                "ltcg_20pct_with_indexation": {"type": "number"},
                "ltcg_125pct_without_indexation": {"type": "number"},
            },
            "required": ["stcg_at_slab", "ltcg_20pct_with_indexation", "ltcg_125pct_without_indexation"],
            "additionalProperties": False,
        },
        "property": {
            "type": "object",
            "properties": {
                "stcg": {"type": "number"},
                "ltcg_with_indexation": {"type": "number"},
                "ltcg_without_indexation": {"type": "number"},
            },
            "required": ["stcg", "ltcg_with_indexation", "ltcg_without_indexation"],
            "additionalProperties": False,
        },
        "tds_on_gains": {"type": "number"},
    },
    "required": ["equity", "other", "property", "tds_on_gains"],
    "additionalProperties": False,
}


def parse_capital_gains(pdf_path: str | Path) -> CapitalGainsSummary:
    """
    Extract capital gains figures from a broker tax P&L PDF.
    Returns a CapitalGainsSummary with pre/post Jul 23 2024 splits where available.
    Property gains are always left at 0 (manual entry by CA).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Broker P&L PDF not found: {pdf_path}")

    client = anthropic.Anthropic()
    raw_text, pdf_b64 = _read_pdf(pdf_path)
    model, extra = get_model_and_thinking_kwargs()

    with client.messages.stream(
        model=model,
        max_tokens=4096,
        **extra,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                        "title": "Broker Tax P&L Report",
                    },
                    {
                        "type": "text",
                        "text": f"Here is also the extracted text for reference:\n\n{raw_text}\n\n{EXTRACTION_PROMPT}",
                    },
                ],
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _OUTPUT_SCHEMA,
            }
        },
    ) as stream:
        final = stream.get_final_message()

    data = json.loads(safe_text_block(final.content))

    return CapitalGainsSummary(
        equity=EquityGainsSplit(**data["equity"]),
        other=OtherGains(**data["other"]),
        property_gains=PropertyGains(**data["property"]),
        tds_on_gains=data["tds_on_gains"],
    )
