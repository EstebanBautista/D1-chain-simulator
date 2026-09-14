"""ORM models for consolidated invoices.

Every attribute carries the same name as its database column, so there is no
translation layer between the schema and the code.

These are owned by ingestion, which writes them; the reports package reads
them.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        # The idempotency guarantee, mirrored from the schema. A store's own
        # invoice number is unique only within that store: both stores number
        # their sales from 1.
        UniqueConstraint(
            "store_id", "store_invoice_id", name="uq_invoices_store_invoice"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("stores.id"), nullable=False
    )
    store_invoice_id: Mapped[int] = mapped_column(Integer, nullable=False)
    register_id: Mapped[str] = mapped_column(String(40), nullable=False)
    # When the sale happened, as the store reported it.
    sold_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # When head office received it. Separate from sold_at so a delivery delay
    # or a wrong store clock is visible rather than invisible.
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    ean: Mapped[str] = mapped_column(String(13), nullable=False)
    # Denormalized: head office has no catalog to resolve an EAN against, and
    # an invoice is a historical document.
    product_name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")
