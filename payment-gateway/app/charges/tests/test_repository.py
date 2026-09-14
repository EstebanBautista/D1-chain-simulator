"""Unit tests for the payment gateway's persistence layer.

These run against a throwaway in-memory database, never against the deployed
gateway store.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.charges import repository, service
from app.core.base import Base

# Imported so the transaction table is registered on the metadata before
# create_all runs.
from app.charges import models  # noqa: F401


@pytest.fixture
def session():
    """An isolated database, created and discarded per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def test_records_an_approved_transaction(session):
    transaction = repository.record_transaction(
        session=session,
        transaction_id="tx-approved",
        amount=Decimal("45000"),
        register_id="register-1",
        status=service.APPROVED,
        decline_reason=None,
    )

    stored = repository.find_by_transaction_id(session, "tx-approved")

    assert stored is not None
    assert stored.status == service.APPROVED
    assert stored.decline_reason is None
    assert Decimal(stored.amount) == Decimal("45000")
    assert stored.register_id == "register-1"
    assert stored.processed_at == transaction.processed_at


def test_records_a_declined_transaction_with_its_reason(session):
    repository.record_transaction(
        session=session,
        transaction_id="tx-declined",
        amount=Decimal("9000000"),
        register_id="register-2",
        status=service.DECLINED,
        decline_reason=service.AMOUNT_EXCEEDED_REASON,
    )

    stored = repository.find_by_transaction_id(session, "tx-declined")

    assert stored is not None
    assert stored.status == service.DECLINED
    assert stored.decline_reason == service.AMOUNT_EXCEEDED_REASON
    assert stored.processed_at is not None


def test_find_by_transaction_id_returns_none_when_unknown(session):
    assert repository.find_by_transaction_id(session, "does-not-exist") is None


def test_process_charge_records_every_outcome(session):
    approved = service.process_charge(session, Decimal("1000"), "register-1")
    declined = service.process_charge(session, Decimal("-5"), "register-1")

    assert approved["status"] == service.APPROVED
    assert declined["status"] == service.DECLINED
    assert repository.find_by_transaction_id(session, approved["transaction_id"])
    assert repository.find_by_transaction_id(session, declined["transaction_id"])
