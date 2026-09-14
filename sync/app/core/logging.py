"""Logging setup for the forwarder.

Every line carries the store this forwarder ships for, so that the two
forwarders' logs stay distinguishable when read together.
"""

import logging

from app.core.config import STORE_ID


def configure_logging() -> None:
    """Install the service-wide logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s %(levelname)s [{STORE_ID}] %(name)s %(message)s",
    )
