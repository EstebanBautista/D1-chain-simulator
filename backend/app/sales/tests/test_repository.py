"""Unit tests for the sales persistence layer.

These run against a throwaway in-memory SQLite database, never against the
deployed PostgreSQL instance.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.base import Base
from app.products import repository as products_repository
from app.products.models import Product
from app.sales import repository


@pytest.fixture
def session():
    """An isolated database, created and discarded per test."""
    engine = create_engine("sqlite:///:memory:", future=True)

    # SQLite ignores foreign keys unless asked to enforce them. Without this
    # the rollback test would pass for the wrong reason.
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
            Product(ean="7702001010301", name="Arroz", price=Decimal("2000")),
            Product(ean="7702354030014", name="Leche", price=Decimal("1500")),
        ]
    )
    db_session.commit()

    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def test_create_sale_stores_header_and_detail(session):
    sale = repository.create_sale(
        session=session,
        register_id="register-1",
        total=Decimal("5500"),
        sale_date=datetime(2026, 8, 4, 10, 30),
        items=[
            {
                "ean": "7702001010301",
                "quantity": 2,
                "unit_price": Decimal("2000"),
                "subtotal": Decimal("4000"),
            },
            {
                "ean": "7702354030014",
                "quantity": 1,
                "unit_price": Decimal("1500"),
                "subtotal": Decimal("1500"),
            },
        ],
    )

    stored = repository.find_sale_by_id(session, sale.id)

    assert stored is not None
    assert stored.register_id == "register-1"
    assert Decimal(stored.total) == Decimal("5500")
    assert stored.sale_date == datetime(2026, 8, 4, 10, 30)
    assert len(stored.items) == 2
    assert {item.ean for item in stored.items} == {"7702001010301", "7702354030014"}


def test_sale_item_keeps_the_price_charged_at_the_time(session):
    sale = repository.create_sale(
        session=session,
        register_id="register-1",
        total=Decimal("4000"),
        sale_date=datetime(2026, 8, 4, 10, 30),
        items=[
            {
                "ean": "7702001010301",
                "quantity": 2,
                "unit_price": Decimal("2000"),
                "subtotal": Decimal("4000"),
            }
        ],
    )

    # The product gets more expensive after the sale.
    product = products_repository.find_product_by_ean(session, "7702001010301")
    product.price = Decimal("2500")
    session.commit()

    stored = repository.find_sale_by_id(session, sale.id)

    assert Decimal(stored.items[0].unit_price) == Decimal("2000")


def test_create_sale_rolls_back_when_the_detail_fails(session):
    sales_before = repository.count_sales(session)

    with pytest.raises(Exception):
        repository.create_sale(
            session=session,
            register_id="register-1",
            total=Decimal("4000"),
            sale_date=datetime(2026, 8, 4, 10, 30),
            items=[
                {
                    # No such product: the foreign key rejects this item, and
                    # the header must go down with it.
                    "ean": "0000000000000",
                    "quantity": 1,
                    "unit_price": Decimal("4000"),
                    "subtotal": Decimal("4000"),
                }
            ],
        )

    assert repository.count_sales(session) == sales_before
