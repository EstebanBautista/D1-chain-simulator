"""Persistence for the product catalog.

All catalog database access goes through here. Neither the router nor the
service builds SQL or touches the session directly.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.products.models import Product


def find_product_by_ean(session: Session, ean: str) -> Product | None:
    """Return the product with this barcode, or None when it does not exist."""
    return session.scalar(select(Product).where(Product.ean == ean))


def find_products_by_eans(session: Session, eans: list[str]) -> dict[str, Product]:
    """Return the requested products keyed by EAN.

    Fetching the whole cart in one query keeps the payment path from issuing a
    round trip per item. Missing EANs are simply absent from the result, which
    is how the service layer detects them.
    """
    if not eans:
        return {}
    products = session.scalars(select(Product).where(Product.ean.in_(eans))).all()
    return {product.ean: product for product in products}
