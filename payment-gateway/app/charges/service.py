"""Payment simulation logic.

The decision rule lives here, away from HTTP, so it can be unit tested by
calling a function rather than by starting a server.
"""

import logging
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.charges import repository
from app.core.config import DECLINE_THRESHOLD

logger = logging.getLogger(__name__)

APPROVED = "APPROVED"
DECLINED = "DECLINED"

INVALID_AMOUNT_REASON = "Invalid amount"
AMOUNT_EXCEEDED_REASON = "Amount exceeds the allowed threshold"


def decide(amount: Decimal, threshold: Decimal = DECLINE_THRESHOLD) -> tuple[str, str | None]:
    """Return (status, decline_reason) for this amount.

    Deterministic by design: the same amount always yields the same answer, so
    the integration test can force a decline on demand and a failure is never
    mistaken for chance.
    """
    if amount <= 0:
        return DECLINED, INVALID_AMOUNT_REASON

    if amount > threshold:
        return DECLINED, AMOUNT_EXCEEDED_REASON

    return APPROVED, None


def process_charge(session: Session, amount: Decimal, register_id: str) -> dict:
    """Decide on a charge and record it, approved or declined."""
    status, decline_reason = decide(amount)
    transaction_id = str(uuid.uuid4())

    repository.record_transaction(
        session=session,
        transaction_id=transaction_id,
        amount=amount,
        register_id=register_id,
        status=status,
        decline_reason=decline_reason,
    )

    logger.info(
        "Charge %s for register %s: %s%s",
        transaction_id,
        register_id,
        status,
        f" ({decline_reason})" if decline_reason else "",
    )

    return {
        "transaction_id": transaction_id,
        "status": status,
        "decline_reason": decline_reason,
    }
