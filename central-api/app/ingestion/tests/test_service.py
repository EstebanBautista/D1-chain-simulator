"""Unit tests for the ingestion service.

The behaviour that matters here is idempotency: a retried batch must not
double the chain's reported revenue.
"""

from decimal import Decimal

import pytest

from app.ingestion import repository, service
from app.ingestion.tests.conftest import make_batch, make_invoice, make_item
from app.stores.service import UnknownStoreError


# --- Happy path ----------------------------------------------------------


def test_a_batch_is_accepted_and_stored(session):
    result = service.ingest_batch(session, make_batch())

    assert result.accepted == [1]
    assert result.duplicates == []
    assert repository.count_invoices(session) == 1


def test_an_invoice_and_its_lines_land_together(session):
    batch = make_batch(
        invoices=[
            make_invoice(
                store_invoice_id=1,
                items=[make_item(), make_item(ean="7702354030014", name="Leche")],
            )
        ]
    )

    service.ingest_batch(session, batch)

    stored = repository.find_invoice(session, "store-1", 1)
    assert stored is not None
    assert len(stored.items) == 2


def test_an_invoice_records_its_origin_and_both_timestamps(session):
    service.ingest_batch(session, make_batch())

    stored = repository.find_invoice(session, "store-1", 1)

    assert stored.store_id == "store-1"
    assert stored.register_id == "register-1"
    assert stored.sold_at is not None
    assert stored.received_at is not None


def test_the_product_name_is_kept_on_the_line(session):
    service.ingest_batch(session, make_batch())

    stored = repository.find_invoice(session, "store-1", 1)

    assert stored.items[0].product_name == "Arroz"


# --- Idempotency ---------------------------------------------------------


def test_a_resent_batch_creates_no_second_invoice(session):
    batch = make_batch()

    service.ingest_batch(session, batch)
    result = service.ingest_batch(session, batch)

    assert result.accepted == []
    assert result.duplicates == [1]
    assert repository.count_invoices(session) == 1


def test_a_duplicate_is_reported_rather_than_raised(session):
    """The forwarder must be able to stamp these and move on."""
    batch = make_batch()
    service.ingest_batch(session, batch)

    result = service.ingest_batch(session, batch)

    assert result.duplicates == [1]


def test_a_partially_overlapping_batch_keeps_its_new_invoices(session):
    service.ingest_batch(session, make_batch(invoices=[make_invoice(1)]))

    result = service.ingest_batch(
        session,
        make_batch(invoices=[make_invoice(1), make_invoice(2), make_invoice(3)]),
    )

    assert result.accepted == [2, 3]
    assert result.duplicates == [1]
    assert repository.count_invoices(session) == 3


def test_the_same_invoice_number_from_two_stores_is_two_invoices(session):
    """Both stores number their sales from 1; that is not a collision."""
    service.ingest_batch(session, make_batch(store_id="store-1"))
    service.ingest_batch(session, make_batch(store_id="store-2"))

    assert repository.count_invoices(session) == 2
    assert repository.find_invoice(session, "store-1", 1) is not None
    assert repository.find_invoice(session, "store-2", 1) is not None


def test_a_resent_batch_does_not_change_the_reported_total(session):
    batch = make_batch()
    service.ingest_batch(session, batch)
    before = repository.count_invoices(session, "store-1")

    service.ingest_batch(session, batch)

    assert repository.count_invoices(session, "store-1") == before


# --- Validation ----------------------------------------------------------


def test_an_unknown_store_is_rejected(session):
    with pytest.raises(UnknownStoreError):
        service.ingest_batch(session, make_batch(store_id="store-99"))

    assert repository.count_invoices(session) == 0


def test_an_empty_batch_is_rejected(session):
    with pytest.raises(service.InvalidBatchError):
        service.ingest_batch(session, make_batch(invoices=[]))


def test_an_invoice_with_no_lines_is_rejected(session):
    with pytest.raises(service.InvalidBatchError):
        service.ingest_batch(
            session, make_batch(invoices=[make_invoice(1, items=[])])
        )

    assert repository.count_invoices(session) == 0


def test_a_non_positive_quantity_is_rejected(session):
    invoice = make_invoice(1, items=[make_item(quantity=0)])

    with pytest.raises(service.InvalidBatchError):
        service.ingest_batch(session, make_batch(invoices=[invoice]))

    assert repository.count_invoices(session) == 0


def test_a_negative_amount_is_rejected(session):
    invoice = make_invoice(1, items=[make_item(unit_price="-100")])

    with pytest.raises(service.InvalidBatchError):
        service.ingest_batch(session, make_batch(invoices=[invoice]))

    assert repository.count_invoices(session) == 0


def test_validation_rejects_before_writing_any_sibling(session):
    """A batch lands whole or not at all.

    The invalid invoice is last, so a service that validated lazily would
    already have written the two good ones by the time it noticed.
    """
    batch = make_batch(
        invoices=[
            make_invoice(1),
            make_invoice(2),
            make_invoice(3, items=[make_item(quantity=-1)]),
        ]
    )

    with pytest.raises(service.InvalidBatchError):
        service.ingest_batch(session, batch)

    assert repository.count_invoices(session) == 0


def test_amounts_survive_as_exact_decimals(session):
    invoice = make_invoice(1, items=[make_item(quantity=3, unit_price="1999.99")])

    service.ingest_batch(session, make_batch(invoices=[invoice]))

    stored = repository.find_invoice(session, "store-1", 1)
    assert Decimal(stored.items[0].subtotal) == Decimal("5999.97")
