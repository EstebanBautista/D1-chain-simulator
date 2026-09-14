"""Sale recording and retrieval business logic.

This layer knows nothing about HTTP: it takes plain values and returns plain
objects, which is what makes it unit testable without starting a server.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.sales import repository
from app.sales.models import Sale


def record_sale(
    session: Session,
    register_id: str,
    total: Decimal,
    sale_date: datetime,
    items: list[dict],
) -> Sale:
    """Persist an approved sale with its detail.

    The payment package calls this rather than the sales repository directly,
    so packages talk to each other at the service level.
    """
    return repository.create_sale(
        session=session,
        register_id=register_id,
        total=total,
        sale_date=sale_date,
        items=items,
    )


def get_sale(session: Session, sale_id: int) -> Sale | None:
    """Return a recorded sale with its detail."""
    return repository.find_sale_by_id(session, sale_id)
