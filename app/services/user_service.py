"""Business logic for the admin-only User Management module."""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import ROLE_ADMIN, User
from app.schemas.user import UserCreate, UserUpdate
from app.utils.pagination import Page, paginate
from app.utils.soft_delete import deleted_query, hard_delete, restore, soft_delete
from app.utils.security import hash_secret

SORTABLE_COLUMNS = {
    "name": User.name,
    "email": User.email,
    "role": User.role,
    "last_login_at": User.last_login_at,
}


class UserError(Exception):
    """Raised for user-management business-rule violations."""


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_active_user(db: Session, user_id: int) -> User | None:
    user = db.get(User, user_id)
    return user if user and not user.is_deleted else None


def _filtered_users_stmt(db: Session, search: str | None, role: str | None, status: str | None):
    stmt = select(User).where(User.is_deleted.is_(False))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(User.name.ilike(like), User.email.ilike(like)))
    if role:
        stmt = stmt.where(User.role == role)
    if status == "active":
        stmt = stmt.where(User.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(User.is_active.is_(False))
    return stmt


def list_users(
    db: Session,
    search: str | None,
    role: str | None,
    status: str | None,
    page: int,
    page_size: int,
    sort: str | None = None,
    direction: str = "asc",
) -> Page:
    stmt = _filtered_users_stmt(db, search, role, status)
    sort_col = SORTABLE_COLUMNS.get(sort, User.name)
    stmt = stmt.order_by(sort_col.desc() if direction == "desc" else sort_col.asc())
    return paginate(db, stmt, page, page_size)


def list_all_users(db: Session, search: str | None, role: str | None, status: str | None) -> list[User]:
    stmt = _filtered_users_stmt(db, search, role, status).order_by(User.name.asc())
    return list(db.scalars(stmt))


def count_active_admins(db: Session, exclude_id: int | None = None) -> int:
    stmt = select(User.id).where(
        User.role == ROLE_ADMIN, User.is_deleted.is_(False), User.is_active.is_(True)
    )
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return len(list(db.scalars(stmt)))


def create_user(db: Session, data: UserCreate) -> User:
    if get_user_by_email(db, data.email) is not None:
        raise UserError(f"A user with email '{data.email}' already exists.")
    user = User(
        name=data.name,
        email=data.email.lower(),
        password_hash=hash_secret(data.password),
        role=data.role,
        security_question=data.security_question,
        security_answer_hash=hash_secret(data.security_answer.strip().lower()),
        admin_pin_hash=hash_secret(data.admin_pin.strip()),
    )
    db.add(user)
    db.flush()
    return user


def update_user(db: Session, user: User, data: UserUpdate, *, acting_user: User) -> User:
    existing = get_user_by_email(db, data.email)
    if existing is not None and existing.id != user.id:
        raise UserError(f"A user with email '{data.email}' already exists.")

    demoting_or_deactivating = (data.role != ROLE_ADMIN and user.role == ROLE_ADMIN) or (
        not data.is_active and user.is_active
    )
    if demoting_or_deactivating and user.id == acting_user.id:
        raise UserError("You cannot remove your own admin access or deactivate your own account.")
    if demoting_or_deactivating and user.role == ROLE_ADMIN and count_active_admins(db, exclude_id=user.id) == 0:
        raise UserError("At least one active admin must remain. Promote another user first.")

    user.name = data.name
    user.email = data.email.lower()
    user.role = data.role
    user.is_active = data.is_active
    db.flush()
    return user


def set_password(db: Session, user: User, new_password: str) -> None:
    from app.services.auth_service import bump_session_version

    user.password_hash = hash_secret(new_password)
    bump_session_version(db, user)
    db.flush()


def delete_user(db: Session, user: User, *, acting_user: User) -> None:
    if user.id == acting_user.id:
        raise UserError("You cannot delete your own account.")
    if user.role == ROLE_ADMIN and count_active_admins(db, exclude_id=user.id) == 0:
        raise UserError("At least one active admin must remain. Promote another user before removing this one.")
    soft_delete(db, user)


def list_deleted_users(db: Session, search: str | None, page: int, page_size: int) -> Page:
    stmt = deleted_query(db, User)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(User.name.ilike(like), User.email.ilike(like)))
    stmt = stmt.order_by(User.updated_at.desc())
    return paginate(db, stmt, page, page_size)


def restore_user(db: Session, user: User) -> User:
    if get_user_by_email(db, user.email) is not None and get_user_by_email(db, user.email).id != user.id:
        raise UserError("Cannot restore: another active user now has this email address.")
    return restore(db, user)


def purge_user(db: Session, user: User) -> None:
    hard_delete(db, user)
