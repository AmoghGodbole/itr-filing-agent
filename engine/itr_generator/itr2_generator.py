"""
Generates ITR-2 JSON in the schema accepted by the Income Tax e-filing portal.
ITR-2 extends ITR-1 with Schedule CG (capital gains) and Schedule SI (special income rates).
Schema reference: IT Department ITR-2 JSON schema for AY 2025-26.

When no capital gains are present, use itr1_generator.py instead.
"""

from typing import Optional

from engine.computation.tax_engine import STANDARD_DEDUCTION_OLD, STANDARD_DEDUCTION_NEW, TaxComputationResult
from engine.itr_generator.itr1_generator import (
    BankAccount,
    _build_chapter_via,
    _build_schedule_tds1,
    _extract_first_name,
    _extract_surname,
)
from engine.models import Form16Data
from engine.models_capital_gains import CapitalGainsSummary
from engine.models_schedule_al import SCHEDULE_AL_THRESHOLD, ScheduleALData


def generate_itr2(
    form16: Form16Data,
    computation: TaxComputationResult,
    bank_account: BankAccount,
    capital_gains: CapitalGainsSummary,
    aadhaar_number: str | None = None,
    mobile: str | None = None,
    email: str | None = None,
    date_of_birth: str | None = None,
    second_form16: Form16Data | None = None,
    schedule_al: Optional[ScheduleALData] = None,
) -> dict:
    is_old = computation.recommended_regime == "Old Regime"
    regime = computation.old_regime if is_old else computation.new_regime
    regime_flag = "O" if is_old else "N"
    std_deduction = STANDARD_DEDUCTION_OLD if is_old else STANDARD_DEDUCTION_NEW

    cg = regime.capital_gains_result  # pre-computed by the tax engine
    if cg is None:
        raise ValueError("generate_itr2 requires capital_gains_result in regime; use generate_itr1 for non-CG returns")

    # ── Salary income (same logic as itr1_generator) ──────────────────────────
    if is_old:
        total_exempt = int(
            regime.hra_exemption_claimed
            + form16.exemptions.lta_exempt
            + form16.exemptions.other_exempt
        )
        prof_tax = int(form16.professional_tax)
    else:
        total_exempt = 0
        prof_tax = 0

    net_salary = int(form16.salary.gross_salary - total_exempt)
    income_from_sal = int(net_salary - std_deduction - prof_tax)

    # ── House property income ──────────────────────────────────────────────────
    if regime.hp_income != 0:
        hp_total = int(round(regime.hp_income))
    else:
        hp_total = -int(round(regime.home_loan_interest_claimed)) if is_old else 0

    # ── Other sources income (AIS interest + dividends + net family pension) ───
    income_oth_src = int(round(regime.other_sources_income))

    # ── Capital gains schedule ─────────────────────────────────────────────────
    # STCG at slab rates is included in income_oth_src equivalent but tracked separately
    # in Schedule CG. The portal adds slab-STCG to GrossTotIncome via Schedule CG.
    stcg_slab = int(round(cg.stcg_for_slab_income)) if cg else 0

    # ── Chapter VI-A (old regime only) ────────────────────────────────────────
    chap_via_breakdown = _build_chapter_via(form16, regime) if is_old else None
    chap_via_total = chap_via_breakdown["TotalChapVIADeductions"] if chap_via_breakdown else 0

    # GrossTotIncome includes slab-rate STCG (goes through normal income path in portal)
    gross_tot_income = income_from_sal + hp_total + income_oth_src + stcg_slab
    total_income = gross_tot_income - chap_via_total

    # ── Tax breakdown ──────────────────────────────────────────────────────────
    # For ITR-2, rebate 87A applies only on slab tax (not special-rate CG tax).
    # The portal's ITR2_TaxComputed separates these.
    tax_special = int(round(cg.total_tax_at_special_rates)) if cg else 0
    tax_on_ti = int(round(regime.tax_before_cess - (cg.total_tax_at_special_rates if cg else 0)))
    rebate = int(regime.rebate_87a)

    ais_tds = max(0, int(regime.tds_deducted - form16.tds.tds_deducted - (cg.tds_on_gains if cg else 0)))
    cg_tds = int(cg.tds_on_gains) if cg else 0

    # ── Build ITR-2 JSON ───────────────────────────────────────────────────────
    itr2 = {
        "ITRForm": {
            "FormName": "ITR-2",
            "AssessmentYear": form16.assessment_year.replace("AY ", "").replace("-", ""),
            "SchemaVersion": "20.0",
        },
        "PersonalInfo": {
            "AssesseeName": {
                "FirstName": _extract_first_name(form16.employee_name),
                "SurName": _extract_surname(form16.employee_name),
            },
            "PAN": form16.employee_pan,
            "Aadhar": aadhaar_number or "",
            "MobileNo": mobile or "",
            "EmailAddress": email or "",
            "Address": {},
            "DOB": date_of_birth or "",
        },
        "FilingStatus": {
            "ReturnType": "11",
            "NewTaxRegime": regime_flag,
        },
        "ITR2_IncomeDeductions": {
            "GrossSalary": int(form16.salary.gross_salary),
            "Salary": int(form16.salary.gross_salary),
            "PerquisitesValue": 0,
            "ProfitsInLieuOfSalary": 0,
            "TotalGrossSalary": int(form16.salary.gross_salary),
            "ExemptAllowances": total_exempt,
            "NetSalary": net_salary,
            "DeductionUS16": {
                "ProfessionalTax": prof_tax,
                "EntertainmentAllow": 0,
                "StandardDeduction": std_deduction,
            },
            "IncomeFromSal": income_from_sal,
            "TotalIncomeOfHP": hp_total,
            "IncomeOthSrc": income_oth_src,
            "GrossTotIncome": gross_tot_income,
            "TotalChapVIADeductions": chap_via_total,
            "TotalIncome": total_income,
        },
        "ScheduleCGFor23": _build_schedule_cg(cg, capital_gains),
        "ScheduleSI": _build_schedule_si(cg),
        "ITR2_TaxComputed": {
            "TaxPayableOnTI": tax_on_ti,
            "TaxPayableSplRate": tax_special,
            "TaxPayableOnTIAndSplRate": tax_on_ti + tax_special,
            "Rebate87A": rebate,
            "TaxPayableAfterRebate": int(max(0, tax_on_ti + tax_special - rebate)),
            "Surcharge": int(regime.surcharge),
            "EducationCess": int(regime.cess),
            "GrossTaxLiability": int(regime.tax_after_cess),
            "TDS": {
                "TDSonSalary": int(form16.tds.tds_deducted),
                "TDSonOtherThanSalary": max(0, ais_tds),
                "TDSonCapGains": cg_tds,
            },
            "TCS": 0,
            "SelfAssessmentTax": 0,
            "AdvanceTax": 0,
            "TotalTaxesPaid": int(regime.tds_deducted),
            "TaxPayable": int(max(0, regime.tax_after_cess - regime.tds_deducted)),
            "Refund": int(max(0, regime.tds_deducted - regime.tax_after_cess)),
        },
        "ScheduleTDS1": _build_schedule_tds1(form16, second_form16),
        "ScheduleTDS2": _build_schedule_tds2(ais_tds),
        "Refund": {
            "BankAccountNo": bank_account.account_number,
            "IFSCCode": bank_account.ifsc,
            "BankName": bank_account.bank_name,
            "AccountType": bank_account.account_type,
        },
    }

    if chap_via_breakdown is not None:
        itr2["ITR2_IncomeDeductions"]["DeductionUndChapVIA"] = chap_via_breakdown

    # Schedule AL: mandatory when TOTAL income > ₹50L. "Total income" (Sec 2(45)) includes
    # special-rate CG — not just slab income — so add cg.total_taxable_at_special_rates here.
    cg_special_for_al = cg.total_taxable_at_special_rates if cg else 0
    if schedule_al and (total_income + cg_special_for_al) > SCHEDULE_AL_THRESHOLD:
        itr2["ScheduleAL"] = _build_schedule_al(schedule_al)

    return itr2


def _build_schedule_cg(cg, raw: CapitalGainsSummary) -> dict:
    """
    Build Schedule CG for ITR-2.
    Each bucket carries SaleValue/CostOfAcquisition/CapGain where the portal
    requires the breakdown; for summary-level input we set CostOfAcquisition=0
    and put the net gain in CapGain — acceptable for paper-trail purposes since
    the actual cost basis is in the broker's ledger.
    """
    if cg is None:
        return _empty_schedule_cg()

    def _cg_entry(gain: float) -> dict:
        g = int(round(gain))
        return {"SaleValue": max(g, 0), "CostOfAcquisition": 0, "Deductions": 0, "CapGain": g}

    def _ltcg_112a_entry(gain: float, exempt: float) -> dict:
        g = int(round(gain))
        ex = int(round(exempt))
        return {"CapGain": g, "Exemption": ex, "LTCGAfterExemption": max(0, g - ex)}

    stcg_pre = _cg_entry(raw.equity.stcg_pre_jul23)
    stcg_post = _cg_entry(raw.equity.stcg_post_jul23)
    stcg_other = _cg_entry(raw.other.stcg_at_slab + raw.property_gains.stcg)
    ltcg_10 = _ltcg_112a_entry(raw.equity.ltcg_pre_jul23, cg.exempt_112a_pre_jul23)
    ltcg_125_eq = _ltcg_112a_entry(raw.equity.ltcg_post_jul23, cg.exempt_112a_post_jul23)
    ltcg_20 = _cg_entry(raw.other.ltcg_20pct_with_indexation + raw.property_gains.ltcg_with_indexation)
    ltcg_125 = _cg_entry(raw.other.ltcg_125pct_without_indexation + raw.property_gains.ltcg_without_indexation)

    total_stcg = (
        stcg_pre["CapGain"] + stcg_post["CapGain"] + stcg_other["CapGain"]
    )
    total_ltcg = (
        ltcg_10["LTCGAfterExemption"] + ltcg_125_eq["LTCGAfterExemption"]
        + max(0, ltcg_20["CapGain"]) + max(0, ltcg_125["CapGain"])
    )

    return {
        "ShortTermCapGainFor15Per": stcg_pre,
        "ShortTermCapGainFor20Per": stcg_post,
        "ShortTermCapGainAtApplicableRate": stcg_other,
        "LongTermCapGain10Per": ltcg_10,
        "LongTermCapGain125Per": ltcg_125_eq,
        "LongTermCapGain20Per": ltcg_20,
        "LongTermCapGain125PerWithoutIndex": ltcg_125,
        "TotalShortTermCapGain": total_stcg,
        "TotalLongTermCapGain": total_ltcg,
        "TotalCapGains": total_stcg + total_ltcg,
    }


def _empty_schedule_cg() -> dict:
    zero_cg = {"SaleValue": 0, "CostOfAcquisition": 0, "Deductions": 0, "CapGain": 0}
    zero_ltcg = {"CapGain": 0, "Exemption": 0, "LTCGAfterExemption": 0}
    return {
        "ShortTermCapGainFor15Per": zero_cg,
        "ShortTermCapGainFor20Per": zero_cg,
        "ShortTermCapGainAtApplicableRate": zero_cg,
        "LongTermCapGain10Per": zero_ltcg,
        "LongTermCapGain125Per": zero_ltcg,
        "LongTermCapGain20Per": zero_cg,
        "LongTermCapGain125PerWithoutIndex": zero_cg,
        "TotalShortTermCapGain": 0,
        "TotalLongTermCapGain": 0,
        "TotalCapGains": 0,
    }


def _build_schedule_si(cg) -> dict:
    """Schedule SI — special income rates with per-category tax amounts."""
    if cg is None:
        return {"SIDetails": [], "TotSITax": 0}

    details = []

    def _add(desc: str, rate: float, income: float, tax: float):
        if income > 0 or tax > 0:
            details.append({
                "SIHeadDescription": desc,
                "SIRate": rate,
                "SIIncome": int(round(income)),
                "SITax": int(round(tax)),
            })

    _add("STCG u/s 111A (before 23-07-2024)", 15, cg.taxable_stcg_111a_pre, cg.tax_stcg_111a_pre)
    _add("STCG u/s 111A (on/after 23-07-2024)", 20, cg.taxable_stcg_111a_post, cg.tax_stcg_111a_post)
    _add("LTCG u/s 112A (before 23-07-2024)", 10, cg.taxable_ltcg_112a_pre, cg.tax_ltcg_112a_pre)
    _add("LTCG u/s 112A (on/after 23-07-2024)", 12.5, cg.taxable_ltcg_112a_post, cg.tax_ltcg_112a_post)
    _add("LTCG u/s 112 with indexation", 20, cg.taxable_ltcg_20pct, cg.tax_ltcg_20pct)
    _add("LTCG u/s 112 without indexation", 12.5, cg.taxable_ltcg_125pct, cg.tax_ltcg_125pct)

    return {
        "SIDetails": details,
        "TotSITax": int(round(cg.total_tax_at_special_rates)),
    }


def _build_schedule_tds2(ais_tds: int) -> list:
    """Schedule TDS2 — non-salary TDS (AIS: FD interest, dividends, etc.)."""
    if ais_tds <= 0:
        return []
    return [
        {
            "TDSClaimed": ais_tds,
            "TaxDeductionSrc": "Interest/Dividends (AIS)",
            "TDSDeducted": ais_tds,
        }
    ]


def _build_schedule_al(al: ScheduleALData) -> dict:
    """
    Schedule AL — Assets and Liabilities as on March 31 of the FY.
    Required when total income > ₹50L. All values in rupees.
    """
    immovable = [
        {
            "Description": p.description,
            "Address": f"{p.address}, {p.city} - {p.pin_code}".strip(", "),
            "State": p.state,
            "Value": int(round(p.value)),
        }
        for p in al.immovable_properties
        if p.value > 0 or p.description
    ]

    return {
        "ImmovableDetails": immovable,
        "MovableDetails": {
            "JewelleryOrnaments": int(round(al.movable.jewellery)),
            "PaintingsCollections": int(round(al.movable.paintings_collections)),
            "Bullion": int(round(al.movable.bullion)),
            "Vehicles": int(round(al.movable.vehicles)),
            "Others": int(round(al.movable.others)),
        },
        "FinancialDetails": {
            "BankBalance": int(round(al.financial.bank_balance)),
            "SharesAndSecurities": int(round(al.financial.shares_securities)),
            "InsuranceSurrenderValue": int(round(al.financial.insurance_surrender_value)),
            "LoansGiven": int(round(al.financial.loans_given)),
            "CashInHand": int(round(al.financial.cash_in_hand)),
            "Others": int(round(al.financial.others)),
        },
        "LiabilityDetails": {
            "LoanFromBanks": int(round(al.liabilities.loan_from_banks)),
            "LoanFromOthers": int(round(al.liabilities.loan_from_others)),
            "Others": int(round(al.liabilities.others)),
        },
        "TotalAssets": int(round(al.total_assets)),
        "TotalLiabilities": int(round(al.total_liabilities)),
    }
