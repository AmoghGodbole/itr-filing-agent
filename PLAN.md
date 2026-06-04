# Implementation Plan — Manual Deductions Batch (P1)

Three features: **80D Parents Tier**, **Home Loan Bank Certificate**, **80GG (Rent without HRA)**

All three follow the same pattern: new field in `GenerateRequest` → engine picks it up → ITR JSON reflects it.

---

## Feature 1 — 80D Parents Health Insurance

### What
Add a parents' health insurance deduction (old regime only).
- Parents < 60: cap ₹25,000
- Parents ≥ 60 (senior): cap ₹50,000
- Combined 80D max: self ₹25k + parents ₹25k/₹50k = ₹50k–₹75k

### Changes

**`engine/computation/tax_engine.py`**
- Add constants: `SECTION_80D_LIMIT_PARENTS = 25_000` and `SECTION_80D_LIMIT_PARENTS_SENIOR = 50_000`
- `compute_old_regime(...)` — add params: `parents_insurance_premium: float = 0`, `parents_senior: bool = False`
- Compute `deduction_80d_parents = min(parents_insurance_premium, 50_000 if parents_senior else 25_000)`
- Add `deduction_80d_parents` to `chapter_via` total
- `RegimeResult` — add field: `deduction_80d_parents_claimed: float = 0`
- `compute_optimal_regime(...)` — add same params, pass through to `compute_old_regime`

**`engine/itr_generator/itr1_generator.py`**
- `_build_chapter_via` — add `Section80D` as sum of self + parents claimed; update `TotalChapVIADeductions`
- Generator needs `deduction_80d_parents_claimed` from `regime` — already available via `RegimeResult`

**`api/schemas.py`**
- `GenerateRequest` — add: `parents_insurance_premium: float = 0`, `parents_senior: bool = False`
- `RegimeOut` — add: `deduction_80d_parents_claimed: float = 0`

**`api/routes/itr.py`**
- `generate()` — pass `parents_insurance_premium` and `parents_senior` to `compute_optimal_regime`
- `_regime_to_out()` — include `deduction_80d_parents_claimed`

**`ui/src/app/page.tsx`**
- In Step 2 (Review), add a "Parents' Health Insurance" card below the existing deductions section
- Fields: `parents_insurance_premium` (number input, ₹), `parents_senior` (checkbox: "One or both parents are senior citizens (60+)")
- Wire into `GenerateRequest` body in `handleGenerate()`
- Show computed 80D parents amount in Step 3 regime card if claimed > 0

---

## Feature 2 — Home Loan Interest via Bank Certificate

### What
An employee may have a home loan whose interest is NOT captured in Form 16 (employer didn't factor it in). The bank issues an annual interest certificate. CA enters the total interest paid for the year; this overrides/replaces the Form 16 value for Section 24(b).

**Rule:** If CA provides a bank certificate amount > 0, use it. Otherwise fall back to Form 16's `home_loan_interest_24b`. Always cap at ₹2L (already implemented as `HOME_LOAN_INTEREST_24B_LIMIT`).

### Changes

**`engine/computation/tax_engine.py`**
- `compute_old_regime(...)` — add param: `home_loan_interest_cert: float = 0`
- Change the `home_loan_interest` line from:
  `home_loan_interest = min(form16.other_deductions.home_loan_interest_24b, HOME_LOAN_INTEREST_24B_LIMIT)`
  to:
  `_raw = home_loan_interest_cert if home_loan_interest_cert > 0 else form16.other_deductions.home_loan_interest_24b`
  `home_loan_interest = min(_raw, HOME_LOAN_INTEREST_24B_LIMIT)`
- `compute_optimal_regime(...)` — add same param, pass through

**`api/schemas.py`**
- `GenerateRequest` — add: `home_loan_interest_certificate: float = 0`

**`api/routes/itr.py`**
- `generate()` — pass `home_loan_interest_certificate` as `home_loan_interest_cert` to `compute_optimal_regime`

**`ui/src/app/page.tsx`**
- In Step 2, add a "Home Loan Interest" field inside the existing deductions section
- Label: "Annual Interest (Bank Certificate, ₹)"
- Helper text: "Enter if your employer did not capture home loan interest in Form 16. Leave blank if Form 16 already reflects it."
- Pre-populate with `parsed.form16.other_deductions.home_loan_interest_24b` if > 0 (so CA can see and override)
- Wire into `GenerateRequest` body

---

## Feature 3 — 80GG (Rent Deduction, No HRA)

### What
For salaried employees whose salary has no HRA component (`form16.salary.hra == 0`) but who pay rent. 80GG gives a deduction under Chapter VI-A instead of the Section 10(13A) HRA exemption. The two are mutually exclusive.

**Formula:** min of:
1. Rent paid − 10% of gross total income (before this deduction)
2. 25% of gross total income
3. ₹60,000/year (₹5,000/month)

**Auto-detection:** If `form16.salary.hra == 0` and monthly rent is entered → apply 80GG instead of HRA exemption. CA uses the same rent input field; no new field needed.

### Changes

**`engine/computation/tax_engine.py`**
- Add constant: `SECTION_80GG_ANNUAL_LIMIT = 60_000`
- Add function `compute_80gg(monthly_rent: float, gross_total_income: float) -> float`
- `RegimeResult` — add field: `deduction_80gg_claimed: float = 0`
- `compute_old_regime(...)` — after computing `gross_total_income`:
  - Current: HRA exemption always applied to salary income
  - New: if `form16.salary.hra == 0 and hra_monthly_rent > 0`: set `hra_exempt = 0`, compute `deduction_80gg` and add it to `chapter_via` total
  - If `form16.salary.hra > 0`: current behaviour unchanged (HRA exemption applied, no 80GG)
- Store `deduction_80gg_claimed` in `RegimeResult`

**`engine/itr_generator/itr1_generator.py`**
- `_build_chapter_via` — add `Section80GG: int(regime.deduction_80gg_claimed)` and include in `TotalChapVIADeductions`

**`api/schemas.py`**
- `RegimeOut` — add: `deduction_80gg_claimed: float = 0`

**`api/routes/itr.py`**
- `_regime_to_out()` — include `deduction_80gg_claimed`

**`ui/src/app/page.tsx`**
- Rename HRA section label to "Rent Details (HRA / 80GG)"
- Add helper text: "If your salary has no HRA component, 80GG will be applied automatically"
- No new input fields needed — same monthly rent + city inputs are reused
- In Step 3, show 80GG claimed amount in regime card if > 0

---

## Order of implementation

1. `engine/computation/tax_engine.py` — all three engine changes together (constants, functions, RegimeResult fields, compute functions)
2. `engine/itr_generator/itr1_generator.py` — update `_build_chapter_via` for 80D parents + 80GG
3. `api/schemas.py` — add all new fields to `GenerateRequest` and `RegimeOut`
4. `api/routes/itr.py` — wire new fields through
5. `ui/src/app/page.tsx` — add the three UI sections in the Review step + update Result display

## Done criteria
- [ ] 80D parents: old regime chapter VI-A includes parents premium, capped correctly, reflected in ITR JSON
- [ ] Home loan cert: if CA enters amount, it overrides Form 16's 24(b) value, capped at ₹2L
- [ ] 80GG: auto-applied when HRA component is zero and rent is entered; ITR JSON includes Section80GG
- [ ] New regime unaffected by all three (80D parents, 80GG, 24(b) are old-regime-only)
- [ ] UI shows all new fields in Step 2; Step 3 regime card reflects what was claimed
