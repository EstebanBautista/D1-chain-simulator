"""Payment API input and output models.

Field names are in English and match the database columns, so a payload can be
read against the schema with no mental translation.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


class CartItem(BaseModel):
    """One line of the cart as the register sends it.

    Only the barcode and the quantity travel: the backend re-reads the price
    from the database, so a client-supplied price would be ignored anyway.
    """

    ean: str = Field(min_length=1)
    quantity: int


class PaymentRequest(BaseModel):
    register_id: str = Field(min_length=1)
    items: list[CartItem]


class PaymentResponse(BaseModel):
    status: str
    total: Decimal
    sale_id: int | None = None
    transaction_id: str | None = None
    decline_reason: str | None = None
