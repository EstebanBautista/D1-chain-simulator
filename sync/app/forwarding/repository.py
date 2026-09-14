"""Database access for the forwarder.

Two operations, written as plain SQL rather than through an ORM mapping. The
forwarder only reads three tables the backend owns and stamps one column; a
duplicated set of ORM models here could silently drift from the backend's,
and these queries are shorter to read than the mapping would be.

The age of the oldest queued invoice is computed BY THE DATABASE. The
forwarder and the store's PostgreSQL are different containers, and comparing a
timestamp written by one against the clock of the other is exactly the kind of
thing that works on a laptop and fails in a demonstration. One clock decides.
"""

from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


class PendingStats(NamedTuple):
    """How much is queued, and how long the oldest has been waiting."""

    pending_count: int
    oldest_age_seconds: float


_PENDING_STATS_SQL = text(
    """
    SELECT COUNT(*)                                                AS pending_count,
           COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(sale_date))), 0) AS oldest_age_seconds
    FROM sales
    WHERE forwarded_at IS NULL
    """
)

# The inner SELECT picks which sales to ship; the joins then fetch their lines.
# Ordering by id means "oldest first", and LIMIT bounds one batch.
_PENDING_SALES_SQL = text(
    """
    SELECT s.id            AS sale_id,
           s.register_id   AS register_id,
           s.sale_date     AS sale_date,
           s.total         AS total,
           i.ean           AS ean,
           p.name          AS product_name,
           i.quantity      AS quantity,
           i.unit_price    AS unit_price,
           i.subtotal      AS subtotal
    FROM sales s
    JOIN sale_items i ON i.sale_id = s.id
    JOIN products   p ON p.ean = i.ean
    WHERE s.id IN (
        SELECT id
        FROM sales
        WHERE forwarded_at IS NULL
        ORDER BY id
        LIMIT :limit
    )
    ORDER BY s.id, i.id
    """
)

_MARK_FORWARDED_SQL = text(
    """
    UPDATE sales
    SET forwarded_at = NOW()
    WHERE id IN :sale_ids
      AND forwarded_at IS NULL
    """
).bindparams(bindparam("sale_ids", expanding=True))


def get_pending_stats(session: Session) -> PendingStats:
    """Return how many invoices are queued and the age of the oldest."""
    row = session.execute(_PENDING_STATS_SQL).one()
    return PendingStats(
        pending_count=int(row.pending_count),
        oldest_age_seconds=float(row.oldest_age_seconds),
    )


def find_pending_sales(session: Session, limit: int) -> list[dict]:
    """Return up to `limit` queued invoices, oldest first, with their lines.

    One query, not one per invoice: a batch of ten would otherwise be eleven
    round trips.
    """
    rows = session.execute(_PENDING_SALES_SQL, {"limit": limit}).all()

    invoices: dict[int, dict] = {}
    for row in rows:
        invoice = invoices.get(row.sale_id)
        if invoice is None:
            invoice = {
                "store_invoice_id": row.sale_id,
                "register_id": row.register_id,
                "sold_at": row.sale_date,
                "total": Decimal(row.total),
                "items": [],
            }
            invoices[row.sale_id] = invoice

        invoice["items"].append(
            {
                "ean": row.ean,
                "product_name": row.product_name,
                "quantity": int(row.quantity),
                "unit_price": Decimal(row.unit_price),
                "subtotal": Decimal(row.subtotal),
            }
        )

    return list(invoices.values())


def mark_forwarded(session: Session, sale_ids: list[int]) -> int:
    """Stamp these sales as confirmed by head office. Returns rows affected.

    Called only after the central site has acknowledged them. The
    `forwarded_at IS NULL` guard makes a repeated call harmless.
    """
    if not sale_ids:
        return 0

    result = session.execute(_MARK_FORWARDED_SQL, {"sale_ids": sale_ids})
    session.commit()
    return result.rowcount


def count_pending(session: Session) -> int:
    """Return how many invoices are still queued. Used by the tests."""
    return int(
        session.execute(
            text("SELECT COUNT(*) FROM sales WHERE forwarded_at IS NULL")
        ).scalar_one()
    )
