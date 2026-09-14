"""Database engine and session handling for the forwarder.

The engine is created once, here. The forwarder is a worker with no HTTP
surface and therefore no framework to inject sessions for it, so it takes them
from this provider and closes them in a `finally` block.

It reads its own store's database — the same PostgreSQL the backend writes to.
It never defines the schema; the store's SQL scripts do that.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DATABASE_URL

# pool_pre_ping matters more here than anywhere: this process is long-lived and
# mostly idle, so its pooled connections are exactly the ones PostgreSQL drops.
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


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session for one unit of work and always close it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
