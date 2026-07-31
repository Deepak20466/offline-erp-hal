"""Persists Excel/Word snapshots generated from a contract as standalone files on disk.

Each save writes a brand-new file plus a DB row that only stores its path — the file
itself is never re-opened or re-parsed by this app. That's what keeps this one-way:
edits made inside a saved Excel/Word file can never flow back into the database, and
later ERP changes never touch files already saved here.
"""
import shutil
import uuid
from pathlib import Path

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.config import CONTRACT_FILES_DIR
from app.models.contract import Contract
from app.models.contract_document import ContractDocument
from app.services import line_item_service
from app.utils.exporters import build_excel_bytes, build_word_bytes

EXTENSION_BY_TYPE = {"excel": "xlsx", "word": "docx"}
LABEL_BY_TYPE = {"excel": "Excel", "word": "Word"}


def _contract_dir(contract_id: int) -> Path:
    directory = CONTRACT_FILES_DIR / str(contract_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def latest_document(db: Session, contract_id: int, doc_type: str) -> ContractDocument | None:
    stmt = (
        select(ContractDocument)
        .where(ContractDocument.contract_id == contract_id, ContractDocument.doc_type == doc_type)
        .order_by(ContractDocument.version.desc())
    )
    return db.scalars(stmt).first()


def latest_documents_map(db: Session, contract_ids: list[int]) -> dict[int, dict[str, ContractDocument]]:
    """Latest saved doc per (contract, type), for driving "View Excel/Word" links on a list page."""
    if not contract_ids:
        return {}
    stmt = (
        select(ContractDocument)
        .where(ContractDocument.contract_id.in_(contract_ids))
        .order_by(ContractDocument.version.desc())
    )
    result: dict[int, dict[str, ContractDocument]] = {}
    for doc in db.scalars(stmt):
        by_type = result.setdefault(doc.contract_id, {})
        by_type.setdefault(doc.doc_type, doc)  # first hit per type is the highest version, thanks to the order_by
    return result


def save_document_version(
    db: Session,
    contract_id: int,
    contract_number: str,
    doc_type: str,
    content: bytes,
    created_by_id: int | None,
) -> ContractDocument:
    """Save ``content`` as the next version for this contract+type, skipping identical duplicates.

    If the newest existing version's file bytes are byte-identical to ``content`` (i.e.
    nothing in the contract actually changed since the last export), that existing row
    is returned as-is instead of writing another copy — avoids piling up duplicate
    files when a user clicks Export repeatedly with no data changes in between.
    """
    previous = latest_document(db, contract_id, doc_type)
    if previous is not None:
        previous_path = resolve_path(previous)
        if previous_path.exists() and previous_path.read_bytes() == content:
            return previous

    extension = EXTENSION_BY_TYPE[doc_type]
    version = (previous.version if previous else 0) + 1
    stored_filename = f"{uuid.uuid4().hex}.{extension}"
    file_path = _contract_dir(contract_id) / stored_filename
    file_path.write_bytes(content)

    label = LABEL_BY_TYPE[doc_type]
    original_filename = f"{contract_number}_{label}_v{version}.{extension}"

    document = ContractDocument(
        contract_id=contract_id,
        doc_type=doc_type,
        version=version,
        original_filename=original_filename,
        stored_filename=stored_filename,
        created_by_id=created_by_id,
    )
    db.add(document)
    db.flush()
    return document


def canonical_document_path(contract_id: int, doc_type: str) -> Path:
    """Path to this contract's single permanent Excel/Word document (the "View" feature).

    Deliberately separate from the versioned Export system above: fixed filename (not
    UUID-based, not tracked in the ``contract_documents`` table), so there is exactly
    one Excel file and one Word file per contract, ever. The caller is responsible for
    only writing to this path once, the first time it doesn't exist — this function
    just resolves where that file lives.
    """
    extension = EXTENSION_BY_TYPE[doc_type]
    return _contract_dir(contract_id) / f"view.{extension}"


def ensure_canonical_document(db: Session, contract: Contract, doc_type: str) -> Path:
    """Return this contract's permanent View document, creating it once if it doesn't exist yet.

    Shared by both the HTTP "View" route and the desktop launcher's open-in-app bridge,
    so a browser tab and the native window resolve/create the exact same file — never
    two separate copies. Only ever writes on the very first call for a given
    contract+type; every call after that just returns the existing path untouched.
    """
    file_path = canonical_document_path(contract.id, doc_type)
    if not file_path.exists():
        items = line_item_service.list_line_items(db, contract.id)
        headers = ["Description", "Quantity", "Unit Rate", "Amount", "Status"]
        rows = [
            [item.description, float(item.quantity), float(item.unit_rate), float(item.amount), item.status]
            for item in items
        ]
        if doc_type == "excel":
            content = build_excel_bytes(headers, rows, sheet_name="Line Items")
        else:
            content = build_word_bytes(f"Contract {contract.contract_number}", headers, rows)
        file_path.write_bytes(content)
    return file_path


def list_documents(db: Session, contract_id: int) -> list[ContractDocument]:
    stmt = (
        select(ContractDocument)
        .where(ContractDocument.contract_id == contract_id)
        .order_by(ContractDocument.doc_type.asc(), ContractDocument.version.desc())
    )
    return list(db.scalars(stmt))


def get_document(db: Session, document_id: int) -> ContractDocument | None:
    return db.get(ContractDocument, document_id)


def resolve_path(document: ContractDocument) -> Path:
    return CONTRACT_FILES_DIR / str(document.contract_id) / document.stored_filename


@event.listens_for(Contract, "after_delete")
def _cleanup_documents_on_purge(mapper, connection, target: Contract) -> None:  # noqa: ANN001
    """Remove a contract's saved document files once its row is permanently purged.

    Hooked on the ORM delete event (rather than in contract_service/recycle_bin) so it
    fires for every path that hard-deletes a Contract — single Recycle Bin purge and
    "Empty Recycle Bin" alike — without touching that existing code. The DB rows for
    this contract's documents are already gone via the ``ON DELETE CASCADE`` foreign
    key; this only cleans up the on-disk files, which the DB cascade can't reach.
    """
    contract_dir = CONTRACT_FILES_DIR / str(target.id)
    shutil.rmtree(contract_dir, ignore_errors=True)
