"""SQLAlchemy engine, session factory, and declarative base."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

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
    """Add columns introduced by newer model versions to an already-existing SQLite file.

    ``create_all`` only creates missing tables, it never alters existing ones, and this
    project has no Alembic migration chain — so on every startup we diff each mapped
    table's columns against ``PRAGMA table_info`` and issue ``ALTER TABLE ADD COLUMN``
    for anything missing. Safe to run every time: already-upgraded columns are skipped.
    """
    from sqlalchemy.schema import CreateColumn

    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            existing_columns = {
                row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table.name}")').fetchall()
            }
            if not existing_columns:
                continue  # brand-new table — create_all already built it in full
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


def init_db() -> None:
    """Create all tables, apply SQLite pragmas, and upgrade any existing schema in place."""
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    import app.models  # noqa: F401  (ensures all models are registered)

    Base.metadata.create_all(bind=engine)
    _upgrade_schema()
    _ensure_admin_exists()
