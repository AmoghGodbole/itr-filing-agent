"""
Playwright E2E tests — all 13 workflow scenarios.

API calls are intercepted via page.route() (see conftest.py).
Tests verify the CA workflow through the real browser UI.
"""
import json
from playwright.sync_api import Page, expect

from tests.e2e.conftest import (
    mock_api, upload_form16, click_extract, fill_bank, click_generate, download_json,
    FIXTURES, _parse_response, _generate_response,
)


def _go_to_result(page: Page, scenario: str, *, ais=False, cg=False, fo=False, f16_2=False):
    """Upload → extract → fill bank → generate in one shot."""
    mock_api(page, scenario)
    upload_form16(page)
    if f16_2:
        page.locator("input[type=file]").nth(1).set_input_files(f"{FIXTURES}/dummy_form16.pdf")
    if ais:
        page.locator("input[type=file][accept='.json']").set_input_files(f"{FIXTURES}/dummy_ais.json")
    if cg:
        page.locator("input[type=file][multiple]").nth(0).set_input_files(f"{FIXTURES}/dummy_broker_cg.pdf")
    if fo:
        page.locator("input[type=file][multiple]").nth(1).set_input_files(f"{FIXTURES}/dummy_fo.pdf")
    click_extract(page)
    fill_bank(page)
    click_generate(page)


def _itr_badge(page: Page, form: str):
    """Return a locator for the specific ITR badge span (not the download button)."""
    labels = {"ITR-2": "ITR-2 (Capital Gains)", "ITR-3": "ITR-3 (F&O Business Income)"}
    return page.get_by_text(labels[form])


# ── Scenario 1: Basic ITR-1 ────────────────────────────────────────────────────

def test_basic_itr1(app_page: Page):
    _go_to_result(app_page, "basic")
    expect(app_page.locator("text=Tax Comparison")).to_be_visible()
    expect(_itr_badge(app_page, "ITR-2")).not_to_be_visible()
    expect(_itr_badge(app_page, "ITR-3")).not_to_be_visible()

    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-1"
    assert "ScheduleCGFor23" not in itr


# ── Scenario 2: AIS income ────────────────────────────────────────────────────

def test_ais_income(app_page: Page):
    mock_api(app_page, "ais")
    upload_form16(app_page)
    app_page.locator("input[type=file][accept='.json']").set_input_files(f"{FIXTURES}/dummy_ais.json")
    click_extract(app_page)

    # AIS summary visible in step 2
    expect(app_page.locator("text=FD / Deposit Interest")).to_be_visible()

    fill_bank(app_page)
    click_generate(app_page)

    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-1"
    assert itr["ITR1_IncomeDeductions"]["IncomeOthSrc"] > 0


# ── Scenario 3: Manual HRA ────────────────────────────────────────────────────

def test_manual_hra(app_page: Page):
    mock_api(app_page, "hra")
    upload_form16(app_page)
    click_extract(app_page)

    app_page.locator("label", has=app_page.locator("span", has_text="Monthly Rent (₹)")).locator("input").fill("20000")
    app_page.locator("select").filter(has_text="Select city").select_option("mumbai")

    fill_bank(app_page)
    click_generate(app_page)

    expect(app_page.locator("text=Tax Comparison")).to_be_visible()
    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-1"


# ── Scenario 4: 80GG (no HRA component) ───────────────────────────────────────

def test_80gg(app_page: Page):
    _go_to_result(app_page, "80gg")

    # 80GG (Rent) row visible in the old regime card (even if new regime recommended)
    expect(app_page.get_by_text("80GG (Rent)")).to_be_visible()


# ── Scenario 5: Two Form 16s ──────────────────────────────────────────────────

def test_two_form16s(app_page: Page):
    mock_api(app_page, "two_f16")
    upload_form16(app_page)
    app_page.locator("input[type=file]").nth(1).set_input_files(f"{FIXTURES}/dummy_form16.pdf")
    click_extract(app_page)

    # Both employers shown in step 2 review
    expect(app_page.get_by_text("Beta Solutions Ltd")).to_be_visible()

    fill_bank(app_page)
    click_generate(app_page)

    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-1"
    tds1 = itr.get("ScheduleTDS1", [])
    assert len(tds1) == 2, f"Expected 2 TDS1 entries, got {len(tds1)}"


# ── Scenario 6: Home loan ─────────────────────────────────────────────────────

def test_home_loan(app_page: Page):
    mock_api(app_page, "home_loan")
    upload_form16(app_page)
    click_extract(app_page)

    # Label: "Annual Interest from Bank Certificate (₹)"
    app_page.get_by_label("Annual Interest from Bank Certificate (₹)").fill("180000")

    fill_bank(app_page)
    click_generate(app_page)

    # Old regime card shows "HP Loss (24b)" row when home loan interest is claimed
    expect(app_page.get_by_text("HP Loss (24b)")).to_be_visible()


# ── Scenario 7: Senior citizen ────────────────────────────────────────────────

def test_senior_citizen(app_page: Page):
    mock_api(app_page, "senior")
    upload_form16(app_page)
    app_page.locator("input[type=file][accept='.json']").set_input_files(f"{FIXTURES}/dummy_ais.json")
    click_extract(app_page)

    # Senior citizen badge appears when DOB entered
    app_page.get_by_label("Date of Birth (optional)").fill("1960-06-01")
    expect(app_page.get_by_text("Senior Citizen (60–79)")).to_be_visible()

    fill_bank(app_page)
    click_generate(app_page)

    itr = download_json(app_page)
    # Senior citizen generate response precomputed with DOB — 80TTB in old regime,
    # but since new regime is recommended, chapter_via isn't in ITR JSON.
    # Verify ITR generated at all and old regime card shows Chapter VI-A
    assert "ITRForm" in itr
    expect(app_page.get_by_text("Chapter VI-A")).to_be_visible()


# ── Scenario 8: Let-out property ─────────────────────────────────────────────

def test_letout_property(app_page: Page):
    _go_to_result(app_page, "letout")
    # HP income = 143,600 (AV 348k × 70% − 100k interest)
    itr = download_json(app_page)
    assert itr["ITR1_IncomeDeductions"]["TotalIncomeOfHP"] == 143_600


# ── Scenario 9: Capital gains ITR-2 ──────────────────────────────────────────

def test_capital_gains_itr2(app_page: Page):
    _go_to_result(app_page, "cg", cg=True)

    expect(_itr_badge(app_page, "ITR-2")).to_be_visible()

    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-2"
    assert "ScheduleCGFor23" in itr
    assert itr["ScheduleCGFor23"]["TotalCapGains"] > 0


# ── Scenario 10: Property sale (manual LTCG entry) ───────────────────────────

def test_property_sale(app_page: Page):
    from tests.mocks.parser_responses import FORM16_BASIC
    from engine.models_capital_gains import CapitalGainsSummary, PropertyGains
    from tests.e2e.conftest import _parse_response, _generate_response

    cg = CapitalGainsSummary(property_gains=PropertyGains(ltcg_with_indexation=500_000))
    parse_r = _parse_response(FORM16_BASIC)
    gen_r = _generate_response(FORM16_BASIC, cg=cg)

    app_page.route("**/api/parse",    lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(parse_r)))
    app_page.route("**/api/generate", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(gen_r)))

    upload_form16(app_page)
    click_extract(app_page)

    # Enter LTCG with indexation manually
    app_page.locator("label", has=app_page.locator("span", has_text="LTCG 20% with CII indexation")).locator("input").fill("500000")

    fill_bank(app_page)
    click_generate(app_page)

    expect(_itr_badge(app_page, "ITR-2")).to_be_visible()
    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-2"
    assert itr["ScheduleCGFor23"]["LongTermCapGain20Per"]["CapGain"] == 500_000


# ── Scenario 11: F&O ITR-3 ───────────────────────────────────────────────────

def test_fo_trader_itr3(app_page: Page):
    mock_api(app_page, "fo")
    upload_form16(app_page)
    app_page.locator("input[type=file][multiple]").nth(1).set_input_files(f"{FIXTURES}/dummy_fo.pdf")
    click_extract(app_page)

    # F&O card visible in step 2
    expect(app_page.get_by_text("F&O Income — Extracted from Broker P&L")).to_be_visible()

    fill_bank(app_page)
    click_generate(app_page)

    expect(_itr_badge(app_page, "ITR-3")).to_be_visible()
    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-3"
    assert "ScheduleBP" in itr
    assert "ScheduleBFLA" in itr
    assert "ScheduleCFL" in itr


# ── Scenario 12: F&O + CG → ITR-3 ────────────────────────────────────────────

def test_fo_plus_cg(app_page: Page):
    _go_to_result(app_page, "fo_cg", cg=True, fo=True)

    expect(_itr_badge(app_page, "ITR-3")).to_be_visible()
    expect(_itr_badge(app_page, "ITR-2")).not_to_be_visible()

    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-3"
    assert "ScheduleBP" in itr
    assert "ScheduleCGFor23" in itr


# ── Scenario 13: Schedule AL ──────────────────────────────────────────────────

def test_schedule_al_high_income(app_page: Page):
    _go_to_result(app_page, "schedule_al", cg=True)

    expect(_itr_badge(app_page, "ITR-2")).to_be_visible()

    itr = download_json(app_page)
    assert itr["ITRForm"]["FormName"] == "ITR-2"
    assert "ScheduleAL" in itr, "Schedule AL must be present when total income > ₹50L"
    assert itr["ScheduleAL"]["TotalAssets"] > 0
