from pydantic import BaseModel, model_validator
from typing import Optional


class EmployerDetails(BaseModel):
    name: str
    tan: str
    pan: Optional[str] = None
    address: Optional[str] = None


class SalaryBreakdown(BaseModel):
    basic: float = 0
    hra: float = 0
    lta: float = 0
    special_allowance: float = 0
    other_allowances: float = 0
    gross_salary: float = 0

    @model_validator(mode="after")
    def derive_other_allowances(self) -> "SalaryBreakdown":
        # Derive rather than trust LLM extraction — gross and named components
        # are reliably extracted; other_allowances is just the remainder.
        named = self.basic + self.hra + self.lta + self.special_allowance
        derived = round(self.gross_salary - named, 2)
        self.other_allowances = max(0, derived)
        return self


class Exemptions(BaseModel):
    hra_exempt: float = 0
    lta_exempt: float = 0
    other_exempt: float = 0
    total_exempt: float = 0

    # Fix #6: override LLM-provided total with the sum of components to prevent
    # silent hallucination mismatches (e.g. LLM returns wrong total_exempt).
    @model_validator(mode="after")
    def recompute_total(self) -> "Exemptions":
        self.total_exempt = self.hra_exempt + self.lta_exempt + self.other_exempt
        return self


class Deductions80C(BaseModel):
    pf: float = 0
    ppf: float = 0
    elss: float = 0
    life_insurance: float = 0
    nsc: float = 0
    home_loan_principal: float = 0
    tuition_fees: float = 0
    other: float = 0
    total: float = 0

    # Fix #6: recompute total from components.
    @model_validator(mode="after")
    def recompute_total(self) -> "Deductions80C":
        self.total = (
            self.pf + self.ppf + self.elss + self.life_insurance
            + self.nsc + self.home_loan_principal + self.tuition_fees + self.other
        )
        return self


class OtherDeductions(BaseModel):
    deduction_80d: float = 0       # Health insurance premium
    deduction_80e: float = 0       # Education loan interest
    deduction_80g: float = 0       # Donations
    deduction_80tta: float = 0     # Savings account interest
    nps_80ccd1b: float = 0         # NPS additional contribution
    home_loan_interest_24b: float = 0
    other: float = 0


class TDSDetails(BaseModel):
    tds_deducted: float = 0
    tds_deposited: float = 0
    assessment_year: str = ""


class Form16Data(BaseModel):
    assessment_year: str
    financial_year: str
    employee_name: str
    employee_pan: str
    employer: EmployerDetails
    salary: SalaryBreakdown
    exemptions: Exemptions
    deductions_80c: Deductions80C
    other_deductions: OtherDeductions
    tds: TDSDetails
    professional_tax: float = 0
    standard_deduction: float = 50000
    # Fix #4: removed net_taxable_income — unused; tax engine computes this authoritatively
    raw_text: Optional[str] = None


def merge_form16s(primary: "Form16Data", secondary: "Form16Data") -> "Form16Data":
    """
    Merge two Form 16s from different employers in the same FY (job change scenario).
    Validates PAN and AY match. Salary, exemptions, deductions, and TDS are summed.
    primary.employer is kept as the base employer in the merged record;
    the original secondary is passed separately to generate_itr1 for ScheduleTDS1.
    """
    if primary.employee_pan != secondary.employee_pan:
        raise ValueError(
            f"PAN mismatch: {primary.employee_pan} vs {secondary.employee_pan} — cannot merge different employees"
        )
    if primary.assessment_year != secondary.assessment_year:
        raise ValueError(
            f"Assessment year mismatch: {primary.assessment_year} vs {secondary.assessment_year}"
        )

    return Form16Data(
        assessment_year=primary.assessment_year,
        financial_year=primary.financial_year,
        employee_name=primary.employee_name,
        employee_pan=primary.employee_pan,
        employer=primary.employer,
        salary=SalaryBreakdown(
            basic=primary.salary.basic + secondary.salary.basic,
            hra=primary.salary.hra + secondary.salary.hra,
            lta=primary.salary.lta + secondary.salary.lta,
            special_allowance=primary.salary.special_allowance + secondary.salary.special_allowance,
            other_allowances=0,  # re-derived by model_validator from gross - named
            gross_salary=primary.salary.gross_salary + secondary.salary.gross_salary,
        ),
        exemptions=Exemptions(
            hra_exempt=primary.exemptions.hra_exempt + secondary.exemptions.hra_exempt,
            lta_exempt=primary.exemptions.lta_exempt + secondary.exemptions.lta_exempt,
            other_exempt=primary.exemptions.other_exempt + secondary.exemptions.other_exempt,
        ),
        deductions_80c=Deductions80C(
            pf=primary.deductions_80c.pf + secondary.deductions_80c.pf,
            ppf=primary.deductions_80c.ppf + secondary.deductions_80c.ppf,
            elss=primary.deductions_80c.elss + secondary.deductions_80c.elss,
            life_insurance=primary.deductions_80c.life_insurance + secondary.deductions_80c.life_insurance,
            nsc=primary.deductions_80c.nsc + secondary.deductions_80c.nsc,
            home_loan_principal=primary.deductions_80c.home_loan_principal + secondary.deductions_80c.home_loan_principal,
            tuition_fees=primary.deductions_80c.tuition_fees + secondary.deductions_80c.tuition_fees,
            other=primary.deductions_80c.other + secondary.deductions_80c.other,
        ),
        other_deductions=OtherDeductions(
            deduction_80d=primary.other_deductions.deduction_80d + secondary.other_deductions.deduction_80d,
            deduction_80e=primary.other_deductions.deduction_80e + secondary.other_deductions.deduction_80e,
            deduction_80g=primary.other_deductions.deduction_80g + secondary.other_deductions.deduction_80g,
            deduction_80tta=primary.other_deductions.deduction_80tta + secondary.other_deductions.deduction_80tta,
            nps_80ccd1b=primary.other_deductions.nps_80ccd1b + secondary.other_deductions.nps_80ccd1b,
            home_loan_interest_24b=primary.other_deductions.home_loan_interest_24b + secondary.other_deductions.home_loan_interest_24b,
        ),
        tds=TDSDetails(
            tds_deducted=primary.tds.tds_deducted + secondary.tds.tds_deducted,
            tds_deposited=primary.tds.tds_deposited + secondary.tds.tds_deposited,
        ),
        professional_tax=primary.professional_tax + secondary.professional_tax,
    )
