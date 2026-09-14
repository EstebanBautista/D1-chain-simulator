"""Persistence for recorded sales.

All sale database access goes through here. Neither the router nor the service
builds SQL or touches the session directly.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.sales.models import Sale, SaleItem


def create_sale(
    session: Session,
    register_id: str,
    total: Decimal,
    sale_date: datetime,
    items: list[dict],
) -> Sale:
    """Write a sale and its detail in a single transaction.

    Either the header and every item land together, or nothing does: a failure
    while writing the detail rolls the header back too.
    """
    sale = Sale(
        sale_date=sale_date,
        total=total,
        register_id=register_id,
    )
    sale.items = [
        SaleItem(
            ean=item["ean"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            subtotal=item["subtotal"],
        )
        for item in items
    ]

    try:
        session.add(sale)
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(sale)
    return sale


def find_sale_by_id(session: Session, sale_id: int) -> Sale | None:
    """Return a sale with its detail, or None when it does not exist."""
    return session.scalar(select(Sale).where(Sale.id == sale_id))


def count_sales(session: Session) -> int:
    """Return how many sales are recorded. Used by the integration test."""
    return len(session.scalars(select(Sale.id)).all())
