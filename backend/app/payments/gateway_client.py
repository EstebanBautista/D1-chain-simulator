"""HTTP client for the external payment gateway.

Kept apart from service.py so the business rules can be unit tested with this
module replaced by a stub, without any HTTP happening.
"""

from decimal import Decimal

import httpx

from app.core.config import PAYMENT_GATEWAY_TIMEOUT_SECONDS, PAYMENT_GATEWAY_URL


class PaymentGatewayUnavailableError(Exception):
    """The gateway could not be reached, or did not answer in time."""


def charge(amount: Decimal, register_id: str) -> dict:
    """Ask the gateway to charge `amount` and return its decision.

    Raises PaymentGatewayUnavailableError on any transport-level problem, so
    the caller can tell "the gateway said no" apart from "the gateway never
    answered" — the second must never be treated as a decline.
    """
    try:
        response = httpx.post(
            f"{PAYMENT_GATEWAY_URL}/charges",
            json={"amount": float(amount), "register_id": register_id},
            timeout=PAYMENT_GATEWAY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise PaymentGatewayUnavailableError(str(error)) from error
