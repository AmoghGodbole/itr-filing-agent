"""
Capital gains data models for FY 2024-25 / AY 2025-26.

Budget 2024 (Finance (No. 2) Act, 2024) changed CG rates effective July 23, 2024 mid-year.
Pre-Jul 23 and post-Jul 23 transactions are tracked as separate buckets because they carry
different rates and exemption limits in the ITR-2 Schedule CG.
"""

from pydantic import BaseModel, model_validator


class EquityGainsSplit(BaseModel):
    """
    Listed equity shares and equity-oriented MF units where STT is paid on sale.
    Gains qualify for special rates under Sec 111A (STCG) and Sec 112A (LTCG).
    """
    stcg_pre_jul23: float = 0   # < 12 months, sold before Jul 23, 2024 — taxed @ 15% (Sec 111A)
    stcg_post_jul23: float = 0  # < 12 months, sold on/after Jul 23, 2024 — taxed @ 20% (Sec 111A)
    ltcg_pre_jul23: float = 0   # ≥ 12 months, sold before Jul 23, 2024 — taxed @ 10% after ₹1L exempt (Sec 112A)
    ltcg_post_jul23: float = 0  # ≥ 12 months, sold on/after Jul 23, 2024 — taxed @ 12.5% after ₹1.25L exempt (Sec 112A)


class OtherGains(BaseModel):
    """
    Non-equity assets: debt MF (units purchased after Apr 1, 2023), bonds, NCDs,
    gold ETF backed by physical gold, unlisted shares, etc.
    Debt MF units purchased before Apr 1, 2023 carry a 36-month LTCG period with
    20% indexation (these are rare and should be entered in ltcg_20pct_with_indexation).
    """
    stcg_at_slab: float = 0                      # Short-term (< 36 months) — added to slab income, no special rate
    ltcg_20pct_with_indexation: float = 0        # Long-term, sold before Jul 23, 2024 — 20% with CII indexation (Sec 112)
    ltcg_125pct_without_indexation: float = 0    # Long-term, sold on/after Jul 23, 2024 — 12.5% without indexation (Sec 112)


class PropertyGains(BaseModel):
    """
    Immovable property — always entered manually (no document source).
    Holding period for LTCG is 24 months (reduced from 36 in Budget 2024).
    For property acquired before Jul 23, 2024 and sold after Jul 23, 2024:
    taxpayer may choose the lower tax between (20% with indexation) and (12.5% without).
    CA enters only the beneficial option's figure; the other stays zero.
    These two fields are mutually exclusive — a CA error entering both is rejected.
    """
    stcg: float = 0                       # Held < 24 months — added to slab income, no special rate
    ltcg_with_indexation: float = 0       # 20% with CII indexation — Sec 112 (old rate, or taxpayer choice)
    ltcg_without_indexation: float = 0    # 12.5% without indexation — Sec 112 (post-Jul 23 rate, or taxpayer choice)

    @model_validator(mode="after")
    def ltcg_indexation_mutually_exclusive(self) -> "PropertyGains":
        if self.ltcg_with_indexation > 0 and self.ltcg_without_indexation > 0:
            raise ValueError(
                "Property LTCG: ltcg_with_indexation and ltcg_without_indexation cannot both be non-zero. "
                "Enter only the more beneficial option (lower tax) per Sec 112 taxpayer choice."
            )
        return self


class CapitalGainsSummary(BaseModel):
    equity: EquityGainsSplit = EquityGainsSplit()
    other: OtherGains = OtherGains()
    property_gains: PropertyGains = PropertyGains()
    tds_on_gains: float = 0    # TDS deducted by broker / buyer on capital gains (Sec 194, 194IA, etc.)

    def has_any_gains(self) -> bool:
        return any([
            self.equity.stcg_pre_jul23, self.equity.stcg_post_jul23,
            self.equity.ltcg_pre_jul23, self.equity.ltcg_post_jul23,
            self.other.stcg_at_slab, self.other.ltcg_20pct_with_indexation,
            self.other.ltcg_125pct_without_indexation,
            self.property_gains.stcg, self.property_gains.ltcg_with_indexation,
            self.property_gains.ltcg_without_indexation,
        ])


def merge_capital_gains(summaries: list["CapitalGainsSummary"]) -> "CapitalGainsSummary":
    """
    Merge capital gains from multiple brokers by summing each bucket.

    The PropertyGains mutual-exclusivity validator (which prevents a single entry
    from having both indexation options) is intentionally bypassed here: across
    multiple brokers a client may legitimately have one property sold with indexation
    and another without. model_construct skips validation on the merged object.
    """
    if not summaries:
        return CapitalGainsSummary()
    if len(summaries) == 1:
        return summaries[0]

    equity = EquityGainsSplit(
        stcg_pre_jul23=sum(s.equity.stcg_pre_jul23 for s in summaries),
        stcg_post_jul23=sum(s.equity.stcg_post_jul23 for s in summaries),
        ltcg_pre_jul23=sum(s.equity.ltcg_pre_jul23 for s in summaries),
        ltcg_post_jul23=sum(s.equity.ltcg_post_jul23 for s in summaries),
    )
    other = OtherGains(
        stcg_at_slab=sum(s.other.stcg_at_slab for s in summaries),
        ltcg_20pct_with_indexation=sum(s.other.ltcg_20pct_with_indexation for s in summaries),
        ltcg_125pct_without_indexation=sum(s.other.ltcg_125pct_without_indexation for s in summaries),
    )
    property_gains = PropertyGains.model_construct(
        stcg=sum(s.property_gains.stcg for s in summaries),
        ltcg_with_indexation=sum(s.property_gains.ltcg_with_indexation for s in summaries),
        ltcg_without_indexation=sum(s.property_gains.ltcg_without_indexation for s in summaries),
    )
    return CapitalGainsSummary(
        equity=equity,
        other=other,
        property_gains=property_gains,
        tds_on_gains=sum(s.tds_on_gains for s in summaries),
    )
