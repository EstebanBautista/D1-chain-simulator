"""Database engine and session handling.

The engine is created once, here, and every domain package takes its sessions
from this module through FastAPI's dependency injection. Nothing in `core/`
imports a domain package.

The schema is NOT created from these models. It comes from the SQL scripts in
`central-db/`, which MySQL runs on first boot. The models mirror that schema;
they do not define it.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_URL

# pool_pre_ping keeps the API from handing out connections MySQL already
# dropped, which happens easily when the database container restarts.
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
    """Yield a session per request and always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
