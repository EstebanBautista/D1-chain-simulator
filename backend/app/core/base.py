"""The declarative base every ORM model inherits from.

Deliberately kept in its own module, apart from the engine in `database.py`.
Importing a model must not open a database connection or require the
PostgreSQL driver to be installed — otherwise the unit tests, which run
against in-memory SQLite, could not so much as import the models they test.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the service."""
