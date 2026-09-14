"""Unit tests for the payment gateway's decision rule.

The rule is deterministic on purpose, so these assertions are exact rather
than statistical.
"""

from decimal import Decimal

from app.charges import service

THRESHOLD = Decimal("1000000")


def test_amount_within_threshold_is_approved():
    status, reason = service.decide(Decimal("50000"), threshold=THRESHOLD)

    assert status == service.APPROVED
    assert reason is None


def test_amount_exactly_at_threshold_is_approved():
    status, reason = service.decide(THRESHOLD, threshold=THRESHOLD)

    assert status == service.APPROVED
    assert reason is None


def test_amount_above_threshold_is_declined():
    status, reason = service.decide(THRESHOLD + Decimal("1"), threshold=THRESHOLD)

    assert status == service.DECLINED
    assert reason == service.AMOUNT_EXCEEDED_REASON


def test_zero_amount_is_declined():
    status, reason = service.decide(Decimal("0"), threshold=THRESHOLD)

    assert status == service.DECLINED
    assert reason == service.INVALID_AMOUNT_REASON


def test_negative_amount_is_declined():
    status, reason = service.decide(Decimal("-1500"), threshold=THRESHOLD)

    assert status == service.DECLINED
    assert reason == service.INVALID_AMOUNT_REASON


def test_the_same_amount_always_yields_the_same_decision():
    first = service.decide(Decimal("75000"), threshold=THRESHOLD)
    second = service.decide(Decimal("75000"), threshold=THRESHOLD)

    assert first == second
