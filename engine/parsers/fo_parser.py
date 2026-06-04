"""
F&O parser — extracts P&L from broker tax P&L PDFs.

Supports: Zerodha Tax P&L, Groww, Upstox, Angel One, and any broker that
produces a readable derivatives P&L report.

Key metric extracted: TURNOVER = absolute sum of all trade profits + losses.
This is NOT the same as net P&L. A trade with +₹50,000 profit AND another
with -₹30,000 loss → turnover ₹80,000, not ₹20,000.

Most brokers already compute turnover per Sec 44AB in their tax reports.
"""

import base64
import io
import json
from pathlib import Path

import anthropic
import pdfplumber

from engine.parsers._claude_utils import get_model_and_thinking_kwargs, safe_text_block
from engine.models_fo import CarryForwardLoss, FOData, FOExpenses, FOSegmentPL

EXTRACTION_PROMPT = """You are an expert Indian tax document parser. Extract F&O (Futures & Options) trading P&L data from this broker tax report.

F&O is classified as non-speculative business income under Section 43(5) of the Income Tax Act.

CRITICAL — TURNOVER DEFINITION:
Turnover for tax audit purposes (Section 44AB) = ABSOLUTE SUM of all profitable trades + ABSOLUTE SUM of all loss-making trades.
Example: if a trader has profits of ₹5L across various trades and losses of ₹3L across other trades, turnover = ₹8L (NOT ₹2L net).
Most broker reports show this directly. If not shown, compute: gross_profit + gross_loss (both as positive numbers).

Segments to extract:
- Equity Futures (Nifty, BankNifty, stock futures)
- Equity Options (calls, puts on indices and stocks)
- Commodity F&O (MCX — gold, silver, crude oil, etc.) if present
- Currency F&O (NSE CDS) if present

For each segment extract:
- gross_profit: total of all profitable trade P&L (positive number)
- gross_loss: total of all loss-making trade P&L (ENTER AS POSITIVE, engine will subtract)
- net_pl: gross_profit - gross_loss (can be negative if net loss)
- turnover: gross_profit + gross_loss (absolute sum for Sec 44AB)

Also extract expenses if shown (brokerage, STT, exchange fees, etc.).

Return ONLY a valid JSON object:
{
  "segments": [
    {
      "segment": "Equity Futures",
      "gross_profit": 0,
      "gross_loss": 0,
      "net_pl": 0,
      "turnover": 0
    }
  ],
  "expenses": {
    "brokerage": 0,
    "stt": 0,
    "exchange_fees": 0,
    "dp_charges": 0,
    "internet_software": 0,
    "advisory_fees": 0,
    "depreciation": 0,
    "others": 0
  },
  "tds_on_fo": 0
}

If a segment is not present in the report, omit it from the array. Do NOT include spot equity or mutual funds in F&O segments — those are capital gains.
If the report already shows a "Tax P&L" or "Business Income" summary, use those figures.
Enter gross_loss as a POSITIVE number (the engine computes net_pl = gross_profit - gross_loss).
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


_SEGMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "segment": {"type": "string"},
        "gross_profit": {"type": "number"},
        "gross_loss": {"type": "number"},
        "net_pl": {"type": "number"},
        "turnover": {"type": "number"},
    },
    "required": ["segment", "gross_profit", "gross_loss", "net_pl", "turnover"],
    "additionalProperties": False,
}

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {"type": "array", "items": _SEGMENT_SCHEMA},
        "expenses": {
            "type": "object",
            "properties": {
                "brokerage": {"type": "number"},
                "stt": {"type": "number"},
                "exchange_fees": {"type": "number"},
                "dp_charges": {"type": "number"},
                "internet_software": {"type": "number"},
                "advisory_fees": {"type": "number"},
                "depreciation": {"type": "number"},
                "others": {"type": "number"},
            },
            "required": ["brokerage", "stt", "exchange_fees", "dp_charges",
                         "internet_software", "advisory_fees", "depreciation", "others"],
            "additionalProperties": False,
        },
        "tds_on_fo": {"type": "number"},
    },
    "required": ["segments", "expenses", "tds_on_fo"],
    "additionalProperties": False,
}


def parse_fo(pdf_path: str | Path) -> FOData:
    """
    Extract F&O P&L from a broker tax P&L PDF.
    Returns FOData with segment-wise breakdown and expenses.
    Carry-forward losses from prior years must be entered manually by the CA.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Broker F&O P&L PDF not found: {pdf_path}")

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
                        "title": "Broker F&O Tax P&L Report",
                    },
                    {
                        "type": "text",
                        "text": f"Extracted text for reference:\n\n{raw_text}\n\n{EXTRACTION_PROMPT}",
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

    return FOData(
        segments=[FOSegmentPL(**s) for s in data["segments"]],
        expenses=FOExpenses(**data["expenses"]),
        tds_on_fo=data["tds_on_fo"],
    )
