# Offline ERP HAL — Contract & Invoice Management System

A self-contained ERP for managing clients, contracts, contract line items,
selective invoicing, payments/ledger, and admin-configurable dynamic
fields — built with FastAPI, SQLAlchemy, and server-rendered Jinja2 +
Bootstrap 5 templates. Ships two ways: as a normal web app, and as a
**native Windows desktop application** with a one-click installer.

## Download

**[⬇ Download v1.0.1 — Windows installer](https://github.com/Deepak20466/offline-erp-hal/releases/download/v1.0.1/BusinessERPSystemSetup.exe)**
(`BusinessERPSystemSetup.exe`) — no admin rights required, installs to your
user profile, and launches the app as a real desktop window. See the
[releases page](https://github.com/Deepak20466/offline-erp-hal/releases)
for release notes and older versions.

See [Running as a Desktop App](#running-as-a-desktop-app-recommended) below
for what that gets you, or [Installation & Setup](#installation--setup-from-source)
to run from source instead.

## Screenshots

> Add screenshots to `docs/screenshots/` and reference them here, e.g.:
> `![Dashboard](docs/screenshots/dashboard.png)`. None are committed yet —
> this section is a placeholder until real screenshots are captured from a
> running instance.

| Login | Dashboard |
|---|---|
| _add screenshot_ | _add screenshot_ |

| Contracts | Invoice Generation |
|---|---|
| _add screenshot_ | _add screenshot_ |

## Project Overview

Offline ERP HAL is an internal back-office system for a contract-to-cash
workflow: create a client, raise a contract with line items, selectively
invoice those line items, record payments against invoices, and export any
of it (CSV/PDF/Excel/Word/A4 print) for audit or filing. Every static asset
(Bootstrap, icons, the HAL logo) is vendored locally under `app/static/` —
no CDN dependency, no external API calls required to run it.

It runs equally well two ways:
- **As a desktop app** (`desktop.py`, packaged via PyInstaller + Inno Setup)
  — a native window, backed by the same FastAPI app, with direct
  Excel/Word document opening (see [Document Management](#document-management)).
- **As a normal web app** (`uvicorn main:app`) — for local dev, or hosted
  behind Postgres/Supabase for a shared, multi-user deployment.

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
- **Document Management** — every contract can generate a versioned Excel/Word
  export snapshot, *and* has one permanent Excel + one permanent Word document
  that opens directly (no download) when running as the desktop app. See
  [Document Management](#document-management) below for the full model.
- **Desktop Application** — `python desktop.py` (or the installed exe) runs
  the app in a native window via [pywebview](https://pywebview.flowrl.com/),
  with a JS↔Python bridge that opens a contract's Excel/Word file directly
  in Microsoft Excel/Word using `os.startfile()` — not a browser download.
- **Windows Installer** — `installer.iss` (Inno Setup) builds a per-user
  installer (no admin required) around the PyInstaller-built exe. See
  [Building the Windows Installer](#building-the-windows-installer).
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
  clients, contracts, and users (and their associated documents). Invoices/
  payments are intentionally excluded — see Void & Reissue above.
- **UI/UX** — dark/light theme toggle, loading states on form submission,
  bulk-select + bulk actions on list pages, toast notifications, confirmation
  dialogs, responsive layout.

## Document Management

Contracts have **two independent, non-syncing** document mechanisms — this
is deliberate, not an oversight:

1. **Export (versioned snapshots)** — "Export Excel"/"Export Word" on a
   contract's detail page generates a fresh file from current database data
   and saves it as a new numbered version (`Contract_Excel_v1.xlsx`,
   `_v2.xlsx`, ...). Every version stays downloadable. Re-exporting with no
   data changes reuses the existing version instead of creating a duplicate.
2. **View (one permanent file per contract)** — "View → Excel" / "View →
   Word" opens **exactly one** permanent `.xlsx` and one permanent `.docx`
   per contract, created the first time it's opened and **never
   regenerated, overwritten, or reset** after that — regardless of later
   contract edits or how many times it's reopened. When running as the
   desktop app, this opens directly in Microsoft Excel/Word via
   `os.startfile()`; in a plain browser tab it downloads instead, since a
   browser cannot launch a desktop application (a platform limitation, not
   a bug). An "Upload Updated Excel" control lets you push a locally-edited
   copy back to the server, replacing that same permanent file.

**Independence is enforced in both directions, always:**
- Dashboard/database edits never touch either document.
- Editing the Excel/Word file (in Excel/Word itself, or via re-upload)
  never touches the database — there is no import/read-back path anywhere
  in the app.
- Deleting a contract (recycle bin) blocks document access until restored;
  permanently purging a contract deletes its documents too — the *only*
  two ways any of these files are ever removed.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend framework | [FastAPI](https://fastapi.tiangolo.com/) (ASGI, Python 3.10+) |
| ORM / Database | SQLAlchemy 2.0 + SQLite (or PostgreSQL/Supabase for hosted deployments) |
| Templates / UI | Jinja2 + Bootstrap 5 (vendored locally, no CDN) |
| Desktop shell | [pywebview](https://pywebview.flowrl.com/) (native window + JS↔Python bridge) |
| Packaging | [PyInstaller](https://pyinstaller.org/) (single-file exe) + [Inno Setup](https://jrsoftware.org/isinfo.php) (Windows installer) |
| Auth & Sessions | Signed, stateless session cookies (`itsdangerous`), `passlib`/`bcrypt` password hashing |
| Validation | Pydantic 2 / `pydantic-settings` |
| Exports | `pandas` + `openpyxl` (Excel), `ReportLab` (PDF), `python-docx` (Word) |
| Images | Pillow (logo aspect-ratio handling for exports) |
| Server | Uvicorn (ASGI) |

## Folder Structure

```
offline-erp-hal/
├── main.py                  # FastAPI app (web mode: uvicorn main:app)
├── desktop.py                # Desktop app entry point (python desktop.py)
├── installer.iss              # Inno Setup script for the Windows installer
├── seed.py                     # Database seeder (admin user + demo data)
├── requirements.txt
├── .env.example                 # Template for local environment overrides
├── data/                          # SQLite database + permanent documents live here
├── app/
│   ├── config.py             # Settings (env-overridable) + frozen-exe-aware paths
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

## Running as a Desktop App (recommended)

The easiest path is the [prebuilt installer](#download) — download, run it
(no admin prompt), launch from the Start Menu.

To run from source instead:

```powershell
pip install -r requirements.txt
python desktop.py
```

This opens a native window (not a browser tab) running the same app. The
one thing a browser genuinely cannot do — launch Microsoft Excel/Word
directly against a specific local file — works here via a JS↔Python
bridge and `os.startfile()`. See [Document Management](#document-management).

## Installation & Setup (from source)

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

### 5. Run it

```powershell
uvicorn main:app --reload
```

Then open **http://127.0.0.1:8000** in your browser — or run `python
desktop.py` instead for the native window experience.

## Building the Windows Installer

For maintainers who want to produce a new release build:

```powershell
pip install pyinstaller

pyinstaller --onefile --windowed --name "Business ERP System" `
  --add-data "app/templates;app/templates" `
  --add-data "app/static;app/static" `
  --hidden-import passlib.handlers.bcrypt `
  desktop.py
```

This produces `dist\Business ERP System.exe`. Then compile the installer
with [Inno Setup](https://jrsoftware.org/isdl.php):

```powershell
"C:\Program Files\Inno Setup 7\ISCC.exe" installer.iss
```

Output lands at `Output\BusinessERPSystemSetup.exe`. It installs per-user
under `%LocalAppData%\Programs\Business ERP System` (no admin rights
needed), and its uninstaller never touches the `data\` folder — business
data always survives an uninstall.

> **Why the extra flags matter:** PyInstaller's `--onefile` mode unpacks
> into a temporary folder that's deleted the moment the exe closes, and its
> static import analysis can miss both non-Python data files (templates/
> static) and dynamically-loaded modules (`passlib`'s bcrypt handler). Skip
> any of these flags and you'll get a broken build — either a crash on
> startup, or (worse) a working app that silently loses its database and
> documents on every restart. `app/config.py` handles the persistent-vs-
> bundled path split; these flags handle what PyInstaller can't infer on
> its own.

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
Desktop window (pywebview)  OR  Browser (Jinja2 + Bootstrap 5, server-rendered)
        │  HTML forms / links (no SPA, no client-side framework)
        ▼
FastAPI routers (app/routers/)  ──►  Pydantic schemas (app/schemas/)
        │                                     │
        ▼                                     ▼
Service layer (app/services/)  ◄────  Business logic / validation
        │
        ▼
SQLAlchemy models (app/models/)  ──►  SQLite / PostgreSQL
```

- **Routers** handle HTTP concerns (auth, redirects, form parsing) and
  delegate to services.
- **Services** own business rules — e.g., invoice totals, sales-journal
  posting, void/reissue logic, soft-delete semantics, document lifecycle
  (`app/services/document_service.py`).
- **Models** are SQLAlchemy 2.0 mapped classes; every table carries an
  `is_deleted` flag and timestamps via shared mixins (`app/models/mixins.py`).
- **Dynamic fields** are stored generically in `custom_fields` /
  `custom_field_values` and rendered through a single Jinja macro
  (`app/templates/partials/dynamic_field_input.html`), so adding a field in
  the admin panel immediately affects the relevant table and form with zero
  code changes.
- **CSRF protection** uses stateless, signed, timestamped tokens
  (`itsdangerous`) embedded as a hidden field in every form — no server-side
  session store is required.
- **Sessions are stateless but revocable** — the session cookie is a signed
  token embedding a `session_version`; changing a password (by the user or an
  admin resetting it) bumps that counter, instantly invalidating every other
  outstanding session/remember-me cookie without a server-side session store.

## Database Setup

- **Engine**: SQLite by default, file-based at `data/hal_erp.db` (created
  automatically on first run); PostgreSQL/Supabase supported via
  `DATABASE_URL` for hosted deployments.
- **No Alembic migration chain.** `init_db()` (in `app/database.py`) diffs
  each SQLAlchemy model's columns against the live database schema and adds
  any missing columns on every startup — a "self-healing" schema, safe to
  run repeatedly (never drops or rewrites existing data).
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
sane defaults, and can be overridden by copying `.env.example` to `.env`
(gitignored — safe for real secrets) or via real environment variables:

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
| `DOCUMENT_STORAGE_DIR` | *(unset — defaults to `data/contract_files`)* | Base folder for permanent Excel/Word documents. **Must** point at a mounted Persistent Disk if deployed to Render, or documents are lost on every redeploy. |

> **Security note:** `SECRET_KEY` ships with a placeholder default. The app
> logs a warning at startup if it detects the default value is still in use.
> Always set a unique `SECRET_KEY` via `.env` before any real/production
> deployment, since it signs both session cookies and CSRF tokens.

## Future Improvements

- Automated test suite (unit + integration) — currently validated manually
  (see `.github/workflows/ci.yml` for the current build/import smoke check).
- Alembic-based migrations for more complex schema evolution.
- macOS/Linux desktop packaging (currently Windows-only via PyInstaller +
  Inno Setup; the desktop app itself runs cross-platform under pywebview,
  just not yet packaged for those platforms).
- Multi-currency support for invoicing.
- Configurable GST/tax rules per client or contract.
- Role granularity beyond Admin/Staff (e.g., read-only auditor role).
- Scheduled/automated database backups.

## License

**Proprietary — All Rights Reserved.** This repository and its
[releases](https://github.com/Deepak20466/offline-erp-hal/releases) are
public for viewing purposes only. No permission is granted to use, copy,
modify, distribute, or create derivative works from this source code or
its compiled binaries without prior written consent from the copyright
holder. See [`LICENSE`](LICENSE) for the full terms.

## Author

**K Deepak**
Email: kdeepak162001@gmail.com
GitHub: [@Deepak20466](https://github.com/Deepak20466)
