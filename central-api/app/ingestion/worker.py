"""Ingestion worker: the ONLY process that writes invoices into MySQL.

Reads batches from the `central.invoices` queue and persists them with the
same `ingest_batch` service the API used to call inside the request. It has no
HTTP surface, exactly like the stores' forwarder.

Delivery is at-least-once: a batch is acknowledged only after its insert
committed, so a crash mid-write redelivers the message. That redelivery is
exactly what the UNIQUE (store_id, store_invoice_id) constraint was designed to
absorb — worker shouldered the insert, but the idempotency guarantee did not
move anywhere.
"""

import logging
import time

import pika
from pika.exceptions import AMQPError

from app.core.config import RABBITMQ_URL
from app.core.database import session_scope
from app.core.logging import configure_logging
from app.ingestion import service
from app.ingestion.broker import QUEUE
from app.ingestion.schemas import BatchRequest

logger = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 5


def handle_message(channel, method, properties, body) -> None:
    """Persist one batch, then acknowledge it.

    The Ack rules: ack only after the commit; requeue on any unexpected error
    so the batch is redelivered and retried; drop (do not requeue) a message
    that cannot even be parsed, so a corrupt batch cannot poison the queue.
    """
    try:
        batch = BatchRequest.model_validate_json(body)
    except Exception as error:
        logger.error("Rejecting undecipherable batch: %s", error)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    try:
        with session_scope() as session:
            # ingest_batch validates, absorbs duplicates via the UNIQUE
            # constraint and commits. `received_at` is stamped here, when the
            # batch is actually written, not when the API accepted it.
            service.ingest_batch(session, batch)
    except Exception as error:
        logger.exception(
            "Batch from %s failed (%s); requeueing for redelivery",
            batch.store_id,
            error,
        )
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        return

    channel.basic_ack(delivery_tag=method.delivery_tag)


def run_forever() -> None:
    """Consume until stopped, reconnecting when the broker is not there."""
    logger.info("Ingestion worker started, consuming from %s", QUEUE)

    while True:
        try:
            with pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL)) as connection:
                channel = connection.channel()
                # Declared here too, not only in the publisher, so the worker
                # is ready even when no batch has been published yet.
                channel.queue_declare(queue=QUEUE, durable=True)
                # One batch at a time per worker: keep the write rate calm and
                # spread redeliveries across a restarted cluster sensibly.
                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(
                    queue=QUEUE,
                    on_message_callback=handle_message,
                    auto_ack=False,
                )
                channel.start_consuming()
        except AMQPError as error:
            logger.error("Broker connection failed (%s); retrying in %ss", error, RECONNECT_DELAY_SECONDS)
        except KeyboardInterrupt:
            break

        time.sleep(RECONNECT_DELAY_SECONDS)


def main() -> None:
    configure_logging()
    run_forever()


if __name__ == "__main__":
    main()