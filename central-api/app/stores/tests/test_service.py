"""Unit tests for the store service layer.

`require_store` is the gate ingestion and the reports both stand behind, so it
is worth testing on its own rather than only through them.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.base import Base
from app.stores import service
from app.stores.models import Store
from app.stores.service import UnknownStoreError

# Imported so the invoice tables are registered on the shared metadata before
# create_all runs; the store tests do not use them.
from app.ingestion import models  # noqa: F401


@pytest.fixture
def session():
    """An isolated database, created and discarded per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db_session = factory()
    db_session.add_all(
        [
            Store(id="store-1", name="Tienda 1 - Chapinero"),
            Store(id="store-2", name="Tienda 2 - Kennedy"),
        ]
    )
    db_session.commit()

    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def test_lists_every_store_in_a_stable_order(session):
    stores = service.list_stores(session)

    assert [store.id for store in stores] == ["store-1", "store-2"]


def test_a_store_carries_its_spanish_display_name(session):
    """The identifier is English; the name is what a reader sees."""
    stores = service.list_stores(session)

    assert stores[0].name == "Tienda 1 - Chapinero"


def test_require_store_accepts_a_known_store(session):
    service.require_store(session, "store-2")


def test_require_store_rejects_an_unknown_store(session):
    with pytest.raises(UnknownStoreError) as error:
        service.require_store(session, "store-99")

    assert error.value.store_id == "store-99"


def test_the_error_names_the_store_it_rejected(session):
    """So a misconfigured forwarder's batch fails with a readable reason."""
    with pytest.raises(UnknownStoreError, match="store-99"):
        service.require_store(session, "store-99")
