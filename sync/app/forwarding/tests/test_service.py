"""Unit tests for the batching rule.

`decide_batch` is a pure function of four numbers, so these need no database,
no network and no waiting.
"""

from app.forwarding import service
from app.forwarding.service import AGE_TRIGGER, COUNT_TRIGGER

BATCH_SIZE = 10
MAX_AGE = 60.0


def decide(pending, age):
    return service.decide_batch(
        pending_count=pending,
        oldest_age_seconds=age,
        batch_size=BATCH_SIZE,
        max_age_seconds=MAX_AGE,
    )


# --- Nothing to do -------------------------------------------------------


def test_an_empty_queue_sends_nothing():
    assert decide(pending=0, age=0).should_send is False


def test_neither_trigger_fires_below_both_thresholds():
    decision = decide(pending=3, age=10)

    assert decision.should_send is False
    assert decision.trigger is None


# --- Count trigger -------------------------------------------------------


def test_reaching_the_batch_size_sends_on_the_count_trigger():
    decision = decide(pending=BATCH_SIZE, age=1)

    assert decision.should_send is True
    assert decision.trigger == COUNT_TRIGGER


def test_the_count_trigger_does_not_wait_for_the_timer():
    """Ten invoices one second old must go out now, not in a minute."""
    decision = decide(pending=BATCH_SIZE, age=0)

    assert decision.should_send is True
    assert decision.trigger == COUNT_TRIGGER


def test_a_backlog_is_capped_at_one_batch_size():
    """A large backlog drains in successive batches, not one huge request."""
    decision = decide(pending=95, age=1)

    assert decision.limit == BATCH_SIZE


# --- Age trigger ---------------------------------------------------------


def test_a_single_old_invoice_sends_on_the_age_trigger():
    decision = decide(pending=1, age=MAX_AGE)

    assert decision.should_send is True
    assert decision.trigger == AGE_TRIGGER
    assert decision.limit == 1


def test_the_age_trigger_sends_everything_queued():
    """However few there are — a quiet minute ships in one request."""
    decision = decide(pending=4, age=MAX_AGE + 5)

    assert decision.trigger == AGE_TRIGGER
    assert decision.limit == 4


def test_an_invoice_just_under_the_maximum_wait_still_waits():
    assert decide(pending=1, age=MAX_AGE - 0.5).should_send is False


# --- The two together ----------------------------------------------------


def test_the_count_trigger_wins_when_both_would_fire():
    """Whichever comes first: the count cap bounds the request size."""
    decision = decide(pending=BATCH_SIZE + 5, age=MAX_AGE + 100)

    assert decision.trigger == COUNT_TRIGGER
    assert decision.limit == BATCH_SIZE


def test_the_age_is_measured_from_the_oldest_invoice_not_the_last_send():
    """The distinction the whole rule rests on.

    `decide_batch` is given the age of the OLDEST QUEUED invoice. It has no
    parameter for when the previous batch went out, and cannot have one — that
    is what guarantees a sale never waits longer than the maximum wait from
    its own creation, regardless of batch timing around it.
    """
    assert "last_send" not in service.decide_batch.__code__.co_varnames
    assert "oldest_age_seconds" in service.decide_batch.__code__.co_varnames

    # One invoice, old enough on its own, goes out — nothing about a recent
    # batch can hold it back.
    assert decide(pending=1, age=MAX_AGE + 1).should_send is True


# --- The log line the requirement is verified by --------------------------


def test_the_count_trigger_is_named_in_the_log_line():
    decision = decide(pending=BATCH_SIZE, age=2)

    assert "count trigger" in service.describe_decision(decision, 2)


def test_the_age_trigger_reports_the_age_in_the_log_line():
    decision = decide(pending=2, age=61)

    message = service.describe_decision(decision, 61)

    assert "age trigger" in message
    assert "61s" in message
