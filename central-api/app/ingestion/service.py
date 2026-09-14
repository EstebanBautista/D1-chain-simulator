"""Ingestion business logic.

This layer knows nothing about HTTP: it takes plain values, raises plain
exceptions and returns a plain result, which is what makes it unit testable
without starting a server.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.ingestion import repository
from app.ingestion.repository import DuplicateInvoiceError
from app.ingestion.schemas import BatchRequest
from app.stores import service as stores_service

logger = logging.getLogger(__name__)


class InvalidBatchError(Exception):
    """The batch cannot be ingested as submitted."""


class IngestionResult(NamedTuple):
    """Which of the batch's invoices were new, and which were already held."""

    accepted: list[int]
    duplicates: list[int]


def validate_batch(batch: BatchRequest) -> None:
    """Reject a batch that must not be written.

    Runs in full BEFORE anything is persisted: a batch is accepted whole or
    not at all, so a malformed invoice never lands half-ingested next to its
    valid siblings.
    """
    if not batch.invoices:
        raise InvalidBatchError("The batch carries no invoices")

    for invoice in batch.invoices:
        if not invoice.items:
            raise InvalidBatchError(
                f"Invoice {invoice.store_invoice_id} carries no lines"
            )

        if invoice.total < Decimal("0"):
            raise InvalidBatchError(
                f"Invoice {invoice.store_invoice_id} has a negative total"
            )

        for item in invoice.items:
            if item.quantity <= 0:
                raise InvalidBatchError(
                    f"Invoice {invoice.store_invoice_id} has a non-positive "
                    f"quantity for EAN {item.ean}"
                )
            if item.unit_price < Decimal("0") or item.subtotal < Decimal("0"):
                raise InvalidBatchError(
                    f"Invoice {invoice.store_invoice_id} has a negative amount "
                    f"for EAN {item.ean}"
                )


def ingest_batch(
    session: Session,
    batch: BatchRequest,
    received_at: datetime | None = None,
) -> IngestionResult:
    """Validate and persist a batch, absorbing invoices already held.

    A duplicate is reported, not raised: the forwarder retrying a batch whose
    response was lost is the normal case this whole design exists for, and
    answering it with an error would leave those invoices stuck in the store's
    queue forever.
    """
    stores_service.require_store(session, batch.store_id)
    validate_batch(batch)

    stamp = received_at or datetime.now()
    accepted: list[int] = []
    duplicates: list[int] = []

    for invoice in batch.invoices:
        try:
            repository.insert_invoice(
                session=session,
                store_id=batch.store_id,
                invoice=invoice,
                received_at=stamp,
            )
        except DuplicateInvoiceError:
            duplicates.append(invoice.store_invoice_id)
        else:
            accepted.append(invoice.store_invoice_id)

    session.commit()

    logger.info(
        "Batch from %s: %s accepted, %s already held",
        batch.store_id,
        len(accepted),
        len(duplicates),
    )

    return IngestionResult(accepted=accepted, duplicates=duplicates)
