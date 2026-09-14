"""Unit tests for the catalog service layer.

No HTTP server and no real database: the service layer takes plain values, so
it can be exercised by calling functions.
"""

from decimal import Decimal

import pytest

from app.products import service
from app.products.models import Product


class FakeSession:
    """Stand-in for a SQLAlchemy session; the repository is stubbed anyway."""


@pytest.fixture
def catalog(monkeypatch):
    """Stub the repository with a small in-memory catalog."""
    products = {
        "7702001010301": Product(ean="7702001010301", name="Arroz", price=Decimal("2000")),
        "7702354030014": Product(ean="7702354030014", name="Leche", price=Decimal("1500")),
    }

    def fake_find_product_by_ean(session, ean):
        return products.get(ean)

    monkeypatch.setattr(
        service.repository, "find_product_by_ean", fake_find_product_by_ean
    )
    return products


def test_get_product_returns_known_product(catalog):
    product = service.get_product(FakeSession(), "7702001010301")

    assert product.name == "Arroz"
    assert product.price == Decimal("2000")


def test_get_product_raises_for_unknown_ean(catalog):
    with pytest.raises(service.ProductNotFoundError):
        service.get_product(FakeSession(), "0000000000000")
