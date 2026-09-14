"""Publisher for the invoice ingestion queue.

The single external client head office has for RabbitMQ, kept apart from the
service the same way the payment gateway client is kept apart: a unit test can
replace this module with a stub and no AMQP ever happens.

Batches travel on one durable queue, `central.invoices`, on the default direct
exchange. Publishing is synchronous and confirmed: the batch is only handed
back as "accepted" once the broker has confirmed it took the message, so a
confirmation failure reads as "head office is down" and the store's forwarder
retries the whole batch later. Exactly-once at the data level comes from the
worker + the UNIQUE (store_id, store_invoice_id) constraint, not from this
publisher.
"""

import logging

import pika
from pika.exceptions import AMQPError

from app.core.config import RABBITMQ_URL
from app.ingestion.schemas import BatchRequest

logger = logging.getLogger(__name__)

QUEUE = "central.invoices"


class BrokerUnavailableError(Exception):
    """The queue could not take the batch; head office is effectively down.

    Raised on any transport or confirmation failure. From the caller's point
    of view the only thing that matters is that the batch was NOT enqueued, so
    it must NOT be released by the store's forwarder.
    """


def publish_batch(batch: BatchRequest) -> None:
    """Enqueue one batch, returning only once the broker confirmed it.

    The body is the batch's own JSON. Amounts are strings in it (pydantic
    renders `Decimal` as text in JSON mode), so the exact figures survive the
    trip and the worker can rebuild the same `BatchRequest` it was sent.
    """
    body = batch.model_dump_json().encode("utf-8")

    try:
        with pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL)) as connection:
            channel = connection.channel()
            # Publisher confirms: basic_publish raises instead of silently
            # losing a message the broker never accepted.
            channel.confirm_delivery()
            channel.queue_declare(queue=QUEUE, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE,
                body=body,
                # delivery_mode=2 persists the message to disk, so a broker
                # restart does not lose what head office already accepted.
                properties=pika.BasicProperties(delivery_mode=2),
            )
    except AMQPError as error:
        logger.error("Failed to enqueue batch from %s: %s", batch.store_id, error)
        raise BrokerUnavailableError(str(error)) from error