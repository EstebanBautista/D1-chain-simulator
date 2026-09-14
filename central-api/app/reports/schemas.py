"""Report API output models.

Amounts are Decimal, in Colombian pesos, in the same unit and precision the
stores charged in.
"""

from decimal import Decimal

from pydantic import BaseModel


class StoreTotalResponse(BaseModel):
    store_id: str
    store_name: str
    total: Decimal
    invoice_count: int


class ProductTotalResponse(BaseModel):
    ean: str
    product_name: str
    units_sold: int
    revenue: Decimal
