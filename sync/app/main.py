"""Forwarder entry point: the polling loop.

This process is the store's only outbound data path. It wakes on a short tick,
asks the batching rule whether anything should go out, ships it, and stamps
what head office confirms.

Stop this container and the store keeps selling — sales simply pile up in the
`sales` table with `forwarded_at IS NULL`. Start it again and the backlog
drains. That is the demonstration the whole design exists for.
"""

import logging
import time

from app.core.config import (
    BATCH_MAX_AGE_SECONDS,
    BATCH_SIZE,
    STORE_ID,
    SYNC_POLL_SECONDS,
)
from app.core.database import session_scope
from app.core.logging import configure_logging
from app.forwarding import client, repository, schemas, service

logger = logging.getLogger(__name__)


def run_once() -> bool:
    """Run one send cycle. Returns True if a batch was sent and more may remain.

    Returning True is what lets a backlog drain in successive batches without
    waiting a full polling interval between each.
    """
    with session_scope() as session:
        stats = repository.get_pending_stats(session)
        decision = service.decide_batch(
            pending_count=stats.pending_count,
            oldest_age_seconds=stats.oldest_age_seconds,
            batch_size=BATCH_SIZE,
            max_age_seconds=BATCH_MAX_AGE_SECONDS,
        )

        if not decision.should_send:
            return False

        invoices = repository.find_pending_sales(session, decision.limit)
        if not invoices:
            return False

        reason = service.describe_decision(decision, stats.oldest_age_seconds)
        logger.info("Sending %s invoices to head office (%s)", len(invoices), reason)

        payload = schemas.build_batch(STORE_ID, invoices)

        try:
            result = client.send_batch(payload)
        except client.CentralSiteUnavailableError as error:
            # Nothing is stamped. Every invoice stays queued and goes out on a
            # later cycle. The store is unaffected and keeps selling.
            logger.warning(
                "Head office unreachable, %s invoices stay queued: %s",
                len(invoices),
                error,
            )
            return False

        # Duplicates count as delivered. This is the path that matters: if a
        # response was lost after head office committed, the retry comes back
        # as "already have these" — and if we did not stamp them, the same
        # invoices would be resent forever.
        accepted = result.get("accepted", [])
        duplicates = result.get("duplicates", [])
        confirmed = list(accepted) + list(duplicates)

        stamped = repository.mark_forwarded(session, confirmed)
        logger.info(
            "Head office confirmed %s new and %s already held; %s marked forwarded",
            len(accepted),
            len(duplicates),
            stamped,
        )

        # A count-triggered batch is capped at BATCH_SIZE, so there may be more
        # waiting; loop immediately rather than sleeping on it.
        return True


def run_forever() -> None:
    """Poll until stopped."""
    logger.info(
        "Forwarder started: batch size %s, max wait %ss, polling every %ss",
        BATCH_SIZE,
        BATCH_MAX_AGE_SECONDS,
        SYNC_POLL_SECONDS,
    )

    while True:
        try:
            # Keep draining while batches are going out; only sleep once the
            # queue no longer warrants a send.
            while run_once():
                pass
        except Exception:
            # A worker that dies on an unexpected error stops forwarding
            # silently. Log it and keep polling: the queue is durable, so
            # whatever failed will be retried.
            logger.exception("Send cycle failed; retrying on the next tick")

        time.sleep(SYNC_POLL_SECONDS)


def main() -> None:
    configure_logging()
    run_forever()


if __name__ == "__main__":
    main()
