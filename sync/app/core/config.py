"""Forwarder configuration, read entirely from the environment.

This is the ONLY module in the service that touches `os.environ`.

The three batching parameters are here rather than baked into the code on
purpose: setting BATCH_MAX_AGE_SECONDS to 10 lets you watch the age trigger
fire during a demonstration instead of waiting a full minute for it.
"""

import os

# Which store this forwarder ships for. Both stores run the same image.
STORE_ID: str = os.getenv("STORE_ID", "store-1")

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://store:store_password@postgres:5432/store",
)

CENTRAL_API_URL: str = os.getenv("CENTRAL_API_URL", "http://central-api:8000")

CENTRAL_API_TIMEOUT_SECONDS: float = float(
    os.getenv("CENTRAL_API_TIMEOUT_SECONDS", "10")
)

# Send as soon as this many invoices are queued, without waiting for the timer.
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))

# Send everything queued once the OLDEST queued invoice reaches this age, however
# few there are. Measured from the oldest invoice, not from the last batch —
# see the forwarding service for why that distinction matters.
BATCH_MAX_AGE_SECONDS: float = float(os.getenv("BATCH_MAX_AGE_SECONDS", "60"))

# How often to look. This is the price of the age trigger's precision: an
# invoice can wait up to BATCH_MAX_AGE_SECONDS plus one poll.
SYNC_POLL_SECONDS: float = float(os.getenv("SYNC_POLL_SECONDS", "5"))
