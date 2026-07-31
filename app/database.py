"""SQLAlchemy engine, session factory, and declarative base."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

is_sqlite = "sqlite" in settings.database_url
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs = {"connect_args": connect_args, "pool_pre_ping": True}
if not is_sqlite:
    # Supabase's pgbouncer transaction pooler caps concurrent server-side
    # connections tightly (15 on the free tier) and closes idle ones, so keep
    # the app-side pool small and recycle connections before Supabase does.
    engine_kwargs.update(pool_size=5, max_overflow=5, pool_recycle=300)

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and guarantees closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _upgrade_schema() -> None:
    """Add columns introduced by newer model versions to an already-existing database.

    ``create_all`` only creates missing tables, it never alters existing ones, and this
    project has no Alembic migration chain — so on every startup we diff each mapped
    table's columns against the live database (via SQLAlchemy's dialect-agnostic
    inspector, so this works for both SQLite and PostgreSQL) and issue
    ``ALTER TABLE ADD COLUMN`` for anything missing. Safe to run every time:
    already-upgraded columns are skipped, and no data is ever dropped or rewritten.
    """
    from sqlalchemy import inspect
    from sqlalchemy.schema import CreateColumn

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if table.name not in existing_tables:
                continue  # brand-new table — create_all already built it in full
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                column_ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
                conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN {column_ddl}')


def _ensure_admin_exists() -> None:
    """Guarantee at least one admin can sign in after the ``role`` column is introduced.

    Existing rows created before this migration get ``role='staff'`` from the column's
    default, which would otherwise lock everyone out of admin-only screens. If no active
    admin exists yet, promote ``admin@hal.internal`` if present, else the oldest account.
    """
    from sqlalchemy import select

    from app.models.user import ROLE_ADMIN, User

    db = SessionLocal()
    try:
        has_admin = db.scalar(
            select(User.id).where(User.role == ROLE_ADMIN, User.is_deleted.is_(False))
        )
        if has_admin is not None:
            return

        candidate = db.scalar(
            select(User).where(User.email == "admin@hal.internal", User.is_deleted.is_(False))
        )
        if candidate is None:
            candidate = db.scalar(
                select(User).where(User.is_deleted.is_(False)).order_by(User.id.asc())
            )
        if candidate is not None:
            candidate.role = ROLE_ADMIN
            db.commit()
    finally:
        db.close()


DEFAULT_ADMIN_EMAIL = "admin@hal.internal"
# Sourced from settings (DEFAULT_ADMIN_PASSWORD env var / .env), not a literal, so a
# real deployment can seed its own admin password instead of this repo's documented
# default -- see the default_admin_password field in app/config.py.
DEFAULT_ADMIN_PASSWORD = settings.default_admin_password


def _ensure_default_admin_user() -> None:
    """Create the default admin account on a brand-new deployment.

    Render (and any other fresh environment) starts from an empty database, so
    ``_ensure_admin_exists`` below has no existing user to promote and nobody could
    log in. This only inserts a row when no user with ``DEFAULT_ADMIN_EMAIL`` exists
    yet — it never touches an existing account's password or other fields.
    """
    import logging

    from app.models.user import ROLE_ADMIN, User
    from app.utils.security import hash_secret

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == DEFAULT_ADMIN_EMAIL).first()
        if existing is not None:
            return
        db.add(
            User(
                name="Administrator",
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=hash_secret(DEFAULT_ADMIN_PASSWORD),
                role=ROLE_ADMIN,
                security_question="What is your favorite aircraft?",
                security_answer_hash=hash_secret("tejas"),
                admin_pin_hash=hash_secret("1234"),
            )
        )
        db.commit()
        logger.warning(
            "Seeded default admin account (%s) with the default password. "
            "Log in and change the password immediately.",
            DEFAULT_ADMIN_EMAIL,
        )
    finally:
        db.close()


def init_db() -> None:
    """Create all tables, apply SQLite pragmas, and upgrade any existing schema in place."""
    from sqlalchemy import event

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    import app.models  # noqa: F401  (ensures all models are registered)

    Base.metadata.create_all(bind=engine)
    _upgrade_schema()
    _ensure_default_admin_user()
    _ensure_admin_exists()
