"""Request and response schemas for the API."""

from pydantic import BaseModel
from typing import Optional


# ── Parsed data returned after upload step ──────────────────────────────────

class EmployerOut(BaseModel):
    name: str
    tan: str
    pan: Optional[str]
    address: Optional[str]

class SalaryOut(BaseModel):
    basic: float
    hra: float
    lta: float
    special_allowance: float
    other_allowances: float
    gross_salary: float

class ExemptionsOut(BaseModel):
    hra_exempt: float
    lta_exempt: float
    other_exempt: float
    total_exempt: float

class Deductions80COut(BaseModel):
    pf: float
    ppf: float
    elss: float
    life_insurance: float
    nsc: float
    home_loan_principal: float
    tuition_fees: float
    other: float
    total: float

class OtherDeductionsOut(BaseModel):
    deduction_80d: float
    deduction_80e: float
    deduction_80g: float
    deduction_80tta: float
    nps_80ccd1b: float
    home_loan_interest_24b: float
    other: float

class TDSOut(BaseModel):
    tds_deducted: float
    tds_deposited: float

class Form16Out(BaseModel):
    assessment_year: str
    financial_year: str
    employee_name: str
    employee_pan: str
    employer: EmployerOut
    salary: SalaryOut
    exemptions: ExemptionsOut
    deductions_80c: Deductions80COut
    other_deductions: OtherDeductionsOut
    tds: TDSOut
    professional_tax: float

class AISIncomeOut(BaseModel):
    source_name: str
    amount: float
    tds_deducted: float

class AISOut(BaseModel):
    taxpayer_name: str
    financial_year: str
    savings_account_interest: list[AISIncomeOut]
    deposit_interest: list[AISIncomeOut]
    dividends: list[AISIncomeOut]
    total_interest: float
    total_dividends: float
    total_tds_from_ais: float

class Form26ASEntryOut(BaseModel):
    tan: str
    deductor_name: str
    nature_of_payment: str
    amount_paid: float
    tds_deducted: float

class Form26ASOut(BaseModel):
    financial_year: str
    part_a: list[Form26ASEntryOut]
    part_c: list[Form26ASEntryOut]
    salary_tds: float
    non_salary_tds: float
    tds_mismatch: bool
    form16_tds: float

class EquityGainsOut(BaseModel):
    stcg_pre_jul23: float
    stcg_post_jul23: float
    ltcg_pre_jul23: float
    ltcg_post_jul23: float

class OtherGainsOut(BaseModel):
    stcg_at_slab: float
    ltcg_20pct_with_indexation: float
    ltcg_125pct_without_indexation: float

class PropertyGainsOut(BaseModel):
    stcg: float
    ltcg_with_indexation: float
    ltcg_without_indexation: float

class CapitalGainsOut(BaseModel):
    equity: EquityGainsOut
    other: OtherGainsOut
    property: PropertyGainsOut
    tds_on_gains: float

class ParseResponse(BaseModel):
    form16: Form16Out
    form16_2: Optional[Form16Out] = None      # Second employer Form 16 (job change mid-year)
    form26as: Optional[Form26ASOut] = None
    ais: Optional[AISOut] = None
    capital_gains: Optional[CapitalGainsOut] = None  # From broker P&L PDF
    fo_data: Optional[FODataIn] = None               # From broker F&O P&L PDF


# ── Schedule AL schemas ──────────────────────────────────────────────────────

class ImmovablePropertyIn(BaseModel):
    description: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    pin_code: str = ""
    value: float = 0

class MovableAssetsIn(BaseModel):
    jewellery: float = 0
    paintings_collections: float = 0
    bullion: float = 0
    vehicles: float = 0
    others: float = 0

class FinancialAssetsIn(BaseModel):
    bank_balance: float = 0
    shares_securities: float = 0
    insurance_surrender_value: float = 0
    loans_given: float = 0
    cash_in_hand: float = 0
    others: float = 0

class LiabilitiesIn(BaseModel):
    loan_from_banks: float = 0
    loan_from_others: float = 0
    others: float = 0

class ScheduleALIn(BaseModel):
    immovable_properties: list[ImmovablePropertyIn] = []
    movable: MovableAssetsIn = MovableAssetsIn()
    financial: FinancialAssetsIn = FinancialAssetsIn()
    liabilities: LiabilitiesIn = LiabilitiesIn()


# ── F&O schemas ──────────────────────────────────────────────────────────────

class FOSegmentIn(BaseModel):
    segment: str = ""
    gross_profit: float = 0
    gross_loss: float = 0
    net_pl: Optional[float] = None   # None → derived by FOSegmentPL validator
    turnover: Optional[float] = None # None → derived by FOSegmentPL validator

class FOExpensesIn(BaseModel):
    brokerage: float = 0
    stt: float = 0
    exchange_fees: float = 0
    dp_charges: float = 0
    internet_software: float = 0
    advisory_fees: float = 0
    depreciation: float = 0
    others: float = 0

class CarryForwardLossIn(BaseModel):
    assessment_year: str
    loss_amount: float

class FODataIn(BaseModel):
    segments: list[FOSegmentIn] = []
    expenses: FOExpensesIn = FOExpensesIn()
    carry_forward_losses: list[CarryForwardLossIn] = []
    tds_on_fo: float = 0


# ── Generate request (sent after CA reviews parsed data) ────────────────────

class BankAccountIn(BaseModel):
    account_number: str
    ifsc: str
    account_type: str   # "Savings" | "Current"
    bank_name: str

class GenerateRequest(BaseModel):
    # Overrides to parsed Form 16 data (CA can correct any wrong values)
    form16: Form16Out
    form16_2: Optional[Form16Out] = None   # Second employer Form 16; merged in engine before computation
    ais: Optional[AISOut] = None
    capital_gains: Optional[CapitalGainsOut] = None   # Triggers ITR-2 generation when present
    fo_data: Optional[FODataIn] = None                # Triggers ITR-3 generation when present
    schedule_al: Optional[ScheduleALIn] = None        # Required in ITR-2/3 when total income > ₹50L

    # Additional inputs not in Form 16
    hra_monthly_rent: float = 0
    hra_city: str = ""
    parents_insurance_premium: float = 0
    parents_senior: bool = False
    home_loan_interest_certificate: float = 0
    rental_annual_rent: float = 0
    rental_municipal_taxes: float = 0
    rental_home_loan_interest: float = 0
    family_pension: float = 0          # Gross family pension; Sec 57(iia) deduction computed in engine
    home_loan_80eea: float = 0         # Section 80EEA eligible interest (affordable housing, first-time buyer)

    # Filing metadata
    bank_account: BankAccountIn
    date_of_birth: str = ""   # DD/MM/YYYY — used for senior/super-senior slab selection
    aadhaar: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None


# ── Tax computation result ───────────────────────────────────────────────────

class CapitalGainsTaxOut(BaseModel):
    exempt_112a_pre_jul23: float
    exempt_112a_post_jul23: float
    taxable_stcg_111a_pre: float
    taxable_stcg_111a_post: float
    taxable_ltcg_112a_pre: float
    taxable_ltcg_112a_post: float
    taxable_ltcg_20pct: float
    taxable_ltcg_125pct: float
    stcg_for_slab_income: float
    total_tax_at_special_rates: float

class RegimeOut(BaseModel):
    regime: str
    gross_income: float
    taxable_income: float
    hra_exemption_claimed: float
    other_sources_income: float
    chapter_via_deductions: float
    home_loan_interest_claimed: float
    hp_income: float
    deduction_80d_parents_claimed: float
    deduction_80gg_claimed: float
    deduction_80eea_claimed: float
    family_pension_deduction_claimed: float
    tax_before_cess: float
    surcharge: float
    cess: float
    tax_after_cess: float
    rebate_87a: float
    tax_payable: float
    tds_deducted: float
    refund_or_payable: float
    capital_gains_tax: Optional[CapitalGainsTaxOut] = None

class GenerateResponse(BaseModel):
    old_regime: RegimeOut
    new_regime: RegimeOut
    recommended_regime: str
    savings: float
    is_itr2: bool
    is_itr3: bool
    itr_json: dict
