"""Aggregate queries powering the dashboard widgets."""
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.contract import Contract
from app.models.invoice import STATUS_VOID, Invoice
from app.models.payment import Payment
from app.models.user import User


@dataclass
class DashboardStats:
    total_contracts: int
    total_ordered_qty: Decimal
    total_pending_qty: Decimal
    total_invoices: int
    outstanding: Decimal
    recycle_bin_count: int


def get_dashboard_stats(db: Session) -> DashboardStats:
    """Compute all dashboard widget values with a handful of aggregate queries."""
    total_contracts = db.scalar(
        select(func.count()).select_from(Contract).where(Contract.is_deleted.is_(False))
    ) or 0

    ordered_total, supplied_total = db.execute(
        select(func.coalesce(func.sum(Contract.qty_ordered), 0), func.coalesce(func.sum(Contract.qty_supplied), 0))
        .where(Contract.is_deleted.is_(False))
    ).one()

    total_invoices = db.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.is_deleted.is_(False), Invoice.status != STATUS_VOID)
    ) or 0

    grand_total_sum = db.scalar(
        select(func.coalesce(func.sum(Invoice.grand_total), 0))
        .where(Invoice.is_deleted.is_(False), Invoice.status != STATUS_VOID)
    ) or 0

    paid_sum = db.scalar(
        select(func.coalesce(func.sum(Payment.amount_received + Payment.tds_deducted + Payment.ld_applied), 0))
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .where(Payment.is_deleted.is_(False), Invoice.is_deleted.is_(False), Invoice.status != STATUS_VOID)
    ) or 0

    outstanding = Decimal(str(grand_total_sum)) - Decimal(str(paid_sum))

    # Invoices/payments are excluded here: once posted they're voided rather than
    # soft-deleted, so they never appear in the Recycle Bin (see Void & Reissue).
    recycle_bin_count = 0
    for model in (Client, Contract, User):
        recycle_bin_count += db.scalar(
            select(func.count()).select_from(model).where(model.is_deleted.is_(True))
        ) or 0

    return DashboardStats(
        total_contracts=total_contracts,
        total_ordered_qty=Decimal(str(ordered_total)),
        total_pending_qty=Decimal(str(ordered_total)) - Decimal(str(supplied_total)),
        total_invoices=total_invoices,
        outstanding=outstanding,
        recycle_bin_count=recycle_bin_count,
    )
