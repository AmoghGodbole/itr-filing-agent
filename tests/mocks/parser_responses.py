"""
Fixed parser return values for Playwright tests.
Each fixture represents a realistic but minimal document for that scenario.
Claude parser functions are monkeypatched to return these objects so tests
are fast, free, and deterministic.
"""
from engine.models import (
    Form16Data, SalaryBreakdown, Exemptions, Deductions80C,
    OtherDeductions, TDSDetails, EmployerDetails,
)
from engine.models_ais import AISData, AISIncomeEntry
from engine.models_capital_gains import CapitalGainsSummary, EquityGainsSplit, OtherGains, PropertyGains
from engine.models_fo import FOData, FOSegmentPL, FOExpenses


# ── Base Form 16 fixture ───────────────────────────────────────────────────────

FORM16_BASIC = Form16Data(
    assessment_year="AY 2025-26",
    financial_year="FY 2024-25",
    employee_name="Rahul Sharma",
    employee_pan="ABCRS1234F",
    employer=EmployerDetails(name="Acme Corp Pvt Ltd", tan="MUMA12345A"),
    salary=SalaryBreakdown(
        basic=600_000,
        hra=120_000,
        lta=20_000,
        special_allowance=260_000,
        gross_salary=1_000_000,
    ),
    exemptions=Exemptions(hra_exempt=0, lta_exempt=20_000, other_exempt=0, total_exempt=20_000),
    deductions_80c=Deductions80C(pf=72_000, elss=28_000, total=100_000),
    other_deductions=OtherDeductions(deduction_80d=15_000),
    tds=TDSDetails(tds_deducted=60_000, tds_deposited=60_000),
    professional_tax=2_400,
)

FORM16_EMPLOYER2 = Form16Data(
    assessment_year="AY 2025-26",
    financial_year="FY 2024-25",
    employee_name="Rahul Sharma",
    employee_pan="ABCRS1234F",
    employer=EmployerDetails(name="Beta Solutions Ltd", tan="BNGL98765B"),
    salary=SalaryBreakdown(
        basic=300_000, hra=60_000, lta=10_000, special_allowance=130_000,
        gross_salary=500_000,
    ),
    exemptions=Exemptions(),
    deductions_80c=Deductions80C(pf=36_000, total=36_000),
    other_deductions=OtherDeductions(),
    tds=TDSDetails(tds_deducted=25_000, tds_deposited=25_000),
    professional_tax=1_200,
)

FORM16_NO_HRA = Form16Data(
    assessment_year="AY 2025-26",
    financial_year="FY 2024-25",
    employee_name="Priya Nair",
    employee_pan="ABCPN5678G",
    employer=EmployerDetails(name="Startup XYZ", tan="BLRA11111C"),
    salary=SalaryBreakdown(
        basic=500_000, hra=0, lta=0, special_allowance=300_000,
        gross_salary=800_000,
    ),
    exemptions=Exemptions(),
    deductions_80c=Deductions80C(total=80_000),
    other_deductions=OtherDeductions(),
    tds=TDSDetails(tds_deducted=40_000, tds_deposited=40_000),
    professional_tax=2_400,
)

FORM16_SENIOR = Form16Data(
    assessment_year="AY 2025-26",
    financial_year="FY 2024-25",
    employee_name="Suresh Patel",
    employee_pan="ABCSP9012H",
    employer=EmployerDetails(name="Govt of India", tan="DLHI00001G"),
    salary=SalaryBreakdown(
        basic=500_000, hra=0, lta=0, special_allowance=300_000,
        gross_salary=800_000,
    ),
    exemptions=Exemptions(),
    deductions_80c=Deductions80C(total=100_000),
    other_deductions=OtherDeductions(),
    tds=TDSDetails(tds_deducted=30_000, tds_deposited=30_000),
    professional_tax=0,
)

FORM16_HIGH_INCOME = Form16Data(
    assessment_year="AY 2025-26",
    financial_year="FY 2024-25",
    employee_name="Ananya Krishnan",
    employee_pan="ABCAK3456J",
    employer=EmployerDetails(name="BigTech India Pvt Ltd", tan="MUMA99999Z"),
    salary=SalaryBreakdown(
        basic=3_500_000, hra=700_000, lta=50_000, special_allowance=950_000,
        gross_salary=5_200_000,
    ),
    exemptions=Exemptions(hra_exempt=350_000),
    deductions_80c=Deductions80C(pf=150_000, total=150_000),
    other_deductions=OtherDeductions(deduction_80d=25_000),
    tds=TDSDetails(tds_deducted=1_500_000, tds_deposited=1_500_000),
    professional_tax=2_400,
)


# ── AIS fixture ────────────────────────────────────────────────────────────────

AIS_BASIC = AISData(
    taxpayer_name="Rahul Sharma",
    financial_year="FY 2024-25",
    savings_account_interest=[AISIncomeEntry(source_name="HDFC Bank", amount=8_000, tds_deducted=0)],
    deposit_interest=[AISIncomeEntry(source_name="SBI FD", amount=45_000, tds_deducted=4_500)],
    dividends=[AISIncomeEntry(source_name="Infosys", amount=12_000, tds_deducted=0)],
    total_savings_interest=8_000,
    total_deposit_interest=45_000,
    total_interest=53_000,
    total_dividends=12_000,
    total_tds_from_ais=4_500,
)


# ── Capital gains fixture ──────────────────────────────────────────────────────

CG_EQUITY_BASIC = CapitalGainsSummary(
    equity=EquityGainsSplit(
        stcg_pre_jul23=30_000,
        stcg_post_jul23=80_000,
        ltcg_pre_jul23=50_000,
        ltcg_post_jul23=200_000,
    ),
    tds_on_gains=0,
)

CG_MULTI_BROKER = CapitalGainsSummary(
    equity=EquityGainsSplit(
        stcg_post_jul23=150_000,
        ltcg_post_jul23=300_000,
    ),
    other=OtherGains(ltcg_125pct_without_indexation=100_000),
    tds_on_gains=0,
)


# ── F&O fixture ────────────────────────────────────────────────────────────────

FO_BASIC = FOData(
    segments=[
        FOSegmentPL(segment="Equity Futures", gross_profit=400_000, gross_loss=200_000),
        FOSegmentPL(segment="Equity Options", gross_profit=100_000, gross_loss=80_000),
    ],
    expenses=FOExpenses(brokerage=5_000, stt=3_000, exchange_fees=2_000),
    tds_on_fo=0,
)
