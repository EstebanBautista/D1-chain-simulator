"""Payment gateway configuration, read from the environment."""

import os
from decimal import Decimal

# Charges strictly above this amount are declined. Deterministic on purpose:
# a random decline would make tests unreproducible and would teach a student to
# dismiss a real failure as bad luck.
DECLINE_THRESHOLD = Decimal(os.getenv("DECLINE_THRESHOLD", "1000000"))

# The gateway keeps its own records, separate from the store database. It is a
# different company in the story, and it stores its data accordingly.
GATEWAY_DATABASE_URL = os.getenv("GATEWAY_DATABASE_URL", "sqlite:////data/gateway.db")
