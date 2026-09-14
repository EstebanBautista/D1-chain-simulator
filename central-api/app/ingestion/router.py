"""HTTP surface for batch ingestion.

This layer only translates between HTTP and the service layer: it parses the
request, calls a service, and maps domain exceptions onto status codes. It
builds no queries and writes nothing to MySQL — the queue's worker does that.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.ingestion import service
from app.ingestion.broker import BrokerUnavailableError
from app.ingestion.schemas import BatchRequest, BatchResponse
from app.stores import service as stores_service
from app.stores.service import UnknownStoreError

router = APIRouter(prefix="/sales", tags=["ingestion"])


@router.post("/batch", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_batch(
    batch: BatchRequest,
    session: Session = Depends(get_session),
) -> BatchResponse:
    """Enqueue a batch for the worker to write into MySQL.

    202 Accepted, not 200: the batch now belongs to head office's durable
    queue, but the worker — the only process that inserts — has not persisted
    it yet. `accepted` therefore lists the batch's own invoice numbers, which
    is all the store's forwarder needs in order to release them; whether the
    worker later finds some already held is decided by the UNIQUE constraint.
    """
    try:
        # The store check stays synchronous so an unknown store is rejected
        # before anything is published. It is a read, not a write.
        stores_service.require_store(session, batch.store_id)
        result = service.enqueue_batch(batch)
    except UnknownStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    except service.InvalidBatchError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    except BrokerUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Head office could not accept the batch right now",
        ) from error

    return BatchResponse(
        store_id=batch.store_id,
        accepted=result.accepted,
        duplicates=result.duplicates,
        accepted_count=len(result.accepted),
        duplicate_count=len(result.duplicates),
    )
