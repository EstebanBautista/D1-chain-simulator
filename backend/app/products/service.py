"""Catalog business logic.

This layer knows nothing about HTTP: it takes plain values, raises plain
exceptions and returns plain objects, which is what makes it unit testable
without starting a server.
"""

from sqlalchemy.orm import Session

from app.products import repository
from app.products.models import Product


class ProductNotFoundError(Exception):
    """No product carries the requested barcode."""

    def __init__(self, ean: str) -> None:
        super().__init__(f"No product found for EAN {ean}")
        self.ean = ean


def get_product(session: Session, ean: str) -> Product:
    """Return the product for this barcode, or raise ProductNotFoundError."""
    product = repository.find_product_by_ean(session, ean)
    if product is None:
        raise ProductNotFoundError(ean)
    return product


def get_products_by_eans(session: Session, eans: list[str]) -> dict[str, Product]:
    """Return the requested products keyed by EAN, omitting unknown ones.

    The payment package prices a cart through this rather than reaching into
    the catalog's repository, so package talks to package at the service
    level.
    """
    return repository.find_products_by_eans(session, eans)
