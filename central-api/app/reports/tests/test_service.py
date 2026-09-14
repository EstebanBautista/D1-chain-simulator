"""Unit tests for the report service layer."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.base import Base
from app.ingestion.models import Invoice, InvoiceItem
from app.reports import service
from app.stores.models import Store
from app.stores.service import UnknownStoreError


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db_session = factory()
    db_session.add_all(
        [
            Store(id="store-1", name="Tienda 1 - Chapinero"),
            Store(id="store-2", name="Tienda 2 - Kennedy"),
        ]
    )
    invoice = Invoice(
        store_id="store-1",
        store_invoice_id=1,
        register_id="register-1",
        sold_at=datetime(2026, 8, 26, 12, 0, 0),
        received_at=datetime(2026, 8, 26, 12, 1, 0),
        total=Decimal("4000"),
    )
    invoice.items = [
        InvoiceItem(
            ean="111",
            product_name="Arroz",
            quantity=2,
            unit_price=Decimal("2000"),
            subtotal=Decimal("4000"),
        )
    ]
    db_session.add(invoice)
    db_session.commit()

    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def test_no_filter_returns_the_chain_wide_ranking(session):
    assert service.top_products(session)[0].ean == "111"


def test_a_known_store_filter_is_accepted(session):
    assert service.top_products(session, store_id="store-1")[0].units_sold == 2


def test_an_unknown_store_filter_is_rejected(session):
    """Never silently widen a filter.

    Falling back to the chain-wide ranking would show a reader more data than
    they asked for while the page still claimed to be filtered.
    """
    with pytest.raises(UnknownStoreError):
        service.top_products(session, store_id="store-99")


def test_the_top_products_limit_is_ten(session):
    """The requirement says ten; this pins the configured default."""
    from app.core.config import TOP_PRODUCTS_LIMIT

    assert TOP_PRODUCTS_LIMIT == 10


def test_sales_by_store_covers_every_store(session):
    assert len(service.sales_by_store(session)) == 2
