"""
F&O (Futures & Options) data models for FY 2024-25 / AY 2025-26.

F&O is classified as non-speculative business income under Sec 43(5) — not capital gains.
Any F&O activity (profit or loss, however small) mandates ITR-3. ITR-1 and ITR-2 cannot
be used when F&O income exists.

Turnover for audit purposes (Sec 44AB) = absolute sum of all trade-level profits and losses,
NOT net P&L. A trader with +₹5L and -₹3L has turnover ₹8L, not ₹2L.
"""

from typing import Optional
from pydantic import BaseModel, model_validator

# Section 44AB audit thresholds
AUDIT_THRESHOLD_TURNOVER = 100_000_000   # ₹10Cr — mandatory audit regardless of profit
AUDIT_THRESHOLD_PRESUMPTIVE = 10_000_000  # ₹1Cr — audit if loss declared and turnover ≤ ₹10Cr
# Note: F&O is excluded from Sec 44AD presumptive scheme per Sec 44AD(6);
# income must always be computed under regular provisions (actual P&L minus expenses).


class FOSegmentPL(BaseModel):
    """Realized P&L for one segment (equity futures, equity options, commodity, currency, etc.)."""
    segment: str = ""                # "Equity F&O", "Commodity", "Currency", etc.
    gross_profit: float = 0          # sum of all profitable trade P&L
    gross_loss: float = 0            # sum of all loss-making trade P&L (enter as positive number)
    net_pl: Optional[float] = None   # derived as gross_profit - gross_loss when not explicitly set
    turnover: Optional[float] = None # derived as gross_profit + gross_loss when not explicitly set

    @model_validator(mode="after")
    def derive_fields(self) -> "FOSegmentPL":
        # Only derive when the caller did not explicitly supply a value (None = "not provided").
        # This prevents overwriting an intentional net_pl=0 (e.g. equal profits and losses).
        if self.turnover is None:
            self.turnover = self.gross_profit + self.gross_loss
        if self.net_pl is None:
            self.net_pl = self.gross_profit - self.gross_loss
        return self


class FOExpenses(BaseModel):
    """Business expenses deductible against F&O income (actual documented expenses)."""
    brokerage: float = 0
    stt: float = 0              # STT is deductible as business expense (not as capital gain deduction)
    exchange_fees: float = 0
    dp_charges: float = 0
    internet_software: float = 0
    advisory_fees: float = 0
    depreciation: float = 0     # on computer/desk if home office is set up for trading
    others: float = 0

    @property
    def total(self) -> float:
        return (self.brokerage + self.stt + self.exchange_fees + self.dp_charges
                + self.internet_software + self.advisory_fees + self.depreciation + self.others)


class CarryForwardLoss(BaseModel):
    """F&O losses carried forward from prior years — entered manually from prior ITR acknowledgements."""
    assessment_year: str        # e.g. "AY 2024-25"
    loss_amount: float          # positive number representing the loss


class FOData(BaseModel):
    """
    Complete F&O data for a taxpayer. Parsed from broker P&L or entered manually by CA.
    Segments are typically: equity futures, equity options, commodity F&O, currency F&O.
    """
    segments: list[FOSegmentPL] = []
    expenses: FOExpenses = FOExpenses()
    carry_forward_losses: list[CarryForwardLoss] = []  # losses from prior years being set off this year
    tds_on_fo: float = 0        # rare, but TDS may be deducted on commodity F&O income

    @property
    def total_gross_pl(self) -> float:
        return sum(s.net_pl for s in self.segments)

    @property
    def total_turnover(self) -> float:
        return sum(s.turnover for s in self.segments)

    @property
    def net_income(self) -> float:
        """Net F&O income after expenses. Negative = business loss."""
        return self.total_gross_pl - self.expenses.total

    @property
    def prior_year_loss_setoff(self) -> float:
        """Total prior-year F&O losses brought forward for set-off this year (capped at net income if positive)."""
        total = sum(l.loss_amount for l in self.carry_forward_losses)
        if self.net_income > 0:
            return min(total, self.net_income)
        return 0.0

    @property
    def taxable_fo_income(self) -> float:
        """Net business income after prior-year loss set-off. Always ≥ 0 (losses carry forward, not set off below zero)."""
        return max(0.0, self.net_income - self.prior_year_loss_setoff)

    @property
    def current_year_loss_to_carry_forward(self) -> float:
        """Net loss this year that can be carried forward for 8 years."""
        return max(0.0, -self.net_income)

    @property
    def requires_tax_audit(self) -> bool:
        """
        Sec 44AB audit requirement:
        - Turnover > ₹10Cr: always requires audit.
        - Turnover ≤ ₹10Cr and net loss declared: requires audit (cannot claim presumptive — F&O excluded from 44AD).
        Note: if turnover ≤ ₹10Cr and profit declared, no audit required.
        """
        if self.total_turnover > AUDIT_THRESHOLD_TURNOVER:
            return True
        if self.net_income < 0 and self.total_turnover > 0:
            return True
        return False
