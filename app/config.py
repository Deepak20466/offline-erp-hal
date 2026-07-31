"""Application configuration loaded from environment variables with sane defaults."""
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SOURCE_ROOT = Path(__file__).resolve().parent.parent

# Bundled, read-only app resources (Jinja templates, static CSS/JS/images). Under a
# PyInstaller --onefile build these are unpacked into a fresh temporary folder every
# time the exe starts (sys._MEIPASS) — fine, since nothing here is ever written to.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    RESOURCE_DIR = Path(sys._MEIPASS)
else:
    RESOURCE_DIR = _SOURCE_ROOT

# Persistent user data (database, saved Excel/Word documents). This must NEVER
# resolve inside PyInstaller's temporary extraction folder — that folder is deleted
# the instant the exe process exits, which would silently wipe the database and
# every "permanent" contract document on every restart. When frozen, anchor this
# next to the actual .exe file instead, so it survives restarts and reboots.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = _SOURCE_ROOT

DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"

DATA_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """Centralized application settings."""

    app_name: str = "Offline ERP HAL"
    database_url: str = f"sqlite:///{(DATA_DIR / 'hal_erp.db').as_posix()}"
    secret_key: str = "hal-erp-offline-secret-key-change-in-production-9f8e7d6c5b4a"
    session_cookie_name: str = "hal_erp_session"
    remember_me_days: int = 30
    session_hours: int = 12
    page_size: int = 50
    company_name: str = "Hindustan Aeronautics Limited"
    gst_default_percentage: float = 18.0
    # Base folder for permanently saved Excel/Word documents. Defaults to a local
    # folder (fine for the offline/single-machine deployment this app targets), but
    # on Render this MUST be overridden to a path under an attached Persistent Disk
    # mount — Render's default filesystem is wiped on every deploy/restart, so
    # without a real disk behind this path, saved documents would silently vanish.
    document_storage_dir: str | None = None

    # Desktop-only: which backend the desktop shell (desktop.py) points its window
    # at. Unset (the default) preserves the original, fully offline behavior --
    # desktop.py spawns its own local FastAPI/uvicorn server and points the window at
    # it. Set this (e.g. to a Render URL) to instead point the desktop window at a
    # hosted backend sharing one Postgres database with the website; see desktop.py.
    # Irrelevant to the website itself -- main.py never reads this setting.
    desktop_backend_url: str | None = None

    # Password seeded for the default admin account (admin@hal.internal) on a
    # brand-new deployment -- see _ensure_default_admin_user() in app/database.py.
    # Default kept identical to the app's historical value for compatibility with
    # existing installs/docs; override via .env or a real environment variable so a
    # given deployment's seeded password isn't the same publicly-documented default
    # every clone of this repo starts with.
    default_admin_password: str = "Admin@123"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Render's managed Postgres add-on (and Supabase) hands out a ``postgres://``
        URL, but SQLAlchemy 2.x only recognizes the ``postgresql://`` scheme. Rewrite
        it so ``DATABASE_URL`` from Render's environment works unmodified.

        Also make sure Postgres connections (whether Supabase's direct host or the
        pgbouncer transaction pooler) negotiate SSL, since Supabase requires it and
        not every copy-pasted connection string includes ``sslmode`` explicitly.
        """
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]

        if value.startswith("postgresql://") or value.startswith("postgresql+psycopg2://"):
            parts = urlsplit(value)
            query = dict(parse_qsl(parts.query))
            query.setdefault("sslmode", "require")
            value = urlunsplit(parts._replace(query=urlencode(query)))

        return value


settings = Settings()

# Resolved after `settings` so DOCUMENT_STORAGE_DIR (env/.env) can override the
# default local path — e.g. point it at a Render Persistent Disk's mount path.
CONTRACT_FILES_DIR = Path(settings.document_storage_dir) if settings.document_storage_dir else DATA_DIR / "contract_files"
CONTRACT_FILES_DIR.mkdir(parents=True, exist_ok=True)
