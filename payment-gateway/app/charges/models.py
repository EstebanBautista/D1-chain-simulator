"""ORM model for the payment gateway's own records."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class Transaction(Base):
    """One processed charge, whether it was approved or declined.

    Declines are recorded too: from the processor's point of view, refusing a
    charge is as much an event as accepting one.
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    register_id: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    decline_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
