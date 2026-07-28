"""Business logic for client CRUD, search, pagination, and soft delete."""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate
from app.utils.pagination import Page, paginate
from app.utils.soft_delete import deleted_query, hard_delete, restore, soft_delete

SORTABLE_COLUMNS = {
    "name": Client.name,
    "email": Client.email,
    "phone": Client.phone,
}


def list_clients(
    db: Session,
    search: str | None,
    page: int,
    page_size: int,
    sort: str | None = None,
    direction: str = "asc",
) -> Page:
    stmt = select(Client).where(Client.is_deleted.is_(False))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Client.name.ilike(like), Client.email.ilike(like)))
    sort_col = SORTABLE_COLUMNS.get(sort, Client.name)
    stmt = stmt.order_by(sort_col.desc() if direction == "desc" else sort_col.asc())
    return paginate(db, stmt, page, page_size)


def get_client(db: Session, client_id: int) -> Client | None:
    return db.get(Client, client_id)


def get_active_client(db: Session, client_id: int) -> Client | None:
    client = db.get(Client, client_id)
    return client if client and not client.is_deleted else None


def list_all_active_clients(db: Session) -> list[Client]:
    return list(db.scalars(select(Client).where(Client.is_deleted.is_(False)).order_by(Client.name.asc())))


def create_client(db: Session, data: ClientCreate) -> Client:
    client = Client(**data.model_dump())
    db.add(client)
    db.flush()
    return client


def update_client(db: Session, client: Client, data: ClientUpdate) -> Client:
    for field, value in data.model_dump().items():
        setattr(client, field, value)
    db.flush()
    return client


def delete_client(db: Session, client: Client) -> None:
    soft_delete(db, client)


def bulk_delete_clients(db: Session, client_ids: list[int]) -> int:
    """Soft-delete every active client whose id is in ``client_ids``. Returns count deleted."""
    count = 0
    for client_id in client_ids:
        client = get_active_client(db, client_id)
        if client is not None:
            soft_delete(db, client)
            count += 1
    return count


def list_deleted_clients(db: Session, search: str | None, page: int, page_size: int) -> Page:
    stmt = deleted_query(db, Client)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Client.name.ilike(like))
    stmt = stmt.order_by(Client.updated_at.desc())
    return paginate(db, stmt, page, page_size)


def restore_client(db: Session, client: Client) -> Client:
    return restore(db, client)


def purge_client(db: Session, client: Client) -> None:
    hard_delete(db, client)
