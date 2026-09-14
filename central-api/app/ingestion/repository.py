"""Persistence for consolidated invoices.

All invoice database access goes through here. Neither the router nor the
service builds SQL or touches the session directly.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ingestion.models import Invoice, InvoiceItem
from app.ingestion.schemas import InvoiceRequest


class DuplicateInvoiceError(Exception):
    """Head office already holds this store's invoice."""


def insert_invoice(
    session: Session,
    store_id: str,
    invoice: InvoiceRequest,
    received_at: datetime,
) -> Invoice:
    """Write one invoice and all of its lines in a single transaction.

    Raises DuplicateInvoiceError when the (store, invoice number) pair is
    already held. The uniqueness constraint in the schema is what detects
    that, rather than a read-then-write check in application code: a check
    would leave a window in which two concurrent batches both pass it.

    A SAVEPOINT wraps the write so that one duplicate in a batch does not tear
    down the whole transaction and take its siblings with it.
    """
    row = Invoice(
        store_id=store_id,
        store_invoice_id=invoice.store_invoice_id,
        register_id=invoice.register_id,
        sold_at=invoice.sold_at,
        received_at=received_at,
        total=invoice.total,
    )
    row.items = [
        InvoiceItem(
            ean=item.ean,
            product_name=item.product_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.subtotal,
        )
        for item in invoice.items
    ]

    try:
        with session.begin_nested():
            session.add(row)
    except IntegrityError as error:
        raise DuplicateInvoiceError(
            f"Invoice {invoice.store_invoice_id} of {store_id} is already held"
        ) from error

    return row


def find_invoice(
    session: Session, store_id: str, store_invoice_id: int
) -> Invoice | None:
    """Return one consolidated invoice, or None when it is not held."""
    return session.scalar(
        select(Invoice).where(
            Invoice.store_id == store_id,
            Invoice.store_invoice_id == store_invoice_id,
        )
    )


def count_invoices(session: Session, store_id: str | None = None) -> int:
    """Return how many invoices are held, optionally for one store."""
    statement = select(func.count()).select_from(Invoice)
    if store_id is not None:
        statement = statement.where(Invoice.store_id == store_id)
    return int(session.scalar(statement) or 0)
