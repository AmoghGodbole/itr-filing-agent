"""
Playwright E2E configuration.

Only Next.js is started as a subprocess. All /api/parse and /api/generate requests
are intercepted by page.route() and answered with pre-computed Python engine
responses. No FastAPI server, no Claude API calls, no real PDFs required.
"""
import json
import os
import socket
import subprocess
import time

import pytest
from playwright.sync_api import Page

from engine.computation.tax_engine import compute_optimal_regime
from engine.itr_generator.itr1_generator import BankAccount, generate_itr1
from engine.itr_generator.itr2_generator import generate_itr2
from engine.itr_generator.itr3_generator import generate_itr3
from tests.mocks.parser_responses import (
    FORM16_BASIC, FORM16_EMPLOYER2, FORM16_NO_HRA, FORM16_SENIOR,
    FORM16_HIGH_INCOME, AIS_BASIC, CG_EQUITY_BASIC, CG_MULTI_BROKER, FO_BASIC,
)

FIXTURES = "tests/fixtures"
_BANK = BankAccount(account_number="1234567890", ifsc="SBIN0000001",
                    account_type="Savings", bank_name="SBI")


# ── Engine helpers ─────────────────────────────────────────────────────────────

def _parse_response(form16, *, form16_2=None, ais=None, cg=None, fo=None) -> dict:
    from api.routes.itr import _form16_to_out, _cg_to_out, _fo_to_out
    from api.schemas import AISOut, AISIncomeOut

    ais_out = None
    if ais is not None:
        ais_out = AISOut(
            taxpayer_name=ais.taxpayer_name,
            financial_year=ais.financial_year,
            savings_account_interest=[AISIncomeOut(**e.__dict__) for e in ais.savings_account_interest],
            deposit_interest=[AISIncomeOut(**e.__dict__) for e in ais.deposit_interest],
            dividends=[AISIncomeOut(**e.__dict__) for e in ais.dividends],
            total_interest=ais.total_interest,
            total_dividends=ais.total_dividends,
            total_tds_from_ais=ais.total_tds_from_ais,
        ).model_dump()

    return {
        "form16": _form16_to_out(form16).model_dump(),
        "form16_2": _form16_to_out(form16_2).model_dump() if form16_2 else None,
        "form26as": None,
        "ais": ais_out,
        "capital_gains": _cg_to_out(cg).model_dump() if cg else None,
        "fo_data": _fo_to_out(fo).model_dump() if fo else None,
    }


def _generate_response(form16, *, form16_2=None, ais=None, cg=None, fo=None,
                        schedule_al=None, rental_annual_rent=0,
                        rental_municipal_taxes=0, rental_home_loan_interest=0,
                        hra_monthly_rent=0, hra_city="", date_of_birth="",
                        home_loan_interest_cert=0) -> dict:
    from api.routes.itr import _regime_to_out
    from engine.models import merge_form16s

    merged = merge_form16s(form16, form16_2) if form16_2 else form16
    computation = compute_optimal_regime(
        merged, ais=ais, capital_gains=cg, fo_data=fo,
        rental_annual_rent=rental_annual_rent,
        rental_municipal_taxes=rental_municipal_taxes,
        rental_home_loan_interest=rental_home_loan_interest,
        hra_monthly_rent=hra_monthly_rent,
        hra_city=hra_city,
        date_of_birth=date_of_birth,
        home_loan_interest_cert=home_loan_interest_cert,
    )
    if computation.is_itr3 and fo:
        itr = generate_itr3(merged, computation, _BANK, fo, cg,
                            second_form16=form16_2, schedule_al=schedule_al)
    elif computation.is_itr2 and cg:
        itr = generate_itr2(merged, computation, _BANK, cg,
                            second_form16=form16_2, schedule_al=schedule_al)
    else:
        itr = generate_itr1(merged, computation, _BANK, second_form16=form16_2)

    return {
        "old_regime": _regime_to_out(computation.old_regime).model_dump(),
        "new_regime": _regime_to_out(computation.new_regime).model_dump(),
        "recommended_regime": computation.recommended_regime,
        "savings": float(computation.savings),
        "is_itr2": computation.is_itr2,
        "is_itr3": computation.is_itr3,
        "itr_json": itr,
    }


# ── Pre-computed scenario pairs ────────────────────────────────────────────────

def _build_scenarios() -> dict[str, tuple[dict, dict]]:
    from engine.models_schedule_al import ScheduleALData, ImmovableProperty
    al = ScheduleALData(immovable_properties=[ImmovableProperty(description="Flat", value=10_000_000)])
    return {
        "basic":       (_parse_response(FORM16_BASIC),
                        _generate_response(FORM16_BASIC)),
        "ais":         (_parse_response(FORM16_BASIC, ais=AIS_BASIC),
                        _generate_response(FORM16_BASIC, ais=AIS_BASIC)),
        "hra":         (_parse_response(FORM16_BASIC),
                        _generate_response(FORM16_BASIC)),
        "80gg":        (_parse_response(FORM16_NO_HRA),
                        _generate_response(FORM16_NO_HRA, hra_monthly_rent=15_000, hra_city="other")),
        "two_f16":     (_parse_response(FORM16_BASIC, form16_2=FORM16_EMPLOYER2),
                        _generate_response(FORM16_BASIC, form16_2=FORM16_EMPLOYER2)),
        "home_loan":   (_parse_response(FORM16_BASIC),
                        _generate_response(FORM16_BASIC, home_loan_interest_cert=180_000)),
        "senior":      (_parse_response(FORM16_SENIOR, ais=AIS_BASIC),
                        _generate_response(FORM16_SENIOR, ais=AIS_BASIC, date_of_birth="01/06/1960")),
        "letout":      (_parse_response(FORM16_BASIC),
                        _generate_response(FORM16_BASIC,
                                           rental_annual_rent=360_000,
                                           rental_municipal_taxes=12_000,
                                           rental_home_loan_interest=100_000)),
        "cg":          (_parse_response(FORM16_BASIC, cg=CG_EQUITY_BASIC),
                        _generate_response(FORM16_BASIC, cg=CG_EQUITY_BASIC)),
        "fo":          (_parse_response(FORM16_BASIC, fo=FO_BASIC),
                        _generate_response(FORM16_BASIC, fo=FO_BASIC)),
        "fo_cg":       (_parse_response(FORM16_BASIC, cg=CG_EQUITY_BASIC, fo=FO_BASIC),
                        _generate_response(FORM16_BASIC, cg=CG_EQUITY_BASIC, fo=FO_BASIC)),
        "schedule_al": (_parse_response(FORM16_HIGH_INCOME, cg=CG_MULTI_BROKER),
                        _generate_response(FORM16_HIGH_INCOME, cg=CG_MULTI_BROKER, schedule_al=al)),
    }


SCENARIOS = _build_scenarios()


# ── Server fixture ─────────────────────────────────────────────────────────────

def _wait_for_port(port: int, timeout: float = 90.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Server on port {port} did not start in {timeout}s")


@pytest.fixture(scope="session")
def ui_server():
    port = 3765
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(port)],
        cwd=os.path.join(root, "ui"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_port(port)
    yield f"http://localhost:{port}"
    proc.terminate()
    proc.wait()


# ── Page fixture ───────────────────────────────────────────────────────────────

@pytest.fixture
def app_page(page: Page, ui_server: str):
    page.goto(ui_server)
    page.wait_for_load_state("networkidle")
    return page


# ── Route-mock ─────────────────────────────────────────────────────────────────

def mock_api(page: Page, scenario: str):
    """Intercept /api/parse and /api/generate; return pre-computed responses."""
    parse_resp, gen_resp = SCENARIOS[scenario]
    page.route("**/api/parse",    lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(parse_resp)))
    page.route("**/api/generate", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(gen_resp)))


# ── Shared UI helpers ──────────────────────────────────────────────────────────

def upload_form16(page: Page):
    page.locator("input[type=file]").first.set_input_files(f"{FIXTURES}/dummy_form16.pdf")


def click_extract(page: Page):
    page.get_by_role("button", name="Extract & Continue →").click()
    page.wait_for_selector("text=Extracted from Form 16", timeout=15_000)


def fill_bank(page: Page):
    page.get_by_label("Account Number *").fill("1234567890")
    page.get_by_label("IFSC Code *").fill("SBIN0000001")
    page.get_by_label("Bank Name *").fill("SBI")


def click_generate(page: Page):
    page.get_by_role("button", name="Compute Tax & Generate ITR →").click()
    page.wait_for_selector("text=Tax Comparison", timeout=15_000)


def download_json(page: Page) -> dict:
    with page.expect_download() as dl:
        page.locator("button", has_text="Download").click()
    return json.loads(open(dl.value.path()).read())
