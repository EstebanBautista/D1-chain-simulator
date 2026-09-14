"""Unit tests for the payment service layer.

No HTTP server and no real database: the service layer takes plain values, so
it can be exercised by calling functions. The catalog and the sales ledger are
stubbed at the service seam this package actually depends on.
"""

from decimal import Decimal

import pytest

from app.payments import service
from app.payments.gateway_client import PaymentGatewayUnavailableError
from app.payments.schemas import CartItem
from app.products.models import Product
from app.products.service import ProductNotFoundError


class FakeSession:
    """Stand-in for a SQLAlchemy session; the catalog is stubbed anyway."""


class RecordingGateway:
    """Gateway stub that records whether it was called and with what."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def charge(self, amount, register_id):
        self.calls.append({"amount": amount, "register_id": register_id})
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def catalog(monkeypatch):
    """Stub the catalog service with a small in-memory catalog."""
    products = {
        "7702001010301": Product(ean="7702001010301", name="Arroz", price=Decimal("2000")),
        "7702354030014": Product(ean="7702354030014", name="Leche", price=Decimal("1500")),
    }

    def fake_get_products_by_eans(session, eans):
        return {ean: products[ean] for ean in eans if ean in products}

    monkeypatch.setattr(
        service.products_service, "get_products_by_eans", fake_get_products_by_eans
    )
    return products


# --- Cart pricing --------------------------------------------------------


def test_subtotal_is_unit_price_times_quantity(catalog):
    total, items = service.calculate_cart(
        FakeSession(), [CartItem(ean="7702001010301", quantity=3)]
    )

    assert items[0]["unit_price"] == Decimal("2000")
    assert items[0]["subtotal"] == Decimal("6000")
    assert total == Decimal("6000")


def test_total_is_the_sum_of_subtotals(catalog):
    total, items = service.calculate_cart(
        FakeSession(),
        [
            CartItem(ean="7702001010301", quantity=3),
            CartItem(ean="7702354030014", quantity=2),
        ],
    )

    assert [item["subtotal"] for item in items] == [Decimal("6000"), Decimal("3000")]
    assert total == Decimal("9000")


def test_calculate_cart_raises_for_unknown_ean(catalog):
    with pytest.raises(ProductNotFoundError):
        service.calculate_cart(FakeSession(), [CartItem(ean="0000000000000", quantity=1)])


# --- Request validation --------------------------------------------------


def test_empty_cart_is_rejected():
    with pytest.raises(service.InvalidPaymentRequestError):
        service.validate_payment_request([])


def test_zero_quantity_is_rejected():
    with pytest.raises(service.InvalidPaymentRequestError):
        service.validate_payment_request([CartItem(ean="7702001010301", quantity=0)])


def test_negative_quantity_is_rejected():
    with pytest.raises(service.InvalidPaymentRequestError):
        service.validate_payment_request([CartItem(ean="7702001010301", quantity=-2)])


def test_empty_cart_never_reaches_the_gateway(catalog):
    gateway = RecordingGateway(result={"status": "APPROVED"})

    with pytest.raises(service.InvalidPaymentRequestError):
        service.process_payment(FakeSession(), "register-1", [], gateway=gateway)

    assert gateway.calls == []


def test_invalid_quantity_never_reaches_the_gateway(catalog):
    gateway = RecordingGateway(result={"status": "APPROVED"})

    with pytest.raises(service.InvalidPaymentRequestError):
        service.process_payment(
            FakeSession(),
            "register-1",
            [CartItem(ean="7702001010301", quantity=0)],
            gateway=gateway,
        )

    assert gateway.calls == []


def test_unknown_ean_never_reaches_the_gateway(catalog):
    gateway = RecordingGateway(result={"status": "APPROVED"})

    with pytest.raises(ProductNotFoundError):
        service.process_payment(
            FakeSession(),
            "register-1",
            [CartItem(ean="0000000000000", quantity=1)],
            gateway=gateway,
        )

    assert gateway.calls == []


# --- Payment orchestration -----------------------------------------------


def test_approved_payment_persists_the_sale(catalog, monkeypatch):
    recorded = {}

    def fake_record_sale(session, register_id, total, sale_date, items):
        recorded.update(
            {"register_id": register_id, "total": total, "items": items}
        )

        class StoredSale:
            id = 42

        return StoredSale()

    monkeypatch.setattr(service.sales_service, "record_sale", fake_record_sale)
    gateway = RecordingGateway(
        result={"status": "APPROVED", "transaction_id": "tx-1", "decline_reason": None}
    )

    result = service.process_payment(
        FakeSession(),
        "register-1",
        [CartItem(ean="7702001010301", quantity=2)],
        gateway=gateway,
    )

    assert result["status"] == "APPROVED"
    assert result["sale_id"] == 42
    assert result["total"] == Decimal("4000")
    assert recorded["total"] == Decimal("4000")
    assert recorded["register_id"] == "register-1"


def test_gateway_is_charged_the_backend_computed_total(catalog, monkeypatch):
    monkeypatch.setattr(
        service.sales_service,
        "record_sale",
        lambda **kwargs: type("StoredSale", (), {"id": 1})(),
    )
    gateway = RecordingGateway(result={"status": "APPROVED", "transaction_id": "tx-1"})

    service.process_payment(
        FakeSession(),
        "register-1",
        [CartItem(ean="7702001010301", quantity=3)],
        gateway=gateway,
    )

    assert gateway.calls[0]["amount"] == Decimal("6000")


def test_declined_payment_persists_nothing(catalog, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("A declined payment must not create a sale")

    monkeypatch.setattr(service.sales_service, "record_sale", fail_if_called)
    gateway = RecordingGateway(
        result={
            "status": "DECLINED",
            "transaction_id": "tx-2",
            "decline_reason": "Amount exceeds the allowed threshold",
        }
    )

    result = service.process_payment(
        FakeSession(),
        "register-1",
        [CartItem(ean="7702001010301", quantity=1)],
        gateway=gateway,
    )

    assert result["status"] == "DECLINED"
    assert result["decline_reason"] == "Amount exceeds the allowed threshold"
    assert "sale_id" not in result


def test_gateway_failure_propagates_and_persists_nothing(catalog, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("An unreachable gateway must not create a sale")

    monkeypatch.setattr(service.sales_service, "record_sale", fail_if_called)
    gateway = RecordingGateway(error=PaymentGatewayUnavailableError("connection refused"))

    with pytest.raises(PaymentGatewayUnavailableError):
        service.process_payment(
            FakeSession(),
            "register-1",
            [CartItem(ean="7702001010301", quantity=1)],
            gateway=gateway,
        )
