# Database Schema

## Overview

PostgreSQL with SQLAlchemy ORM. Multi-tenant: one `organisations` row per CA
firm. All data (clients, filings, documents) is scoped to an org — any member
of the org can see and work on everything within it.

JSON columns for variable-schema blobs (parsed documents, computation results,
ITR output). Files (PDFs, AIS JSON) stored in S3-compatible object storage;
only the S3 key lives in the DB.

All tables have `created_at` and `updated_at`. Every query that touches client
or filing data filters by `org_id` — one firm cannot see another firm's data.

---

## Tables

### `organisations`

One row per CA firm. This is the top-level tenant. All clients and filings
belong to an org, not to an individual user.

```sql
organisations
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
  name            TEXT NOT NULL                -- "Sharma & Associates"
  is_active       BOOLEAN DEFAULT TRUE         -- soft-disable without deleting
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
```

---

### `users`

One row per person (CA owner or staff). A user belongs to exactly one org.
Cannot belong to multiple orgs. Role controls what they can do within their org.

```sql
users
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE
  email           TEXT UNIQUE NOT NULL
  name            TEXT NOT NULL
  password_hash   TEXT NOT NULL               -- bcrypt
  role            TEXT NOT NULL DEFAULT 'member'
                  -- owner  : full access + invite/remove staff
                  -- member : create/edit clients and filings; no staff management
  is_active       BOOLEAN DEFAULT TRUE        -- soft-disable (e.g. staff leaves)
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
```

**Invariants:**
- Each org has exactly one `owner` (the CA who created it)
- `owner` cannot be deactivated while the org is active
- A deactivated `member`'s work remains visible and editable by other members

---

### `clients`

One row per taxpayer. Belongs to the org, not to an individual user. Any
member of the org can open, edit, and file for any client.

```sql
clients
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE
  created_by      UUID NOT NULL REFERENCES users(id)    -- accountability only
  pan             TEXT NOT NULL
  name            TEXT NOT NULL
  date_of_birth   DATE
  email           TEXT
  mobile          TEXT
  notes           TEXT                                   -- free-text CA notes
  is_active       BOOLEAN DEFAULT TRUE
  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()

  UNIQUE (org_id, pan)           -- one client per PAN per firm
```

---

### `filings`

One row per client per assessment year. The **working copy** — holds the
current state of all inputs and outputs. When the CA clicks Generate, the
entire current state is snapshotted into `filing_revisions` (append-only) and
this row is updated in place.

```sql
filings
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid()
  org_id                  UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE
  client_id               UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE
  assessment_year         TEXT NOT NULL               -- "AY 2025-26"
  status                  TEXT NOT NULL DEFAULT 'draft'
                          -- draft | reviewed | generated | filed
  assigned_to             UUID REFERENCES users(id)   -- optional; who is handling this
  last_modified_by        UUID REFERENCES users(id)   -- last user to save changes

  -- ── Manual inputs (CA enters in Step 2) ─────────────────────────────────
  hra_monthly_rent            NUMERIC(12,2) DEFAULT 0
  hra_city                    TEXT DEFAULT ''
  parents_insurance_premium   NUMERIC(12,2) DEFAULT 0
  parents_senior              BOOLEAN DEFAULT FALSE
  home_loan_interest_cert     NUMERIC(12,2) DEFAULT 0
  rental_annual_rent          NUMERIC(12,2) DEFAULT 0
  rental_municipal_taxes      NUMERIC(12,2) DEFAULT 0
  rental_home_loan_interest   NUMERIC(12,2) DEFAULT 0
  family_pension              NUMERIC(12,2) DEFAULT 0
  home_loan_80eea             NUMERIC(12,2) DEFAULT 0
  date_of_birth               TEXT DEFAULT ''        -- overrides client DOB if corrected
  aadhaar                     TEXT
  mobile                      TEXT
  email                       TEXT
  bank_account_number         TEXT
  bank_ifsc                   TEXT
  bank_name                   TEXT
  bank_account_type           TEXT DEFAULT 'Savings' -- Savings | Current

  -- ── Parsed data — raw from Claude, before CA edits ──────────────────────
  -- Null until the corresponding document is uploaded and parsed.
  parsed_form16_raw       JSONB
  parsed_form16_2_raw     JSONB
  parsed_ais_raw          JSONB
  parsed_form26as_raw     JSONB
  parsed_cg_raw           JSONB
  parsed_fo_raw           JSONB

  -- ── CA-reviewed data — what actually goes into computation ───────────────
  -- Written when CA confirms Step 2. Null until review is complete.
  form16_reviewed         JSONB
  form16_2_reviewed       JSONB
  ais_reviewed            JSONB
  cg_reviewed             JSONB
  fo_reviewed             JSONB
  schedule_al             JSONB

  -- ── Computed output ──────────────────────────────────────────────────────
  -- Written when CA clicks Generate.
  computation_result      JSONB
  itr_json                JSONB
  itr_form                TEXT           -- "ITR-1" | "ITR-2" | "ITR-3"
  recommended_regime      TEXT           -- "Old Regime" | "New Regime"

  -- ── Post-filing ──────────────────────────────────────────────────────────
  acknowledgement_number  TEXT           -- entered after portal upload
  filed_at                TIMESTAMPTZ
  filed_by                UUID REFERENCES users(id)

  created_at              TIMESTAMPTZ DEFAULT now()
  updated_at              TIMESTAMPTZ DEFAULT now()

  UNIQUE (client_id, assessment_year)    -- one filing per client per AY
```

---

### `filing_revisions`

**Append-only. Never updated or deleted.** One row written on every Generate.
Full snapshot of every input and output that produced the ITR. This is the
audit trail — a CA can reconstruct exactly what was computed and when.

```sql
filing_revisions
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
  filing_id           UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE
  org_id              UUID NOT NULL REFERENCES organisations(id)  -- for fast org-scoped queries
  revision_number     INTEGER NOT NULL               -- 1, 2, 3, ...
  generated_by        UUID NOT NULL REFERENCES users(id)

  -- Complete snapshot of inputs at generation time
  form16_snapshot     JSONB NOT NULL
  form16_2_snapshot   JSONB
  ais_snapshot        JSONB
  cg_snapshot         JSONB
  fo_snapshot         JSONB
  schedule_al_snapshot JSONB
  manual_inputs       JSONB NOT NULL                -- all numeric fields as JSON

  -- Complete snapshot of outputs
  computation_result  JSONB NOT NULL
  itr_json            JSONB NOT NULL
  itr_form            TEXT NOT NULL
  recommended_regime  TEXT NOT NULL

  -- Human-readable summary of what changed (auto-generated on write)
  change_summary      TEXT

  created_at          TIMESTAMPTZ DEFAULT now()     -- immutable; no updated_at

  UNIQUE (filing_id, revision_number)
```

---

### `documents`

One row per uploaded file. The file lives in S3; `storage_key` is the S3
object key. `parse_status` tracks whether Claude has processed it yet.

```sql
documents
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
  filing_id       UUID NOT NULL REFERENCES filings(id) ON DELETE CASCADE
  org_id          UUID NOT NULL REFERENCES organisations(id)  -- for fast scoped queries
  uploaded_by     UUID NOT NULL REFERENCES users(id)
  doc_type        TEXT NOT NULL
                  -- form16 | form16_2 | ais | form26as | broker_cg | fo_pl | bank_cert
  original_name   TEXT NOT NULL               -- filename shown in UI
  storage_key     TEXT NOT NULL UNIQUE        -- S3 object key
  size_bytes      INTEGER
  mime_type       TEXT
  parse_status    TEXT NOT NULL DEFAULT 'pending'
                  -- pending | processing | success | failed
  parsed_at       TIMESTAMPTZ
  parse_error     TEXT                        -- populated on failure; CA can retry

  created_at      TIMESTAMPTZ DEFAULT now()
  updated_at      TIMESTAMPTZ DEFAULT now()
```

---

## Entity relationships

```
organisations
  └── users (org_id)
  └── clients (org_id)
        └── filings (client_id, org_id)
              ├── filing_revisions (filing_id, org_id)   ← append-only
              └── documents (filing_id, org_id)
```

`org_id` is denormalised onto `filings`, `filing_revisions`, and `documents`
(even though it can be derived via joins) so that all org-scoped queries remain
single-table lookups without joins — important for list views with many rows.

---

## Authorization model

```
owner  → full access to all clients + filings within the org
         + invite / deactivate members
         + cannot be deactivated while org is active

member → full access to all clients + filings within the org
         cannot manage staff
```

Every API request:
1. FastAPI middleware extracts `user_id` and `org_id` from JWT
2. All queries filter by `org_id`
3. Staff-management endpoints additionally check `role = owner`

A deactivated member (`is_active = FALSE`) cannot log in. Their filings remain
intact and are immediately visible to the rest of the team.

---

## Multi-tenancy

Each org is fully isolated. There is no cross-org data access at any layer:
- DB: all queries carry `WHERE org_id = ?`
- API: `org_id` comes from the verified JWT, never from the request body
- S3: storage keys are prefixed with `org_id/` — `{org_id}/{filing_id}/{filename}`

Onboarding a new firm = insert one `organisations` row + one `users` row with
`role = owner`. No schema changes, no provisioning, no tenant-specific config.

---

## Key design decisions

### `org_id` on `clients` not `user_id`

Clients belong to the firm. When staff leaves (`is_active = FALSE`), their
clients and filings are still visible and editable by the rest of the team.
`created_by` on `clients` is accountability metadata only — it does not
restrict access.

### Why `assigned_to` is optional

Filings don't need to be formally assigned. Any member can open any filing.
`assigned_to` is a lightweight indicator ("I'm working on this") not an access
control mechanism. A member can pick up an unassigned filing or one assigned to
a colleague who is on leave.

### `org_id` denormalised on child tables

`filings`, `filing_revisions`, and `documents` all carry `org_id` even though
it's derivable via join. This lets us write `WHERE org_id = ?` on any table
without a join — critical for dashboard list views that scan thousands of rows.

### Raw vs reviewed data are separate

`parsed_form16_raw` = what Claude extracted.
`form16_reviewed` = what the CA confirmed (with edits).
Both are kept permanently so the audit trail shows CA intent: did the CA accept
the parser's output as-is, or did they correct something?

### `filing_revisions` is append-only

Every Generate writes a new revision row with a complete snapshot. Rows are
never updated or deleted. A CA can reconstruct the exact ITR JSON produced at
any point in time, see who generated it, and compare inputs across revisions.

---

## Authentication

**NextAuth.js** (credentials provider) on the Next.js side. Passwords are
bcrypt-hashed. Sessions are JWTs signed with a server secret.

The JWT payload carries:
```json
{ "user_id": "...", "org_id": "...", "role": "owner|member" }
```

FastAPI verifies the JWT on every request. `org_id` is extracted from the
token — never trusted from the request body.

---

## S3 key structure

```
{org_id}/{filing_id}/{doc_type}/{uuid}_{original_filename}
```

Example:
```
550e8400-e29b-41d4-a716-446655440000/
  7f3a1b2c-4d5e-6f7a-8b9c-0d1e2f3a4b5c/
    form16/
      a1b2c3d4_Form16_FY2024-25.pdf
    broker_cg/
      e5f6a7b8_Zerodha_PL_FY2024-25.pdf
```

Pre-signed URLs are generated on demand (15-minute expiry) so files are never
served directly through the application server.

---

## Admin layer (org owner only)

The admin surface is separate from the filing dashboard. The dashboard is for
doing work; the admin page is for overseeing and controlling the firm.
All `/admin/*` routes require `role = owner` — a `member` gets a 403.

### Routes

```
/admin                 → redirect to /admin/team
/admin/team            → member list, invite, deactivate, reassign
/admin/filings         → all filings across the org with filters
/admin/audit           → revision history and activity feed
/admin/settings        → firm name, owner profile
```

### /admin/team — Team management

The most critical section for the leave-handoff scenario.

| Feature | Detail |
|---|---|
| Member list | Name, email, role, is_active, last_active_at, filing count |
| Invite member | Sends a signup link scoped to the org; creates a pending user row |
| Deactivate member | Sets `is_active = FALSE`; blocks login immediately; work stays intact |
| Reactivate member | Sets `is_active = TRUE`; restores login access |
| Reassign filings | Bulk action — move all open filings from one member to another; critical when someone goes on leave mid-season |
| Per-member workload | How many filings assigned, broken down by status (draft / reviewed / generated / filed) |

Reassign writes `assigned_to` on all selected `filings` rows and appends a
`change_summary` entry to the next revision. The member going on leave is
deactivated in the same action.

### /admin/filings — Filing oversight

Full cross-org view of every filing. The owner sees what the team sees, plus
who owns each filing.

| Column | Source |
|---|---|
| Client name + PAN | `clients` |
| Assessment year | `filings.assessment_year` |
| Status | `filings.status` |
| Assigned to | `users.name` via `filings.assigned_to` |
| Last modified by | `users.name` via `filings.last_modified_by` |
| Last modified at | `filings.updated_at` |
| ITR form | `filings.itr_form` (once generated) |
| Acknowledgement | `filings.acknowledgement_number` (once filed) |

**Filters:** status, assigned member, assessment year, client name search.

**Stuck filings alert:** filings in `draft` or `reviewed` status not touched in
7+ days — surfaced at the top so the owner can reassign or follow up.

### /admin/audit — Audit trail

Where the revision history pays off. Owner can reconstruct exactly what was
computed, by whom, and when — useful for client disputes and internal review.

| Feature | Detail |
|---|---|
| Per-filing revision log | List of all revisions: who generated, when, `change_summary` |
| Download any revision | Pre-signed S3 URL or JSON download for any historical ITR JSON — not just the latest |
| Org-wide activity feed | Last N actions across all clients: who created/modified/generated/filed what |

The activity feed is derived from `filing_revisions.generated_by` +
`filing_revisions.created_at` + `filings.last_modified_by` — no separate
`activity_log` table needed for v1.

### /admin/settings — Org settings

| Field | Editable |
|---|---|
| Firm name | Yes |
| Owner name | Yes |
| Owner email | Yes (re-verification required) |

Billing and ERI registration details are deferred to a future version.

### What is deferred from admin v1

| Feature | Reason deferred |
|---|---|
| Analytics (filing volume, regime distribution) | Useful but not urgent; add when owners ask |
| Client merge (duplicate PAN) | Edge case; handle manually for now |
| Audit export (CSV download of activity log) | Add when a CA requests it |
| Role promotion (member → owner) | Keep single-owner simple for v1 |
| Billing / subscription management | Not relevant until monetisation |

---

## Build order

1. **Postgres + Alembic** — all six tables with indexes and constraints
2. **SQLAlchemy models** — `Organisation`, `User`, `Client`, `Filing`,
   `FilingRevision`, `Document`
3. **Auth routes** — `POST /auth/register` (creates org + owner in one
   transaction), `POST /auth/login`, `POST /auth/invite` (owner only)
4. **FastAPI JWT middleware** — injects `org_id` + `role` into every request
5. **NextAuth.js** — credentials provider; session carries `user_id`, `org_id`,
   `role`; Next.js middleware protects `/dashboard/*` (any logged-in user) and
   `/admin/*` (owner only)
6. **Landing page** at `/` — hero, features, CTA (Sign up / Sign in)
7. **Dashboard** at `/dashboard` — client list, new client form, filing status
   overview (scoped to org)
8. **Filing UI** at `/dashboard/clients/[id]/filings/[ay]` — current `page.tsx`
   moved here; all API calls carry org-scoped JWT
9. **Existing API routes updated** — filter by `org_id`, write
   `last_modified_by`, snapshot into `filing_revisions` on Generate
10. **S3 wiring** — stream upload on parse, pre-signed URL on download
11. **Admin — team** at `/admin/team` — member list, invite, deactivate,
    bulk reassign
12. **Admin — filings** at `/admin/filings` — full cross-org table, filters,
    stuck-filing alert
13. **Admin — audit** at `/admin/audit` — revision log per filing, org-wide
    activity feed, download any historical ITR JSON
14. **Admin — settings** at `/admin/settings` — firm name, owner profile
