"""Simple offset-based pagination helper shared by all list views."""
from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

ItemT = TypeVar("ItemT")


@dataclass
class Page(Generic[ItemT]):
    """A single page of results plus the metadata needed to render pager controls."""

    items: list[ItemT]
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        return max(1, (self.total_items + self.page_size - 1) // self.page_size)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def start_index(self) -> int:
        return 0 if self.total_items == 0 else (self.page - 1) * self.page_size + 1

    @property
    def end_index(self) -> int:
        return min(self.page * self.page_size, self.total_items)

    @property
    def page_range(self) -> list[int]:
        """A small window of page numbers centered on the current page."""
        window = 2
        start = max(1, self.page - window)
        end = min(self.total_pages, self.page + window)
        return list(range(start, end + 1))


def paginate(db: Session, stmt, page: int, page_size: int) -> Page:
    """Execute ``stmt`` with an offset/limit window and return a Page of ORM objects."""
    page = max(1, page)
    page_size = max(1, page_size)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_items = db.scalar(count_stmt) or 0

    items_stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(items_stmt).all())

    return Page(items=items, page=page, page_size=page_size, total_items=total_items)
