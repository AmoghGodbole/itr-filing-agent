from pydantic import BaseModel
from typing import Optional


class AISIncomeEntry(BaseModel):
    source_name: str = ""       # Bank/company name
    amount: float = 0
    tds_deducted: float = 0


class AISData(BaseModel):
    pan: str = ""
    taxpayer_name: str = ""
    financial_year: str = ""

    # Interest income
    savings_account_interest: list[AISIncomeEntry] = []
    deposit_interest: list[AISIncomeEntry] = []         # FD, RD, etc.

    # Dividend
    dividends: list[AISIncomeEntry] = []

    # Other TDS sources (Form 16A equivalent)
    other_tds: list[AISIncomeEntry] = []

    # Rent received
    rent_received: list[AISIncomeEntry] = []

    # Aggregated totals (computed by parser)
    total_savings_interest: float = 0
    total_deposit_interest: float = 0
    total_interest: float = 0
    total_dividends: float = 0
    total_rent_received: float = 0
    total_other_tds: float = 0
    total_tds_from_ais: float = 0
