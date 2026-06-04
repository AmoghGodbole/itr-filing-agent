"""
Parses Form 26AS downloaded from TRACES / IT portal.
Portal path: incometax.gov.in → e-File → Income Tax Returns → View Form 26AS

Form 26AS has standard parts:
  Part A  - TDS on salary and other payments
  Part B  - TDS on sale of immovable property
  Part C  - TDS on non-salary payments (FD interest, rent, etc.)
  Part D  - TDS defaults (if any)
  Part F  - TCS (Tax Collected at Source)
  Part G  - TDS defaults by statement processor

We care about Part A and Part C primarily.
Available as PDF or text from the portal — we use Claude to parse both.
"""

import base64
import io
import json
from pathlib import Path

import anthropic
import pdfplumber

from engine.models_ais import AISIncomeEntry
from engine.parsers._claude_utils import get_model_and_thinking_kwargs, safe_text_block


EXTRACTION_PROMPT = """You are parsing a Form 26AS document from the Indian Income Tax portal.

Extract all TDS entries from Part A (TDS on salary) and Part C (TDS on other payments like FD interest, rent, etc.).

Return ONLY this JSON:
{
  "pan": "",
  "taxpayer_name": "",
  "financial_year": "",
  "part_a": [
    {
      "tan": "",
      "deductor_name": "",
      "amount_paid": 0,
      "tds_deducted": 0,
      "tds_deposited": 0
    }
  ],
  "part_c": [
    {
      "tan": "",
      "deductor_name": "",
      "nature_of_payment": "",
      "amount_paid": 0,
      "tds_deducted": 0,
      "tds_deposited": 0
    }
  ],
  "total_tds_deducted": 0,
  "total_tds_deposited": 0
}

Use 0 for missing numbers, empty string for missing text."""


from dataclasses import dataclass


@dataclass
class Form26ASEntry:
    tan: str
    deductor_name: str
    nature_of_payment: str
    amount_paid: float
    tds_deducted: float
    tds_deposited: float


@dataclass
class Form26ASData:
    pan: str
    taxpayer_name: str
    financial_year: str
    part_a: list[Form26ASEntry]   # Salary TDS
    part_c: list[Form26ASEntry]   # Other TDS (FD, rent, etc.)
    total_tds_deducted: float
    total_tds_deposited: float

    def get_salary_tds(self) -> float:
        return sum(e.tds_deducted for e in self.part_a)

    def get_non_salary_tds(self) -> float:
        return sum(e.tds_deducted for e in self.part_c)

    def tds_mismatch_with_form16(self, form16_tds: float, tolerance: float = 5.0) -> bool:
        """Flag if Form 16 TDS and Form 26AS salary TDS diverge beyond tolerance."""
        return abs(self.get_salary_tds() - form16_tds) > tolerance


def parse_form26as(path: str | Path) -> Form26ASData:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Form 26AS not found: {path}")

    client = anthropic.Anthropic()
    model, extra = get_model_and_thinking_kwargs()

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        raw_bytes = path.read_bytes()
        # Extract text for context
        text_parts = []
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        raw_text = "\n\n".join(text_parts)
        pdf_b64 = base64.standard_b64encode(raw_bytes).decode("utf-8")

        content = [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}, "title": "Form 26AS"},
            {"type": "text", "text": f"Extracted text:\n{raw_text}\n\n{EXTRACTION_PROMPT}"},
        ]
    else:
        # Text file (.txt)
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
        content = [{"type": "text", "text": f"Form 26AS text:\n{raw_text}\n\n{EXTRACTION_PROMPT}"}]

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        **extra,
        messages=[{"role": "user", "content": content}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "pan": {"type": "string"},
                        "taxpayer_name": {"type": "string"},
                        "financial_year": {"type": "string"},
                        "part_a": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tan": {"type": "string"},
                                    "deductor_name": {"type": "string"},
                                    "amount_paid": {"type": "number"},
                                    "tds_deducted": {"type": "number"},
                                    "tds_deposited": {"type": "number"},
                                },
                                "required": ["tan", "deductor_name", "amount_paid", "tds_deducted", "tds_deposited"],
                                "additionalProperties": False,
                            },
                        },
                        "part_c": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tan": {"type": "string"},
                                    "deductor_name": {"type": "string"},
                                    "nature_of_payment": {"type": "string"},
                                    "amount_paid": {"type": "number"},
                                    "tds_deducted": {"type": "number"},
                                    "tds_deposited": {"type": "number"},
                                },
                                "required": ["tan", "deductor_name", "nature_of_payment", "amount_paid", "tds_deducted", "tds_deposited"],
                                "additionalProperties": False,
                            },
                        },
                        "total_tds_deducted": {"type": "number"},
                        "total_tds_deposited": {"type": "number"},
                    },
                    "required": ["pan", "taxpayer_name", "financial_year", "part_a", "part_c", "total_tds_deducted", "total_tds_deposited"],
                    "additionalProperties": False,
                },
            }
        },
    )

    data = json.loads(safe_text_block(response.content))

    def to_entries(items: list, default_nature: str = "Salary") -> list[Form26ASEntry]:
        return [
            Form26ASEntry(
                tan=i["tan"],
                deductor_name=i["deductor_name"],
                nature_of_payment=i.get("nature_of_payment") or default_nature,
                amount_paid=i["amount_paid"],
                tds_deducted=i["tds_deducted"],
                tds_deposited=i["tds_deposited"],
            )
            for i in items
        ]

    return Form26ASData(
        pan=data["pan"],
        taxpayer_name=data["taxpayer_name"],
        financial_year=data["financial_year"],
        part_a=to_entries(data["part_a"], default_nature="Salary"),
        part_c=to_entries(data["part_c"], default_nature="Interest/Other"),
        total_tds_deducted=data["total_tds_deducted"],
        total_tds_deposited=data["total_tds_deposited"],
    )
