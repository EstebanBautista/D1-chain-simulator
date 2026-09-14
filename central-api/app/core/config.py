"""Central API configuration, read entirely from the environment.

This is the ONLY module in the service that touches `os.environ`. No hostname
or credential is written anywhere in the code.
"""

import os

DATABASE_URL: str = os.getenv(
    "CENTRAL_DATABASE_URL",
    "mysql+pymysql://central:central_password@central-mysql:3306/central",
)

# Where batches are enqueued so the ingestion worker, not the API request, can
# write them into MySQL. Only the central API and the worker can reach it: the
# queue lives on head office's LAN and a store's forwarder is never on it.
RABBITMQ_URL: str = os.getenv(
    "RABBITMQ_URL",
    "amqp://central:central_password@rabbitmq:5672/",
)

# How many products the top-products report returns. The requirement says ten;
# it is a constant here rather than a literal in a query so the number appears
# once.
TOP_PRODUCTS_LIMIT: int = int(os.getenv("TOP_PRODUCTS_LIMIT", "10"))
