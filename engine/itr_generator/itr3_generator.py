"""
Generates ITR-3 JSON in the schema accepted by the Income Tax e-filing portal.
ITR-3 is mandatory for any taxpayer with F&O (Futures & Options) or other business income.
It extends ITR-2's schema with Schedule BP (business/profession income), Schedule BFLA
(brought-forward loss set-off), and Schedule CFL (carry-forward losses).

Schema reference: IT Department ITR-3 JSON schema for AY 2025-26.
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
from engine.itr_generator.itr2_generator import (
    _build_schedule_al,
    _build_schedule_cg,
    _build_schedule_si,
    _build_schedule_tds2,
    _empty_schedule_cg,
)
from engine.models import Form16Data
from engine.models_capital_gains import CapitalGainsSummary
from engine.models_fo import FOData
from engine.models_schedule_al import SCHEDULE_AL_THRESHOLD, ScheduleALData


def generate_itr3(
    form16: Form16Data,
    computation: TaxComputationResult,
    bank_account: BankAccount,
    fo_data: FOData,
    capital_gains: Optional[CapitalGainsSummary] = None,
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

    cg = regime.capital_gains_result
    fo = regime.fo_result

    if fo is None:
        raise ValueError("generate_itr3 requires F&O result in regime; use generate_itr1/itr2 for non-F&O returns")

    # ── Salary income ──────────────────────────────────────────────────────────
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

    # ── HP income ──────────────────────────────────────────────────────────────
    if regime.hp_income != 0:
        hp_total = int(round(regime.hp_income))
    else:
        hp_total = -int(round(regime.home_loan_interest_claimed)) if is_old else 0

    # ── Other sources ──────────────────────────────────────────────────────────
    income_oth_src = int(round(regime.other_sources_income))

    # ── Business income (F&O) ─────────────────────────────────────────────────
    fo_business_income = int(round(fo.taxable_fo_income))
    stcg_slab = int(round(cg.stcg_for_slab_income)) if cg else 0

    # ── Chapter VI-A ──────────────────────────────────────────────────────────
    chap_via_breakdown = _build_chapter_via(form16, regime) if is_old else None
    chap_via_total = chap_via_breakdown["TotalChapVIADeductions"] if chap_via_breakdown else 0

    gross_tot_income = income_from_sal + hp_total + income_oth_src + stcg_slab + fo_business_income
    total_income = gross_tot_income - chap_via_total

    # ── Tax breakdown ──────────────────────────────────────────────────────────
    cg_tax_special = int(round(cg.total_tax_at_special_rates)) if cg else 0
    tax_on_ti = int(round(regime.tax_before_cess - (cg.total_tax_at_special_rates if cg else 0)))
    rebate = int(regime.rebate_87a)

    ais_tds = int(regime.tds_deducted - form16.tds.tds_deducted
                  - (cg.tds_on_gains if cg else 0) - fo.tds_on_fo)
    cg_tds = int(cg.tds_on_gains) if cg else 0
    fo_tds = int(round(fo.tds_on_fo))

    itr3 = {
        "ITRForm": {
            "FormName": "ITR-3",
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
        "ITR3_IncomeDeductions": {
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
        "ScheduleBP": _build_schedule_bp(fo_data, fo),
        "ScheduleCGFor23": _build_schedule_cg(cg, capital_gains) if cg and capital_gains else _empty_schedule_cg(),
        "ScheduleSI": _build_schedule_si(cg),
        "ScheduleBFLA": _build_schedule_bfla(fo_data, fo),
        "ScheduleCFL": _build_schedule_cfl(fo, form16.assessment_year, fo_data),
        "ITR3_TaxComputed": {
            "TaxPayableOnTI": tax_on_ti,
            "TaxPayableSplRate": cg_tax_special,
            "TaxPayableOnTIAndSplRate": tax_on_ti + cg_tax_special,
            "Rebate87A": rebate,
            "TaxPayableAfterRebate": int(max(0, tax_on_ti + cg_tax_special - rebate)),
            "Surcharge": int(regime.surcharge),
            "EducationCess": int(regime.cess),
            "GrossTaxLiability": int(regime.tax_after_cess),
            "TDS": {
                "TDSonSalary": int(form16.tds.tds_deducted),
                "TDSonOtherThanSalary": max(0, ais_tds),
                "TDSonCapGains": cg_tds,
                "TDSonBusinessIncome": fo_tds,
            },
            "TCS": 0,
            "SelfAssessmentTax": 0,
            "AdvanceTax": 0,
            "TotalTaxesPaid": int(regime.tds_deducted),
            "TaxPayable": int(max(0, regime.tax_after_cess - regime.tds_deducted)),
            "Refund": int(max(0, regime.tds_deducted - regime.tax_after_cess)),
        },
        "ScheduleTDS1": _build_schedule_tds1(form16, second_form16),
        "ScheduleTDS2": _build_schedule_tds2(max(0, ais_tds)),
        "Refund": {
            "BankAccountNo": bank_account.account_number,
            "IFSCCode": bank_account.ifsc,
            "BankName": bank_account.bank_name,
            "AccountType": bank_account.account_type,
        },
        "AuditInformation": {
            "TaxAuditRequired": fo.requires_tax_audit,
            "Turnover": int(round(fo.total_turnover)),
        },
    }

    if chap_via_breakdown is not None:
        itr3["ITR3_IncomeDeductions"]["DeductionUndChapVIA"] = chap_via_breakdown

    cg_special_for_al = cg.total_taxable_at_special_rates if cg else 0
    if schedule_al and (total_income + cg_special_for_al) > SCHEDULE_AL_THRESHOLD:
        itr3["ScheduleAL"] = _build_schedule_al(schedule_al)

    return itr3


def _build_schedule_bp(fo_data: FOData, fo) -> dict:
    """
    Schedule BP — Business/Profession income.
    For F&O traders: reports gross receipts (turnover), expenses, and net income.
    """
    gross_receipts = int(round(fo.total_turnover))
    gross_profit = int(round(max(0, fo.gross_pl)))
    gross_loss = int(round(max(0, -fo.gross_pl)))
    expenses = int(round(fo.total_expenses))
    net_income = int(round(fo.net_income))

    segment_breakdown = [
        {
            "Segment": s.segment,
            "GrossProfit": int(round(s.gross_profit)),
            "GrossLoss": int(round(s.gross_loss)),
            "NetPL": int(round(s.net_pl)),
            "Turnover": int(round(s.turnover)),
        }
        for s in fo_data.segments
    ]

    return {
        "NatureOfBusiness": "F&O — Futures and Options (Non-Speculative Business Income u/s 43(5))",
        "GrossReceipts": gross_receipts,
        "GrossProfitFromFO": gross_profit,
        "GrossLossFromFO": gross_loss,
        "Expenses": {
            "Brokerage": int(round(fo_data.expenses.brokerage)),
            "STT": int(round(fo_data.expenses.stt)),
            "ExchangeFees": int(round(fo_data.expenses.exchange_fees)),
            "DPCharges": int(round(fo_data.expenses.dp_charges)),
            "InternetSoftware": int(round(fo_data.expenses.internet_software)),
            "AdvisoryFees": int(round(fo_data.expenses.advisory_fees)),
            "Depreciation": int(round(fo_data.expenses.depreciation)),
            "Others": int(round(fo_data.expenses.others)),
            "TotalExpenses": int(round(fo_data.expenses.total)),
        },
        "NetIncomeFromFO": net_income,
        "SegmentBreakdown": segment_breakdown,
    }


def _build_schedule_bfla(fo_data: FOData, fo) -> dict:
    """Schedule BFLA — Brought Forward Loss Adjustment: prior-year F&O losses set off this year.

    TotalBFLossSetOff uses the engine-computed value (capped at net income) so it reconciles
    with Schedule BP net income. Raw sum of carry_forward_losses would overstate when
    net income < total prior losses.
    """
    entries = [
        {
            "AssessmentYear": cf.assessment_year,
            "LossAmount": int(round(cf.loss_amount)),
        }
        for cf in fo_data.carry_forward_losses
        if cf.loss_amount > 0
    ]
    return {
        "BFLossDetails": entries,
        "TotalBFLossSetOff": int(round(fo.prior_year_loss_setoff)),
    }


def _build_schedule_cfl(fo, assessment_year: str, fo_data: FOData) -> dict:
    """Schedule CFL — Carry Forward Loss: losses to carry forward to future years.

    Includes:
    1. Unconsumed prior-year losses (not fully set off this year) — applied FIFO by AY.
    2. Current-year net loss (if any).
    """
    cfl_entries = []

    # Apportion prior-year losses FIFO (oldest year first); residual carries forward.
    remaining_setoff = fo.prior_year_loss_setoff
    for cf in sorted(fo_data.carry_forward_losses, key=lambda x: x.assessment_year):
        if cf.loss_amount <= 0:
            continue
        consumed = min(remaining_setoff, cf.loss_amount)
        remaining_setoff -= consumed
        residual = cf.loss_amount - consumed
        if residual > 0:
            cfl_entries.append({
                "AssessmentYear": cf.assessment_year,
                "LossType": "Business (F&O)",
                "LossAmount": int(round(residual)),
                "CarryForwardYearsRemaining": 8,
            })

    # Current-year loss (only when there is a net loss this year)
    if fo.current_year_loss_cf > 0:
        cfl_entries.append({
            "AssessmentYear": assessment_year,
            "LossType": "Business (F&O)",
            "LossAmount": int(round(fo.current_year_loss_cf)),
            "CarryForwardYearsRemaining": 8,
        })

    if not cfl_entries:
        return {"CFLossDetails": [], "TotalCFLoss": 0}

    return {
        "CFLossDetails": cfl_entries,
        "TotalCFLoss": sum(e["LossAmount"] for e in cfl_entries),
    }
