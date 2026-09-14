"""ORM models for recorded sales.

Every attribute carries the same name as its database column, so there is no
translation layer between the schema and the code.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    register_id: Mapped[str] = mapped_column(String(20), nullable=False)
    # NULL until head office confirms it holds this sale. Set by the forwarder,
    # never by the backend: recording a sale only puts it in the queue.
    forwarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale",
        cascade="all, delete-orphan",
    )


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_sale_items_quantity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False
    )
    ean: Mapped[str] = mapped_column(
        String(13), ForeignKey("products.ean"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Frozen at charge time so the sale stays auditable if the price changes.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="items")
