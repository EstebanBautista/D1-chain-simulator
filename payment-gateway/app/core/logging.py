"""Logging setup for the payment gateway.

Configured once, from here, and called by the application entry point. Modules
take a module-level logger with `logging.getLogger(__name__)` and never print
operational messages to standard output.
"""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    """Install the service-wide logging configuration."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
