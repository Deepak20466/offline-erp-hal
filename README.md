# Offline ERP HAL — Contract & Invoice Management System

A fully offline, self-contained ERP for managing clients, contracts, contract
line items, selective invoicing, payments/ledger, and admin-configurable
dynamic fields — built with FastAPI, SQLAlchemy (SQLite), and server-rendered
Jinja2 + Bootstrap 5 templates. Every static asset (Bootstrap, icons, the HAL
logo) is bundled locally under `app/static/` — there is **no CDN dependency**
and the app works with no internet connection at runtime.

## Features

- **Authentication** — login, logout, "remember me", forgot password via
  security question or admin PIN, change password, profile management,
  account lockout after repeated failed logins, and stateless session
  invalidation on password change (signs out every other device/tab).
- **Roles & User Management** — Admin and Staff roles with route-level
  enforcement; admins get a full Users module (create, edit, search/filter
  by role & status, reset passwords, soft delete/restore/permanently delete),
  with guard rails so the last remaining admin can never be demoted, deactivated,
  or deleted, and nobody can lock themselves out.
- **Dashboard** — live widgets (contracts, ordered/pending qty, invoices,
  outstanding receivables, recycle bin count) and quick actions.
- **Clients** — CRUD, search, pagination (50/page, tested to 500+ records),
  bulk soft delete, restore, export to CSV/PDF/Excel/Word.
- **Contracts** — CRUD with the exact specified column layout, admin-defined
  dynamic columns, search (contract #/client/description), status filter,
  sortable headers, pagination, bulk soft delete, export to CSV/PDF/Excel/Word
  + A4 print, restore.
- **Line Items** — stored in the database (not Excel) per contract; drive
  selective invoicing.
- **Dynamic Field Manager** (admin-only) — add/edit/delete/reorder/hide
  custom fields per module (Contracts, Clients, Invoices) with 9 field types;
  changes apply instantly to tables and forms with no code changes.
- **Invoice Generation Engine** — pick a contract, select which line items to
  bill, auto-populate customer/GSTIN/PAN from the client master, auto-compute
  line total/GST/grand total, auto-generate the amount in Indian-English words,
  auto-post the sales journal, and export as CSV/PDF (with the HAL letterhead)
  /Excel/Word/A4 print. **Posted invoices are immutable** — there is no edit
  route; correcting one goes through admin-only **Void & Reissue**: voiding
  keeps the invoice and reverses its sales-journal entries (rather than
  deleting them) for a permanent audit trail, then unlocks its line items so a
  corrected invoice can be raised and linked back to the voided original.
- **Payments & Ledger** — log receipts with TDS/LD, auto-derived status tags
  (Fully Paid / Partially Paid / LD Applied / Pending), invoice register with
  outstanding balances, export CSV/PDF/Excel/Word + print. **Posted payments
  are immutable** too — admins void (with a mandatory reason) instead of
  deleting; voided payments stay visible in the payment history for audit.
- **Recycle Bin** — view, restore, permanently delete, or empty soft-deleted
  clients, contracts, and users. (Invoices/payments are intentionally excluded
  — see Void & Reissue above.)
- **UI/UX** — dark/light theme toggle, loading states on form submission,
  bulk-select + bulk actions on list pages, toast notifications, confirmation
  dialogs, responsive layout.

## Tech Stack

Python 3.10+, FastAPI, SQLAlchemy 2.0 (SQLite), Jinja2, Bootstrap 5 (vendored
locally), pandas + openpyxl (Excel export), ReportLab (PDF export),
python-docx (Word export), Pillow (reads the logo's aspect ratio for exports).

## Project Structure

```
Hal/
├── main.py                  # FastAPI app entrypoint (uvicorn main:app)
├── seed.py                  # Database seeder (admin user + demo data)
├── requirements.txt
├── data/                    # SQLite database file lives here
├── app/
│   ├── config.py            # Settings (env-overridable)
│   ├── database.py          # Engine/session/Base + init_db()
│   ├── dependencies.py       # get_current_user / require_login / CSRF check
│   ├── templating.py         # Jinja2Templates + filters (inr, fdate) + render()
│   ├── models/               # 9 SQLAlchemy models (soft delete + timestamps)
│   ├── schemas/               # Pydantic request/response schemas
│   ├── services/              # Business logic / repository layer
│   ├── routers/                # FastAPI APIRouters (one per module)
│   ├── utils/                   # number-to-words, security, exporters, pagination
│   ├── templates/                # Jinja2 templates (Bootstrap 5 UI)
│   └── static/                    # Local Bootstrap/Icons + custom CSS/JS + logo
└── scripts/                    # One-off maintenance scripts
```

## Setup

```powershell
# 1. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Seed the database (creates data/hal_erp.db with an admin user + demo data)
python seed.py

# 4. Run the app
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

### Default login (created by `seed.py`)

| Field           | Value              |
|-----------------|--------------------|
| Email           | `admin@hal.internal` |
| Password        | `Admin@123`        |
| Admin PIN       | `1234`             |
| Security Q&A    | "What is your favorite aircraft?" → `tejas` |

Change the password after first login via **Forgot Password** on the login
page, using either the security answer or the admin PIN to authorize the reset.
This account is seeded with the `admin` role — see Design Decisions below for
why there's no public self-registration.

## Notes on Design Decisions

- **Excel is export-only.** Line items, contracts, and invoices are always
  edited in the dashboard; Excel files are generated on demand as read-only
  archives. There is no import path, so there is no two-way sync to reason about.
- **Soft deletes everywhere.** Every table has an `is_deleted` flag; list
  queries always filter it out, and the Recycle Bin is simply a view over
  `is_deleted = true` rows, with a separate hard-delete path for permanent purge.
- **Dynamic fields** are stored generically in `custom_fields` /
  `custom_field_values` and rendered through a single Jinja macro
  (`app/templates/partials/dynamic_field_input.html`), so adding a field in
  the admin panel immediately affects the relevant table and form with zero
  code changes.
- **Selective invoicing**: an invoice is generated from one or more contract
  line items (not the whole contract). Selected line items are stamped with
  the invoice's id and locked from further edits; the invoice's own
  `quantity`/`unit_rate` fields store the aggregate quantity and the
  quantity-weighted average rate across the selected items.
- **CSRF protection** uses stateless, signed, timestamped tokens
  (`itsdangerous`) embedded as a hidden field in every form — no server-side
  session store is required, which fits the fully offline deployment model.
- **No public self-registration.** This is an internal, admin-provisioned ERP:
  new accounts are created by an admin from the Users module (with a role,
  password, and recovery Q&A/PIN set up front) rather than through an open
  sign-up form, which would be the wrong trust model for an offline aerospace
  back office.
- **Sessions are stateless but revocable.** The session cookie is a signed
  token embedding a `session_version`; changing a password (by the user or an
  admin resetting it) bumps that counter, which instantly invalidates every
  other outstanding session/remember-me cookie without needing a server-side
  session store.
- **Self-healing schema.** There's no Alembic migration chain; `init_db()`
  diffs each SQLAlchemy model's columns against the live SQLite file via
  `PRAGMA table_info` and adds anything missing on every startup. A companion
  startup check guarantees at least one `admin` account always exists (it
  promotes `admin@hal.internal`, or else the oldest account, if a schema
  upgrade would otherwise leave nobody with admin rights).

## Branding — the HAL logo

The official Hindustan Aeronautics Limited logo lives at a single canonical
path, `app/static/images/hal-logo.jpeg`, and is reused everywhere in the app:
the login page, dashboard header, sidebar, top navbar, browser favicon, every
PDF/Word export (letterhead), and every printable A4 report (`app/templates/partials/print_header.html`).
`app/utils/branding.py` centralizes the file path and computes each export's
logo height from its actual aspect ratio, so it is always scaled proportionally
and never stretched or cropped, whether it's rendered at 200px (login), 50px
(navbar), or 100px (PDF/print letterhead). To update the logo, replace that
one file with a new image of the same name — no other code needs to change.

## Running Tests / Manual QA

There is no bundled test suite; validate changes by running the app locally
(`uvicorn main:app --reload`), signing in with the seeded admin account, and
exercising the CRUD/export/invoice/payment/recycle-bin flows through the UI.
