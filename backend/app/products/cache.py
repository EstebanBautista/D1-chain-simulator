"""The catalog cache: whole-product snapshots keyed by EAN.

This module plays the same role for the catalog that `payments.gateway_client`
plays for payments: the outside resource lives inside the domain package that
owns it, and the service talks to this module rather than to Redis directly,
which is what lets a unit test supply a stub.

A cached value is the WHOLE product — EAN, name and price — because the API
answer carries all three. The price is stored as a string so the `Decimal`
survives without the rounding that a JSON float would quietly introduce.

The cache is a shortcut, never a dependency: if Redis is unreachable the
request still works, it just falls through to PostgreSQL.
"""

import json
import logging
from decimal import Decimal

import redis

from app.core.config import PRODUCT_CACHE_TTL_SECONDS, REDIS_URL
from app.products.models import Product

logger = logging.getLogger(__name__)

KEY_PREFIX = "product:"

_client: "redis.Redis | None" = None


def _get_client() -> "redis.Redis":
    """Return the shared Redis client, created lazily.

    Lazy so that importing this module — or running its unit tests, which
    replace it with a stub — never opens a connection to a Redis that is not
    there.
    """
    global _client
    if _client is None:
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def _key(ean: str) -> str:
    return f"{KEY_PREFIX}{ean}"


def get_cached(ean: str) -> Product | None:
    """Return the cached product for this barcode, or None on a miss.

    Falls back to None, and logs, if Redis is unreachable: a caching outage
    degrades to "read PostgreSQL", never to an error. The same fallback is
    used when a stored value fails to parse.
    """
    try:
        raw = _get_client().get(_key(ean))
    except redis.RedisError as error:
        logger.warning("Catalog cache read failed for EAN %s: %s", ean, error)
        return None

    if raw is None:
        return None

    try:
        data = json.loads(raw)
        return Product(
            ean=data["ean"],
            name=data["name"],
            price=Decimal(data["price"]),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        logger.warning("Catalog cache holds a corrupt value for EAN %s: %s", ean, error)
        return None


def set_cached(ean: str, product: Product) -> None:
    """Store the whole product for this barcode with the configured TTL."""
    payload = {
        "ean": product.ean,
        "name": product.name,
        "price": str(product.price),
    }
    try:
        _get_client().set(_key(ean), json.dumps(payload), ex=PRODUCT_CACHE_TTL_SECONDS)
    except redis.RedisError as error:
        logger.warning("Catalog cache write failed for EAN %s: %s", ean, error)