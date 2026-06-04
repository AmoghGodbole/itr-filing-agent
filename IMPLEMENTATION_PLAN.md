# Implementation Plan

Stepwise build order. Each step has a clear done definition and can be
committed independently. Steps within a phase can sometimes overlap but the
phase order is strict — later phases depend on earlier ones.

---

## Phase 1 — Local infrastructure

### Step 1: Docker Compose + environment

**What:**
- `docker-compose.yml` — Postgres 16 + MinIO
- `.env.example` updated with all required variables
- `docker-compose.yml` added to `.gitignore` overrides (data volumes never committed)

**Done when:**
- `docker compose up -d` starts both services with no errors
- `psql` connects to `localhost:5432`
- MinIO console loads at `localhost:9001`

---

### Step 2: Alembic setup + migrations

**What:**
- `alembic init alembic` in project root
- `alembic/env.py` configured to use `DATABASE_URL` from env
- One migration file per table, in dependency order:
  1. `organisations`
  2. `users`
  3. `clients`
  4. `filings`
  5. `filing_revisions`
  6. `documents`
- Indexes on all FK columns and frequently filtered columns
  (`org_id`, `assessment_year`, `status`, `pan`)

**Done when:**
- `alembic upgrade head` runs clean on a fresh DB
- `alembic downgrade base` rolls everything back cleanly
- All six tables exist with correct columns, constraints, and indexes

---

### Step 3: SQLAlchemy models

**What:**
- `api/db/models.py` — six SQLAlchemy ORM models:
  `Organisation`, `User`, `Client`, `Filing`, `FilingRevision`, `Document`
- `api/db/session.py` — async engine + `get_db` dependency
- `api/db/base.py` — declarative base with `created_at` / `updated_at`
  auto-populated via `server_default` and `onupdate`

**Done when:**
- All models importable with no errors
- `Organisation` → `User` → `Client` → `Filing` → `FilingRevision` /
  `Document` relationships navigable in both directions
- A simple `pytest` fixture can create and query all six models against
  the local DB

---

### Step 4: Seed script

**What:**
- `scripts/seed.py` — idempotent (safe to run multiple times)
- Creates:
  - 1 org: `"Sharma & Associates"`
  - 1 owner: `ca@sharma.com` / `test1234`
  - 2 members: `priya@sharma.com`, `rahul@sharma.com` / `test1234`
  - 5 clients with realistic names and PANs
  - Filings in all four statuses (`draft`, `reviewed`, `generated`, `filed`)
    spread across the three users, so the admin views have something to show
- Prints a summary of what was created

**Done when:**
- `python scripts/seed.py` runs clean on a freshly migrated DB
- All seed rows visible in the DB
- Running it twice does not create duplicates

---

## Phase 2 — Authentication

### Step 5: FastAPI auth routes + JWT middleware

**What:**
- `api/routes/auth.py`:
  - `POST /auth/register` — creates org + owner in a single transaction;
    returns JWT
  - `POST /auth/login` — verifies email + bcrypt password; returns JWT
  - `POST /auth/invite` — owner only; creates a `pending` user row and
    sends an invite email (local: prints to console, prod: sends via SMTP)
  - `POST /auth/accept-invite` — invited user sets their password;
    activates their account
- JWT payload: `{ user_id, org_id, role, exp }`
- `api/middleware/auth.py` — FastAPI dependency that verifies JWT on
  every request, injects `CurrentUser` dataclass into route handlers
- All existing routes in `api/routes/itr.py` updated to require auth

**Done when:**
- Register → login → call a protected route works end-to-end via
  `localhost:8000/docs`
- A request with no JWT gets 401
- A request with a valid JWT but wrong `org_id` manipulation gets 403
  (org_id always comes from token, never from request body)
- `POST /auth/invite` from a member account gets 403

---

### Step 6: NextAuth.js credentials provider

**What:**
- `npm install next-auth` in `ui/`
- `ui/src/app/api/auth/[...nextauth]/route.ts` — credentials provider
  that calls `POST /auth/login` on the FastAPI backend
- Session carries `{ user_id, org_id, role, name, email }`
- `ui/src/middleware.ts` — Next.js middleware:
  - `/dashboard/*` — redirect to `/login` if no session
  - `/admin/*` — redirect to `/dashboard` if session exists but
    `role !== owner`
  - `/login`, `/register` — redirect to `/dashboard` if already logged in
- `ui/src/lib/auth.ts` — typed `useSession` hook + `getServerSession` helper
- Login page at `/login`
- Register page at `/register` (creates org + owner)
- Accept-invite page at `/invite/[token]`

**Done when:**
- Register creates org + owner; redirects to `/dashboard`
- Login redirects to `/dashboard`; logout clears session
- Unauthenticated visit to `/dashboard` redirects to `/login`
- Member visiting `/admin` is redirected to `/dashboard`
- Session `org_id` and `role` are accessible in every page component

---

## Phase 3 — Core UI

### Step 7: Landing page

**What:** `ui/src/app/page.tsx` replaced with a proper landing page.
Current filing UI moves to `ui/src/app/dashboard/...` (Step 8).

Landing page sections:
- **Nav** — logo, Features anchor, Sign In, Get Started
- **Hero** — headline, subheadline, two CTAs (Get Started / Sign In)
- **How it works** — 3 steps (Upload → Review → Download), visual
- **Features grid** — 6 cards:
  - Form 16 + AIS → ITR-1/2/3 automatically
  - Old vs new regime comparison
  - Capital gains (Budget 2024 pre/post Jul 23 split)
  - F&O income with audit flag
  - Schedule AL for high-income clients
  - Audit-ready revision history
- **Footer** — GitHub, SCHEMA.md link (docs), contact email

**Done when:**
- `/` renders the landing page for logged-out users
- "Get Started" links to `/register`
- "Sign In" links to `/login`
- Page is responsive (Tailwind)

---

### Step 8: Dashboard — client list

**What:** `ui/src/app/dashboard/page.tsx`

- Lists all clients belonging to the current org (fetched from new
  `GET /api/clients` route)
- Each client row shows: name, PAN, current AY filing status, assigned to,
  last modified at
- "New Client" button → modal or inline form (name, PAN, DOB, email, mobile)
- Clicking a client opens their filing list
- Search / filter by name or PAN

**New API routes:**
- `GET /api/clients` — list all clients in org (paginated)
- `POST /api/clients` — create client
- `GET /api/clients/{id}/filings` — list filings for a client
- `POST /api/clients/{id}/filings` — create new filing for AY

**Done when:**
- Seed data visible in the dashboard immediately after login
- New client created via form appears in list
- All queries return only this org's data (verify by checking SQL logs)

---

### Step 9: Filing UI — moved and wired to DB

**What:**
Current `ui/src/app/dashboard/page.tsx` (Step 1 filing flow) moves to:
`ui/src/app/dashboard/clients/[clientId]/filings/[ay]/page.tsx`

Changes from current:
- On load: fetch filing from `GET /api/filings/{id}` — pre-populate all
  fields from `filings.*_reviewed` if they exist, else from `*_raw`
- Step 1 (Upload): `POST /api/parse` now also saves parsed data to
  `filings.parsed_*_raw` and `documents` rows
- Step 2 (Review): changes auto-saved to `filings.*_reviewed` on edit
  (debounced `PATCH /api/filings/{id}`)
- Step 3 (Generate): `POST /api/generate` now also:
  - Updates `filings.itr_json`, `computation_result`, `itr_form`,
    `recommended_regime`, `status = generated`
  - Writes a new `filing_revisions` row (full snapshot)
  - Sets `filings.last_modified_by = current_user`
- "Mark as Filed" button: `PATCH /api/filings/{id}` with
  `{ status: filed, acknowledgement_number: "..." }`

**New API routes:**
- `GET /api/filings/{id}` — fetch filing with all parsed + reviewed data
- `PATCH /api/filings/{id}` — partial update (manual inputs, reviewed data,
  status, acknowledgement number)
- `GET /api/filings/{id}/revisions` — list revision history
- `GET /api/filings/{id}/revisions/{rev_num}` — fetch a specific revision
  (for audit / comparison)

**Done when:**
- Refreshing the page mid-review does not lose any entered data
- Generating ITR creates a revision row (verify in DB)
- Two browser tabs (simulating two staff) can both see the same filing;
  last save wins (no conflict UI needed for v1)
- `assigned_to` updated when a user opens a filing (optional soft-claim)

---

### Step 10: S3 wiring

**What:**
- `api/services/storage.py` — boto3 client configured from env;
  `upload_file(key, data)`, `generate_presigned_url(key, expiry=900)`
- Upload flow in `POST /api/parse`:
  1. Stream each uploaded file to MinIO/S3 under
     `{org_id}/{filing_id}/{doc_type}/{uuid}_{filename}`
  2. Insert `documents` row with `parse_status = processing`
  3. Parse with Claude
  4. Update `documents.parse_status = success | failed`
  5. Save parsed JSON to `filings.parsed_*_raw`
- Download: `GET /api/filings/{id}/documents/{doc_id}/url` returns a
  15-minute pre-signed URL; frontend opens it in a new tab

**Done when:**
- Upload a PDF via the filing UI; verify the file appears in MinIO console
  at the correct key path
- Parsing failure sets `parse_status = failed` with an error message;
  CA can retry without re-uploading
- Pre-signed URL opens the file in a new tab and expires after 15 minutes

---

## Phase 4 — Admin

### Step 11: Admin — team management

**What:** `ui/src/app/admin/team/page.tsx`

- Member table: name, email, role, status (active/inactive), filing count,
  last active
- **Invite** — form: name + email → calls `POST /auth/invite` → shows
  "Invite sent" (local: logs invite link to console)
- **Deactivate** — confirmation modal → `PATCH /api/admin/users/{id}`
  with `{ is_active: false }`
- **Reactivate** — same endpoint with `{ is_active: true }`
- **Reassign** — select a member → "Reassign all open filings to..." →
  dropdown of active members → `POST /api/admin/users/{id}/reassign`
  which bulk-updates `filings.assigned_to`

**New API routes (owner only):**
- `GET /api/admin/users` — list all users in org with filing counts
- `PATCH /api/admin/users/{id}` — update `is_active` or `role`
- `POST /api/admin/users/{id}/reassign` — bulk reassign filings

**Done when:**
- Invite creates a user row; invite link printed to console (local)
- Deactivating a member blocks their login (verify by logging in as them)
- Bulk reassign updates all open filings (verify in DB)
- Member cannot access `/admin/team` (middleware blocks, gets redirected)

---

### Step 12: Admin — filing oversight

**What:** `ui/src/app/admin/filings/page.tsx`

- Table of all filings across the org
- Columns: client name + PAN, AY, status badge, assigned to, last modified
  by, last modified at, ITR form (once generated), acknowledgement (once filed)
- Filters: status, assigned member, assessment year, client search
- **Stuck alert** — banner at top listing filings in `draft` or `reviewed`
  status not touched in 7+ days, with quick-reassign action
- Clicking a row opens the filing (same URL as Step 9)

**New API routes:**
- `GET /api/admin/filings` — list all filings in org with filter params;
  includes `is_stuck` flag (not modified in 7 days + not filed)

**Done when:**
- Seed data shows filings in all statuses
- Stuck alert appears for filings untouched for 7+ days
- Filters narrow the table correctly
- Clicking a row opens the filing UI

---

### Step 13: Admin — audit trail

**What:** `ui/src/app/admin/audit/page.tsx`

Two sections:

**Per-filing revision log** (opened from a filing page):
- List of all revisions for that filing: revision number, generated by,
  generated at, change summary
- Each row has a "Download ITR JSON" button — calls
  `GET /api/filings/{id}/revisions/{rev_num}` and triggers download
- "Compare" — side-by-side diff of manual inputs between two revisions
  (highlight what changed: regime, deductions, etc.)

**Org-wide activity feed** (on `/admin/audit`):
- Last 100 actions across the org: who generated/filed/modified what,
  with timestamps
- Derived from `filing_revisions` + `filings.updated_at` +
  `filings.last_modified_by` — no separate activity log table

**Done when:**
- Generating an ITR twice creates two revision rows visible in the log
- Downloading a historical revision returns that version's ITR JSON,
  not the current one
- Activity feed shows the seed users' actions

---

### Step 14: Admin — settings

**What:** `ui/src/app/admin/settings/page.tsx`

- Org name — editable, `PATCH /api/admin/org`
- Owner name + email — editable (email change requires re-login)
- Change password — `POST /api/admin/change-password` (current + new)
- Danger zone — deactivate org (requires typing firm name to confirm);
  deferred to future version (button present but disabled with tooltip)

**New API routes:**
- `PATCH /api/admin/org` — update org name
- `POST /api/admin/change-password` — owner password change

**Done when:**
- Org name change reflected immediately in the nav
- Password change invalidates existing sessions (logout required)

---

## Summary

| Phase | Steps | What you get |
|---|---|---|
| 1 — Infrastructure | 1–4 | Postgres + MinIO running locally, all tables migrated, seed data |
| 2 — Auth | 5–6 | Register, login, protected routes, role-based access |
| 3 — Core UI | 7–10 | Landing page, client dashboard, filing UI wired to DB, files in S3 |
| 4 — Admin | 11–14 | Team management, filing oversight, audit trail, org settings |

**Total: 14 steps across 4 phases.**

Each step is a self-contained commit. Phase 1 and 2 are pure backend/infra —
no UI changes. Phase 3 replaces the current single-page prototype with a
proper multi-page app. Phase 4 adds the owner-only admin surface.

The existing engine, parsers, tax computation, ITR generators, BDD tests, and
Playwright tests remain untouched throughout — they are called by the updated
API routes, not rewritten.
