# Offline ERP HAL — Contract & Invoice Management System

A fully offline, self-contained ERP for managing clients, contracts, contract
line items, selective invoicing, payments/ledger, and admin-configurable
dynamic fields — built with FastAPI, SQLAlchemy (SQLite), and server-rendered
Jinja2 + Bootstrap 5 templates.

## Project Overview

Offline ERP HAL is an internal back-office system designed for environments
with no internet dependency at runtime. Every static asset (Bootstrap, icons,
the HAL logo) is vendored locally under `app/static/` — there is **no CDN
dependency**, no external API calls, and no cloud service requirement. The
entire application — authentication, contracts, invoicing, payments, and
reporting — runs against a local SQLite database and can be deployed on a
single offline machine.

It was built for a contract-to-cash workflow: create a client, raise a
contract with line items, selectively invoice those line items, record
payments against invoices, and export any of it (CSV/PDF/Excel/Word/A4 print)
for audit or filing.

## Features

- **Authentication** — login, logout, "remember me", forgot password via
  security question or admin PIN, change password, profile management,
  account lockout after repeated failed logins, and stateless session
  invalidation on password change (signs out every other device/tab).
- **Roles & User Management** — Admin and Staff roles with route-level
  enforcement; admins get a full Users module (create, edit, search/filter
  by role & status, reset passwords, soft delete/restore/permanently delete),
  with guard rails so the last remaining admin can never be demoted,
  deactivated, or deleted, and nobody can lock themselves out.
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

## Screenshots

> Placeholders — replace with actual screenshots once available.

| Login | Dashboard |
|---|---|
| ![Login screen](docs/screenshots/login.png) | ![Dashboard](docs/screenshots/dashboard.png) |

| Contracts | Invoice Generation |
|---|---|
| ![Contracts list](docs/screenshots/contracts.png) | ![Invoice generation](docs/screenshots/invoice.png) |

## Technology Stack

| Layer | Technology |
|---|---|
| Backend framework | [FastAPI](https://fastapi.tiangolo.com/) (ASGI, Python 3.10+) |
| ORM / Database | SQLAlchemy 2.0 + SQLite |
| Templates / UI | Jinja2 + Bootstrap 5 (vendored locally, no CDN) |
| Auth & Sessions | Signed, stateless session cookies (`itsdangerous`), `passlib`/`bcrypt` password hashing |
| Validation | Pydantic 2 / `pydantic-settings` |
| Exports | `pandas` + `openpyxl` (Excel), `ReportLab` (PDF), `python-docx` (Word) |
| Images | Pillow (logo aspect-ratio handling for exports) |
| Server | Uvicorn (ASGI) |

## Folder Structure

```
Hal/
├── main.py                  # FastAPI app entrypoint (uvicorn main:app)
├── seed.py                  # Database seeder (admin user + demo data)
├── requirements.txt
├── data/                    # SQLite database file lives here
├── app/
│   ├── config.py             # Settings (env-overridable)
│   ├── database.py           # Engine/session/Base + init_db()
│   ├── dependencies.py       # get_current_user / require_login / require_admin / CSRF check
│   ├── templating.py         # Jinja2Templates + filters (inr, fdate) + render()
│   ├── models/                # SQLAlchemy models (soft delete + timestamps)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/                # Business logic / repository layer
│   ├── routers/                   # FastAPI APIRouters (one per module)
│   ├── utils/                       # number-to-words, security, exporters, pagination
│   ├── templates/                    # Jinja2 templates (Bootstrap 5 UI)
│   └── static/                        # Local Bootstrap/Icons + custom CSS/JS + logo
└── scripts/                            # One-off maintenance scripts
```

## Installation & Setup

### Prerequisites

- Python 3.10+
- `pip` and `venv`

### 1. Clone the repository

```bash
git clone https://github.com/Deepak20466/offline-erp-hal.git
cd offline-erp-hal
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Seed the database

```powershell
python seed.py
```

This creates `data/hal_erp.db` with a seeded admin account and demo data.

## Running the Application

```powershell
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

## Login Instructions

Use the seeded admin account created by `seed.py`:

| Field           | Value              |
|-----------------|--------------------|
| Email           | `admin@hal.internal` |
| Password        | `Admin@123`        |
| Admin PIN       | `1234`             |
| Security Q&A    | "What is your favorite aircraft?" → `tejas` |

Change the password after first login via **Forgot Password** on the login
page, using either the security answer or the admin PIN to authorize the
reset. There is no public self-registration — new accounts are provisioned by
an admin from the Users module.

## User Roles

| Role | Permissions |
|---|---|
| **Admin** | Full access: Users module (create/edit/reset password/soft delete/restore), Dynamic Field Manager, Void & Reissue on invoices and payments, Recycle Bin, all Staff permissions. Guard rails prevent the last remaining admin from being demoted, deactivated, or deleted. |
| **Staff** | Clients, Contracts, Line Items, Invoices, Payments — create/edit/search/export within assigned modules. No access to Users module, Dynamic Field Manager, or Void & Reissue. |

Role checks are enforced at the route/dependency layer (`app/dependencies.py`
— `require_login` / `require_admin`), not just hidden in the UI.

## Project Architecture

```
Browser (Jinja2 + Bootstrap 5, server-rendered)
        │  HTML forms / links (no SPA, no client-side framework)
        ▼
FastAPI routers (app/routers/)  ──►  Pydantic schemas (app/schemas/)
        │                                     │
        ▼                                     ▼
Service layer (app/services/)  ◄────  Business logic / validation
        │
        ▼
SQLAlchemy models (app/models/)  ──►  SQLite (data/hal_erp.db)
```

- **Routers** handle HTTP concerns (auth, redirects, form parsing) and
  delegate to services.
- **Services** own business rules — e.g., invoice totals, sales-journal
  posting, void/reissue logic, soft-delete semantics.
- **Models** are SQLAlchemy 2.0 mapped classes; every table carries an
  `is_deleted` flag and timestamps via shared mixins (`app/models/mixins.py`).
- **Dynamic fields** are stored generically in `custom_fields` /
  `custom_field_values` and rendered through a single Jinja macro
  (`app/templates/partials/dynamic_field_input.html`), so adding a field in
  the admin panel immediately affects the relevant table and form with zero
  code changes.
- **CSRF protection** uses stateless, signed, timestamped tokens
  (`itsdangerous`) embedded as a hidden field in every form — no server-side
  session store is required, which fits the fully offline deployment model.
- **Sessions are stateless but revocable** — the session cookie is a signed
  token embedding a `session_version`; changing a password (by the user or an
  admin resetting it) bumps that counter, instantly invalidating every other
  outstanding session/remember-me cookie without a server-side session store.

## Database Setup

- **Engine**: SQLite, file-based at `data/hal_erp.db` (created automatically
  on first run).
- **No Alembic migration chain.** `init_db()` (in `app/database.py`) diffs
  each SQLAlchemy model's columns against the live SQLite file via
  `PRAGMA table_info` and adds any missing columns on every startup —
  a "self-healing" schema.
- A companion startup check guarantees at least one `admin` account always
  exists (it promotes `admin@hal.internal`, or else the oldest account, if a
  schema upgrade would otherwise leave nobody with admin rights).
- **Soft deletes everywhere.** Every table has an `is_deleted` flag; list
  queries always filter it out, and the Recycle Bin is simply a view over
  `is_deleted = true` rows, with a separate hard-delete path for permanent
  purge.
- To reset the database, stop the app, delete `data/hal_erp.db*`, and re-run
  `python seed.py`.

## Environment Variables

All settings are defined in `app/config.py` (via `pydantic-settings`) with
sane defaults, and can be overridden with an `.env` file in the project root
or real environment variables:

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `Offline ERP HAL` | Application display name |
| `DATABASE_URL` | `sqlite:///data/hal_erp.db` | SQLAlchemy database URL |
| `SECRET_KEY` | *(insecure placeholder — see below)* | Signing key for session cookies and CSRF tokens |
| `SESSION_COOKIE_NAME` | `hal_erp_session` | Name of the session cookie |
| `REMEMBER_ME_DAYS` | `30` | "Remember me" cookie lifetime, in days |
| `SESSION_HOURS` | `12` | Normal session lifetime, in hours |
| `PAGE_SIZE` | `50` | Rows per page on list views |
| `COMPANY_NAME` | `Hindustan Aeronautics Limited` | Name used on exports/letterheads |
| `GST_DEFAULT_PERCENTAGE` | `18.0` | Default GST % applied on invoices |

> **Security note:** `SECRET_KEY` ships with a placeholder default. The app
> logs a warning at startup if it detects the default value is still in use.
> Always set a unique `SECRET_KEY` via `.env` before any real/production
> deployment, since it signs both session cookies and CSRF tokens.

## Future Improvements

- Automated test suite (unit + integration) — currently validated manually.
- Alembic-based migrations for more complex schema evolution.
- Multi-currency support for invoicing.
- Configurable GST/tax rules per client or contract.
- Role granularity beyond Admin/Staff (e.g., read-only auditor role).
- Scheduled/automated database backups.

## License

This project is provided for internal use. Add a license of your choice
(e.g., MIT, Apache 2.0) here if the project is to be distributed or
open-sourced.

## Author

**K Deepak**
Email: kdeepak162001@gmail.com
GitHub: [@Deepak20466](https://github.com/Deepak20466)
