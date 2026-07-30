"""Application configuration loaded from environment variables with sane defaults."""
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
CONTRACT_FILES_DIR = DATA_DIR / "contract_files"

DATA_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)
CONTRACT_FILES_DIR.mkdir(exist_ok=True)


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
