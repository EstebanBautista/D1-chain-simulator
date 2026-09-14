"""ORM model for the product catalog.

Every attribute carries the same name as its database column, so there is no
translation layer between the schema and the code.
"""

from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class Product(Base):
    __tablename__ = "products"

    ean: Mapped[str] = mapped_column(String(13), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
