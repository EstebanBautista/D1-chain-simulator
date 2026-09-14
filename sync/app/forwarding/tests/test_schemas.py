"""Unit tests for the batch payload.

What travels to head office is the contract between the two sites, so it is
asserted field by field rather than by shape.
"""

from datetime import datetime
from decimal import Decimal

from app.forwarding import schemas

SALE = {
    "store_invoice_id": 7,
    "register_id": "store-1-register-2",
    "sold_at": datetime(2026, 8, 26, 14, 5, 30),
    "total": Decimal("9500.00"),
    "items": [
        {
            "ean": "7702001010301",
            "product_name": "Arroz",
            "quantity": 3,
            "unit_price": Decimal("2000.00"),
            "subtotal": Decimal("6000.00"),
        },
        {
            "ean": "7702354030014",
            "product_name": "Leche",
            "quantity": 1,
            "unit_price": Decimal("3500.00"),
            "subtotal": Decimal("3500.00"),
        },
    ],
}


def test_the_batch_names_its_store():
    batch = schemas.build_batch("store-2", [SALE])

    assert batch["store_id"] == "store-2"


def test_the_store_travels_once_per_batch_not_per_invoice():
    """One batch comes from one store; repeating it would invite disagreement."""
    batch = schemas.build_batch("store-1", [SALE])

    assert "store_id" not in batch["invoices"][0]


def test_an_invoice_carries_its_identity_and_origin():
    invoice = schemas.build_batch("store-1", [SALE])["invoices"][0]

    assert invoice["store_invoice_id"] == 7
    assert invoice["register_id"] == "store-1-register-2"
    assert invoice["sold_at"] == "2026-08-26T14:05:30"
    assert invoice["total"] == "9500.00"


def test_an_invoice_carries_every_line_with_every_field():
    invoice = schemas.build_batch("store-1", [SALE])["invoices"][0]

    assert len(invoice["items"]) == 2
    assert invoice["items"][0] == {
        "ean": "7702001010301",
        "product_name": "Arroz",
        "quantity": 3,
        "unit_price": "2000.00",
        "subtotal": "6000.00",
    }


def test_the_product_name_travels_because_head_office_has_no_catalog():
    invoice = schemas.build_batch("store-1", [SALE])["invoices"][0]

    assert [item["product_name"] for item in invoice["items"]] == ["Arroz", "Leche"]


def test_amounts_travel_as_strings_so_the_decimal_survives():
    """JSON floats are binary and would quietly round Colombian pesos."""
    invoice = schemas.build_batch("store-1", [SALE])["invoices"][0]

    assert isinstance(invoice["total"], str)
    assert isinstance(invoice["items"][0]["unit_price"], str)
    assert Decimal(invoice["items"][0]["subtotal"]) == Decimal("6000.00")


def test_an_empty_batch_is_still_well_formed():
    batch = schemas.build_batch("store-1", [])

    assert batch == {"store_id": "store-1", "invoices": []}
