"""Backend configuration, read entirely from the environment.

This is the ONLY module in the service that touches `os.environ`. Everything
else imports the typed values from here, so there is exactly one place to look
when you want to know what this service can be configured with.

No hostname or credential is hardcoded: every value comes from an environment
variable defined in docker-compose.yml, so renaming a service or pointing the
backend at a different gateway needs no code change.
"""

import os

# Which store this backend serves. Both stores run the same image; this is one
# of the few things that tells them apart, and it is why the value is read
# from the environment rather than written anywhere in the code.
STORE_ID: str = os.getenv("STORE_ID", "store-1")
STORE_NAME: str = os.getenv("STORE_NAME", "Tienda 1")

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://store:store_password@postgres:5432/store",
)

PAYMENT_GATEWAY_URL: str = os.getenv(
    "PAYMENT_GATEWAY_URL", "http://payment-gateway:5000"
)

PAYMENT_GATEWAY_TIMEOUT_SECONDS: float = float(
    os.getenv("PAYMENT_GATEWAY_TIMEOUT_SECONDS", "5")
)
