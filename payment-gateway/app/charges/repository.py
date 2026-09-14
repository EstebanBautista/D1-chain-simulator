"""Persistence layer for processed transactions."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.charges.models import Transaction


def record_transaction(
    session: Session,
    transaction_id: str,
    amount: Decimal,
    register_id: str,
    status: str,
    decline_reason: str | None,
) -> Transaction:
    """Store one processed transaction and return it."""
    transaction = Transaction(
        transaction_id=transaction_id,
        amount=amount,
        register_id=register_id,
        status=status,
        decline_reason=decline_reason,
        processed_at=datetime.now(),
    )

    try:
        session.add(transaction)
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(transaction)
    return transaction


def find_by_transaction_id(session: Session, transaction_id: str) -> Transaction | None:
    """Return a recorded transaction, or None when it does not exist."""
    return session.scalar(
        select(Transaction).where(Transaction.transaction_id == transaction_id)
    )
