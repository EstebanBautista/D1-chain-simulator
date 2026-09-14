"""HTTP surface for charges.

This layer only translates between HTTP and the service layer: it parses the
request, calls a service, and maps failures onto status codes. It builds no
queries.

Flask has no dependency-injection mechanism, so the session is taken from the
shared provider in `core.database` and closed in a `finally` block. It still
comes from the one provider; this module never builds an engine of its own.
"""

import logging
from decimal import Decimal, InvalidOperation

from flask import Blueprint, Response, jsonify, request

from app.charges import service
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

blueprint = Blueprint("gateway", __name__)


@blueprint.get("/health")
def health() -> Response:
    """Liveness probe."""
    return jsonify({"status": "ok", "service": "payment-gateway"})


@blueprint.post("/charges")
def create_charge() -> Response | tuple[Response, int]:
    """Process a charge request and answer with the decision."""
    payload = request.get_json(silent=True) or {}

    register_id = payload.get("register_id")
    if not register_id:
        return jsonify({"error": "register_id is required"}), 400

    try:
        amount = Decimal(str(payload["amount"]))
    except (KeyError, TypeError, InvalidOperation):
        return jsonify({"error": "amount must be a number"}), 400

    session = SessionLocal()
    try:
        result = service.process_charge(
            session=session,
            amount=amount,
            register_id=register_id,
        )
    finally:
        session.close()

    return jsonify(result)
