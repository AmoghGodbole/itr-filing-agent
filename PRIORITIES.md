# Priorities

What we build next, in order. Each item has a clear "done" definition.

---

## P0 — Needed for a complete, correct ITR

### 1. AIS Parser
**Why:** CAs already fetch AIS from the IT portal to get FD interest, dividends, savings account interest, etc. Without this, our return is incomplete — we'd miss income the IT department already knows about, which triggers notices.

**What AIS gives us:**
- Interest income (FD, RD, savings account)
- Dividend income (stocks, mutual funds)
- Securities transactions (for capital gains)
- Rent received
- All TDS sources (not just employer)

**Approach (v1):** CA downloads AIS as JSON from incometax.gov.in → uploads to our tool → we parse and merge with Form 16 data.
*(Portal: incometax.gov.in → Services → Annual Information Statement → Download JSON)*

**Done when:** AIS JSON parsed, interest + dividend income merged into tax computation, correct 80TTA deduction applied on savings interest.

---

### 2. Form 26AS Parser
**Why:** Confirms TDS from all sources (banks, tenants, buyers). Cross-validates Form 16 TDS figure. Flags mismatches before filing.

**Approach:** CA downloads Form 26AS as PDF or text from TRACES → we parse it.

**Done when:** All TDS entries extracted, total TDS reconciled against Form 16 TDS, mismatches flagged to CA.

---

### 3. HRA Exemption Computation
**Why:** Many employees pay rent but don't declare it to their employer — so Form 16 shows zero HRA exemption. They can still claim it while filing. We're leaving money on the table if we don't compute this.

**What we need from user:** Monthly rent paid, city (metro/non-metro), landlord PAN (if rent > ₹1L/year).

**Formula:** Min of (actual HRA received, 50%/40% of basic, actual rent − 10% of basic).

**Done when:** HRA exemption computed from user inputs, applied to taxable income, ITR-1 JSON updated.

---

### 4. CA-facing UI
**Why:** The engine works but there's no interface. A CA can't use a Python script.

**Stack:** Next.js (React frontend + API routes calling the Python engine via FastAPI).

**Screens needed:**
- Upload Form 16 PDF + AIS JSON
- Review extracted data (editable)
- Regime comparison (old vs new, savings shown clearly)
- Enter bank details + Aadhaar
- Download ITR-1 JSON

**Done when:** CA can go from PDF upload to downloadable ITR JSON without touching the terminal.

---

## P1 — Makes the tool accurate for more taxpayers

### ~~5. Rental Income (Let-out Property)~~ ✓ Done
Annual rent − municipal taxes = Annual Value → 70% of AV − home loan interest (no ₹2L cap for let-out) = HP income. HP loss capped at ₹2L same-year set-off. Self-occupied home loan deduction zeroed out when let-out is active.

### ~~6. Other Sources Income~~ ✓ Done
FD/deposit interest + dividends pulled from AIS. Family pension manual entry added: Section 57(iia) deduction (min of ₹15,000 or 1/3 pension) computed automatically. Available in both old and new regime.

### ~~7. Senior Citizen Slabs~~ ✓ Done
Different basic exemption limits for age 60–80 and 80+. DOB field added to Review step.

### ~~8. 80D — Parents' Health Insurance~~ ✓ Done
Parents tier added: ₹25,000 cap (₹50,000 for senior parents). Manual entry in Review step.

### ~~9. Multiple Form 16s (Job Change)~~ ✓ Done
Optional second Form 16 PDF upload. Both are parsed, PAN + AY validated to match, then merged: salary/exemptions/deductions/TDS summed. ITR JSON ScheduleTDS1 carries both employers as separate entries. Merge happens at generation time so CA can review both Form 16 summaries before confirming.

### ~~10. Home Loan Interest via Bank Certificate~~ ✓ Done
Manual field in Review step. Overrides Form 16 value. Capped at ₹2L.

### ~~11. 80GG — Rent Deduction Without HRA~~ ✓ Done
Auto-detected when HRA component = 0 and rent is entered. Same inputs as HRA, different formula.

---

## P2 — Expands scope beyond ITR-1

### ~~12. Capital Gains (ITR-2)~~ ✓ Done
STCG/LTCG from stocks, mutual funds, property. Budget 2024 pre/post Jul 23 rate split (111A: 15%→20%, 112A: 10%→12.5%, 1.25L exempt). Broker P&L PDF parsed by Claude (Zerodha, Groww, CAMS). Property gains always manual. Triggers ITR-2 automatically when any gain is non-zero.

### ~~13. ITR-2 Generator~~ ✓ Done
Schedule CG (all 7 rate buckets), Schedule SI (special income rates), ScheduleTDS2. Full tax computation separates slab tax from special-rate CG tax. Portal JSON invariants maintained.

### ~~14. Schedule AL (Assets & Liabilities)~~ ✓ Done
Mandatory in ITR-2/3 when total income > ₹50L. Dynamic immovable property list + movable/financial/liability flat fields. Auto-included in ITR-2 JSON when threshold exceeded; silently omitted below threshold. Live net-worth preview in UI.

### ~~15. 80EEA — Additional Home Loan Interest (Affordable Housing)~~ ✓ Done
Extra ₹1.5L deduction on home loan interest for first-time buyers (stamp duty value ≤ ₹45L, loan Apr 2019–Mar 2022). Stacks on Sec 24(b). Manual entry; CA verifies eligibility. Old regime only. Auto-zeroed when let-out property active.

### 16. IT Portal Login + Auto AIS Fetch
Instead of CA manually downloading AIS, log into the portal on the client's behalf and fetch it programmatically. Requires session handling (Playwright).

### 17. ERI Registration + Direct Filing
File directly via IT department API — eliminates manual JSON upload step. Requires ERI registration.
*(See FUTURE_SCOPE.md for details)*

---

## P3 — Business Income / ITR-3

### ~~18. F&O (Futures & Options) Income~~ ✓ Done
F&O is non-speculative business income (Sec 43(5)) → mandates ITR-3 regardless of amount. Claude-powered broker P&L parser (Zerodha, Groww, Upstox, Angel One). Turnover = absolute sum (gross profit + gross loss, not net). Business expenses deductible. Prior-year loss set-off (8-year carry-forward, business income only). Tax audit flag when turnover > ₹10Cr or loss declared. Schedule BP + BFLA + CFL in ITR-3 JSON. Schedule CG included if both F&O and capital gains present. ITR-3 selection is automatic when F&O data is uploaded.

---

## Data source reference

| Income / Deduction | Auto-extracted from | Manual if |
|---|---|---|
| Salary, TDS | Form 16 | — |
| HRA exemption | Form 16 (if employer computed it) | Employee didn't declare rent to employer |
| FD/RD/bond interest | AIS (SFT-015, SFT-016) | — |
| Savings interest + 80TTA | AIS (SFT-014) | — |
| Dividends | AIS (SFT-011) | — |
| Rent received (let-out) | AIS (SFT-013) | Always verify with manual entry |
| TDS cross-check | Form 26AS | — |
| 80C, 80D self, 80E, 80G (employer-routed) | Form 16 | — |
| 80D parents | — | Always manual (insurance certificate) |
| Home loan interest 24(b) | Form 16 (if employer-routed) | Bank interest certificate |
| Capital gains | Broker P&L PDF / CAMS statement | Property sales always manual |
| Family pension | AIS (sometimes) | Usually manual |
| Assets & liabilities | — | Always manual |
