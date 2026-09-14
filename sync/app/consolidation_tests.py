#!/usr/bin/env python3
"""End-to-end tests for the store-to-head-office path.

Run from a forwarder container, which is the one place that can see all three
sides at once: its own store's database over the store LAN, the other store's
backend and the central API over the simulated internet.

    make shell CONTAINER=store-1-sync
    python -m app.consolidation_tests

Subcommands exist so the resilience scenario, which has to stop and start
containers, can drive the pieces from the host:

    python -m app.consolidation_tests sell 3 store-1
    python -m app.consolidation_tests pending
    python -m app.consolidation_tests central-count store-1

Exits zero when every check passes, non-zero as soon as one fails.
"""

import sys
import time
from decimal import Decimal

import httpx
from sqlalchemy import text

from app.core.config import (
    BATCH_MAX_AGE_SECONDS,
    BATCH_SIZE,
    CENTRAL_API_URL,
    STORE_ID,
    SYNC_POLL_SECONDS,
)
from app.core.database import session_scope

# Reached over the store LAN and the simulated internet respectively.
OWN_BACKEND_URL = f"http://{STORE_ID}-backend:8000"
OTHER_STORE_ID = "store-2" if STORE_ID == "store-1" else "store-1"
OTHER_BACKEND_URL = f"http://{OTHER_STORE_ID}-backend:8000"

KNOWN_EAN = "7702001010301"

REQUEST_TIMEOUT_SECONDS = 15

# How long to wait for the age trigger: the configured maximum wait, plus one
# polling interval, plus a margin for the round trip.
AGE_TRIGGER_WAIT = BATCH_MAX_AGE_SECONDS + SYNC_POLL_SECONDS + 8

GREEN = "\033[32m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

failures: list[str] = []


def check(description: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"  {GREEN}PASS{RESET}  {description}")
    else:
        print(f"  {RED}FAIL{RESET}  {description}")
        if detail:
            print(f"        {detail}")
        failures.append(description)
    return condition


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


# --- Helpers -------------------------------------------------------------


def backend_url_for(store_id: str) -> str:
    return OWN_BACKEND_URL if store_id == STORE_ID else OTHER_BACKEND_URL


def make_purchase(store_id: str, quantity: int = 1) -> dict:
    """Ring up one purchase at a store and return the payment result."""
    response = httpx.post(
        f"{backend_url_for(store_id)}/payments",
        json={
            "register_id": f"{store_id}-register-1",
            "items": [{"ean": KNOWN_EAN, "quantity": quantity}],
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def pending_count() -> int:
    """How many of this store's sales are still queued."""
    with session_scope() as session:
        return int(
            session.execute(
                text("SELECT COUNT(*) FROM sales WHERE forwarded_at IS NULL")
            ).scalar_one()
        )


def central_report() -> dict[str, dict]:
    """Head office's sales-by-store report, keyed by store."""
    response = httpx.get(
        f"{CENTRAL_API_URL}/reports/sales-by-store", timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return {row["store_id"]: row for row in response.json()}


def quiesce() -> None:
    """Wait until nothing is in flight anywhere, then let the tests measure.

    Every check below is a DELTA against a snapshot: "head office gained
    exactly one invoice", "the total grew by exactly what was charged". A
    delta is only meaningful if nothing else lands during the window — and
    something usually is in flight, because the register integration tests ring
    up real purchases moments before this runs.

    Draining our own queue is not enough: the OTHER store's forwarder may still
    be sitting on sales, and we cannot see its queue from here (its database is
    on its own network, correctly). So we drain what we can see and then wait
    out one full batching cycle, after which anything the other store had must
    have shipped.
    """
    wait = BATCH_MAX_AGE_SECONDS + SYNC_POLL_SECONDS + 5
    print(f"\nSettling: draining this store, then waiting {wait:.0f}s so any")
    print("sale already in flight at either store has landed before measuring.")
    wait_for_drain(AGE_TRIGGER_WAIT)
    time.sleep(wait)


def wait_for_drain(timeout_seconds: float) -> bool:
    """Wait until nothing is queued, or the timeout expires."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if pending_count() == 0:
            return True
        time.sleep(1)
    return pending_count() == 0


# --- 1. A purchase reaches head office -----------------------------------


def test_end_to_end_consolidation() -> None:
    section("1. A purchase reaches head office")

    before = central_report()
    before_total = Decimal(str(before[STORE_ID]["total"]))
    before_count = int(before[STORE_ID]["invoice_count"])

    result = make_purchase(STORE_ID, quantity=2)
    ok = check(
        "A purchase at this store is approved",
        result.get("status") == "APPROVED",
        f"Payload: {result}",
    )
    if not ok:
        return

    charged = Decimal(str(result["total"]))

    check(
        "The sale is queued for head office straight away",
        pending_count() >= 1,
        "Nothing is queued, so the sale was never enqueued",
    )

    print(
        f"        waiting up to {AGE_TRIGGER_WAIT:.0f}s for the age trigger "
        f"(max wait {BATCH_MAX_AGE_SECONDS:.0f}s + one {SYNC_POLL_SECONDS:.0f}s poll)"
    )
    drained = check(
        "The queue drains within the configured maximum wait",
        wait_for_drain(AGE_TRIGGER_WAIT),
        f"Still queued: {pending_count()}",
    )
    if not drained:
        return

    after = central_report()
    check(
        "Head office holds one more invoice for this store",
        int(after[STORE_ID]["invoice_count"]) == before_count + 1,
        f"Was {before_count}, now {after[STORE_ID]['invoice_count']}",
    )
    check(
        "The consolidated total grew by exactly what was charged",
        Decimal(str(after[STORE_ID]["total"])) == before_total + charged,
        f"Was {before_total}, now {after[STORE_ID]['total']}, charged {charged}",
    )


# --- 2. The count trigger ------------------------------------------------


def test_count_trigger() -> None:
    section("2. Ten invoices ship without waiting for the timer")

    before = central_report()
    before_count = int(before[STORE_ID]["invoice_count"])

    for _ in range(BATCH_SIZE):
        make_purchase(STORE_ID, quantity=1)

    check(
        f"{BATCH_SIZE} purchases were queued",
        pending_count() >= BATCH_SIZE,
        f"Queued: {pending_count()}",
    )

    # Well under the maximum wait: if these arrive, it was the count trigger
    # that sent them, not the timer.
    budget = min(SYNC_POLL_SECONDS * 3 + 10, BATCH_MAX_AGE_SECONDS - 5)
    print(f"        waiting up to {budget:.0f}s, well under the {BATCH_MAX_AGE_SECONDS:.0f}s timer")

    drained = check(
        "They ship on the count trigger, before the timer could fire",
        wait_for_drain(budget),
        f"Still queued after {budget:.0f}s: {pending_count()}",
    )
    if not drained:
        return

    after = central_report()
    check(
        "Head office holds all ten",
        int(after[STORE_ID]["invoice_count"]) == before_count + BATCH_SIZE,
        f"Was {before_count}, now {after[STORE_ID]['invoice_count']}",
    )


# --- 3. Both stores are consolidated separately --------------------------


def test_both_stores_are_separate() -> None:
    section("3. Each store's sales are attributed to it alone")

    quiesce()
    before = central_report()
    other_before = Decimal(str(before[OTHER_STORE_ID]["total"]))
    own_before = Decimal(str(before[STORE_ID]["total"]))

    result = make_purchase(OTHER_STORE_ID, quantity=3)
    ok = check(
        f"A purchase at {OTHER_STORE_ID} is approved",
        result.get("status") == "APPROVED",
        f"Payload: {result}",
    )
    if not ok:
        return

    charged = Decimal(str(result["total"]))

    print(f"        waiting up to {AGE_TRIGGER_WAIT:.0f}s for {OTHER_STORE_ID} to ship")
    deadline = time.monotonic() + AGE_TRIGGER_WAIT
    arrived = False
    while time.monotonic() < deadline:
        now = central_report()
        if Decimal(str(now[OTHER_STORE_ID]["total"])) == other_before + charged:
            arrived = True
            break
        time.sleep(2)

    check(
        f"{OTHER_STORE_ID}'s total grew by what it charged",
        arrived,
        f"Was {other_before}, expected {other_before + charged}",
    )

    after = central_report()
    check(
        f"{STORE_ID}'s total was not touched by {OTHER_STORE_ID}'s sale",
        Decimal(str(after[STORE_ID]["total"])) == own_before,
        f"Was {own_before}, now {after[STORE_ID]['total']}",
    )


# --- 4. Idempotency ------------------------------------------------------


def test_resending_a_batch_changes_nothing() -> None:
    section("4. Resending a batch does not inflate the report")

    before = central_report()
    before_total = Decimal(str(before[STORE_ID]["total"]))
    before_count = int(before[STORE_ID]["invoice_count"])

    # Take an invoice head office already holds and send it again, exactly as a
    # forwarder would after losing a response to a timeout.
    with session_scope() as session:
        row = session.execute(
            text(
                """
                SELECT s.id AS sale_id, s.register_id, s.sale_date, s.total,
                       i.ean, p.name AS product_name,
                       i.quantity, i.unit_price, i.subtotal
                FROM sales s
                JOIN sale_items i ON i.sale_id = s.id
                JOIN products   p ON p.ean = i.ean
                WHERE s.forwarded_at IS NOT NULL
                ORDER BY s.id DESC
                LIMIT 1
                """
            )
        ).first()

    if row is None:
        check("There is a forwarded sale to resend", False, "None found")
        return

    payload = {
        "store_id": STORE_ID,
        "invoices": [
            {
                "store_invoice_id": row.sale_id,
                "register_id": row.register_id,
                "sold_at": row.sale_date.isoformat(),
                "total": str(Decimal(row.total)),
                "items": [
                    {
                        "ean": row.ean,
                        "product_name": row.product_name,
                        "quantity": int(row.quantity),
                        "unit_price": str(Decimal(row.unit_price)),
                        "subtotal": str(Decimal(row.subtotal)),
                    }
                ],
            }
        ],
    }

    response = httpx.post(
        f"{CENTRAL_API_URL}/sales/batch",
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    ok = check(
        "The resent batch is accepted, not rejected",
        response.status_code == 200,
        f"Got HTTP {response.status_code}: {response.text}",
    )
    if not ok:
        return

    result = response.json()
    check(
        "Head office reports it as a duplicate, not as new",
        result.get("duplicate_count") == 1 and result.get("accepted_count") == 0,
        f"Payload: {result}",
    )

    after = central_report()
    check(
        "The invoice count is unchanged",
        int(after[STORE_ID]["invoice_count"]) == before_count,
        f"Was {before_count}, now {after[STORE_ID]['invoice_count']}",
    )
    check(
        "The reported total is unchanged",
        Decimal(str(after[STORE_ID]["total"])) == before_total,
        f"Was {before_total}, now {after[STORE_ID]['total']}",
    )


# --- Subcommands for the resilience scenario -----------------------------


def command_sell(argv: list[str]) -> int:
    """sell N [store] - ring up N purchases."""
    count = int(argv[0]) if argv else 1
    store = argv[1] if len(argv) > 1 else STORE_ID
    for _ in range(count):
        result = make_purchase(store, quantity=1)
        if result.get("status") != "APPROVED":
            print(f"Purchase was not approved: {result}", file=sys.stderr)
            return 1
    print(f"{count} purchase(s) completed at {store}")
    return 0


def command_pending(_: list[str]) -> int:
    """pending - print how many sales are queued."""
    print(pending_count())
    return 0


def command_central_count(argv: list[str]) -> int:
    """central-count [store] - print how many invoices head office holds."""
    store = argv[0] if argv else STORE_ID
    print(int(central_report()[store]["invoice_count"]))
    return 0


def command_wait_drain(argv: list[str]) -> int:
    """wait-drain [seconds] - block until the queue is empty."""
    timeout = float(argv[0]) if argv else AGE_TRIGGER_WAIT
    if wait_for_drain(timeout):
        print("drained")
        return 0
    print(f"still queued: {pending_count()}", file=sys.stderr)
    return 1


COMMANDS = {
    "sell": command_sell,
    "pending": command_pending,
    "central-count": command_central_count,
    "wait-drain": command_wait_drain,
}


def main(argv: list[str]) -> int:
    if argv and argv[0] in COMMANDS:
        return COMMANDS[argv[0]](argv[1:])

    print(f"{BOLD}Consolidation tests from {STORE_ID}'s forwarder{RESET}")
    print(f"Central API: {CENTRAL_API_URL}")
    print(
        f"Batch size {BATCH_SIZE}, max wait {BATCH_MAX_AGE_SECONDS:.0f}s, "
        f"polling every {SYNC_POLL_SECONDS:.0f}s"
    )

    quiesce()

    test_end_to_end_consolidation()
    test_count_trigger()
    test_both_stores_are_separate()
    test_resending_a_batch_changes_nothing()

    print()
    if failures:
        print(f"{RED}{BOLD}{len(failures)} check(s) failed:{RESET}")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"{GREEN}{BOLD}All checks passed.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
