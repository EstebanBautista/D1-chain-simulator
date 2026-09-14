"""Payment orchestration business logic.

This layer knows nothing about HTTP: it takes plain values, raises plain
exceptions and returns plain dictionaries, which is what makes it unit
testable without starting a server.

It reaches the catalog and the sales ledger through their own service layers
rather than through their repositories, so packages meet at the service level.
"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.payments import gateway_client
from app.payments.gateway_client import PaymentGatewayUnavailableError
from app.payments.schemas import CartItem
from app.products import service as products_service
from app.products.service import ProductNotFoundError
from app.sales import service as sales_service

logger = logging.getLogger(__name__)

APPROVED = "APPROVED"
DECLINED = "DECLINED"


class InvalidPaymentRequestError(Exception):
    """The payment request cannot be processed as submitted."""


def validate_payment_request(items: list[CartItem]) -> None:
    """Reject a cart that cannot be charged.

    Runs before anything is sent to the gateway: an invalid request must never
    reach the payment processor.
    """
    if not items:
        raise InvalidPaymentRequestError("The cart is empty")

    for item in items:
        if item.quantity <= 0:
            raise InvalidPaymentRequestError(
                f"Quantity for EAN {item.ean} must be a positive integer"
            )


def calculate_cart(
    session: Session, items: list[CartItem]
) -> tuple[Decimal, list[dict]]:
    """Price the cart against the database and return (total, priced_items).

    Prices are read here rather than taken from the request: whatever the
    client believed an item costs is irrelevant, only the current database
    price is charged.
    """
    products = products_service.get_products_by_eans(
        session, [item.ean for item in items]
    )

    priced_items: list[dict] = []
    total = Decimal("0")

    for item in items:
        product = products.get(item.ean)
        if product is None:
            raise ProductNotFoundError(item.ean)

        unit_price = Decimal(product.price)
        subtotal = unit_price * item.quantity
        total += subtotal

        priced_items.append(
            {
                "ean": item.ean,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
            }
        )

    return total, priced_items


def process_payment(
    session: Session,
    register_id: str,
    items: list[CartItem],
    gateway=gateway_client,
) -> dict:
    """Validate, price, charge and — only if approved — record the sale.

    `gateway` is injected so unit tests can supply a stub. A decline leaves no
    trace in the store database.
    """
    validate_payment_request(items)
    total, priced_items = calculate_cart(session, items)

    try:
        result = gateway.charge(amount=total, register_id=register_id)
    except PaymentGatewayUnavailableError:
        logger.exception("Payment gateway unavailable; no sale recorded")
        raise

    if result.get("status") != APPROVED:
        logger.info(
            "Charge declined for register %s: %s",
            register_id,
            result.get("decline_reason"),
        )
        return {
            "status": DECLINED,
            "total": total,
            "decline_reason": result.get("decline_reason"),
            "transaction_id": result.get("transaction_id"),
        }

    sale = sales_service.record_sale(
        session=session,
        register_id=register_id,
        total=total,
        sale_date=datetime.now(),
        items=priced_items,
    )
    logger.info("Sale %s recorded for register %s", sale.id, register_id)

    return {
        "status": APPROVED,
        "total": total,
        "sale_id": sale.id,
        "transaction_id": result.get("transaction_id"),
    }
