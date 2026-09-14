"""Unit tests for the catalog persistence layer.

These run against a throwaway in-memory SQLite database, never against the
deployed PostgreSQL instance.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.base import Base
from app.products import repository
from app.products.models import Product

# Imported so the sale tables are registered on the shared metadata; the
# catalog's own tests do not use them, but create_all needs the full mapping.
from app.sales import models as sale_models  # noqa: F401


@pytest.fixture
def session():
    """An isolated database, created and discarded per test."""
    engine = create_engine("sqlite:///:memory:", future=True)

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


def test_find_product_by_ean_returns_the_product(session):
    product = repository.find_product_by_ean(session, "7702001010301")

    assert product is not None
    assert product.name == "Arroz"


def test_find_product_by_ean_returns_none_when_unknown(session):
    assert repository.find_product_by_ean(session, "0000000000000") is None


def test_find_products_by_eans_skips_unknown_codes(session):
    products = repository.find_products_by_eans(
        session, ["7702001010301", "0000000000000"]
    )

    assert list(products) == ["7702001010301"]
