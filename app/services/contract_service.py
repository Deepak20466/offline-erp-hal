"""Business logic for contract CRUD, search, sort, pagination, and soft delete."""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.client import Client
from app.models.contract import Contract
from app.schemas.contract import ContractCreate, ContractUpdate
from app.utils.pagination import Page, paginate
from app.utils.soft_delete import deleted_query, hard_delete, restore, soft_delete

SORTABLE_COLUMNS = {
    "client_name": Client.name,
    "contract_number": Contract.contract_number,
    "contract_date": Contract.contract_date,
    "qty_ordered": Contract.qty_ordered,
    "qty_supplied": Contract.qty_supplied,
    "qty_pending": Contract.qty_ordered - Contract.qty_supplied,
}


def list_contracts(
    db: Session,
    search: str | None,
    sort: str | None,
    direction: str,
    page: int,
    page_size: int,
    status: str | None = None,
) -> Page:
    stmt = (
        select(Contract)
        .join(Client, Client.id == Contract.client_id)
        .options(joinedload(Contract.client))
        .where(Contract.is_deleted.is_(False))
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Contract.contract_number.ilike(like),
                Contract.description.ilike(like),
                Client.name.ilike(like),
            )
        )
    if status:
        stmt = stmt.where(Contract.status == status)

    sort_col = SORTABLE_COLUMNS.get(sort, Contract.contract_date)
    stmt = stmt.order_by(sort_col.desc() if direction == "desc" else sort_col.asc())

    return paginate(db, stmt, page, page_size)


def list_all_active_contracts(db: Session, search: str | None = None, status: str | None = None) -> list[Contract]:
    stmt = (
        select(Contract)
        .join(Client, Client.id == Contract.client_id)
        .options(joinedload(Contract.client))
        .where(Contract.is_deleted.is_(False))
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(Contract.contract_number.ilike(like), Client.name.ilike(like), Contract.description.ilike(like))
        )
    if status:
        stmt = stmt.where(Contract.status == status)
    stmt = stmt.order_by(Contract.contract_date.desc())
    return list(db.scalars(stmt))


def get_active_contract(db: Session, contract_id: int) -> Contract | None:
    contract = db.get(Contract, contract_id)
    return contract if contract and not contract.is_deleted else None


def create_contract(db: Session, data: ContractCreate) -> Contract:
    contract = Contract(**data.model_dump())
    db.add(contract)
    db.flush()
    return contract


def update_contract(db: Session, contract: Contract, data: ContractUpdate) -> Contract:
    for field, value in data.model_dump().items():
        setattr(contract, field, value)
    db.flush()
    return contract


def delete_contract(db: Session, contract: Contract) -> None:
    soft_delete(db, contract)


def bulk_delete_contracts(db: Session, contract_ids: list[int]) -> int:
    """Soft-delete every active contract whose id is in ``contract_ids``. Returns count deleted."""
    count = 0
    for contract_id in contract_ids:
        contract = get_active_contract(db, contract_id)
        if contract is not None:
            soft_delete(db, contract)
            count += 1
    return count


def list_deleted_contracts(db: Session, search: str | None, page: int, page_size: int) -> Page:
    stmt = deleted_query(db, Contract).options(joinedload(Contract.client))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Contract.contract_number.ilike(like))
    stmt = stmt.order_by(Contract.updated_at.desc())
    return paginate(db, stmt, page, page_size)


def restore_contract(db: Session, contract: Contract) -> Contract:
    return restore(db, contract)


def purge_contract(db: Session, contract: Contract) -> None:
    hard_delete(db, contract)
