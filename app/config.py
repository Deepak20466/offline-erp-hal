"""Application configuration loaded from environment variables with sane defaults."""
from pathlib import Path

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


settings = Settings()
