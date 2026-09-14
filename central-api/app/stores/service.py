"""Store business logic.

This layer knows nothing about HTTP: it takes plain values and returns plain
objects, which is what makes it unit testable without starting a server.
"""

from sqlalchemy.orm import Session

from app.stores import repository
from app.stores.models import Store


class UnknownStoreError(Exception):
    """The chain has no store with this identifier."""

    def __init__(self, store_id: str) -> None:
        super().__init__(f"Unknown store {store_id}")
        self.store_id = store_id


def list_stores(session: Session) -> list[Store]:
    """Return every store in the chain."""
    return repository.list_stores(session)


def require_store(session: Session, store_id: str) -> None:
    """Raise UnknownStoreError unless the chain knows this store."""
    if not repository.store_exists(session, store_id):
        raise UnknownStoreError(store_id)
