"""
Parses AIS (Annual Information Statement) JSON downloaded from the IT portal.
Portal path: incometax.gov.in → Services → Annual Information Statement → Download (JSON)

AIS SFT codes we care about:
  SFT-001  Salary
  SFT-011  Dividend
  SFT-013  Rent received
  SFT-014  Interest from savings account
  SFT-015  Interest from deposits (FD, RD, etc.)
  SFT-016  Interest from others (bonds, etc.)
  Other    Any TDS entry not covered above
"""

import json
from pathlib import Path
from typing import Any

import anthropic

from engine.models_ais import AISData, AISIncomeEntry
from engine.parsers._claude_utils import get_model_and_thinking_kwargs, safe_text_block

# SFT codes → category
SAVINGS_INTEREST_CODES = {"SFT-014"}
DEPOSIT_INTEREST_CODES = {"SFT-015", "SFT-016"}
DIVIDEND_CODES = {"SFT-011"}
RENT_CODES = {"SFT-013"}
SALARY_CODES = {"SFT-001"}  # We have Form 16 for this, but useful for cross-check


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _extract_entries(info_block: dict) -> list[AISIncomeEntry]:
    """Extract AISIncomeEntry list from an AIS information block."""
    entries = []
    for item in info_block.get("informationDetails", []):
        source = item.get("reportingEntityName", item.get("description", ""))
        # AIS stores both reported and modified values — use modified if present
        amount = _safe_float(
            item.get("modifiedValue") or item.get("derivedValue") or item.get("reportedValue", 0)
        )
        tds = _safe_float(
            item.get("tdsModifiedValue") or item.get("tdsDeducted", 0)
        )
        if amount > 0:
            entries.append(AISIncomeEntry(source_name=source, amount=amount, tds_deducted=tds))
    return entries


def _parse_ais_structure(raw: dict) -> AISData | None:
    """
    Try to parse the known IT portal AIS JSON structure.
    Returns None if the structure doesn't match — triggers Claude fallback.
    """
    try:
        root = raw.get("annualInformationStatement", raw)
        taxpayer = root.get("taxpayerInfo", {})
        pan = taxpayer.get("panNo", taxpayer.get("pan", ""))
        name = taxpayer.get("taxpayerName", taxpayer.get("name", ""))
        fy = taxpayer.get("financialYear", "")

        ais_info = root.get("aisInformation", {})
        other_info = ais_info.get("aisOtherInformation", {})
        info_list = other_info.get("otherInformation", [])

        if not info_list:
            return None

        savings_entries, deposit_entries, dividend_entries = [], [], []
        rent_entries, other_tds_entries = [], []

        for block in info_list:
            code = block.get("sftCode", block.get("informationCode", ""))
            if code in SALARY_CODES:
                continue  # covered by Form 16
            elif code in SAVINGS_INTEREST_CODES:
                savings_entries.extend(_extract_entries(block))
            elif code in DEPOSIT_INTEREST_CODES:
                deposit_entries.extend(_extract_entries(block))
            elif code in DIVIDEND_CODES:
                dividend_entries.extend(_extract_entries(block))
            elif code in RENT_CODES:
                rent_entries.extend(_extract_entries(block))
            else:
                other_tds_entries.extend(_extract_entries(block))

        return _build_ais_data(
            pan, name, fy,
            savings_entries, deposit_entries, dividend_entries,
            rent_entries, other_tds_entries,
        )

    except Exception:
        return None


def _build_ais_data(
    pan: str, name: str, fy: str,
    savings: list, deposits: list, dividends: list,
    rent: list, other_tds: list,
) -> AISData:
    total_savings = sum(e.amount for e in savings)
    total_deposits = sum(e.amount for e in deposits)
    total_divs = sum(e.amount for e in dividends)
    total_rent = sum(e.amount for e in rent)
    total_other = sum(e.tds_deducted for e in other_tds)
    total_tds = (
        sum(e.tds_deducted for e in savings)
        + sum(e.tds_deducted for e in deposits)
        + sum(e.tds_deducted for e in dividends)
        + sum(e.tds_deducted for e in rent)
        + total_other
    )

    return AISData(
        pan=pan,
        taxpayer_name=name,
        financial_year=fy,
        savings_account_interest=savings,
        deposit_interest=deposits,
        dividends=dividends,
        rent_received=rent,
        other_tds=other_tds,
        total_savings_interest=round(total_savings, 2),
        total_deposit_interest=round(total_deposits, 2),
        total_interest=round(total_savings + total_deposits, 2),
        total_dividends=round(total_divs, 2),
        total_rent_received=round(total_rent, 2),
        total_other_tds=round(total_other, 2),
        total_tds_from_ais=round(total_tds, 2),
    )


def _parse_ais_with_claude(raw_text: str) -> AISData:
    """Fallback: let Claude extract the key figures from an unknown AIS structure."""
    model, extra = get_model_and_thinking_kwargs()
    client = anthropic.Anthropic()

    # Pass raw text directly — no re-serialization of the already-parsed dict
    prompt = f"""This is an Annual Information Statement (AIS) JSON from the Indian Income Tax portal.
Extract the following and return as JSON:

{{
  "pan": "",
  "taxpayer_name": "",
  "financial_year": "",
  "savings_interest": [{{"source": "", "amount": 0, "tds": 0}}],
  "deposit_interest": [{{"source": "", "amount": 0, "tds": 0}}],
  "dividends": [{{"source": "", "amount": 0, "tds": 0}}],
  "rent_received": [{{"source": "", "amount": 0, "tds": 0}}],
  "other_tds": [{{"source": "", "amount": 0, "tds": 0}}]
}}

AIS JSON:
{raw_text[:12000]}"""

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        **extra,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "pan": {"type": "string"},
                        "taxpayer_name": {"type": "string"},
                        "financial_year": {"type": "string"},
                        "savings_interest": {"type": "array", "items": {"type": "object", "properties": {"source": {"type": "string"}, "amount": {"type": "number"}, "tds": {"type": "number"}}, "required": ["source", "amount", "tds"], "additionalProperties": False}},
                        "deposit_interest": {"type": "array", "items": {"type": "object", "properties": {"source": {"type": "string"}, "amount": {"type": "number"}, "tds": {"type": "number"}}, "required": ["source", "amount", "tds"], "additionalProperties": False}},
                        "dividends": {"type": "array", "items": {"type": "object", "properties": {"source": {"type": "string"}, "amount": {"type": "number"}, "tds": {"type": "number"}}, "required": ["source", "amount", "tds"], "additionalProperties": False}},
                        "rent_received": {"type": "array", "items": {"type": "object", "properties": {"source": {"type": "string"}, "amount": {"type": "number"}, "tds": {"type": "number"}}, "required": ["source", "amount", "tds"], "additionalProperties": False}},
                        "other_tds": {"type": "array", "items": {"type": "object", "properties": {"source": {"type": "string"}, "amount": {"type": "number"}, "tds": {"type": "number"}}, "required": ["source", "amount", "tds"], "additionalProperties": False}},
                    },
                    "required": ["pan", "taxpayer_name", "financial_year", "savings_interest", "deposit_interest", "dividends", "rent_received", "other_tds"],
                    "additionalProperties": False,
                }
            }
        },
    )

    data = json.loads(safe_text_block(response.content))

    def to_entries(items: list) -> list[AISIncomeEntry]:
        return [AISIncomeEntry(source_name=i["source"], amount=i["amount"], tds_deducted=i["tds"]) for i in items]

    return _build_ais_data(
        data["pan"], data["taxpayer_name"], data["financial_year"],
        to_entries(data["savings_interest"]),
        to_entries(data["deposit_interest"]),
        to_entries(data["dividends"]),
        to_entries(data["rent_received"]),
        to_entries(data["other_tds"]),
    )


def parse_ais(ais_path: str | Path) -> AISData:
    ais_path = Path(ais_path)
    if not ais_path.exists():
        raise FileNotFoundError(f"AIS JSON not found: {ais_path}")

    # Read text once; share between rule-based parse and Claude fallback
    raw_text = ais_path.read_text(encoding="utf-8")
    raw = json.loads(raw_text)

    result = _parse_ais_structure(raw)
    if result is None:
        print("  AIS structure not recognised — using Claude fallback parser")
        result = _parse_ais_with_claude(raw_text)

    return result
