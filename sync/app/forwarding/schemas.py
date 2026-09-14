"""The batch payload sent to head office.

Built at SEND time, not at sale time. The money figures — unit price, subtotal
and total — are frozen columns on the store's own tables, so they are exactly
what was charged. The product name is read live from the catalog, so if a name
changed between the sale and the batch, the new one travels. Only the label
moves; no amount does.
"""

from decimal import Decimal
from typing import Any


def _serialize_item(item: dict) -> dict[str, Any]:
    """One line of an invoice, as JSON-safe values."""
    return {
        "ean": item["ean"],
        "product_name": item["product_name"],
        "quantity": item["quantity"],
        "unit_price": _money(item["unit_price"]),
        "subtotal": _money(item["subtotal"]),
    }


def _money(value: Decimal) -> str:
    """Render an amount as a string.

    Sent as a string rather than a float so the exact decimal survives the
    trip: JSON floats are binary and would quietly round Colombian pesos.
    """
    return str(Decimal(value))


def build_batch(store_id: str, invoices: list[dict]) -> dict[str, Any]:
    """Assemble the request body for one batch.

    The store travels on the batch rather than on every invoice: one batch
    comes from exactly one store, and repeating it per invoice would invite
    the two to disagree.
    """
    return {
        "store_id": store_id,
        "invoices": [
            {
                "store_invoice_id": invoice["store_invoice_id"],
                "register_id": invoice["register_id"],
                "sold_at": invoice["sold_at"].isoformat(),
                "total": _money(invoice["total"]),
                "items": [_serialize_item(item) for item in invoice["items"]],
            }
            for invoice in invoices
        ],
    }
