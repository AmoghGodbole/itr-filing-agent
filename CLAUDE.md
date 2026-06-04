# ITR Filing Agent — Project Context

## What this is
A Python-based ITR (Indian Income Tax Return) filing engine for CAs (Chartered Accountants) who file on behalf of clients. The CA is already authorized to file — this tool handles the computation and JSON generation. ERI registration is deferred to a future version.

## Stack
- **Engine:** Python (`engine/`)
- **API:** FastAPI (`api/`)
- **UI:** Next.js + Tailwind (`ui/`)
- **LLM:** Anthropic Claude — `PARSER_MODEL` env var controls the model
  - Dev: `claude-haiku-4-5`
  - Prod: `claude-opus-4-8`
- **Python env:** Always use `.venv/bin/python` — system Python is externally managed on macOS

## Core pipeline
Form 16 PDF + AIS JSON + Form 26AS PDF → Claude parsers → tax engine → ITR-1 JSON → portal upload

## Key files
| File | Purpose |
|---|---|
| `engine/parsers/form16_parser.py` | Claude-powered Form 16 PDF extractor |
| `engine/parsers/ais_parser.py` | AIS JSON parser — rule-based + Claude fallback |
| `engine/parsers/form26as_parser.py` | Form 26AS PDF/text parser via Claude |
| `engine/parsers/_claude_utils.py` | Shared Claude client helpers |
| `engine/computation/tax_engine.py` | Old vs new regime comparison, FY 2024-25 slabs, HRA computation |
| `engine/itr_generator/itr1_generator.py` | ITR-1 JSON in IT portal schema |
| `engine/models.py` | Form 16 data models |
| `engine/models_ais.py` | AIS data models |
| `engine/pipeline.py` | End-to-end CLI orchestrator |
| `api/main.py` | FastAPI app entry point |
| `api/routes/itr.py` | `/api/parse` and `/api/generate` routes |
| `api/schemas.py` | Pydantic request/response schemas |
| `ui/src/app/page.tsx` | Main 3-step CA UI (upload → review → download) |
| `ui/src/components/` | Step, RegimeCard, MismatchBanner components |

## What's done (P0 — complete)
- [x] Form 16 parser
- [x] AIS parser (FD interest, dividends, savings interest, TDS)
- [x] Form 26AS parser (TDS cross-validation, mismatch flagging)
- [x] HRA exemption computation (`compute_hra_exemption` in tax_engine.py)
- [x] Tax engine — old vs new regime, FY 2024-25 slabs, 87A rebate, surcharge, cess, 80TTA
- [x] ITR-1 JSON generator
- [x] FastAPI backend (`/api/parse`, `/api/generate`)
- [x] CA-facing UI — 3-step flow: upload docs → review/edit + enter bank/Aadhaar → download ITR JSON

Tested against a real J P Morgan employee Form 16 (FY 2023-24). New regime recommended, ₹18,200 refund computed correctly.

## What's left

### P1 — More taxpayer coverage
- Rental income (let-out property) — annual rent, municipal taxes, home loan interest on that property (manual)
- Senior citizen slabs — DOB input, different basic exemption limits for age 60–80 and 80+
- 80D parents health insurance tier — always manual (insurance certificate); +₹25k or +₹50k if senior parents
- Multiple Form 16s — two employers in one FY, merge salary + sum TDS
- **Home loan interest via bank certificate** — for employees whose 24(b) is not routed through employer (manual field, engine cap already implemented)
- **80GG** — rent deduction for employees with no HRA component in salary (manual, same inputs as HRA)

### P2 — Expanded scope
- Capital gains (ITR-2) — STCG/LTCG from equity/MF (broker P&L PDF / CAMS statement) and property (manual)
- ITR-2 generator
- Schedule AL (assets & liabilities) — required if income > ₹50L, always manual
- 80EEA — affordable housing extra home loan deduction (manual)
- ERI registration + direct filing via IT department API
- IT portal login + auto AIS/26AS fetch (Playwright)

## HRA — two paths (important)
- **Path 1:** Employer computed it → Form 16 Part B has `hra_exempt` → engine uses it directly, manual box is irrelevant
- **Path 2:** Employee didn't declare rent to employer → Form 16 shows ₹0 → CA enters monthly rent + city → engine computes
- There is no third document source for rent data — manual entry is correct and complete

## Data source map (what comes from where)
| Income / Deduction | Source |
|---|---|
| Salary, exemptions, most deductions, TDS | Form 16 |
| FD/RD/bond interest, savings interest, dividends | AIS |
| TDS cross-validation | Form 26AS |
| HRA (if employer-computed) | Form 16 |
| HRA (if not declared to employer) | Manual — monthly rent + city |
| 80D parents, home loan bank certificate, family pension, donations not via employer | Always manual |
| Capital gains | Broker P&L PDF / CAMS statement (P2) |
| Property sale gains, assets & liabilities | Always manual |

## AIS structure notes
Portal: incometax.gov.in → Services → Annual Information Statement → Download JSON

SFT codes we care about:
- `SFT-014` — savings account interest (80TTA eligible)
- `SFT-015`, `SFT-016` — FD/RD/bond interest
- `SFT-011` — dividends
- `SFT-013` — rent received
- `SFT-001` — salary (skipped, covered by Form 16)

## Tax rules implemented (FY 2024-25 / AY 2025-26)
- Old regime: ₹2.5L / 5L / 10L slabs at 0% / 5% / 20% / 30%
- New regime: ₹3L / 7L / 10L / 12L / 15L slabs at 0% / 5% / 10% / 15% / 20% / 30%
- Standard deduction: ₹50k (old), ₹75k (new)
- 87A rebate: ≤₹5L → ₹12,500 (old); ≤₹7L → ₹25,000 (new)
- 80C cap: ₹1.5L | 80D self cap: ₹25k | 80CCD(1B) NPS: ₹50k
- 80TTA savings interest deduction: ₹10k cap
- Section 24(b) home loan interest: ₹2L cap
- HRA: min(actual HRA, 50%/40% basic, rent − 10% basic)

## Future scope
See `FUTURE_SCOPE.md` for deferred decisions (hybrid parser, ERI, OCR, senior citizen slabs, etc.)
