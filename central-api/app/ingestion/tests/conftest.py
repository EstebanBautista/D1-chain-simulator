"""Shared fixtures for the ingestion tests.

These run against a throwaway in-memory SQLite database, never against the
deployed MySQL instance.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.base import Base
from app.ingestion.schemas import BatchRequest, InvoiceRequest, InvoiceItemRequest
from app.ingestion.models import Invoice, InvoiceItem  # noqa: F401
from app.stores.models import Store


@pytest.fixture
def session():
    """An isolated database, created and discarded per test."""
    engine = create_engine("sqlite:///:memory:", future=True)

    # SQLite ignores foreign keys and UNIQUE enforcement details unless asked.
    # Without this the duplicate tests would pass for the wrong reason.
    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db_session = factory()
    db_session.add_all(
        [
            Store(id="store-1", name="Tienda 1 - Chapinero"),
            Store(id="store-2", name="Tienda 2 - Kennedy"),
        ]
    )
    db_session.commit()

    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def make_item(ean="7702001010301", name="Arroz", quantity=2, unit_price="2000"):
    price = Decimal(unit_price)
    return InvoiceItemRequest(
        ean=ean,
        product_name=name,
        quantity=quantity,
        unit_price=price,
        subtotal=price * quantity,
    )


def make_invoice(store_invoice_id=1, items=None, register_id="register-1"):
    items = items if items is not None else [make_item()]
    return InvoiceRequest(
        store_invoice_id=store_invoice_id,
        register_id=register_id,
        sold_at=datetime(2026, 8, 26, 12, 0, 0),
        total=sum(item.subtotal for item in items),
        items=items,
    )


def make_batch(store_id="store-1", invoices=None):
    return BatchRequest(
        store_id=store_id,
        invoices=invoices if invoices is not None else [make_invoice()],
    )
