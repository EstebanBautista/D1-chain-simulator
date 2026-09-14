"""The batching rule and the send cycle.

`decide_batch` is deliberately a pure function of four numbers: no database,
no network, no clock. That is what makes the rule this whole change is about
testable by calling a function, and it is where you should look first if the
timing ever behaves unexpectedly.
"""

import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)

COUNT_TRIGGER = "count"
AGE_TRIGGER = "age"


class BatchDecision(NamedTuple):
    """Whether to send now, why, and how many invoices to take."""

    should_send: bool
    trigger: str | None = None
    limit: int = 0


def decide_batch(
    pending_count: int,
    oldest_age_seconds: float,
    batch_size: int,
    max_age_seconds: float,
) -> BatchDecision:
    """Decide whether a batch goes out now, on either trigger.

    Two triggers, whichever fires first:

    - COUNT: at least `batch_size` invoices are queued. Send exactly
      `batch_size` of them — the oldest — and let the caller loop, so a large
      backlog drains in successive batches instead of one enormous request.

    - AGE: the OLDEST queued invoice has been waiting `max_age_seconds`. Send
      everything queued, however few, so a single purchase in a quiet minute
      still reaches head office.

    The age is measured from the oldest queued invoice, NOT from when the last
    batch was sent. That distinction is the whole point. Anchored to the last
    send, a sale made 59 seconds after a batch would wait nearly two minutes,
    breaking the promise that a lone purchase arrives within the maximum wait.
    Anchored to the oldest invoice, nothing ever waits longer than
    `max_age_seconds` plus one polling interval.
    """
    if pending_count <= 0:
        return BatchDecision(should_send=False)

    if pending_count >= batch_size:
        return BatchDecision(should_send=True, trigger=COUNT_TRIGGER, limit=batch_size)

    if oldest_age_seconds >= max_age_seconds:
        return BatchDecision(should_send=True, trigger=AGE_TRIGGER, limit=pending_count)

    return BatchDecision(should_send=False)


def describe_decision(decision: BatchDecision, oldest_age_seconds: float) -> str:
    """Render the reason a batch is going out, for the log.

    This line is the acceptance evidence for the batching requirement: a
    student confirms the rule by reading the logs, not by trusting the code.
    """
    if decision.trigger == COUNT_TRIGGER:
        return f"count trigger, {decision.limit} invoices queued"
    return (
        f"age trigger, oldest invoice {oldest_age_seconds:.0f}s old, "
        f"{decision.limit} invoices queued"
    )
