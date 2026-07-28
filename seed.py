"""Database seeder: creates an admin user, sample clients, contracts, line items,
invoices, payments, and a few dynamic fields so the app is usable immediately.

Run with: python seed.py
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from app.database import SessionLocal, init_db
from app.models.client import Client
from app.models.contract import Contract
from app.models.custom_field import CustomField
from app.models.line_item import LineItem
from app.models.user import User
from app.schemas.custom_field import CustomFieldCreate
from app.schemas.invoice import InvoiceCreate
from app.schemas.payment import PaymentCreate
from app.services import custom_field_service, invoice_service, payment_service
from app.utils.security import hash_secret

random.seed(42)

CLIENT_NAMES = [
    "Indian Air Force", "Indian Navy", "Indian Army", "ISRO", "DRDO",
    "Bharat Electronics Limited", "Mazagon Dock Shipbuilders", "Coal India Limited",
    "Bharat Dynamics Limited", "National Aerospace Laboratories", "Airports Authority of India",
    "GAIL India Limited", "Oil and Natural Gas Corporation", "Steel Authority of India",
    "Bharat Heavy Electricals Limited", "Power Grid Corporation of India",
]

CONTRACT_DESCRIPTIONS = [
    "Supply of Aircraft Landing Gear Assemblies",
    "Avionics Overhaul and Maintenance Contract",
    "Helicopter Engine Spare Parts Supply",
    "Radar System Upgrade and Installation",
    "Composite Structure Manufacturing Order",
    "Ground Support Equipment Supply",
    "Turbine Blade Fabrication Contract",
    "Flight Simulator Software License",
    "Hydraulic System Components Supply",
    "Aircraft Sheet Metal Fabrication",
]

LINE_ITEM_DESCRIPTIONS = [
    "Landing Gear Strut Assembly", "Avionics Control Module", "Turbine Blade Set",
    "Hydraulic Actuator Unit", "Radar Antenna Unit", "Composite Wing Panel",
    "Engine Mounting Bracket", "Cockpit Display Unit", "Fuel Control Valve",
    "Structural Reinforcement Kit",
]


def seed_users(db) -> User:
    existing = db.query(User).filter(User.email == "admin@hal.internal").first()
    if existing:
        return existing
    user = User(
        name="Administrator",
        email="admin@hal.internal",
        password_hash=hash_secret("Admin@123"),
        role="admin",
        security_question="What is your favorite aircraft?",
        security_answer_hash=hash_secret("tejas"),
        admin_pin_hash=hash_secret("1234"),
    )
    db.add(user)
    db.flush()
    print(f"Seeded admin user: {user.email} / password: Admin@123 / PIN: 1234")
    return user


def seed_custom_fields(db) -> None:
    if db.query(CustomField).count() > 0:
        return
    definitions = [
        CustomFieldCreate(
            module="contracts", field_name="project_manager", field_label="Project Manager",
            field_type="text", is_required=False, is_visible=True, field_order=0,
        ),
        CustomFieldCreate(
            module="contracts", field_name="priority", field_label="Priority",
            field_type="dropdown", is_required=False, is_visible=True, field_order=1,
            options='["Low", "Medium", "High", "Critical"]',
        ),
        CustomFieldCreate(
            module="clients", field_name="account_manager", field_label="Account Manager",
            field_type="text", is_required=False, is_visible=True, field_order=0,
        ),
    ]
    for definition in definitions:
        custom_field_service.create_field(db, definition)
    db.flush()
    print("Seeded 3 sample dynamic custom fields.")


def seed_clients(db) -> list[Client]:
    if db.query(Client).count() > 0:
        return db.query(Client).all()
    clients = []
    for idx, name in enumerate(CLIENT_NAMES):
        client = Client(
            name=name,
            email=f"contact{idx}@{name.lower().replace(' ', '')[:12]}.gov.in",
            phone=f"+91-{random.randint(7000000000, 9999999999)}",
            address=f"{random.randint(1, 200)} Defence Colony, Bengaluru, Karnataka",
            gstin=f"29AAAAA{1000 + idx}A1Z{idx % 10}",
            pan=f"AAAAA{1000 + idx}A",
        )
        db.add(client)
        clients.append(client)
    db.flush()
    print(f"Seeded {len(clients)} clients.")
    return clients


def seed_contracts_and_line_items(db, clients: list[Client]) -> list[Contract]:
    if db.query(Contract).count() > 0:
        return db.query(Contract).all()
    contracts = []
    for i in range(24):
        client = random.choice(clients)
        qty_ordered = random.randint(50, 500)
        qty_supplied = random.randint(0, qty_ordered)
        contract = Contract(
            client_id=client.id,
            contract_number=f"HAL/CT/2025/{1000 + i}",
            description=random.choice(CONTRACT_DESCRIPTIONS),
            contract_date=date(2025, 1, 1) + timedelta(days=random.randint(0, 200)),
            qty_ordered=qty_ordered,
            qty_supplied=qty_supplied,
            escalation_notes="Price escalation as per RBI wholesale price index." if i % 5 == 0 else None,
            status="active",
        )
        db.add(contract)
        db.flush()

        for _ in range(random.randint(2, 4)):
            quantity = Decimal(random.randint(5, 50))
            unit_rate = Decimal(random.randint(1000, 50000))
            db.add(
                LineItem(
                    contract_id=contract.id,
                    description=random.choice(LINE_ITEM_DESCRIPTIONS),
                    quantity=quantity,
                    unit_rate=unit_rate,
                    amount=quantity * unit_rate,
                    status=random.choice(["ordered", "supplied", "pending"]),
                )
            )
        contracts.append(contract)
    db.flush()
    print(f"Seeded {len(contracts)} contracts with line items.")
    return contracts


def seed_invoices_and_payments(db, contracts: list[Contract]) -> None:
    invoice_seq = 1
    for contract in contracts[:14]:
        db.flush()
        available_items = [
            item for item in contract.line_items if not item.is_deleted and item.invoice_id is None
        ]
        if not available_items:
            continue
        chosen = available_items[: random.randint(1, len(available_items))]
        try:
            data = InvoiceCreate(
                contract_id=contract.id,
                invoice_number=f"HAL/INV/2025/{2000 + invoice_seq}",
                invoice_date=contract.contract_date + timedelta(days=random.randint(10, 60)),
                gst_percentage=18.0,
                line_item_ids=[item.id for item in chosen],
            )
            invoice = invoice_service.generate_invoice(db, data)
        except invoice_service.InvoiceError:
            continue
        invoice_seq += 1

        if random.random() < 0.7:
            payment_service.record_payment(
                db,
                invoice,
                PaymentCreate(
                    invoice_id=invoice.id,
                    amount_received=float(invoice.grand_total) * random.choice([0.5, 1.0, 1.0]),
                    payment_date=invoice.invoice_date + timedelta(days=random.randint(5, 30)),
                    tds_deducted=float(invoice.grand_total) * 0.02 if random.random() < 0.5 else 0,
                    ld_applied=float(invoice.grand_total) * 0.01 if random.random() < 0.2 else 0,
                    remarks="Payment received via NEFT.",
                ),
            )
    db.flush()
    print(f"Seeded {invoice_seq - 1} invoices with sales journal entries and sample payments.")


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_users(db)
        seed_custom_fields(db)
        clients = seed_clients(db)
        contracts = seed_contracts_and_line_items(db, clients)
        seed_invoices_and_payments(db, contracts)
        db.commit()
        print("Database seeding complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
