"""ORM model registry — import every model so Base.metadata sees all tables."""
from app.models.client import Client
from app.models.contract import Contract
from app.models.contract_document import ContractDocument
from app.models.custom_field import CustomField, CustomFieldValue
from app.models.invoice import Invoice
from app.models.line_item import LineItem
from app.models.payment import Payment
from app.models.sales_journal import SalesJournal
from app.models.user import User

__all__ = [
    "Client",
    "Contract",
    "ContractDocument",
    "CustomField",
    "CustomFieldValue",
    "Invoice",
    "LineItem",
    "Payment",
    "SalesJournal",
    "User",
]
