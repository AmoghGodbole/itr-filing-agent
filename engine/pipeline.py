"""End-to-end pipeline: Form 16 PDF + AIS JSON [+ broker P&L PDF] → ITR-1 or ITR-2 JSON."""

import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from engine.computation.tax_engine import compute_optimal_regime
from engine.itr_generator.itr1_generator import BankAccount, generate_itr1
from engine.itr_generator.itr2_generator import generate_itr2
from engine.itr_generator.itr3_generator import generate_itr3
from engine.models import merge_form16s
from engine.models_ais import AISData
from engine.models_capital_gains import CapitalGainsSummary
from engine.models_fo import FOData
from engine.parsers.ais_parser import parse_ais
from engine.parsers.capital_gains_parser import parse_capital_gains
from engine.parsers.fo_parser import parse_fo
from engine.parsers.form16_parser import parse_form16
from engine.parsers.form26as_parser import parse_form26as


def run_pipeline(
    form16_pdf: str | Path,
    bank_account: BankAccount,
    form16_pdf_2: Optional[str | Path] = None,
    ais_json: Optional[str | Path] = None,
    form26as_path: Optional[str | Path] = None,
    broker_pl_pdf: Optional[str | Path] = None,
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
    fo_pdf: Optional[str | Path] = None,
    aadhaar: Optional[str] = None,
    mobile: Optional[str] = None,
    email: Optional[str] = None,
    output_path: Optional[str | Path] = None,
) -> dict:
    print("Step 1/4: Parsing Form 16...")
    form16_primary = parse_form16(form16_pdf)
    print(f"  Employee : {form16_primary.employee_name} | PAN: {form16_primary.employee_pan}")
    print(f"  Employer : {form16_primary.employer.name}")
    print(f"  Gross    : ₹{form16_primary.salary.gross_salary:,.2f}")
    print(f"  TDS (F16): ₹{form16_primary.tds.tds_deducted:,.2f}")

    second_form16 = None
    if form16_pdf_2:
        print("  Parsing Form 16 (Employer 2)...")
        second_form16 = parse_form16(form16_pdf_2)
        print(f"  Employer 2: {second_form16.employer.name} | Gross: ₹{second_form16.salary.gross_salary:,.2f} | TDS: ₹{second_form16.tds.tds_deducted:,.2f}")
        form16 = merge_form16s(form16_primary, second_form16)
        print(f"  Merged gross: ₹{form16.salary.gross_salary:,.2f} | Merged TDS: ₹{form16.tds.tds_deducted:,.2f}")
    else:
        form16 = form16_primary

    ais: Optional[AISData] = None
    if ais_json:
        print("\nStep 2/4: Parsing AIS...")
        ais = parse_ais(ais_json)
        print(f"  Savings interest : ₹{ais.total_savings_interest:,.2f}")
        print(f"  FD/deposit int.  : ₹{ais.total_deposit_interest:,.2f}")
        print(f"  Dividends        : ₹{ais.total_dividends:,.2f}")
        print(f"  TDS from AIS     : ₹{ais.total_tds_from_ais:,.2f}")
    else:
        print("\nStep 2/4: AIS not provided — skipping (income from other sources will be 0)")

    if form26as_path:
        print("\nStep 2b: Parsing Form 26AS for TDS cross-check...")
        f26 = parse_form26as(form26as_path)
        mismatch = f26.tds_mismatch_with_form16(form16.tds.tds_deducted)
        if mismatch:
            print(f"  TDS MISMATCH: Form 16 shows Rs.{form16.tds.tds_deducted:,.2f}, "
                  f"Form 26AS shows Rs.{f26.get_salary_tds():,.2f} -- review before filing")
        else:
            print(f"  TDS cross-check passed")

    if broker_pl_pdf and capital_gains is None:
        print("\nStep 2c: Parsing broker P&L for capital gains...")
        capital_gains = parse_capital_gains(broker_pl_pdf)
        cg = capital_gains
        print(f"  Equity STCG (pre/post Jul 23): Rs.{cg.equity.stcg_pre_jul23:,.0f} / Rs.{cg.equity.stcg_post_jul23:,.0f}")
        print(f"  Equity LTCG (pre/post Jul 23): Rs.{cg.equity.ltcg_pre_jul23:,.0f} / Rs.{cg.equity.ltcg_post_jul23:,.0f}")
        if cg.other.stcg_at_slab or cg.other.ltcg_20pct_with_indexation or cg.other.ltcg_125pct_without_indexation:
            print(f"  Other STCG/LTCG: Rs.{cg.other.stcg_at_slab:,.0f} / Rs.{cg.other.ltcg_20pct_with_indexation + cg.other.ltcg_125pct_without_indexation:,.0f}")
    elif capital_gains:
        print("\nStep 2c: Capital gains provided directly (skipping broker PDF parsing)")

    if hra_monthly_rent > 0:
        print(f"\n  HRA/80GG inputs: ₹{hra_monthly_rent:,.0f}/month rent | City: {hra_city or 'not specified'}")
    if parents_insurance_premium > 0:
        print(f"  80D parents: ₹{parents_insurance_premium:,.0f} | Senior: {parents_senior}")
    if home_loan_interest_cert > 0:
        print(f"  Home loan cert: ₹{home_loan_interest_cert:,.0f}")
    if date_of_birth:
        print(f"  Date of birth: {date_of_birth}")

    print("\nStep 3/4: Computing tax (old vs new regime)...")
    if rental_annual_rent > 0:
        print(f"  Rental income: ₹{rental_annual_rent:,.0f}/yr rent | Municipal taxes: ₹{rental_municipal_taxes:,.0f} | HL interest: ₹{rental_home_loan_interest:,.0f}")

    if fo_pdf and fo_data is None:
        print("\nStep 2d: Parsing F&O P&L for business income...")
        fo_data = parse_fo(fo_pdf)
        print(f"  Segments: {len(fo_data.segments)} | Turnover: Rs.{fo_data.total_turnover:,.0f} | Net P&L: Rs.{fo_data.total_gross_pl:,.0f}")
        if fo_data.requires_tax_audit:
            print("  TAX AUDIT (Sec 44AB) may be required -- review with CA")

    computation = compute_optimal_regime(
        form16, ais, hra_monthly_rent, hra_city,
        parents_insurance_premium, parents_senior, home_loan_interest_cert,
        date_of_birth, rental_annual_rent, rental_municipal_taxes, rental_home_loan_interest,
        family_pension, home_loan_80eea, capital_gains, fo_data,
    )
    old = computation.old_regime
    new = computation.new_regime

    print(f"  Old Regime -> Taxable: Rs.{old.taxable_income:,.0f} | Tax: Rs.{old.tax_payable:,.0f} | "
          f"{'Refund' if old.refund_or_payable >= 0 else 'Payable'}: Rs.{abs(old.refund_or_payable):,.0f}")
    print(f"  New Regime -> Taxable: Rs.{new.taxable_income:,.0f} | Tax: Rs.{new.tax_payable:,.0f} | "
          f"{'Refund' if new.refund_or_payable >= 0 else 'Payable'}: Rs.{abs(new.refund_or_payable):,.0f}")
    print(f"  Recommended: {computation.recommended_regime} (saves Rs.{computation.savings:,.0f})")

    if old.hra_exemption_claimed > 0:
        print(f"  HRA exemption applied: Rs.{old.hra_exemption_claimed:,.0f}")
    if old.other_sources_income > 0:
        print(f"  Other sources income (from AIS): Rs.{old.other_sources_income:,.0f}")
    if old.capital_gains_result:
        cg_r = old.capital_gains_result
        print(f"  Capital gains tax (special rates): Rs.{cg_r.total_tax_at_special_rates:,.0f}")

    form_name = "ITR-2" if computation.is_itr2 else "ITR-1"
    print(f"\nStep 4/4: Generating {form_name} JSON...")

    if computation.is_itr3 and fo_data:
        itr_json = generate_itr3(form16, computation, bank_account, fo_data, capital_gains, aadhaar, mobile, email, date_of_birth or None, second_form16)
    elif computation.is_itr2 and capital_gains:
        itr_json = generate_itr2(form16, computation, bank_account, capital_gains, aadhaar, mobile, email, date_of_birth or None, second_form16)
    else:
        itr_json = generate_itr1(form16, computation, bank_account, aadhaar, mobile, email, date_of_birth or None, second_form16)

    if output_path:
        output_path = Path(output_path)
        output_path.write_text(json.dumps(itr_json, indent=2))
        print(f"  Saved to: {output_path}")

    print(f"\nDone. {form_name} JSON ready for upload.")
    return itr_json
