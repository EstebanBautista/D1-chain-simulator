"""Logging setup for the backend.

Configured once, from here, and called by the application entry point. Modules
take a module-level logger with `logging.getLogger(__name__)` and never print
operational messages to standard output.

Every line carries the store this backend serves. With two stores running side
by side, `docker compose logs` interleaves both, and a line that does not say
where it came from is not much use.
"""

import logging

from app.core.config import STORE_ID


def configure_logging() -> None:
    """Install the service-wide logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s %(levelname)s [{STORE_ID}] %(name)s %(message)s",
    )
