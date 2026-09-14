"""Service-wide endpoints that belong to no business domain."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe used by the forwarders and by `make test`."""
    return {"status": "ok", "service": "central-api"}
