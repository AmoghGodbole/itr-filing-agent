# Project Context

## How to resume a session

Read these four files in order. That is all you need — no conversation history required.

| File | What it covers |
|---|---|
| `CLAUDE.md` | Engine, stack, what is built, key files, data source map |
| `SCHEMA.md` | 6 DB tables, auth model, org isolation, admin layer design |
| `IMPLEMENTATION_PLAN.md` | 14 steps across 4 phases, done criteria for each step |
| `TESTING_STRATEGY.md` | BDD + Playwright architecture, how mocks work |

---

## What this project is

An ITR (Indian Income Tax Return) filing engine for CA firms. A CA uploads
their client's documents (Form 16, AIS, broker P&L), the engine parses them
via Claude, computes old vs new regime tax, and generates a ready-to-upload
ITR-1 / ITR-2 / ITR-3 JSON for the IT portal.

---

## Current state (as of last update)

### Engine — complete
- Form 16, AIS, Form 26AS, capital gains, F&O parsers (Claude-powered)
- Tax engine: old/new regime, FY 2024-25 slabs, HRA, 80GG, 80TTB, 80EEA,
  let-out property, family pension, senior/super-senior citizen slabs,
  Budget 2024 pre/post Jul-23 CG rate split, F&O business income,
  Schedule AL threshold check
- ITR-1, ITR-2, ITR-3 JSON generators
- Multi-broker PDF support (merge_capital_gains, merge_fo_data)

### API — complete
- `POST /api/parse` — accepts multiple PDFs per broker, returns parsed data
- `POST /api/generate` — computes tax, selects ITR form, returns JSON

### UI — complete (prototype, not yet wired to DB)
- 3-step CA flow: Upload → Review & edit → Download ITR JSON
- Capital gains, F&O, Schedule AL, senior citizen DOB, all manual fields

### Tests — complete
- 39 BDD scenarios (pytest-bdd) — engine correctness, runs in 0.1s
- 13 Playwright E2E scenarios — full UI flow, API mocked via page.route()
- 52 tests total, all green

### What is not built yet
- Database (Postgres + Alembic + SQLAlchemy models)
- Authentication (NextAuth.js + FastAPI JWT)
- Organisation / multi-user / multi-tenant layer
- Client and filing management (dashboard)
- Filing UI wired to DB (currently stateless prototype)
- S3 file storage
- Admin panel
- Landing page

The implementation plan in `IMPLEMENTATION_PLAN.md` covers all of the above
across 14 steps. Start at Phase 1, Step 1.

---

## Stack

| Layer | Technology |
|---|---|
| Engine | Python — `engine/` |
| API | FastAPI — `api/` |
| UI | Next.js + Tailwind — `ui/` |
| LLM | Anthropic Claude (`PARSER_MODEL` env var) |
| DB (planned) | PostgreSQL + SQLAlchemy + Alembic |
| Auth (planned) | NextAuth.js (UI) + JWT middleware (API) |
| File storage (planned) | S3 / MinIO (local) |
| Tests | pytest-bdd + Playwright |

---

## Python environment

Always use `.venv/bin/python`. System Python is externally managed on macOS.

```bash
.venv/bin/uvicorn api.main:app --reload   # API
cd ui && npm run dev                       # UI
.venv/bin/pytest tests/                   # all tests
.venv/bin/pytest tests/bdd/               # BDD only (0.1s)
.venv/bin/pytest tests/e2e/               # Playwright only (~17s)
```

---

## Repository

GitHub: https://github.com/AmoghGodbole/itr-filing-agent
