"""ORM model for the stores in the chain.

Every attribute carries the same name as its database column, so there is no
translation layer between the schema and the code.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class Store(Base):
    __tablename__ = "stores"

    # The identifier each store's containers are configured with, e.g.
    # "store-1". English, like every identifier in the project.
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    # Spanish: this is what a reader sees on the dashboard.
    name: Mapped[str] = mapped_column(String(80), nullable=False)
