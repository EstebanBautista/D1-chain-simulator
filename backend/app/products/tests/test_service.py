"""Unit tests for the catalog service layer.

No HTTP server and no real database: the service layer takes plain values, so
it can be exercised by calling functions. The cache is replaced by a stub the
same way the repository is, so no Redis has to be running.
"""

from decimal import Decimal

import pytest

from app.products import service
from app.products.models import Product


class FakeSession:
    """Stand-in for a SQLAlchemy session; the repository is stubbed anyway."""


@pytest.fixture
def catalog(monkeypatch):
    """Stub the repository and the cache with an in-memory catalog.

    The cache starts cold (every get is a miss) and records every write, so a
    test can assert both sides of the cache-first rule.
    """
    products = {
        "7702001010301": Product(ean="7702001010301", name="Arroz", price=Decimal("2000")),
        "7702354030014": Product(ean="7702354030014", name="Leche", price=Decimal("1500")),
    }
    cache_writes: list[tuple[str, Product]] = []

    def fake_find_product_by_ean(session, ean):
        return products.get(ean)

    def fake_get_cached(ean):
        return None

    def fake_set_cached(ean, product):
        cache_writes.append((ean, product))

    monkeypatch.setattr(
        service.repository, "find_product_by_ean", fake_find_product_by_ean
    )
    monkeypatch.setattr(service.cache, "get_cached", fake_get_cached)
    monkeypatch.setattr(service.cache, "set_cached", fake_set_cached)
    return {"products": products, "cache_writes": cache_writes}


def test_get_product_returns_known_product(catalog):
    product = service.get_product(FakeSession(), "7702001010301")

    assert product.name == "Arroz"
    assert product.price == Decimal("2000")


def test_get_product_raises_for_unknown_ean(catalog):
    with pytest.raises(service.ProductNotFoundError):
        service.get_product(FakeSession(), "0000000000000")


# --- Cache-first behaviour ----------------------------------------------


def test_a_cache_miss_reads_the_database_and_populates_the_cache(catalog):
    product = service.get_product(FakeSession(), "7702001010301")

    assert catalog["cache_writes"] == [("7702001010301", product)]


def test_an_unknown_ean_is_never_cached(catalog):
    with pytest.raises(service.ProductNotFoundError):
        service.get_product(FakeSession(), "0000000000000")

    assert catalog["cache_writes"] == []


def test_a_cache_hit_never_touches_the_repository(catalog, monkeypatch):
    cached = Product(ean="7702001010301", name="Arroz", price=Decimal("2000"))

    def repository_must_not_run(session, ean):
        raise AssertionError("the repository ran on a cache hit")

    monkeypatch.setattr(
        service.repository, "find_product_by_ean", repository_must_not_run
    )
    monkeypatch.setattr(service.cache, "get_cached", lambda ean: cached)

    product = service.get_product(FakeSession(), "7702001010301")

    assert product is cached
    assert catalog["cache_writes"] == []