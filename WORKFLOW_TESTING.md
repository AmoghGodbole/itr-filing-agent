# ITR Filing Agent — Test Scenarios

Start the system before running any scenario:
```bash
# Terminal 1 — API
cd /path/to/itr-filing-agent
.venv/bin/uvicorn api.main:app --reload --port 8000

# Terminal 2 — UI
cd ui && npm run dev
```
Open: http://localhost:3000

---

## Scenario 1 — Straightforward salaried employee (ITR-1)

**Profile:** Single employer, no investments beyond what employer already computed. No rent, no FDs, no capital gains.

**Step 1 — Upload**
- Form 16 PDF: upload any Form 16
- Leave all other upload fields blank

**Step 2 — Review**
- Verify name, PAN, employer name auto-populated
- Verify gross salary, HRA, standard deduction look correct
- Enter bank account details and Aadhaar
- Leave all manual fields (rent, 80D parents, home loan cert) at zero

**Step 3 — Generate**
- Click Generate
- Expect: ITR-1 badge, regime recommendation shown, refund or tax payable displayed
- Download JSON — open it and confirm `FormName: "ITR-1"`

**Pass criteria:** JSON has `ITR-1`, `TotalIncome` matches salary minus standard deduction minus Chapter VI-A.

---

## Scenario 2 — Salaried + FD interest + dividends (ITR-1 with AIS)

**Profile:** Employee with fixed deposits and mutual fund dividends. AIS downloaded from IT portal.

**Step 1 — Upload**
- Form 16 PDF: upload Form 16
- AIS JSON: upload AIS JSON from IT portal

**Step 2 — Review**
- AIS section should appear showing FD interest and dividend income broken down by bank/source
- Verify `total_interest` and `total_dividends` figures
- Note: if you edit any individual AIS entry amount, the totals update automatically
- Enter bank details

**Step 3 — Generate**
- Expect: `IncomeOthSrc` in JSON = FD interest + dividends (after 80TTA savings deduction)
- Old regime: 80TTA deduction (up to ₹10,000) applied on savings account interest only
- New regime: no 80TTA, full interest taxable

**Pass criteria:** `IncomeOthSrc` > 0, `Section80TTA` in `DeductionUndChapVIA` reflects savings interest (old regime).

---

## Scenario 3 — Rent paid but not declared to employer (ITR-1, manual HRA)

**Profile:** Employee receives HRA in salary but declared ₹0 rent to employer — Form 16 shows `hra_exempt = 0`. CA claims exemption while filing.

**Step 1 — Upload**
- Form 16 PDF only

**Step 2 — Review**
- Notice HRA exemption shows ₹0 (as parsed from Form 16)
- Enter: Monthly rent = e.g. ₹25,000 | City = Mumbai (metro)
- The HRA exemption field should update in the regime preview

**Step 3 — Generate**
- Old regime: HRA exemption = min(HRA received, 50% basic, annual rent − 10% basic)
- New regime: HRA exemption = ₹0 (not allowed under new regime)
- Expect old regime to show lower tax due to HRA claim

**Pass criteria:** Old regime `hra_exemption_claimed` > 0, new regime = 0. Old regime likely recommended.

---

## Scenario 4 — No HRA component, paying rent (80GG, ITR-1)

**Profile:** Employee whose salary structure has zero HRA component (e.g. some PSU/startup structures). Pays rent — claims 80GG instead of HRA.

**Step 1 — Upload**
- Form 16 PDF where HRA = ₹0 in salary breakdown

**Step 2 — Review**
- Enter: Monthly rent = e.g. ₹15,000 | City = Pune (non-metro)
- No HRA exemption field should show (it's auto-suppressed when HRA component = 0)

**Step 3 — Generate**
- Expect: `Section80GG` in Chapter VI-A (old regime)
- 80GG = min(annual rent − 10% GTI, 25% GTI, ₹60,000)
- New regime: no 80GG

**Pass criteria:** `deduction_80gg_claimed` > 0 in old regime result, `Section80GG` in JSON.

---

## Scenario 5 — Job change mid-year (two Form 16s, ITR-1)

**Profile:** Employee switched jobs in October. Has Form 16 from Employer A (Apr–Oct) and Employer B (Nov–Mar).

**Step 1 — Upload**
- Form 16 PDF (Employer A) in the primary slot
- Form 16 PDF (Employer B) in the "Second Employer" slot

**Step 2 — Review**
- Both employers should show with their individual salary and TDS figures
- Merged totals (gross salary = A + B, TDS = A + B) shown at top
- Verify PAN and assessment year match — mismatch will show an error

**Step 3 — Generate**
- `ScheduleTDS1` in JSON must have two entries — one per employer
- Combined gross salary and TDS should equal the sum

**Pass criteria:** JSON `ScheduleTDS1` is an array of 2 objects with different TANs.

---

## Scenario 6 — Home loan (self-occupied, ITR-1)

**Profile:** Employee has a home loan but either (a) declared it to employer and Form 16 reflects it, or (b) has a bank certificate with a different figure.

**Step 1 — Upload**
- Form 16 PDF

**Step 2 — Review**
- If Form 16 already has home loan interest: verify the parsed `home_loan_interest_24b` value
- To override with bank certificate: enter the bank certificate figure in "Home Loan Interest (Bank Certificate)" field
- Bank cert overrides Form 16 value; capped at ₹2,00,000

**Step 3 — Generate**
- Old regime: `TotalIncomeOfHP` = negative (home loan creates HP loss)
- New regime: home loan interest = ₹0 (not deductible)

**Pass criteria:** Old regime JSON `TotalIncomeOfHP` is negative (up to −2,00,000).

---

## Scenario 7 — Senior citizen (ITR-1, different slabs + 80TTB)

**Profile:** Taxpayer aged 65 — senior citizen slabs apply, 80TTB replaces 80TTA.

**Step 1 — Upload**
- Form 16 PDF
- AIS JSON (to show FD interest)

**Step 2 — Review**
- Enter Date of Birth: e.g. 15/06/1960
- Basic exemption limit for old regime changes to ₹3,00,000
- With AIS: 80TTB (up to ₹50,000 on all deposit interest) replaces 80TTA

**Step 3 — Generate**
- Old regime uses senior citizen slabs (₹3L / ₹5L / ₹10L at 0% / 5% / 20% / 30%)
- `Section80TTB` in Chapter VI-A (not Section80TTA)

**Pass criteria:** `Section80TTB` > 0, `Section80TTA` = 0 in JSON.

---

## Scenario 8 — Let-out property (rental income, ITR-1)

**Profile:** Employee rents out a flat. Receives ₹30,000/month rent, pays ₹12,000 municipal taxes, has ₹4,00,000 home loan interest on that property.

**Step 1 — Upload**
- Form 16 PDF

**Step 2 — Review**
- Enter in the "Let-Out Property" section:
  - Annual rent: ₹3,60,000
  - Municipal taxes: ₹12,000
  - Home loan interest on rental property: ₹4,00,000

**Step 3 — Generate**
- Annual value = ₹3,60,000 − ₹12,000 = ₹3,48,000
- Standard deduction (Sec 24a) = 30% of AV = ₹1,04,400
- Net HP income = ₹3,48,000 − ₹1,04,400 − ₹4,00,000 = −₹1,56,400 (loss)
- HP loss set off against salary capped at ₹2,00,000 (this loss is within cap)
- `TotalIncomeOfHP` = −₹1,56,400

**Pass criteria:** `TotalIncomeOfHP` is negative, total taxable income reduced.

---

## Scenario 9 — Capital gains from equity MF (ITR-2)

**Profile:** Taxpayer sold equity mutual funds during the year. Broker (Zerodha/Groww) P&L PDF available.

**Step 1 — Upload**
- Form 16 PDF
- Broker Capital Gains P&L PDF (in the "Broker CG PDF" slot)

**Step 2 — Review**
- Capital Gains section appears with parsed pre/post Jul 23, 2024 split
- Verify STCG and LTCG figures against your broker statement
- Edit any mis-parsed values directly

**Step 3 — Generate**
- Expect: **ITR-2** badge
- STCG pre-Jul 23: taxed at 15% (Sec 111A)
- STCG post-Jul 23: taxed at 20%
- LTCG pre-Jul 23: taxed at 10% after ₹1,00,000 exemption (Sec 112A)
- LTCG post-Jul 23: taxed at 12.5% after ₹1,25,000 exemption
- JSON has `ScheduleCGFor23` and `ScheduleSI`

**Pass criteria:** `FormName: "ITR-2"`, `ScheduleCGFor23` has non-zero buckets, `ScheduleSI` has rate entries.

---

## Scenario 10 — Property sale (ITR-2, manual CG entry)

**Profile:** Taxpayer sold a residential flat held for 3+ years. No broker PDF — all manual.

**Step 1 — Upload**
- Form 16 PDF only

**Step 2 — Review**
- In the Capital Gains section, scroll to "Property Gains"
- Enter LTCG (choose one):
  - If acquired before Jul 23, 2024: enter in "LTCG with indexation (20%)" OR "LTCG without indexation (12.5%)" — whichever gives lower tax (mutually exclusive, system will reject if both non-zero)
  - If acquired after Jul 23, 2024: enter in "LTCG without indexation (12.5%)"

**Step 3 — Generate**
- Expect: ITR-2, property LTCG in `LongTermCapGain20Per` or `LongTermCapGain125PerWithoutIndex`

**Pass criteria:** Only one of the two property LTCG buckets is non-zero in the JSON.

---

## Scenario 11 — F&O trader (ITR-3)

**Profile:** Salaried employee who also trades futures & options. Has F&O P&L from Zerodha.

**Step 1 — Upload**
- Form 16 PDF
- F&O P&L PDF (in the "F&O P&L PDF" slot)

**Step 2 — Review**
- F&O section appears: segments (equity futures, equity options, etc.), gross profit, gross loss, turnover
- Add business expenses if any (brokerage, STT, exchange fees, internet)
- If there are prior-year F&O losses from previous ITRs, add them in "Carry Forward Losses" (assessment year + amount)

**Step 3 — Generate**
- Expect: **ITR-3** badge
- If turnover > ₹10Cr or net loss declared: audit warning shown
- JSON has `ScheduleBP`, `ScheduleBFLA`, `ScheduleCFL`
- F&O income (profit after expenses and set-off) added to slab taxable income

**Pass criteria:** `FormName: "ITR-3"`, `ScheduleBP.NetIncomeFromFO` matches computed net, `AuditInformation.TaxAuditRequired` is true/false correctly.

---

## Scenario 12 — F&O + capital gains (ITR-3 with CG)

**Profile:** Trader with both F&O income and equity MF capital gains in the same year.

**Step 1 — Upload**
- Form 16 PDF
- Broker Capital Gains P&L PDF
- F&O P&L PDF

**Step 2 — Review**
- Both CG section and F&O section appear
- Fill in both sets of figures

**Step 3 — Generate**
- Expect: **ITR-3** (F&O takes priority over ITR-2)
- JSON has both `ScheduleBP` (F&O) and `ScheduleCGFor23` (capital gains)

**Pass criteria:** `FormName: "ITR-3"`, both Schedule BP and Schedule CG present and non-empty.

---

## Scenario 13 — High income requiring Schedule AL (ITR-2/3)

**Profile:** Taxpayer with total income > ₹50L — Schedule AL (assets & liabilities) is mandatory.

**Step 1 — Upload**
- Form 16 PDF reflecting high salary (> ₹50L gross), or combine with capital gains to cross ₹50L

**Step 2 — Review**
- Schedule AL section appears automatically when total income is likely to exceed ₹50L
- Fill in:
  - Immovable properties: add each property (description, address, value)
  - Movable assets: jewellery, vehicles, etc.
  - Financial assets: bank balances, shares, insurance surrender value
  - Liabilities: outstanding home loan, other loans
- Live net-worth preview updates as you type

**Step 3 — Generate**
- Expect: `ScheduleAL` present in the JSON
- Total assets and total liabilities match what was entered

**Note:** If total income (including special-rate capital gains) is ≤ ₹50L, Schedule AL is silently omitted even if you fill it in — this is correct per the IT Act.

**Pass criteria:** `ScheduleAL` key exists in JSON, `TotalAssets` and `TotalLiabilities` are non-zero.

---

## Common things to verify across all scenarios

| Check | What to look for |
|---|---|
| Regime recommendation | Old vs New; savings amount shown |
| Refund / payable | Positive = refund, negative = payable |
| TDS reconciliation | `TotalTaxesPaid` = Form 16 TDS + AIS TDS |
| Form 26AS mismatch | Red banner if TDS in 26AS ≠ Form 16 TDS |
| ITR form selected | Badge shows ITR-1 / ITR-2 / ITR-3 |
| JSON validity | All amounts are integers (portal rejects floats) |
