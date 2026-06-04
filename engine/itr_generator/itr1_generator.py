"""
Generates ITR-1 (Sahaj) JSON in the schema accepted by the Income Tax e-filing portal.
Schema reference: IT Department JSON schema for ITR-1 AY 2024-25.
"""

from dataclasses import dataclass

from engine.computation.tax_engine import (
    SECTION_80C_LIMIT,
    SECTION_80CCD1B_LIMIT,
    SECTION_80D_LIMIT_SELF,
    SECTION_80EEA_LIMIT,
    STANDARD_DEDUCTION_OLD,
    STANDARD_DEDUCTION_NEW,
    TaxComputationResult,
)
from engine.models import Form16Data


@dataclass
class BankAccount:
    account_number: str
    ifsc: str
    account_type: str  # "Savings" | "Current"
    bank_name: str


def generate_itr1(
    form16: Form16Data,
    computation: TaxComputationResult,
    bank_account: BankAccount,
    aadhaar_number: str | None = None,
    mobile: str | None = None,
    email: str | None = None,
    date_of_birth: str | None = None,
    second_form16: Form16Data | None = None,
) -> dict:
    is_old = computation.recommended_regime == "Old Regime"
    regime = computation.old_regime if is_old else computation.new_regime
    regime_flag = "O" if is_old else "N"
    std_deduction = STANDARD_DEDUCTION_OLD if is_old else STANDARD_DEDUCTION_NEW

    # ITR-1 income structure:
    #   GrossSalary → ExemptAllowances → NetSalary → IncomeFromSal (after Sec 16)
    #   + TotalIncomeOfHP (let-out HP income, or self-occupied loss in old regime)
    #   + IncomeOthSrc (FD interest, dividends from AIS)
    #   = GrossTotIncome
    #   − Chapter VI-A deductions
    #   = TotalIncome

    # New regime: LTA (Sec 10(5)) and other allowance exemptions are not available;
    # professional tax (Sec 16(iii)) is not deductible. Using them creates
    # GrossTotIncome - ChapVIA ≠ TotalIncome, which the portal rejects.
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

    # House property income:
    # - Let-out: use computed HP income (regime.hp_income, already loss-capped) — both regimes
    # - Self-occupied: home loan interest creates HP loss (old regime only)
    if regime.hp_income != 0:
        hp_total = int(round(regime.hp_income))
    else:
        hp_total = -int(round(regime.home_loan_interest_claimed)) if is_old else 0

    # Income from other sources (FD interest + dividends from AIS + net family pension after Sec 57 deduction)
    income_oth_src = int(round(regime.other_sources_income))

    # Build the Chapter VI-A breakdown first (old regime only) and take its sub-total as the
    # authoritative figure, so the top-level TotalChapVIADeductions, the DeductionUndChapVIA
    # sub-total, and TotalIncome are all derived from the same integers. New regime allows no
    # Chapter VI-A deductions, so the total is 0 there.
    # round() rather than truncate so components sum cleanly and TotalIncome is derived from
    # them (not from regime.taxable_income independently) — guarantees the portal invariant
    # GrossTotIncome − TotalChapVIADeductions == TotalIncome.
    chap_via_breakdown = _build_chapter_via(form16, regime) if is_old else None
    chap_via_total = chap_via_breakdown["TotalChapVIADeductions"] if chap_via_breakdown else 0
    gross_tot_income = income_from_sal + hp_total + income_oth_src
    total_income = gross_tot_income - chap_via_total

    # AIS TDS (on FD, dividends, rent) is already included in regime.tds_deducted;
    # split it back out for the TDS schedule fields
    ais_tds = int(regime.tds_deducted - form16.tds.tds_deducted)

    itr1 = {
        "ITRForm": {
            "FormName": "ITR-1",
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
            "ReturnType": "11",  # Original
            "NewTaxRegime": regime_flag,
        },
        "ITR1_IncomeDeductions": {
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
        "ITR1_TaxComputed": {
            "TaxPayableOnTI": int(regime.tax_before_cess),
            "Rebate87A": int(regime.rebate_87a),
            "TaxPayableAfterRebate": int(max(0, regime.tax_before_cess - regime.rebate_87a)),
            "Surcharge": int(regime.surcharge),
            "EducationCess": int(regime.cess),  # Fix #5: cess only, not surcharge+cess
            "GrossTaxLiability": int(regime.tax_after_cess),
            "TDS": {
                "TDSonSalary": int(form16.tds.tds_deducted),
                "TDSonOtherThanSalary": ais_tds,
            },
            "TCS": 0,
            "SelfAssessmentTax": 0,
            "AdvanceTax": 0,
            "TotalTaxesPaid": int(regime.tds_deducted),
            "TaxPayable": int(max(0, regime.tax_after_cess - regime.tds_deducted)),
            "Refund": int(max(0, regime.tds_deducted - regime.tax_after_cess)),
        },
        "ScheduleTDS1": _build_schedule_tds1(form16, second_form16),
        "Refund": {
            "BankAccountNo": bank_account.account_number,
            "IFSCCode": bank_account.ifsc,
            "BankName": bank_account.bank_name,
            "AccountType": bank_account.account_type,
        },
    }

    if chap_via_breakdown is not None:
        itr1["ITR1_IncomeDeductions"]["DeductionUndChapVIA"] = chap_via_breakdown

    return itr1


def _build_schedule_tds1(merged: Form16Data, second: Form16Data | None) -> list:
    if second is None:
        return [
            {
                "TAN": merged.employer.tan,
                "EmployerName": merged.employer.name,
                "GrossSalary": int(merged.salary.gross_salary),
                "TaxDeducted": int(merged.tds.tds_deducted),
                "TaxClaimed": int(merged.tds.tds_deducted),
            }
        ]
    # Two employers — merged form has totals; recover primary figures by subtracting secondary.
    # round() before int() guards against float subtraction imprecision (e.g. 30248.5 - 10248.5).
    primary_gross = int(round(merged.salary.gross_salary - second.salary.gross_salary))
    primary_tds = int(round(merged.tds.tds_deducted - second.tds.tds_deducted))
    return [
        {
            "TAN": merged.employer.tan,
            "EmployerName": merged.employer.name,
            "GrossSalary": primary_gross,
            "TaxDeducted": primary_tds,
            "TaxClaimed": primary_tds,
        },
        {
            "TAN": second.employer.tan,
            "EmployerName": second.employer.name,
            "GrossSalary": int(second.salary.gross_salary),
            "TaxDeducted": int(second.tds.tds_deducted),
            "TaxClaimed": int(second.tds.tds_deducted),
        },
    ]


def _extract_first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else ""


def _extract_surname(full_name: str) -> str:
    parts = full_name.strip().split()
    return " ".join(parts[1:]) if len(parts) > 1 else ""


def _build_chapter_via(form16: Form16Data, regime) -> dict:
    # Caps for age-independent sections are sourced from tax_engine constants.
    # Age-sensitive / engine-capped sections (80D self & parents, 80TTA/80TTB, 80GG, 80EEA)
    # use regime-computed values so this breakdown matches what the engine actually deducted —
    # otherwise the sub-total would diverge from regime.chapter_via_deductions and the portal
    # would reject the return.
    section_80c = int(min(form16.deductions_80c.total, SECTION_80C_LIMIT))
    section_80d_self = int(round(regime.deduction_80d_self_claimed))
    section_80d_parents = int(round(regime.deduction_80d_parents_claimed))
    section_80d = section_80d_self + section_80d_parents
    section_80ccd1b = int(min(form16.other_deductions.nps_80ccd1b, SECTION_80CCD1B_LIMIT))
    section_80e = int(form16.other_deductions.deduction_80e)
    section_80g = int(form16.other_deductions.deduction_80g)
    section_80tta = int(round(regime.deduction_80tta_claimed))
    section_80ttb = int(round(regime.deduction_80ttb_claimed))
    section_80gg = int(round(regime.deduction_80gg_claimed))
    section_80eea = int(round(regime.deduction_80eea_claimed))

    total = (
        section_80c + section_80d + section_80ccd1b + section_80e + section_80g
        + section_80tta + section_80ttb + section_80gg + section_80eea
    )
    return {
        "Section80C": section_80c,
        "Section80CCC": 0,
        "Section80CCDEmployeeOrSE": 0,
        "Section80CCD1B": section_80ccd1b,
        "Section80D": section_80d,
        "Section80E": section_80e,
        "Section80G": section_80g,
        "Section80TTA": section_80tta,
        "Section80TTB": section_80ttb,
        "Section80GG": section_80gg,
        "Section80EEA": section_80eea,
        "TotalChapVIADeductions": total,
    }
