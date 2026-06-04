"""
F&O (Futures & Options) tax computation for FY 2024-25 / AY 2025-26.

F&O income is business income (Sec 43(5)), not capital gains.
It is added to other income and taxed at normal slab rates.
"""

from dataclasses import dataclass
from typing import Optional

from engine.models_fo import FOData


@dataclass
class FOTaxResult:
    # Income summary
    total_turnover: float
    gross_pl: float          # total P&L across all segments before expenses
    total_expenses: float
    net_income: float        # gross_pl - expenses (can be negative)

    # Set-off
    prior_year_loss_setoff: float   # brought-forward losses applied this year
    taxable_fo_income: float        # net income after set-off (≥ 0); added to slab income

    # Loss carry-forward
    current_year_loss_cf: float     # new loss carried forward to future years (8-year window)

    # Compliance flags
    requires_tax_audit: bool
    tds_on_fo: float


def compute_fo_tax(fo: FOData) -> FOTaxResult:
    """
    Compute F&O income position. The taxable_fo_income amount is added to the
    taxpayer's normal slab income in the main tax engine.

    F&O losses are NOT set off against salary or capital gains in the same year
    (inter-head set-off is not permitted for F&O losses under Sec 71(2A)).
    They are carried forward for up to 8 assessment years and set off only
    against future business income.
    """
    return FOTaxResult(
        total_turnover=fo.total_turnover,
        gross_pl=fo.total_gross_pl,
        total_expenses=fo.expenses.total,
        net_income=fo.net_income,
        prior_year_loss_setoff=fo.prior_year_loss_setoff,
        taxable_fo_income=fo.taxable_fo_income,
        current_year_loss_cf=fo.current_year_loss_to_carry_forward,
        requires_tax_audit=fo.requires_tax_audit,
        tds_on_fo=fo.tds_on_fo,
    )
