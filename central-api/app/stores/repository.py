"""Persistence for the chain's stores.

All store database access goes through here. Neither the router nor the
service builds SQL or touches the session directly.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.stores.models import Store


def list_stores(session: Session) -> list[Store]:
    """Return every store in the chain, in a stable order."""
    return list(session.scalars(select(Store).order_by(Store.id)).all())


def find_store(session: Session, store_id: str) -> Store | None:
    """Return one store, or None when the chain has no such store."""
    return session.get(Store, store_id)


def store_exists(session: Session, store_id: str) -> bool:
    """Whether the chain knows this store.

    Ingestion checks this before writing anything: a batch naming a store that
    does not exist is a configuration error, not an invoice.
    """
    return find_store(session, store_id) is not None
