"""Engine and session for the gateway's own data store.

The engine is created once, here. Flask has no dependency-injection mechanism
of its own, so the router takes a session from `SessionLocal` and closes it in
a `finally` block rather than receiving one injected — but it still comes from
this single provider, and no other module builds an engine.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.base import Base
from app.core.config import GATEWAY_DATABASE_URL

engine = create_engine(GATEWAY_DATABASE_URL, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_tables() -> None:
    """Create the gateway's tables if they are not there yet.

    This is the one service in the project that creates its own schema. It
    keeps a SQLite file on its own volume, so there is no database image to
    run initialization scripts for it, and in the exercise's story the gateway
    is a black box operated by someone else: it sets itself up. The store and
    central databases take their schema from readable SQL instead.

    The caller is responsible for importing the models first, so that they are
    registered on the metadata. That import belongs in the entry point, not
    here: nothing in `core/` may import a domain package.
    """
    Base.metadata.create_all(engine)
