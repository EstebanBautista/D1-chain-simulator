"""The declarative base every ORM model inherits from.

Kept apart from the engine in `database.py` so that importing a model does not
open a connection — the unit tests run against in-memory SQLite and must be
able to import the models without the deployed store existing.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the gateway."""
