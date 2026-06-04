from dataclasses import dataclass, field
from datetime import date as _date, datetime as _datetime
from typing import Optional

from engine.models import Form16Data
from engine.models_ais import AISData
from engine.models_capital_gains import CapitalGainsSummary
from engine.models_fo import FOData
from engine.computation.capital_gains_engine import CapitalGainsTaxResult, compute_capital_gains_tax
from engine.computation.fo_engine import FOTaxResult, compute_fo_tax

# FY 2024-25 / AY 2025-26 slabs

SENIOR_CITIZEN_AGE = 60       # 60–79
SUPER_SENIOR_CITIZEN_AGE = 80  # 80+

OLD_REGIME_SLABS_REGULAR = [
    (250_000, 0.00),
    (500_000, 0.05),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]

OLD_REGIME_SLABS_SENIOR = [
    (300_000, 0.00),
    (500_000, 0.05),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]

OLD_REGIME_SLABS_SUPER_SENIOR = [
    (500_000, 0.00),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]

NEW_REGIME_SLABS = [
    (300_000, 0.00),
    (700_000, 0.05),
    (1_000_000, 0.10),
    (1_200_000, 0.15),
    (1_500_000, 0.20),
    (float("inf"), 0.30),
]

STANDARD_DEDUCTION_OLD = 50_000
STANDARD_DEDUCTION_NEW = 75_000
SECTION_80C_LIMIT = 150_000
SECTION_80D_LIMIT_SELF = 25_000
SECTION_80D_LIMIT_SELF_SENIOR = 50_000   # ₹50k cap when the taxpayer (self/family) is a senior citizen
SECTION_80D_LIMIT_PARENTS = 25_000
SECTION_80D_LIMIT_PARENTS_SENIOR = 50_000
SECTION_80CCD1B_LIMIT = 50_000
SECTION_80GG_ANNUAL_LIMIT = 60_000  # ₹5,000/month
HOME_LOAN_INTEREST_24B_LIMIT = 200_000  # Fix #1: Section 24(b) cap
REBATE_87A_LIMIT_OLD = 500_000
REBATE_87A_AMOUNT_OLD = 12_500
REBATE_87A_LIMIT_NEW = 700_000
REBATE_87A_AMOUNT_NEW = 25_000
SECTION_80TTA_LIMIT = 10_000       # Savings interest deduction (under-60 taxpayers)
SECTION_80TTB_LIMIT = 50_000       # Senior citizens: all deposit interest (savings + FD/RD); replaces 80TTA
SECTION_80EEA_LIMIT = 150_000      # Affordable housing extra home loan interest (first-time buyer, stamp duty ≤ ₹45L)
FAMILY_PENSION_DEDUCTION_MAX = 15_000  # Section 57(iia): min(₹15k, pension/3)
HP_STANDARD_DEDUCTION_RATE = 0.30  # Section 24(a) — always 30% of Annual Value for let-out
HP_LOSS_SETOFF_LIMIT = 200_000     # Max HP loss that can reduce other income in same year
HRA_METRO_PERCENT = 0.50           # Delhi, Mumbai, Kolkata, Chennai
HRA_NON_METRO_PERCENT = 0.40

METRO_CITIES = {"delhi", "mumbai", "kolkata", "chennai"}


def compute_hp_income(annual_rent: float, municipal_taxes: float, loan_interest: float) -> float:
    """
    Net HP income from a let-out property.
    Annual Value = rent − municipal taxes paid.
    Section 24(a): 30% standard deduction on Annual Value.
    Section 24(b): full home loan interest (no cap for let-out).
    Returns value before the ₹2L loss set-off cap — caller applies the cap.
    """
    if annual_rent <= 0:
        return 0.0
    annual_value = max(0.0, annual_rent - municipal_taxes)
    std_deduction_hp = HP_STANDARD_DEDUCTION_RATE * annual_value
    return round(annual_value - std_deduction_hp - loan_interest, 2)


def _age_at_fy_end(date_of_birth: str, assessment_year: str) -> Optional[int]:
    """
    Age "at any time during the previous year" — evaluated at March 31 (FY end),
    which is the relevant date for senior/super-senior status under the IT Act.
    "AY 2025-26" → FY 2024-25 → March 31, 2025. Returns None if DOB is missing/unparseable.
    """
    if not date_of_birth:
        return None
    try:
        dob = _datetime.strptime(date_of_birth, "%d/%m/%Y").date()
        ay_start = int(assessment_year.replace("AY ", "").split("-")[0])
        fy_end = _date(ay_start, 3, 31)
        return fy_end.year - dob.year - ((fy_end.month, fy_end.day) < (dob.month, dob.day))
    except (ValueError, AttributeError, IndexError):
        return None


def _old_regime_slabs(date_of_birth: str, assessment_year: str) -> list:
    """Selects old-regime slab table based on age at any time during the FY (uses March 31 — FY end)."""
    age = _age_at_fy_end(date_of_birth, assessment_year)
    if age is None:
        return OLD_REGIME_SLABS_REGULAR
    if age >= SUPER_SENIOR_CITIZEN_AGE:
        return OLD_REGIME_SLABS_SUPER_SENIOR
    if age >= SENIOR_CITIZEN_AGE:
        return OLD_REGIME_SLABS_SENIOR
    return OLD_REGIME_SLABS_REGULAR


def compute_80gg(monthly_rent: float, gross_total_income: float) -> float:
    """
    80GG deduction for employees with no HRA component who pay rent.
    Min of: (1) rent paid − 10% GTI, (2) 25% GTI, (3) ₹60,000/year.
    """
    if monthly_rent <= 0 or gross_total_income <= 0:
        return 0.0
    annual_rent = monthly_rent * 12
    option1 = annual_rent - 0.10 * gross_total_income
    option2 = 0.25 * gross_total_income
    option3 = float(SECTION_80GG_ANNUAL_LIMIT)
    return max(0.0, round(min(option1, option2, option3), 2))


def compute_hra_exemption(
    hra_received: float,
    basic_salary: float,
    monthly_rent: float,
    city: str,
) -> float:
    """
    HRA exemption = Min of:
      1. Actual HRA received from employer
      2. 50% of basic (metro) or 40% of basic (non-metro)
      3. Actual rent paid − 10% of basic salary
    Returns 0 if no rent paid.
    """
    if monthly_rent <= 0:
        return 0.0
    annual_rent = monthly_rent * 12
    metro = city.strip().lower() in METRO_CITIES
    percent = HRA_METRO_PERCENT if metro else HRA_NON_METRO_PERCENT
    exemption = min(
        hra_received,
        percent * basic_salary,
        annual_rent - 0.10 * basic_salary,
    )
    return max(0.0, round(exemption, 2))


def _compute_tax_on_slabs(income: float, slabs: list) -> float:
    tax = 0.0
    prev_limit = 0
    for limit, rate in slabs:
        if income <= prev_limit:
            break
        taxable_in_slab = min(income, limit) - prev_limit
        tax += taxable_in_slab * rate
        prev_limit = limit
    return tax


def _surcharge_rate(total_income: float) -> float:
    if total_income > 50_000_000:
        return 0.37
    if total_income > 20_000_000:
        return 0.25
    if total_income > 10_000_000:
        return 0.15
    if total_income > 5_000_000:
        return 0.10
    return 0.0


def _compute_surcharge_and_cess(
    tax: float,
    total_income: float,
    equity_cg_tax: float = 0.0,
) -> tuple[float, float]:
    """
    Surcharge and education cess.
    equity_cg_tax: portion of 'tax' from Sec 111A/112A (listed equity/MF gains).
    Per Sec 112A proviso, surcharge on this portion is capped at 15% regardless of income bracket.
    All other income (slab + non-equity CG) gets the full income-bracket rate.
    """
    rate = _surcharge_rate(total_income)
    other_tax = tax - equity_cg_tax
    surcharge = other_tax * rate + equity_cg_tax * min(rate, 0.15)
    cess = (tax + surcharge) * 0.04
    return surcharge, cess


def _apply_capital_gains(
    capital_gains: Optional[CapitalGainsSummary],
) -> tuple[Optional[CapitalGainsTaxResult], float, float]:
    """
    Compute capital gains tax result if gains are present.
    Returns (cg_result, stcg_for_slab_income, cg_tax_at_special_rates).
    """
    if capital_gains and capital_gains.has_any_gains():
        cg_result = compute_capital_gains_tax(capital_gains)
        return cg_result, cg_result.stcg_for_slab_income, cg_result.total_tax_at_special_rates
    return None, 0.0, 0.0


@dataclass
class RegimeResult:
    regime: str
    gross_income: float
    total_deductions: float
    taxable_income: float
    # Breakdown needed by the ITR generator for correct schedule reporting
    chapter_via_deductions: float
    deduction_80tta_claimed: float
    deduction_80ttb_claimed: float          # Senior citizens (replaces 80TTA); 0 otherwise
    deduction_80d_self_claimed: float       # Capped 80D self/family — age-aware; needed by ITR generator
    deduction_80d_parents_claimed: float
    deduction_80gg_claimed: float
    deduction_80eea_claimed: float          # Section 80EEA; old regime only; 0 otherwise
    family_pension_deduction_claimed: float  # Section 57(iia); 0 when no family pension
    home_loan_interest_claimed: float  # self-occupied only; 0 when let-out
    hp_income: float                   # let-out HP income (capped loss); 0 when self-occupied
    hra_exemption_claimed: float
    other_sources_income: float       # FD interest + dividends from AIS + net family pension
    tax_before_cess: float
    surcharge: float
    cess: float
    tax_after_cess: float
    rebate_87a: float
    tax_payable: float
    tds_deducted: float               # Form 16 TDS + AIS TDS + gains TDS combined
    refund_or_payable: float
    # Capital gains — present only for ITR-2/3 filers; None means ITR-1
    capital_gains_result: Optional[CapitalGainsTaxResult] = None
    # F&O — present only for ITR-3 filers
    fo_result: Optional[FOTaxResult] = None


@dataclass
class TaxComputationResult:
    old_regime: RegimeResult
    new_regime: RegimeResult
    recommended_regime: str
    savings: float
    is_itr2: bool = False   # True when capital gains are present (but no F&O)
    is_itr3: bool = False   # True when F&O income is present (overrides is_itr2)


def compute_old_regime(
    form16: Form16Data,
    ais: Optional[AISData] = None,
    hra_monthly_rent: float = 0,
    hra_city: str = "",
    parents_insurance_premium: float = 0,
    parents_senior: bool = False,
    home_loan_interest_cert: float = 0,
    date_of_birth: str = "",
    rental_annual_rent: float = 0,
    rental_municipal_taxes: float = 0,
    rental_home_loan_interest: float = 0,
    family_pension: float = 0,
    home_loan_80eea: float = 0,
    capital_gains: Optional[CapitalGainsSummary] = None,
    fo_data: Optional[FOData] = None,
) -> RegimeResult:
    gross = form16.salary.gross_salary

    # HRA exemption — use Form 16 value if present, else compute from rent inputs.
    # 80GG applies instead when salary has no HRA component at all.
    has_hra_component = form16.salary.hra > 0
    hra_exempt = form16.exemptions.hra_exempt
    if has_hra_component and hra_exempt == 0 and hra_monthly_rent > 0:
        hra_exempt = compute_hra_exemption(
            form16.salary.hra, form16.salary.basic, hra_monthly_rent, hra_city
        )

    total_exempt = hra_exempt + form16.exemptions.lta_exempt + form16.exemptions.other_exempt
    income_after_exempt = max(0, gross - total_exempt)

    # Other sources income from AIS (FD interest, dividends) + family pension net
    other_sources = 0.0
    if ais:
        other_sources = ais.total_interest + ais.total_dividends
    # Section 57(iia): family pension deduction = min(₹15,000, pension/3); both regimes
    fp_deduction = min(FAMILY_PENSION_DEDUCTION_MAX, family_pension / 3) if family_pension > 0 else 0.0
    other_sources += (family_pension - fp_deduction)

    # Senior-citizen status of the taxpayer (≥60 at FY end) widens several caps.
    taxpayer_age = _age_at_fy_end(date_of_birth, form16.assessment_year)
    is_senior = taxpayer_age is not None and taxpayer_age >= SENIOR_CITIZEN_AGE

    std_deduction = STANDARD_DEDUCTION_OLD
    professional_tax = form16.professional_tax
    deduction_80c = min(form16.deductions_80c.total, SECTION_80C_LIMIT)
    self_cap = SECTION_80D_LIMIT_SELF_SENIOR if is_senior else SECTION_80D_LIMIT_SELF
    deduction_80d_self = min(form16.other_deductions.deduction_80d, self_cap)
    parents_cap = SECTION_80D_LIMIT_PARENTS_SENIOR if parents_senior else SECTION_80D_LIMIT_PARENTS
    deduction_80d_parents = min(parents_insurance_premium, parents_cap)
    deduction_80d = deduction_80d_self + deduction_80d_parents
    deduction_80e = form16.other_deductions.deduction_80e
    deduction_80g = form16.other_deductions.deduction_80g
    nps_80ccd1b = min(form16.other_deductions.nps_80ccd1b, SECTION_80CCD1B_LIMIT)

    # House property income — let-out and self-occupied are mutually exclusive in ITR-1
    is_letout = rental_annual_rent > 0
    if is_letout:
        hp_income_raw = compute_hp_income(rental_annual_rent, rental_municipal_taxes, rental_home_loan_interest)
        # HP loss can reduce other income by at most ₹2L in the same year
        hp_income = max(hp_income_raw, -float(HP_LOSS_SETOFF_LIMIT)) if hp_income_raw < 0 else hp_income_raw
        home_loan_interest = 0.0  # interest already embedded in HP income
    else:
        hp_income = 0.0
        # Self-occupied: bank cert overrides Form 16 when provided; capped at ₹2L
        _raw_hl = home_loan_interest_cert if home_loan_interest_cert > 0 else form16.other_deductions.home_loan_interest_24b
        home_loan_interest = min(_raw_hl, HOME_LOAN_INTEREST_24B_LIMIT)

    # Interest deduction — mutually exclusive by age:
    #   < 60: 80TTA — savings-account interest only, ₹10,000 cap
    #   ≥ 60: 80TTB — all deposit interest (savings + FD/RD), ₹50,000 cap (80TTA not allowed)
    # Use AIS figure when AIS is provided (even if zero), else fall back to Form 16.
    if is_senior:
        senior_interest = ais.total_interest if ais is not None else form16.other_deductions.deduction_80tta
        deduction_80ttb = min(senior_interest, SECTION_80TTB_LIMIT)
        deduction_80tta = 0.0
    else:
        savings_interest = ais.total_savings_interest if ais is not None else form16.other_deductions.deduction_80tta
        deduction_80tta = min(savings_interest, SECTION_80TTA_LIMIT)
        deduction_80ttb = 0.0

    # Capital gains and F&O must be computed before GTI so that 80GG uses the correct
    # Gross Total Income (which includes CG taxed at slab rates and F&O business income).
    cg_result, cg_stcg_slab, cg_tax_special = _apply_capital_gains(capital_gains)

    # F&O income — taxable_fo_income is net business income after prior-year loss set-off.
    # F&O losses are NOT set off against salary (Sec 71(2A)); they carry forward.
    fo_result: Optional[FOTaxResult] = compute_fo_tax(fo_data) if fo_data and fo_data.total_turnover > 0 else None
    fo_income = fo_result.taxable_fo_income if fo_result else 0.0

    # GTI includes CG at slab rates and F&O — needed for the 10%/25%-of-GTI thresholds in 80GG.
    gross_total_income = income_after_exempt + other_sources + hp_income + cg_stcg_slab + fo_income

    # 80GG: rent deduction for employees with no HRA component (mutually exclusive with HRA)
    deduction_80gg = 0.0
    if not has_hra_component and hra_monthly_rent > 0:
        deduction_80gg = compute_80gg(hra_monthly_rent, gross_total_income)

    # 80EEA: extra ₹1.5L deduction for affordable housing first-time buyers (old regime only).
    # CA verifies eligibility conditions (stamp duty ≤ ₹45L, loan Apr 2019–Mar 2022, first-time buyer).
    # Not applicable when let-out (property must be self-occupied or deemed self-occupied).
    deduction_80eea = min(home_loan_80eea, SECTION_80EEA_LIMIT) if not is_letout else 0.0

    chapter_via = (
        deduction_80c + deduction_80d + deduction_80e + deduction_80g
        + deduction_80tta + deduction_80ttb + nps_80ccd1b + deduction_80gg + deduction_80eea
    )

    total_deductions = std_deduction + professional_tax + chapter_via + home_loan_interest
    taxable_income = max(0, gross_total_income - total_deductions)
    slabs = _old_regime_slabs(date_of_birth, form16.assessment_year)
    tax_slab = _compute_tax_on_slabs(taxable_income, slabs)

    # 87A rebate threshold uses total income including special-rate CG.
    cg_special_taxable = cg_result.total_taxable_at_special_rates if cg_result else 0.0
    total_income = taxable_income + cg_special_taxable
    rebate = 0.0
    if total_income <= REBATE_87A_LIMIT_OLD:
        rebate = min(tax_slab, REBATE_87A_AMOUNT_OLD)

    tax_after_rebate = max(0, tax_slab - rebate)
    # Surcharge: income bracket based on full total income; Sec 112A proviso caps surcharge
    # on listed equity (111A/112A) tax at 15% regardless of income bracket.
    equity_cg_tax = cg_result.equity_cg_tax if cg_result else 0.0
    surcharge, cess = _compute_surcharge_and_cess(tax_after_rebate + cg_tax_special, total_income, equity_cg_tax)
    tax_before_cess = tax_slab + cg_tax_special
    tax_after_cess = tax_after_rebate + cg_tax_special + surcharge + cess

    tds = (form16.tds.tds_deducted + (ais.total_tds_from_ais if ais else 0)
           + (cg_result.tds_on_gains if cg_result else 0)
           + (fo_result.tds_on_fo if fo_result else 0))
    refund_or_payable = round(tds - tax_after_cess, 2)

    return RegimeResult(
        regime="Old Regime",
        gross_income=gross,
        total_deductions=total_deductions,
        taxable_income=taxable_income,
        chapter_via_deductions=chapter_via,
        deduction_80tta_claimed=deduction_80tta,
        deduction_80ttb_claimed=deduction_80ttb,
        deduction_80d_self_claimed=deduction_80d_self,
        deduction_80d_parents_claimed=deduction_80d_parents,
        deduction_80gg_claimed=deduction_80gg,
        deduction_80eea_claimed=deduction_80eea,
        family_pension_deduction_claimed=fp_deduction,
        home_loan_interest_claimed=home_loan_interest,
        hp_income=hp_income,
        hra_exemption_claimed=hra_exempt,
        other_sources_income=other_sources,
        tax_before_cess=tax_before_cess,
        surcharge=surcharge,
        cess=cess,
        tax_after_cess=tax_after_cess,
        rebate_87a=rebate,
        tax_payable=round(tax_after_cess, 2),
        tds_deducted=tds,
        refund_or_payable=refund_or_payable,
        capital_gains_result=cg_result,
        fo_result=fo_result,
    )


def compute_new_regime(
    form16: Form16Data,
    ais: Optional[AISData] = None,
    rental_annual_rent: float = 0,
    rental_municipal_taxes: float = 0,
    rental_home_loan_interest: float = 0,
    family_pension: float = 0,
    capital_gains: Optional[CapitalGainsSummary] = None,
    fo_data: Optional[FOData] = None,
) -> RegimeResult:
    gross = form16.salary.gross_salary
    std_deduction = STANDARD_DEDUCTION_NEW

    # New regime (Sec 115BAC): Chapter VI-A deductions are NOT allowed except 80CCD(2)
    # (employer NPS) and 80JJAA — neither of which we capture separately. In particular
    # 80CCD(1B) (self NPS) and 80TTA/80TTB are disallowed here. Only the standard deduction
    # under Sec 16(ia) and the Sec 57(iia) family-pension deduction apply.
    other_sources = (ais.total_interest + ais.total_dividends) if ais else 0
    fp_deduction = min(FAMILY_PENSION_DEDUCTION_MAX, family_pension / 3) if family_pension > 0 else 0.0
    other_sources += (family_pension - fp_deduction)
    if rental_annual_rent > 0:
        hp_income_raw = compute_hp_income(rental_annual_rent, rental_municipal_taxes, rental_home_loan_interest)
        hp_income = max(hp_income_raw, -float(HP_LOSS_SETOFF_LIMIT)) if hp_income_raw < 0 else hp_income_raw
    else:
        hp_income = 0.0

    # Capital gains — special rates are identical in old and new regime for listed equity.
    cg_result, cg_stcg_slab, cg_tax_special = _apply_capital_gains(capital_gains)

    fo_result: Optional[FOTaxResult] = compute_fo_tax(fo_data) if fo_data and fo_data.total_turnover > 0 else None
    fo_income = fo_result.taxable_fo_income if fo_result else 0.0

    chapter_via = 0.0
    total_deductions = std_deduction + chapter_via
    taxable_income = max(0, gross + other_sources + hp_income + cg_stcg_slab + fo_income - total_deductions)

    tax_slab = _compute_tax_on_slabs(taxable_income, NEW_REGIME_SLABS)

    cg_special_taxable = cg_result.total_taxable_at_special_rates if cg_result else 0.0
    total_income = taxable_income + cg_special_taxable
    rebate = 0.0
    if total_income <= REBATE_87A_LIMIT_NEW:
        rebate = min(tax_slab, REBATE_87A_AMOUNT_NEW)

    tax_after_rebate = max(0, tax_slab - rebate)
    equity_cg_tax = cg_result.equity_cg_tax if cg_result else 0.0
    surcharge, cess = _compute_surcharge_and_cess(tax_after_rebate + cg_tax_special, total_income, equity_cg_tax)
    tax_before_cess = tax_slab + cg_tax_special
    tax_after_cess = tax_after_rebate + cg_tax_special + surcharge + cess

    tds = (form16.tds.tds_deducted + (ais.total_tds_from_ais if ais else 0)
           + (cg_result.tds_on_gains if cg_result else 0)
           + (fo_result.tds_on_fo if fo_result else 0))
    refund_or_payable = round(tds - tax_after_cess, 2)

    return RegimeResult(
        regime="New Regime",
        gross_income=gross,
        total_deductions=total_deductions,
        taxable_income=taxable_income,
        chapter_via_deductions=chapter_via,
        deduction_80tta_claimed=0,
        deduction_80ttb_claimed=0,
        deduction_80d_self_claimed=0,
        deduction_80d_parents_claimed=0,
        deduction_80gg_claimed=0,
        deduction_80eea_claimed=0,
        family_pension_deduction_claimed=fp_deduction,
        home_loan_interest_claimed=0,
        hp_income=hp_income,
        hra_exemption_claimed=0,
        other_sources_income=other_sources,
        tax_before_cess=tax_before_cess,
        surcharge=surcharge,
        cess=cess,
        tax_after_cess=tax_after_cess,
        rebate_87a=rebate,
        tax_payable=round(tax_after_cess, 2),
        tds_deducted=tds,
        refund_or_payable=refund_or_payable,
        capital_gains_result=cg_result,
        fo_result=fo_result,
    )


def compute_optimal_regime(
    form16: Form16Data,
    ais: Optional[AISData] = None,
    hra_monthly_rent: float = 0,
    hra_city: str = "",
    parents_insurance_premium: float = 0,
    parents_senior: bool = False,
    home_loan_interest_cert: float = 0,
    date_of_birth: str = "",
    rental_annual_rent: float = 0,
    rental_municipal_taxes: float = 0,
    rental_home_loan_interest: float = 0,
    family_pension: float = 0,
    home_loan_80eea: float = 0,
    capital_gains: Optional[CapitalGainsSummary] = None,
    fo_data: Optional[FOData] = None,
) -> TaxComputationResult:
    old = compute_old_regime(
        form16, ais, hra_monthly_rent, hra_city,
        parents_insurance_premium, parents_senior, home_loan_interest_cert,
        date_of_birth, rental_annual_rent, rental_municipal_taxes, rental_home_loan_interest,
        family_pension, home_loan_80eea, capital_gains, fo_data,
    )
    new = compute_new_regime(
        form16, ais, rental_annual_rent, rental_municipal_taxes, rental_home_loan_interest,
        family_pension, capital_gains, fo_data,
    )

    if old.tax_payable <= new.tax_payable:
        recommended = "Old Regime"
        savings = round(new.tax_payable - old.tax_payable, 2)
    else:
        recommended = "New Regime"
        savings = round(old.tax_payable - new.tax_payable, 2)

    has_fo = fo_data is not None and fo_data.total_turnover > 0
    has_cg = capital_gains is not None and capital_gains.has_any_gains()

    return TaxComputationResult(
        old_regime=old,
        new_regime=new,
        recommended_regime=recommended,
        savings=savings,
        is_itr2=has_cg and not has_fo,
        is_itr3=has_fo,
    )
