"""Catalog business logic.

This layer knows nothing about HTTP: it takes plain values, raises plain
exceptions and returns plain objects, which is what makes it unit testable
without starting a server.
"""

from sqlalchemy.orm import Session

from app.products import cache, repository
from app.products.models import Product


class ProductNotFoundError(Exception):
    """No product carries the requested barcode."""

    def __init__(self, ean: str) -> None:
        super().__init__(f"No product found for EAN {ean}")
        self.ean = ean


def get_product(session: Session, ean: str, catalog_cache=cache) -> Product:
    """Return the product for this barcode, or raise ProductNotFoundError.

    The cache is checked first: a hit answers without touching PostgreSQL. On
    a miss the database is read and, when the product exists, the answer is
    stored so the next request for the same barcode is served from cache.
    `catalog_cache` is injected like `gateway` in payments, so a unit test can
    replace the real Redis client with a stub.
    """
    cached = catalog_cache.get_cached(ean)
    if cached is not None:
        return cached

    product = repository.find_product_by_ean(session, ean)
    if product is None:
        raise ProductNotFoundError(ean)

    catalog_cache.set_cached(ean, product)
    return product


def get_products_by_eans(session: Session, eans: list[str]) -> dict[str, Product]:
    """Return the requested products keyed by EAN, omitting unknown ones.

    The payment package prices a cart through this rather than reaching into
    the catalog's repository, so package talks to package at the service
    level.
    """
    return repository.find_products_by_eans(session, eans)
