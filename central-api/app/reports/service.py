"""Report business logic.

Thin by design: the aggregation is the database's job, so what is left here is
deciding which report to run and refusing a filter that names a store the
chain does not have.
"""

from sqlalchemy.orm import Session

from app.core.config import TOP_PRODUCTS_LIMIT
from app.reports import repository
from app.reports.repository import ProductTotal, StoreTotal
from app.stores import service as stores_service


def sales_by_store(session: Session) -> list[StoreTotal]:
    """Total consolidated sales per store, every store included."""
    return repository.sales_by_store(session)


def top_products(session: Session, store_id: str | None = None) -> list[ProductTotal]:
    """The ten best-selling products, chain-wide or for one store.

    An unknown store filter raises rather than falling back to the chain-wide
    ranking. Silently widening a filter would show a reader more data than
    they asked for while the page still claimed to be filtered.
    """
    if store_id is not None:
        stores_service.require_store(session, store_id)

    return repository.top_products(
        session, limit=TOP_PRODUCTS_LIMIT, store_id=store_id
    )
