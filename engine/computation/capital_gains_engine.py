"""
Capital gains tax computation for FY 2024-25 / AY 2025-26.

Budget 2024 (Finance (No. 2) Act, 2024) changed rates effective July 23, 2024:
  - Listed equity STCG (Sec 111A): 15% → 20%
  - Listed equity LTCG (Sec 112A): 10% → 12.5%; annual exemption ₹1L → ₹1.25L
  - Other LTCG (Sec 112): 20% with indexation → 12.5% without indexation

Pre and post Jul 23 transactions are computed separately because they carry different
rates and exemption limits in ITR-2 Schedule CG.
"""

from dataclasses import dataclass

from engine.models_capital_gains import CapitalGainsSummary

# FY 2024-25 / AY 2025-26 special rates
STCG_111A_RATE_PRE = 0.15         # Listed equity / equity MF, before Jul 23, 2024
STCG_111A_RATE_POST = 0.20        # On/after Jul 23, 2024
LTCG_112A_RATE_PRE = 0.10         # Listed equity / equity MF, before Jul 23, 2024
LTCG_112A_RATE_POST = 0.125       # On/after Jul 23, 2024
LTCG_112A_EXEMPT_PRE = 100_000    # ₹1L annual exemption (pre-Jul 23 bucket)
LTCG_112A_EXEMPT_POST = 125_000   # ₹1.25L annual exemption (post-Jul 23 bucket)
LTCG_112_RATE_WITH_INDEX = 0.20   # Sec 112 with indexation (pre-Jul 23 sale / taxpayer choice)
LTCG_112_RATE_WITHOUT_INDEX = 0.125  # Sec 112 without indexation (post-Jul 23 sale)


@dataclass
class CapitalGainsTaxResult:
    # LTCG 112A exemptions actually claimed
    exempt_112a_pre_jul23: float
    exempt_112a_post_jul23: float

    # Net amounts taxable at each special rate
    taxable_stcg_111a_pre: float    # @ 15%
    taxable_stcg_111a_post: float   # @ 20%
    taxable_ltcg_112a_pre: float    # @ 10%
    taxable_ltcg_112a_post: float   # @ 12.5%
    taxable_ltcg_20pct: float       # @ 20% with indexation (other + property, combined)
    taxable_ltcg_125pct: float      # @ 12.5% without indexation (other + property, combined)

    # STCG taxed at normal slab rates — caller adds this to slab income before slab computation
    stcg_for_slab_income: float     # other STCG + property STCG

    # Tax at special rates (before surcharge / cess)
    tax_stcg_111a_pre: float
    tax_stcg_111a_post: float
    tax_ltcg_112a_pre: float
    tax_ltcg_112a_post: float
    tax_ltcg_20pct: float
    tax_ltcg_125pct: float
    total_tax_at_special_rates: float

    # TDS on gains — included in this result for easy pass-through to ITR generator
    tds_on_gains: float

    @property
    def total_taxable_at_special_rates(self) -> float:
        """All CG taxable at special rates (excludes stcg_for_slab_income which flows into normal slabs)."""
        return (self.taxable_stcg_111a_pre + self.taxable_stcg_111a_post
                + self.taxable_ltcg_112a_pre + self.taxable_ltcg_112a_post
                + self.taxable_ltcg_20pct + self.taxable_ltcg_125pct)

    @property
    def equity_cg_tax(self) -> float:
        """Tax on Sec 111A + 112A gains — surcharge is capped at 15% on this portion per Sec 112A proviso."""
        return (self.tax_stcg_111a_pre + self.tax_stcg_111a_post
                + self.tax_ltcg_112a_pre + self.tax_ltcg_112a_post)


def compute_capital_gains_tax(cg: CapitalGainsSummary) -> CapitalGainsTaxResult:
    """
    Compute tax on capital gains at special rates.

    Losses within a category (negative figures) are clamped to zero here — inter-head
    and carry-forward set-offs are handled manually by the CA before entering figures.
    STCG "at slab" (other + property) is returned as stcg_for_slab_income so the caller
    can add it to normal taxable income before running the slab computation.

    Note: Surcharge for listed equity gains (Sec 111A / 112A) is capped at 15% regardless
    of income — this cap is applied in the ITR generator, not here, because it requires
    knowledge of total income.
    """
    # Equity STCG (clamp losses; losses are not set off here)
    taxable_stcg_pre = max(0.0, cg.equity.stcg_pre_jul23)
    taxable_stcg_post = max(0.0, cg.equity.stcg_post_jul23)

    # Equity LTCG — apply per-bucket annual exemption
    ltcg_pre = max(0.0, cg.equity.ltcg_pre_jul23)
    ltcg_post = max(0.0, cg.equity.ltcg_post_jul23)
    exempt_pre = min(ltcg_pre, float(LTCG_112A_EXEMPT_PRE))
    exempt_post = min(ltcg_post, float(LTCG_112A_EXEMPT_POST))
    taxable_ltcg_pre = ltcg_pre - exempt_pre
    taxable_ltcg_post = ltcg_post - exempt_post

    # Other LTCG + property LTCG merged into same rate buckets (same rates apply)
    taxable_ltcg_20 = max(0.0, cg.other.ltcg_20pct_with_indexation + cg.property_gains.ltcg_with_indexation)
    taxable_ltcg_125 = max(0.0, cg.other.ltcg_125pct_without_indexation + cg.property_gains.ltcg_without_indexation)

    # STCG at slab rates — goes into normal income, not taxed at special rate
    stcg_slab = max(0.0, cg.other.stcg_at_slab + cg.property_gains.stcg)

    # Tax at special rates
    tax_stcg_pre = round(taxable_stcg_pre * STCG_111A_RATE_PRE, 2)
    tax_stcg_post = round(taxable_stcg_post * STCG_111A_RATE_POST, 2)
    tax_ltcg_pre = round(taxable_ltcg_pre * LTCG_112A_RATE_PRE, 2)
    tax_ltcg_post = round(taxable_ltcg_post * LTCG_112A_RATE_POST, 2)
    tax_ltcg_20 = round(taxable_ltcg_20 * LTCG_112_RATE_WITH_INDEX, 2)
    tax_ltcg_125 = round(taxable_ltcg_125 * LTCG_112_RATE_WITHOUT_INDEX, 2)

    total_special = (
        tax_stcg_pre + tax_stcg_post
        + tax_ltcg_pre + tax_ltcg_post
        + tax_ltcg_20 + tax_ltcg_125
    )

    return CapitalGainsTaxResult(
        exempt_112a_pre_jul23=exempt_pre,
        exempt_112a_post_jul23=exempt_post,
        taxable_stcg_111a_pre=taxable_stcg_pre,
        taxable_stcg_111a_post=taxable_stcg_post,
        taxable_ltcg_112a_pre=taxable_ltcg_pre,
        taxable_ltcg_112a_post=taxable_ltcg_post,
        taxable_ltcg_20pct=taxable_ltcg_20,
        taxable_ltcg_125pct=taxable_ltcg_125,
        stcg_for_slab_income=stcg_slab,
        tax_stcg_111a_pre=tax_stcg_pre,
        tax_stcg_111a_post=tax_stcg_post,
        tax_ltcg_112a_pre=tax_ltcg_pre,
        tax_ltcg_112a_post=tax_ltcg_post,
        tax_ltcg_20pct=tax_ltcg_20,
        tax_ltcg_125pct=tax_ltcg_125,
        total_tax_at_special_rates=total_special,
        tds_on_gains=cg.tds_on_gains,
    )
