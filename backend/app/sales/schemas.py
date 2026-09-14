"""Sale API input and output models.

Field names are in English and match the database columns, so a payload can be
read against the schema with no mental translation.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SaleItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ean: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sale_date: datetime
    total: Decimal
    register_id: str
    items: list[SaleItemResponse]
