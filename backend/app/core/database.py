"""Database engine and session handling.

The engine is created once, here, and every domain package takes its sessions
from this module. Nothing in `core/` imports a domain package, so the
dependency always runs one way: domain depends on core, never the reverse.

The declarative base lives in `base.py` rather than here, so that importing a
model does not pull in the engine. See that module for why.

The schema itself is NOT created from these models. It comes from the SQL
scripts in `db/`, which PostgreSQL runs on first boot. The models mirror that
schema; they do not define it.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_URL

# pool_pre_ping keeps the backend from handing out connections that PostgreSQL
# already dropped, which happens easily when the database container restarts.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Iterator[Session]:
    """Yield a session per request and always close it.

    Routers receive this through FastAPI's dependency injection rather than
    opening a session themselves.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
