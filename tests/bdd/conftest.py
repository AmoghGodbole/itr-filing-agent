"""Shared fixtures for BDD tests."""
import pytest
from engine.models import (
    Form16Data, SalaryBreakdown, Exemptions, Deductions80C,
    OtherDeductions, TDSDetails, EmployerDetails,
)
from engine.models_ais import AISData, AISIncomeEntry


def make_form16(
    gross_salary: float = 1_000_000,
    tds: float = 60_000,
    basic: float = 0,
    hra: float = 0,
    hra_exempt: float = 0,
    home_loan_interest_24b: float = 0,
    deductions_80c_total: float = 0,
    deduction_80d: float = 0,
    pan: str = "ABCDE1234F",
    assessment_year: str = "AY 2025-26",
) -> Form16Data:
    if basic == 0:
        basic = gross_salary * 0.5
    return Form16Data(
        assessment_year=assessment_year,
        financial_year="FY 2024-25",
        employee_name="Test Taxpayer",
        employee_pan=pan,
        employer=EmployerDetails(name="Test Employer", tan="MUMA00000A"),
        salary=SalaryBreakdown(
            basic=basic,
            hra=hra,
            lta=0,
            special_allowance=gross_salary - basic - hra,
            gross_salary=gross_salary,
        ),
        exemptions=Exemptions(hra_exempt=hra_exempt),
        deductions_80c=Deductions80C(total=deductions_80c_total),
        other_deductions=OtherDeductions(
            deduction_80d=deduction_80d,
            home_loan_interest_24b=home_loan_interest_24b,
        ),
        tds=TDSDetails(tds_deducted=tds, tds_deposited=tds),
        professional_tax=0,
    )


def make_ais(
    savings_interest: float = 0,
    fd_interest: float = 0,
    dividends: float = 0,
) -> AISData:
    savings = [AISIncomeEntry(source_name="Test Bank", amount=savings_interest, tds_deducted=0)] if savings_interest else []
    deposits = [AISIncomeEntry(source_name="Test FD", amount=fd_interest, tds_deducted=0)] if fd_interest else []
    divs = [AISIncomeEntry(source_name="Test MF", amount=dividends, tds_deducted=0)] if dividends else []
    return AISData(
        taxpayer_name="Test Taxpayer",
        financial_year="FY 2024-25",
        savings_account_interest=savings,
        deposit_interest=deposits,
        dividends=divs,
        total_savings_interest=savings_interest,
        total_deposit_interest=fd_interest,
        total_interest=savings_interest + fd_interest,
        total_dividends=dividends,
        total_tds_from_ais=0,
    )
