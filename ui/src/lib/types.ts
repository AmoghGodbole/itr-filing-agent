export interface Employer { name: string; tan: string; pan: string | null; address: string | null }
export interface Salary { basic: number; hra: number; lta: number; special_allowance: number; other_allowances: number; gross_salary: number }
export interface Exemptions { hra_exempt: number; lta_exempt: number; other_exempt: number; total_exempt: number }
export interface Deductions80C { pf: number; ppf: number; elss: number; life_insurance: number; nsc: number; home_loan_principal: number; tuition_fees: number; other: number; total: number }
export interface OtherDeductions { deduction_80d: number; deduction_80e: number; deduction_80g: number; deduction_80tta: number; nps_80ccd1b: number; home_loan_interest_24b: number; other: number }
export interface TDS { tds_deducted: number; tds_deposited: number }

export interface Form16Data {
  assessment_year: string; financial_year: string
  employee_name: string; employee_pan: string
  employer: Employer; salary: Salary; exemptions: Exemptions
  deductions_80c: Deductions80C; other_deductions: OtherDeductions
  tds: TDS; professional_tax: number
}

export interface AISIncomeEntry { source_name: string; amount: number; tds_deducted: number }
export interface AISData {
  taxpayer_name: string; financial_year: string
  savings_account_interest: AISIncomeEntry[]; deposit_interest: AISIncomeEntry[]; dividends: AISIncomeEntry[]
  total_interest: number; total_dividends: number; total_tds_from_ais: number
}

export interface Form26ASEntry { tan: string; deductor_name: string; nature_of_payment: string; amount_paid: number; tds_deducted: number }
export interface Form26ASData {
  financial_year: string; part_a: Form26ASEntry[]; part_c: Form26ASEntry[]
  salary_tds: number; non_salary_tds: number; tds_mismatch: boolean; form16_tds: number
}

export interface EquityGains { stcg_pre_jul23: number; stcg_post_jul23: number; ltcg_pre_jul23: number; ltcg_post_jul23: number }
export interface OtherGains { stcg_at_slab: number; ltcg_20pct_with_indexation: number; ltcg_125pct_without_indexation: number }
export interface PropertyGains { stcg: number; ltcg_with_indexation: number; ltcg_without_indexation: number }
export interface CapitalGainsData {
  equity: EquityGains; other: OtherGains; property: PropertyGains; tds_on_gains: number
}

export interface FOSegment { segment: string; gross_profit: number; gross_loss: number; net_pl: number; turnover: number }
export interface FOExpenses { brokerage: number; stt: number; exchange_fees: number; dp_charges: number; internet_software: number; advisory_fees: number; depreciation: number; others: number }
export interface CarryForwardLoss { assessment_year: string; loss_amount: number }
export interface FOData {
  segments: FOSegment[]; expenses: FOExpenses; carry_forward_losses: CarryForwardLoss[]; tds_on_fo: number
}

export interface ParseResponse {
  form16: Form16Data; form16_2: Form16Data | null; form26as: Form26ASData | null
  ais: AISData | null; capital_gains: CapitalGainsData | null; fo_data: FOData | null
}

export interface CapitalGainsTax {
  exempt_112a_pre_jul23: number; exempt_112a_post_jul23: number
  taxable_stcg_111a_pre: number; taxable_stcg_111a_post: number
  taxable_ltcg_112a_pre: number; taxable_ltcg_112a_post: number
  taxable_ltcg_20pct: number; taxable_ltcg_125pct: number
  stcg_for_slab_income: number; total_tax_at_special_rates: number
}

export interface RegimeResult {
  regime: string; gross_income: number; taxable_income: number
  hra_exemption_claimed: number; other_sources_income: number; chapter_via_deductions: number
  tax_payable: number; tds_deducted: number; refund_or_payable: number
  tax_before_cess: number; surcharge: number; cess: number; tax_after_cess: number; rebate_87a: number
  home_loan_interest_claimed: number
  hp_income: number
  deduction_80d_parents_claimed: number
  deduction_80gg_claimed: number
  deduction_80eea_claimed: number
  family_pension_deduction_claimed: number
  capital_gains_tax: CapitalGainsTax | null
}

export interface ImmovableProperty { description: string; address: string; city: string; state: string; pin_code: string; value: number }
export interface MovableAssets { jewellery: number; paintings_collections: number; bullion: number; vehicles: number; others: number }
export interface FinancialAssets { bank_balance: number; shares_securities: number; insurance_surrender_value: number; loans_given: number; cash_in_hand: number; others: number }
export interface Liabilities { loan_from_banks: number; loan_from_others: number; others: number }
export interface ScheduleALData {
  immovable_properties: ImmovableProperty[]; movable: MovableAssets; financial: FinancialAssets; liabilities: Liabilities
}

export interface GenerateResponse {
  old_regime: RegimeResult; new_regime: RegimeResult
  recommended_regime: string; savings: number; is_itr2: boolean; is_itr3: boolean; itr_json: Record<string, unknown>
}
