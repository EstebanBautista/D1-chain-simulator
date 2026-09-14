"""Service-wide endpoints that belong to no business domain.

Only the liveness probe lives here. Keeping it out of the domain packages
means `products`, `sales` and `payments` each hold nothing but their own
concern, and keeping it in a router rather than in `main.py` means every route
the service exposes is registered the same way.
"""

from fastapi import APIRouter

from app.core.config import STORE_ID, STORE_NAME

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe used by the registers and by `make test`.

    It reports the store as well as the status: with two stores running side
    by side, "the backend is up" is not a useful answer on its own.
    """
    return {
        "status": "ok",
        "service": "store-backend",
        "store_id": STORE_ID,
        "store_name": STORE_NAME,
    }
