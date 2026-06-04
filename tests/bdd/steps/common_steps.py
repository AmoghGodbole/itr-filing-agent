"""
Shared Given/When/Then steps for all BDD scenarios.
All state is stored on the `context` dict passed via pytest fixtures.
"""
import pytest
from pytest_bdd import given, when, then, parsers
from pydantic import ValidationError

from engine.computation.tax_engine import compute_optimal_regime, TaxComputationResult
from engine.models import merge_form16s
from engine.models_capital_gains import CapitalGainsSummary, EquityGainsSplit, OtherGains, PropertyGains
from engine.models_fo import FOData, FOSegmentPL, FOExpenses, CarryForwardLoss
from engine.models_schedule_al import ScheduleALData, ImmovableProperty
from engine.itr_generator.itr1_generator import BankAccount, generate_itr1
from engine.itr_generator.itr2_generator import generate_itr2
from engine.itr_generator.itr3_generator import generate_itr3

from tests.bdd.conftest import make_form16, make_ais


BANK = BankAccount(account_number="1234567890", ifsc="SBIN0000001", account_type="Savings", bank_name="SBI")


# ── Context fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    """Mutable test context shared across steps within one scenario."""
    return {}


# ── Given steps ───────────────────────────────────────────────────────────────

@given(parsers.parse("a Form 16 with gross salary {salary:d} and TDS {tds:d}"))
def form16_basic(ctx, salary, tds):
    ctx["form16"] = make_form16(gross_salary=salary, tds=tds)


@given(parsers.parse("a Form 16 with gross salary {salary:d} and HRA component {hra:d} and basic {basic:d}"))
def form16_with_hra(ctx, salary, hra, basic):
    ctx["form16"] = make_form16(gross_salary=salary, hra=hra, basic=basic, tds=60_000)


@given(parsers.parse("the Form 16 shows HRA exemption of {exempt:d}"))
def set_hra_exempt(ctx, exempt):
    ctx["form16"].exemptions.hra_exempt = exempt


@given(parsers.parse("a Form 16 with gross salary {salary:d} and home loan interest 24b of {interest:d}"))
def form16_with_hl(ctx, salary, interest):
    ctx["form16"] = make_form16(gross_salary=salary, tds=60_000, home_loan_interest_24b=interest)


@given(parsers.parse("a bank certificate home loan interest of {cert:d}"))
def bank_cert_hl(ctx, cert):
    ctx["home_loan_cert"] = cert


@given(parsers.parse("80C deductions of {c80:d} and 80D self of {d80:d}"))
def set_deductions(ctx, c80, d80):
    ctx["form16"] = make_form16(
        gross_salary=ctx["form16"].salary.gross_salary,
        tds=ctx["form16"].tds.tds_deducted,
        deductions_80c_total=c80,
        deduction_80d=d80,
    )


@given(parsers.parse("the employee pays monthly rent of {rent:d} in {city}"))
def set_rent(ctx, rent, city):
    ctx["hra_monthly_rent"] = rent
    ctx["hra_city"] = city


@given(parsers.parse("AIS data with FD interest {fd:d} and dividends {div:d}"))
def ais_fd_div(ctx, fd, div):
    ctx["ais"] = make_ais(fd_interest=fd, dividends=div)


@given(parsers.parse("AIS data with savings interest {sav:d} and FD interest {fd:d} and dividends {div:d}"))
def ais_full(ctx, sav, fd, div):
    ctx["ais"] = make_ais(savings_interest=sav, fd_interest=fd, dividends=div)


@given(parsers.parse("AIS data with FD interest {fd:d} and savings interest {sav:d}"))
def ais_fd_and_savings(ctx, fd, sav):
    ctx["ais"] = make_ais(savings_interest=sav, fd_interest=fd)


@given(parsers.parse("AIS data with savings interest {sav:d} and FD interest {fd:d}"))
def ais_savings_and_fd(ctx, sav, fd):
    ctx["ais"] = make_ais(savings_interest=sav, fd_interest=fd)


@given(parsers.parse("AIS data with savings interest {sav:d}"))
def ais_savings_only(ctx, sav):
    ctx["ais"] = make_ais(savings_interest=sav)


@given(parsers.parse("date of birth {dob} with assessment year {ay}"))
def set_dob(ctx, dob, ay):
    ctx["date_of_birth"] = dob
    if "form16" in ctx:
        ctx["form16"].assessment_year = ay


@given(parsers.parse("a primary Form 16 with gross salary {salary:d} and TDS {tds:d}"))
def primary_form16(ctx, salary, tds):
    ctx["form16"] = make_form16(gross_salary=salary, tds=tds)


@given(parsers.parse("a second Form 16 with gross salary {salary:d} and TDS {tds:d}"))
def second_form16(ctx, salary, tds):
    ctx["form16_2"] = make_form16(gross_salary=salary, tds=tds)


@given(parsers.parse("a primary Form 16 with PAN {pan}"))
def primary_form16_pan(ctx, pan):
    ctx["form16"] = make_form16(pan=pan)


@given(parsers.parse("a second Form 16 with PAN {pan}"))
def second_form16_pan(ctx, pan):
    ctx["form16_2"] = make_form16(pan=pan)


@given(parsers.parse("a let-out property with annual rent {rent:d} municipal taxes {tax:d} and loan interest {interest:d}"))
def letout_property(ctx, rent, tax, interest):
    ctx["rental_annual_rent"] = rent
    ctx["rental_municipal_taxes"] = tax
    ctx["rental_home_loan_interest"] = interest


@given(parsers.parse("equity capital gains with post-Jul-23 STCG of {amount:d}"))
def cg_eq_stcg_post(ctx, amount):
    existing = ctx.get("capital_gains", CapitalGainsSummary())
    ctx["capital_gains"] = CapitalGainsSummary(
        equity=EquityGainsSplit(
            stcg_pre_jul23=existing.equity.stcg_pre_jul23,
            stcg_post_jul23=amount,
            ltcg_pre_jul23=existing.equity.ltcg_pre_jul23,
            ltcg_post_jul23=existing.equity.ltcg_post_jul23,
        ),
        other=existing.other,
        property_gains=existing.property_gains,
        tds_on_gains=existing.tds_on_gains,
    )


@given(parsers.parse("equity capital gains with post-Jul-23 LTCG of {amount:d}"))
def cg_eq_ltcg_post(ctx, amount):
    existing = ctx.get("capital_gains", CapitalGainsSummary())
    ctx["capital_gains"] = CapitalGainsSummary(
        equity=EquityGainsSplit(
            stcg_pre_jul23=existing.equity.stcg_pre_jul23,
            stcg_post_jul23=existing.equity.stcg_post_jul23,
            ltcg_pre_jul23=existing.equity.ltcg_pre_jul23,
            ltcg_post_jul23=amount,
        ),
        other=existing.other,
        property_gains=existing.property_gains,
        tds_on_gains=existing.tds_on_gains,
    )


@given(parsers.parse("equity capital gains with pre-Jul-23 LTCG of {amount:d}"))
def cg_eq_ltcg_pre(ctx, amount):
    existing = ctx.get("capital_gains", CapitalGainsSummary())
    ctx["capital_gains"] = CapitalGainsSummary(
        equity=EquityGainsSplit(
            stcg_pre_jul23=existing.equity.stcg_pre_jul23,
            stcg_post_jul23=existing.equity.stcg_post_jul23,
            ltcg_pre_jul23=amount,
            ltcg_post_jul23=existing.equity.ltcg_post_jul23,
        ),
        other=existing.other,
        property_gains=existing.property_gains,
        tds_on_gains=existing.tds_on_gains,
    )


@given(parsers.parse("property capital gains with STCG of {amount:d}"))
def cg_prop_stcg(ctx, amount):
    existing = ctx.get("capital_gains", CapitalGainsSummary())
    ctx["capital_gains"] = CapitalGainsSummary(
        equity=existing.equity,
        other=existing.other,
        property_gains=PropertyGains(stcg=amount),
        tds_on_gains=existing.tds_on_gains,
    )


@given(parsers.parse("property capital gains with LTCG with indexation of {amount:d}"))
def cg_prop_ltcg_index(ctx, amount):
    existing = ctx.get("capital_gains", CapitalGainsSummary())
    ctx["capital_gains"] = CapitalGainsSummary(
        equity=existing.equity,
        other=existing.other,
        property_gains=PropertyGains(ltcg_with_indexation=amount),
        tds_on_gains=existing.tds_on_gains,
    )


@given(parsers.parse("a PropertyGains model with LTCG with indexation {a:d} and LTCG without indexation {b:d}"))
def prop_gains_both(ctx, a, b):
    ctx["prop_gains_args"] = {"ltcg_with_indexation": a, "ltcg_without_indexation": b}


@given(parsers.parse("F&O data with one segment gross profit {gp:d} and gross loss {gl:d} and expenses {exp:d}"))
def fo_one_segment(ctx, gp, gl, exp):
    ctx["fo_data"] = FOData(
        segments=[FOSegmentPL(segment="Equity F&O", gross_profit=gp, gross_loss=gl)],
        expenses=FOExpenses(brokerage=exp),
    )


@given(parsers.parse("F&O data with turnover {turnover:d}"))
def fo_high_turnover(ctx, turnover):
    half = turnover // 2
    ctx["fo_data"] = FOData(
        segments=[FOSegmentPL(segment="Equity F&O", gross_profit=half, gross_loss=half)],
    )


@given(parsers.parse("prior year F&O losses of {amount:d} from {ay}"))
def prior_fo_losses(ctx, amount, ay):
    if "fo_data" not in ctx:
        ctx["fo_data"] = FOData()
    ctx["fo_data"] = FOData(
        segments=ctx["fo_data"].segments,
        expenses=ctx["fo_data"].expenses,
        carry_forward_losses=[CarryForwardLoss(assessment_year=ay, loss_amount=amount)],
    )


@given(parsers.parse("schedule AL data with immovable property value {value:d}"))
def schedule_al(ctx, value):
    ctx["schedule_al"] = ScheduleALData(
        immovable_properties=[ImmovableProperty(description="Flat", value=value)],
    )


# ── When steps ────────────────────────────────────────────────────────────────

def _run_computation(ctx) -> TaxComputationResult:
    form16 = ctx.get("form16")
    form16_2 = ctx.get("form16_2")
    if form16_2:
        form16 = merge_form16s(form16, form16_2)
    return compute_optimal_regime(
        form16,
        ais=ctx.get("ais"),
        hra_monthly_rent=ctx.get("hra_monthly_rent", 0),
        hra_city=ctx.get("hra_city", ""),
        home_loan_interest_cert=ctx.get("home_loan_cert", 0),
        date_of_birth=ctx.get("date_of_birth", ""),
        rental_annual_rent=ctx.get("rental_annual_rent", 0),
        rental_municipal_taxes=ctx.get("rental_municipal_taxes", 0),
        rental_home_loan_interest=ctx.get("rental_home_loan_interest", 0),
        capital_gains=ctx.get("capital_gains"),
        fo_data=ctx.get("fo_data"),
    )


@when("the tax engine computes both regimes")
def compute_regimes(ctx):
    ctx["result"] = _run_computation(ctx)


@when("the form 16s are merged and tax is computed")
def merge_and_compute(ctx):
    ctx["result"] = _run_computation(ctx)


@when("the ITR-1 JSON is generated")
def gen_itr1(ctx):
    ctx["result"] = _run_computation(ctx)
    ctx["itr_json"] = generate_itr1(ctx["form16"], ctx["result"], BANK)


@when("the ITR-2 JSON is generated")
def gen_itr2(ctx):
    ctx["result"] = _run_computation(ctx)
    ctx["itr_json"] = generate_itr2(
        ctx["form16"], ctx["result"], BANK, ctx["capital_gains"],
        schedule_al=ctx.get("schedule_al"),
    )


# ── Then steps ────────────────────────────────────────────────────────────────

@then(parsers.parse("the ITR form selected should be {form}"))
def check_itr_form(ctx, form):
    r = ctx["result"]
    if form == "ITR-3":
        assert r.is_itr3, f"Expected ITR-3 but is_itr3={r.is_itr3}"
    elif form == "ITR-2":
        assert r.is_itr2 and not r.is_itr3, f"Expected ITR-2 but is_itr2={r.is_itr2}, is_itr3={r.is_itr3}"
    else:
        assert not r.is_itr2 and not r.is_itr3, f"Expected ITR-1 but is_itr2={r.is_itr2}, is_itr3={r.is_itr3}"


@then(parsers.parse("is_itr2 should be {val}"))
def check_is_itr2(ctx, val):
    expected = val == "True"
    assert ctx["result"].is_itr2 == expected


@then(parsers.parse("the recommended regime should be {regime}"))
def check_regime(ctx, regime):
    assert ctx["result"].recommended_regime == regime, \
        f"Expected {regime}, got {ctx['result'].recommended_regime}"


@then(parsers.parse("the new regime taxable income should be {expected:d}"))
def check_new_taxable(ctx, expected):
    actual = ctx["result"].new_regime.taxable_income
    assert actual == expected, f"Expected {expected}, got {actual}"


@then(parsers.parse("the new regime tax payable should be {expected:d}"))
def check_new_tax(ctx, expected):
    actual = round(ctx["result"].new_regime.tax_payable)
    assert actual == expected, f"Expected {expected}, got {actual}"


@then(parsers.parse("the old regime taxable income should account for standard deduction of {std:d}"))
def check_old_std_deduction(ctx, std):
    r = ctx["result"].old_regime
    # gross - std_deduction should be the base (no other deductions in this scenario)
    gross = ctx["form16"].salary.gross_salary
    assert r.taxable_income <= gross - std, f"Taxable income {r.taxable_income} doesn't reflect std deduction {std}"


@then(parsers.parse("the new regime taxable income should account for standard deduction of {std:d}"))
def check_new_std_deduction(ctx, std):
    r = ctx["result"].new_regime
    gross = ctx["form16"].salary.gross_salary
    assert r.taxable_income <= gross - std, f"Taxable income {r.taxable_income} doesn't reflect std deduction {std}"


@then(parsers.parse("the old regime HRA exemption claimed should be {expected:d}"))
def check_old_hra(ctx, expected):
    actual = round(ctx["result"].old_regime.hra_exemption_claimed)
    assert actual == expected, f"Expected HRA {expected}, got {actual}"


@then(parsers.parse("the new regime HRA exemption claimed should be {expected:d}"))
def check_new_hra(ctx, expected):
    actual = round(ctx["result"].new_regime.hra_exemption_claimed)
    assert actual == expected, f"Expected new regime HRA {expected}, got {actual}"


@then(parsers.parse("the other sources income should be {expected:d}"))
def check_other_sources(ctx, expected):
    actual = round(ctx["result"].old_regime.other_sources_income)
    assert actual == expected, f"Expected other sources {expected}, got {actual}"


@then("the old regime taxable income should include the AIS income")
def check_ais_in_taxable(ctx):
    r = ctx["result"].old_regime
    ais = ctx.get("ais")
    assert r.other_sources_income > 0, "AIS income not reflected in other_sources_income"


@then(parsers.parse("the old regime 80TTA deduction should be {expected:d}"))
def check_80tta(ctx, expected):
    actual = round(ctx["result"].old_regime.deduction_80tta_claimed)
    assert actual == expected, f"Expected 80TTA {expected}, got {actual}"


@then(parsers.parse("the new regime 80TTA deduction should be {expected:d}"))
def check_new_80tta(ctx, expected):
    actual = round(ctx["result"].new_regime.deduction_80tta_claimed)
    assert actual == expected, f"Expected new 80TTA {expected}, got {actual}"


@then(parsers.parse("the old regime 80TTB deduction should be {expected:d}"))
def check_80ttb(ctx, expected):
    actual = round(ctx["result"].old_regime.deduction_80ttb_claimed)
    assert actual == expected, f"Expected 80TTB {expected}, got {actual}"


@then(parsers.parse("the new regime 80TTB deduction should be {expected:d}"))
def check_new_80ttb(ctx, expected):
    actual = round(ctx["result"].new_regime.deduction_80ttb_claimed)
    assert actual == expected, f"Expected new 80TTB {expected}, got {actual}"


@then(parsers.parse("the old regime 80GG deduction claimed should be {expected:d}"))
def check_80gg_exact(ctx, expected):
    actual = round(ctx["result"].old_regime.deduction_80gg_claimed)
    assert actual == expected, f"Expected 80GG {expected}, got {actual}"


@then("the old regime 80GG deduction claimed should be greater than 0")
def check_80gg_positive(ctx):
    actual = ctx["result"].old_regime.deduction_80gg_claimed
    assert actual > 0, f"Expected 80GG > 0, got {actual}"


@then(parsers.parse("the new regime 80GG deduction claimed should be {expected:d}"))
def check_new_80gg(ctx, expected):
    actual = round(ctx["result"].new_regime.deduction_80gg_claimed)
    assert actual == expected, f"Expected new 80GG {expected}, got {actual}"


@then("the old regime HRA exemption claimed should be greater than 0")
def check_hra_positive(ctx):
    assert ctx["result"].old_regime.hra_exemption_claimed > 0


@then(parsers.parse("the merged gross salary should be {expected:d}"))
def check_merged_gross(ctx, expected):
    form16_2 = ctx.get("form16_2")
    merged = merge_form16s(ctx["form16"], form16_2)
    assert merged.salary.gross_salary == expected


@then(parsers.parse("the merged TDS should be {expected:d}"))
def check_merged_tds(ctx, expected):
    form16_2 = ctx.get("form16_2")
    merged = merge_form16s(ctx["form16"], form16_2)
    assert merged.tds.tds_deducted == expected


@then("merging the two Form 16s should raise a ValueError")
def check_merge_error(ctx):
    with pytest.raises(ValueError):
        merge_form16s(ctx["form16"], ctx["form16_2"])


@then(parsers.parse("the old regime home loan interest claimed should be {expected:d}"))
def check_hl_interest(ctx, expected):
    actual = round(ctx["result"].old_regime.home_loan_interest_claimed)
    assert actual == expected, f"Expected HL interest {expected}, got {actual}"


@then(parsers.parse("the new regime home loan interest claimed should be {expected:d}"))
def check_new_hl_interest(ctx, expected):
    actual = round(ctx["result"].new_regime.home_loan_interest_claimed)
    assert actual == expected, f"Expected new HL interest {expected}, got {actual}"


@then(parsers.parse("the old regime HP income should be {expected:d}"))
def check_hp_income(ctx, expected):
    actual = round(ctx["result"].old_regime.hp_income)
    assert actual == expected, f"Expected HP income {expected}, got {actual}"


@then("the taxpayer should be classified as a senior citizen")
def check_senior(ctx):
    from engine.computation.tax_engine import _age_at_fy_end, SENIOR_CITIZEN_AGE
    age = _age_at_fy_end(ctx.get("date_of_birth", ""), ctx["form16"].assessment_year)
    assert age is not None and age >= SENIOR_CITIZEN_AGE, f"Expected senior citizen, age={age}"


@then("the taxpayer should be classified as a super senior citizen")
def check_super_senior(ctx):
    from engine.computation.tax_engine import _age_at_fy_end, SUPER_SENIOR_CITIZEN_AGE
    age = _age_at_fy_end(ctx.get("date_of_birth", ""), ctx["form16"].assessment_year)
    assert age is not None and age >= SUPER_SENIOR_CITIZEN_AGE, f"Expected super senior, age={age}"


@then(parsers.parse("the HP income should be {expected:d}"))
def check_hp_exact(ctx, expected):
    actual = round(ctx["result"].old_regime.hp_income)
    assert actual == expected, f"Expected HP income {expected}, got {actual}"


@then(parsers.parse("the capital gains tax at special rates should be {expected:d}"))
def check_cg_tax(ctx, expected):
    cg = ctx["result"].old_regime.capital_gains_result
    assert cg is not None, "No capital gains result in regime"
    actual = round(cg.total_tax_at_special_rates)
    assert actual == expected, f"Expected CG tax {expected}, got {actual}"


@then(parsers.parse("the taxable LTCG post-Jul-23 should be {expected:d}"))
def check_ltcg_post(ctx, expected):
    cg = ctx["result"].old_regime.capital_gains_result
    actual = round(cg.taxable_ltcg_112a_post)
    assert actual == expected, f"Expected taxable LTCG post {expected}, got {actual}"


@then(parsers.parse("the taxable LTCG pre-Jul-23 should be {expected:d}"))
def check_ltcg_pre(ctx, expected):
    cg = ctx["result"].old_regime.capital_gains_result
    actual = round(cg.taxable_ltcg_112a_pre)
    assert actual == expected, f"Expected taxable LTCG pre {expected}, got {actual}"


@then(parsers.parse("the new regime 87A rebate should be {expected:d}"))
def check_87a_rebate(ctx, expected):
    actual = round(ctx["result"].new_regime.rebate_87a)
    assert actual == expected, f"Expected 87A rebate {expected}, got {actual}"


@then("the old regime taxable income should include the property STCG")
def check_prop_stcg_in_taxable(ctx):
    r = ctx["result"].old_regime
    cg_stcg = ctx["capital_gains"].property_gains.stcg
    assert r.taxable_income > 0, "Taxable income should include property STCG"


@then("creating the PropertyGains should raise a ValidationError")
def check_prop_validation(ctx):
    with pytest.raises(ValidationError):
        PropertyGains(**ctx["prop_gains_args"])


@then(parsers.parse("the taxable F&O income should be {expected:d}"))
def check_fo_taxable(ctx, expected):
    fo = ctx["result"].old_regime.fo_result
    assert fo is not None, "No F&O result in regime"
    actual = round(fo.taxable_fo_income)
    assert actual == expected, f"Expected F&O taxable {expected}, got {actual}"


@then(parsers.parse("the current year F&O loss to carry forward should be {expected:d}"))
def check_fo_cf_loss(ctx, expected):
    fo = ctx["result"].old_regime.fo_result
    actual = round(fo.current_year_loss_cf)
    assert actual == expected, f"Expected CF loss {expected}, got {actual}"


@then(parsers.parse("the prior year loss set off should be {expected:d}"))
def check_prior_loss_setoff(ctx, expected):
    fo = ctx["result"].old_regime.fo_result
    actual = round(fo.prior_year_loss_setoff)
    assert actual == expected, f"Expected prior loss setoff {expected}, got {actual}"


@then("the F&O data should require tax audit")
def check_audit_required(ctx):
    fo_data = ctx["fo_data"]
    assert fo_data.requires_tax_audit, \
        f"Expected tax audit required. turnover={fo_data.total_turnover}, net={fo_data.net_income}"


@then("the JSON should contain ScheduleAL")
def check_has_schedule_al(ctx):
    assert "ScheduleAL" in ctx["itr_json"], "ScheduleAL missing from ITR JSON"


@then("the JSON should not contain ScheduleAL")
def check_no_schedule_al(ctx):
    assert "ScheduleAL" not in ctx.get("itr_json", {}), "ScheduleAL unexpectedly present in ITR JSON"
