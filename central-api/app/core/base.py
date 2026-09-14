"""The declarative base every ORM model inherits from.

Deliberately kept apart from the engine in `database.py`, so that importing a
model does not open a connection or require the MySQL driver — the unit tests
run against in-memory SQLite and must be able to import the models they test.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the service."""
