"""Batch API input and output models.

Amounts arrive as strings and are parsed into Decimal. Accepting a JSON float
would round Colombian pesos on the way in, which is not a rounding a reporting
system may do quietly.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InvoiceItemRequest(BaseModel):
    ean: str = Field(min_length=1, max_length=13)
    product_name: str = Field(min_length=1, max_length=120)
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class InvoiceRequest(BaseModel):
    """One invoice as its store sends it."""

    # The invoice's identifier in its own store. Paired with the batch's
    # store_id, this is what makes ingestion idempotent.
    store_invoice_id: int
    register_id: str = Field(min_length=1, max_length=40)
    sold_at: datetime
    total: Decimal
    items: list[InvoiceItemRequest]


class BatchRequest(BaseModel):
    """One batch from one store.

    The store travels here rather than on each invoice: a batch comes from
    exactly one store, and repeating it per invoice would invite the two to
    disagree.
    """

    store_id: str = Field(min_length=1, max_length=20)
    invoices: list[InvoiceRequest]


class BatchResponse(BaseModel):
    """What head office now holds, as a result of this batch.

    `accepted` and `duplicates` carry the store's own invoice numbers, so the
    forwarder knows exactly which of its rows to stamp. Both count as
    delivered: an invoice we already hold does not need sending again.
    """

    store_id: str
    accepted: list[int]
    duplicates: list[int]
    accepted_count: int
    duplicate_count: int
