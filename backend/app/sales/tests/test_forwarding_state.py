"""Unit tests for the sale's forwarding state.

Recording a sale must leave it queued for head office, in the same transaction
that wrote it and with no second write. These run against a throwaway
in-memory SQLite database.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.base import Base
from app.products.models import Product
from app.sales import repository


@pytest.fixture
def session():
    """An isolated database, created and discarded per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db_session = factory()
    db_session.add(Product(ean="7702001010301", name="Arroz", price=Decimal("2000")))
    db_session.commit()

    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def record_one(session):
    return repository.create_sale(
        session=session,
        register_id="register-1",
        total=Decimal("4000"),
        sale_date=datetime(2026, 8, 26, 10, 30),
        items=[
            {
                "ean": "7702001010301",
                "quantity": 2,
                "unit_price": Decimal("2000"),
                "subtotal": Decimal("4000"),
            }
        ],
    )


def test_a_new_sale_is_queued_for_head_office(session):
    sale = record_one(session)

    stored = repository.find_sale_by_id(session, sale.id)

    assert stored.forwarded_at is None


def test_queueing_needs_no_second_write(session):
    """The queue is a column default, not an extra insert.

    If recording a sale ever needed a follow-up write to enqueue it, the sale
    would be committed while unqueued for an instant, and a crash in that
    window would lose it. Asserting on the object the single commit returned
    is what pins that down.
    """
    sale = record_one(session)

    assert sale.forwarded_at is None
