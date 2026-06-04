# Testing Strategy

## Overview

Two independent test layers. Both cover all 13 workflow scenarios. Neither layer
depends on the other — BDD runs without servers, Playwright runs without touching
the engine internals directly.

---

## Layer 1 — BDD (pytest-bdd)

**Purpose:** Verify tax computation correctness. Given a set of inputs, does the
engine produce the right taxable income, right deductions, right ITR form, right
refund/payable?

**Stack:** `pytest` + `pytest-bdd` + Gherkin `.feature` files

**What is real:** The entire Python engine — models, tax_engine, generators.

**What is mocked:** Nothing. Inputs are injected as Python objects directly
(no PDFs, no Claude API calls, no servers needed).

**Speed:** Entire suite runs in < 5 seconds. Safe for CI on every push.

**Structure:**
```
tests/
  bdd/
    features/
      01_basic_itr1.feature
      02_ais_income.feature
      03_manual_hra.feature
      04_80gg.feature
      05_two_form16s.feature
      06_home_loan.feature
      07_senior_citizen.feature
      08_letout_property.feature
      09_capital_gains_itr2.feature
      10_property_sale.feature
      11_fo_trader_itr3.feature
      12_fo_plus_cg.feature
      13_schedule_al.feature
    steps/
      common_steps.py       # shared Given/When/Then steps
      computation_steps.py  # regime, tax, refund assertions
      generator_steps.py    # ITR JSON structure assertions
    conftest.py             # fixtures: sample Form16Data, AISData, etc.
```

**Example feature (Scenario 3 — manual HRA):**
```gherkin
Feature: Manual HRA claim when not declared to employer

  Scenario: Employee pays rent but Form 16 shows zero HRA exemption
    Given a Form 16 with gross salary 1200000 and HRA component 120000
    And the Form 16 shows HRA exemption of 0
    And the employee pays monthly rent of 25000 in Mumbai
    When the tax engine runs under the old regime
    Then the HRA exemption claimed should be 90000
    And the taxable income should be less than without the HRA claim
    And the new regime HRA exemption should be 0
```

**Key assertions per scenario:**
| Scenario | BDD asserts |
|---|---|
| 1 Basic ITR-1 | Taxable income = gross − std deduction − 80C/D; ITR-1 selected |
| 2 AIS income | other_sources_income = FD interest + dividends; 80TTA applied |
| 3 Manual HRA | hra_exemption_claimed = min(HRA, 50%/40% basic, rent − 10% basic) |
| 4 80GG | deduction_80gg_claimed > 0; HRA exemption = 0 |
| 5 Two Form 16s | Merged gross = sum of both; ScheduleTDS1 has 2 entries |
| 6 Home loan | TotalIncomeOfHP is negative; capped at −2,00,000 |
| 7 Senior citizen | Senior slabs used; Section80TTB > 0; Section80TTA = 0 |
| 8 Let-out property | hp_income computed correctly; loss set-off capped at 2L |
| 9 Capital gains | is_itr2 = True; ScheduleCGFor23 has correct buckets; special-rate tax correct |
| 10 Property sale | ltcg_with_indexation and ltcg_without_indexation mutually exclusive |
| 11 F&O | is_itr3 = True; ScheduleBP present; taxable_fo_income added to slab |
| 12 F&O + CG | is_itr3 = True (F&O takes priority); both ScheduleBP and ScheduleCG present |
| 13 Schedule AL | ScheduleAL present when total income > 50L; absent when below threshold |

---

## Layer 2 — Playwright (end-to-end)

**Purpose:** Verify the full CA workflow through the real browser UI. Does the
upload work? Do the right fields appear? Does the result screen show the right
outcome? Does the downloaded JSON have the right form name?

**Stack:** `playwright` + `pytest-playwright` (Python) or `@playwright/test` (TypeScript)

**What is real:** Next.js UI, FastAPI backend, full HTTP round-trip.

**What is mocked:** Claude parsers — each parser is patched to return a pre-built
fixture object instead of calling the Anthropic API. Tests are fast, free, and
deterministic regardless of model availability.

**Speed:** Each scenario ~5–15 seconds (browser + server round-trip). Full suite
~3–5 minutes.

**Fixture files (created once, committed to repo):**
```
tests/
  fixtures/
    form16_basic.pdf          # minimal valid Form 16 PDF (or synthetic)
    form16_employer2.pdf      # second employer Form 16
    ais_basic.json            # AIS with one FD entry and one dividend
    form26as_basic.pdf        # Form 26AS matching form16_basic TDS
    broker_cg_zerodha.pdf     # Zerodha P&L with equity STCG/LTCG
    broker_cg_cams.pdf        # CAMS statement with MF gains (multi-broker test)
    fo_zerodha.pdf            # Zerodha F&O P&L with one segment
  mocks/
    parser_responses.py       # fixed return values for each parser mock
```

**Claude parser mocking approach:**
```python
# conftest.py
@pytest.fixture(autouse=True)
def mock_parsers(monkeypatch):
    monkeypatch.setattr("engine.parsers.form16_parser.parse_form16", lambda _: FIXTURE_FORM16)
    monkeypatch.setattr("engine.parsers.ais_parser.parse_ais", lambda _: FIXTURE_AIS)
    monkeypatch.setattr("engine.parsers.capital_gains_parser.parse_capital_gains", lambda _: FIXTURE_CG)
    monkeypatch.setattr("engine.parsers.fo_parser.parse_fo", lambda _: FIXTURE_FO)
```

**Structure:**
```
tests/
  e2e/
    conftest.py               # server startup, parser mocks, browser fixture
    test_01_basic_itr1.py
    test_02_ais_income.py
    test_03_manual_hra.py
    test_04_80gg.py
    test_05_two_form16s.py
    test_06_home_loan.py
    test_07_senior_citizen.py
    test_08_letout_property.py
    test_09_capital_gains.py
    test_10_property_sale.py
    test_11_fo_trader.py
    test_12_fo_plus_cg.py
    test_13_schedule_al.py
    helpers.py                # fill_bank_details(), download_and_parse_json(), etc.
```

**Example Playwright test (Scenario 9 — capital gains):**
```python
def test_capital_gains_itr2(page, live_server):
    page.goto(live_server)

    # Step 1 — Upload
    page.get_by_label("Form 16 PDF").set_input_files("tests/fixtures/form16_basic.pdf")
    page.get_by_label("Broker Tax P&L PDFs").set_input_files("tests/fixtures/broker_cg_zerodha.pdf")
    page.get_by_role("button", name="Extract & Continue").click()
    page.wait_for_selector("text=Extracted from Form 16")

    # Step 2 — Review: verify CG fields pre-filled, fill bank details
    assert page.locator("[data-testid='cg-eq-stcg-pre']").input_value() != ""
    fill_bank_details(page)
    page.get_by_role("button", name="Compute Tax & Generate ITR").click()
    page.wait_for_selector("text=Tax Comparison")

    # Step 3 — Result: ITR-2 badge visible, download JSON and verify
    assert page.locator("text=ITR-2").is_visible()
    itr = download_and_parse_json(page)
    assert itr["ITRForm"]["FormName"] == "ITR-2"
    assert "ScheduleCGFor23" in itr
```

**Key UI assertions per scenario:**
| Scenario | Playwright asserts |
|---|---|
| 1 Basic ITR-1 | ITR-1 badge; JSON FormName=ITR-1; refund/payable shown |
| 2 AIS income | AIS summary section visible; income from other sources > 0 |
| 3 Manual HRA | HRA exemption row shows non-zero in old regime card |
| 4 80GG | Old regime shows 80GG deduction row |
| 5 Two Form 16s | Both employer names visible in review; TDS is sum of both |
| 6 Home loan | HP income row shows negative value in old regime card |
| 7 Senior citizen | "Senior Citizen" badge appears after DOB entry |
| 8 Let-out property | HP income computed and shown; old regime typically recommended |
| 9 Capital gains | ITR-2 badge; CG fields pre-filled from broker PDF |
| 10 Property sale | Manual LTCG entry accepted; one of two indexation fields non-zero |
| 11 F&O | ITR-3 badge; audit warning shown if triggered |
| 12 F&O + CG | ITR-3 badge (not ITR-2); both F&O and CG sections visible |
| 13 Schedule AL | Schedule AL section present when income > 50L |

---

## What we are NOT testing (and why)

| Excluded | Reason |
|---|---|
| Claude parser accuracy | Model output is non-deterministic; accuracy is validated manually against real documents |
| PDF rendering | Not our code |
| IT portal acceptance | Requires real ERI registration and portal access |
| Concurrent users | Not in scope for v1 |

---

## Running the tests

```bash
# BDD only (no servers needed)
.venv/bin/pytest tests/bdd/ -v

# Playwright (requires both servers running)
.venv/bin/uvicorn api.main:app --port 8000 &
cd ui && npm run dev &
.venv/bin/pytest tests/e2e/ -v

# Both layers
.venv/bin/pytest tests/ -v
```

---

## CI pipeline (future)

1. On every push: BDD suite (fast, no external deps)
2. On PR to main: BDD + Playwright (needs browser installed in CI)
3. Never in CI: real Claude API calls
