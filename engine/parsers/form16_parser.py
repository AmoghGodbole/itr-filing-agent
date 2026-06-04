import base64
import io
import json
from pathlib import Path

import anthropic
import pdfplumber

from engine.parsers._claude_utils import get_model_and_thinking_kwargs, safe_text_block

from engine.models import (
    Deductions80C,
    EmployerDetails,
    Exemptions,
    Form16Data,
    OtherDeductions,
    SalaryBreakdown,
    TDSDetails,
)

EXTRACTION_PROMPT = """You are an expert Indian tax document parser. Extract all financial data from this Form 16 document.

Form 16 has two parts:
- Part A: TDS certificate from employer (TAN, PAN, TDS deducted/deposited)
- Part B: Salary breakdown, exemptions, deductions under Chapter VI-A

Return ONLY a valid JSON object with exactly this structure (use 0 for missing numeric values, empty string for missing text):

{
  "assessment_year": "AY YYYY-YY format",
  "financial_year": "FY YYYY-YY format",
  "employee_name": "",
  "employee_pan": "",
  "employer": {
    "name": "",
    "tan": "",
    "pan": "",
    "address": ""
  },
  "salary": {
    "basic": 0,
    "hra": 0,
    "lta": 0,
    "special_allowance": 0,
    "other_allowances": 0,
    "gross_salary": 0
  },
  "exemptions": {
    "hra_exempt": 0,
    "lta_exempt": 0,
    "other_exempt": 0,
    "total_exempt": 0
  },
  "deductions_80c": {
    "pf": 0,
    "ppf": 0,
    "elss": 0,
    "life_insurance": 0,
    "nsc": 0,
    "home_loan_principal": 0,
    "tuition_fees": 0,
    "other": 0,
    "total": 0
  },
  "other_deductions": {
    "deduction_80d": 0,
    "deduction_80e": 0,
    "deduction_80g": 0,
    "deduction_80tta": 0,
    "nps_80ccd1b": 0,
    "home_loan_interest_24b": 0,
    "other": 0
  },
  "tds": {
    "tds_deducted": 0,
    "tds_deposited": 0,
    "assessment_year": ""
  },
  "professional_tax": 0,
  "standard_deduction": 50000
}

Extract every number you can find. For gross salary, if not explicitly stated, sum up all salary components."""


def _read_pdf(pdf_path: Path) -> tuple[str, str]:
    """Fix #8: read PDF bytes once; derive both extracted text and base64 from that."""
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


def parse_form16(pdf_path: str | Path) -> Form16Data:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Form 16 PDF not found: {pdf_path}")

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
                        "title": "Form 16",
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
                "schema": {
                    "type": "object",
                    "properties": {
                        "assessment_year": {"type": "string"},
                        "financial_year": {"type": "string"},
                        "employee_name": {"type": "string"},
                        "employee_pan": {"type": "string"},
                        "employer": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "tan": {"type": "string"},
                                "pan": {"type": "string"},
                                "address": {"type": "string"},
                            },
                            "required": ["name", "tan", "pan", "address"],
                            "additionalProperties": False,
                        },
                        "salary": {
                            "type": "object",
                            "properties": {
                                "basic": {"type": "number"},
                                "hra": {"type": "number"},
                                "lta": {"type": "number"},
                                "special_allowance": {"type": "number"},
                                "other_allowances": {"type": "number"},
                                "gross_salary": {"type": "number"},
                            },
                            "required": ["basic", "hra", "lta", "special_allowance", "other_allowances", "gross_salary"],
                            "additionalProperties": False,
                        },
                        "exemptions": {
                            "type": "object",
                            "properties": {
                                "hra_exempt": {"type": "number"},
                                "lta_exempt": {"type": "number"},
                                "other_exempt": {"type": "number"},
                                "total_exempt": {"type": "number"},
                            },
                            "required": ["hra_exempt", "lta_exempt", "other_exempt", "total_exempt"],
                            "additionalProperties": False,
                        },
                        "deductions_80c": {
                            "type": "object",
                            "properties": {
                                "pf": {"type": "number"},
                                "ppf": {"type": "number"},
                                "elss": {"type": "number"},
                                "life_insurance": {"type": "number"},
                                "nsc": {"type": "number"},
                                "home_loan_principal": {"type": "number"},
                                "tuition_fees": {"type": "number"},
                                "other": {"type": "number"},
                                "total": {"type": "number"},
                            },
                            "required": ["pf", "ppf", "elss", "life_insurance", "nsc", "home_loan_principal", "tuition_fees", "other", "total"],
                            "additionalProperties": False,
                        },
                        "other_deductions": {
                            "type": "object",
                            "properties": {
                                "deduction_80d": {"type": "number"},
                                "deduction_80e": {"type": "number"},
                                "deduction_80g": {"type": "number"},
                                "deduction_80tta": {"type": "number"},
                                "nps_80ccd1b": {"type": "number"},
                                "home_loan_interest_24b": {"type": "number"},
                                "other": {"type": "number"},
                            },
                            "required": ["deduction_80d", "deduction_80e", "deduction_80g", "deduction_80tta", "nps_80ccd1b", "home_loan_interest_24b", "other"],
                            "additionalProperties": False,
                        },
                        "tds": {
                            "type": "object",
                            "properties": {
                                "tds_deducted": {"type": "number"},
                                "tds_deposited": {"type": "number"},
                                "assessment_year": {"type": "string"},
                            },
                            "required": ["tds_deducted", "tds_deposited", "assessment_year"],
                            "additionalProperties": False,
                        },
                        "professional_tax": {"type": "number"},
                        "standard_deduction": {"type": "number"},
                    },
                    "required": [
                        "assessment_year", "financial_year", "employee_name", "employee_pan",
                        "employer", "salary", "exemptions", "deductions_80c", "other_deductions",
                        "tds", "professional_tax", "standard_deduction"
                    ],
                    "additionalProperties": False,
                },
            }
        },
    ) as stream:
        final = stream.get_final_message()

    data = json.loads(safe_text_block(final.content))

    return Form16Data(
        assessment_year=data["assessment_year"],
        financial_year=data["financial_year"],
        employee_name=data["employee_name"],
        employee_pan=data["employee_pan"],
        employer=EmployerDetails(**data["employer"]),
        salary=SalaryBreakdown(**data["salary"]),
        exemptions=Exemptions(**data["exemptions"]),
        deductions_80c=Deductions80C(**data["deductions_80c"]),
        other_deductions=OtherDeductions(**data["other_deductions"]),
        tds=TDSDetails(**data["tds"]),
        professional_tax=data["professional_tax"],
        standard_deduction=data["standard_deduction"],
        raw_text=raw_text,
    )
