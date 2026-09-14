"""The dashboard's aggregation queries.

Both reports are computed by the database with GROUP BY. Pulling every invoice
into Python to sum it would work at classroom volume and be wrong at every
other volume — and it is what the indexes in `central-db/01-schema.sql` exist
to support.
"""

from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion.models import Invoice, InvoiceItem
from app.stores.models import Store


class StoreTotal(NamedTuple):
    store_id: str
    store_name: str
    total: Decimal
    invoice_count: int


class ProductTotal(NamedTuple):
    ean: str
    product_name: str
    units_sold: int
    revenue: Decimal


def sales_by_store(session: Session) -> list[StoreTotal]:
    """Total consolidated sales per store, in Colombian pesos.

    A LEFT OUTER JOIN, so a store that has forwarded nothing yet reports zero
    rather than vanishing from the chart. A store missing from a comparison
    reads as a bug; a store showing zero reads as information.
    """
    statement = (
        select(
            Store.id,
            Store.name,
            func.coalesce(func.sum(Invoice.total), 0).label("total"),
            func.count(Invoice.id).label("invoice_count"),
        )
        .select_from(Store)
        .outerjoin(Invoice, Invoice.store_id == Store.id)
        .group_by(Store.id, Store.name)
        .order_by(Store.id)
    )

    return [
        StoreTotal(
            store_id=row.id,
            store_name=row.name,
            total=Decimal(row.total),
            invoice_count=int(row.invoice_count),
        )
        for row in session.execute(statement).all()
    ]


def top_products(
    session: Session, limit: int, store_id: str | None = None
) -> list[ProductTotal]:
    """The best-selling products, ranked by units sold.

    Grouped by EAN, which is the stable product identity — never by name. If
    the two stores happen to spell the same product differently, grouping by
    name would split one product into two entries and the ranking would be
    wrong.

    The display name is then resolved in a second, bounded query: see
    `_latest_names`.
    """
    statement = (
        select(
            InvoiceItem.ean,
            func.sum(InvoiceItem.quantity).label("units_sold"),
            func.sum(InvoiceItem.subtotal).label("revenue"),
        )
        .group_by(InvoiceItem.ean)
        .order_by(func.sum(InvoiceItem.quantity).desc(), InvoiceItem.ean)
        .limit(limit)
    )

    if store_id is not None:
        statement = statement.join(
            Invoice, Invoice.id == InvoiceItem.invoice_id
        ).where(Invoice.store_id == store_id)

    rows = session.execute(statement).all()
    if not rows:
        return []

    names = _latest_names(session, [row.ean for row in rows])

    return [
        ProductTotal(
            ean=row.ean,
            product_name=names.get(row.ean, row.ean),
            units_sold=int(row.units_sold),
            revenue=Decimal(row.revenue),
        )
        for row in rows
    ]


def _latest_names(session: Session, eans: list[str]) -> dict[str, str]:
    """The most recently recorded name for each of these EANs.

    A second query rather than a cleverer single one. It is bounded to the ten
    rows the ranking returned, and "the name on the most recent invoice line"
    is both what a reader expects and readable as SQL — which a window
    function folded into the aggregate above would not have been.
    """
    latest = (
        select(func.max(InvoiceItem.id).label("item_id"))
        .where(InvoiceItem.ean.in_(eans))
        .group_by(InvoiceItem.ean)
        .subquery()
    )

    statement = select(InvoiceItem.ean, InvoiceItem.product_name).join(
        latest, latest.c.item_id == InvoiceItem.id
    )

    return {row.ean: row.product_name for row in session.execute(statement).all()}
