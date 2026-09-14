"""HTTP surface for batch ingestion.

This layer only translates between HTTP and the service layer: it parses the
request, calls a service, and maps domain exceptions onto status codes. It
builds no queries.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.ingestion import service
from app.ingestion.schemas import BatchRequest, BatchResponse
from app.stores.service import UnknownStoreError

router = APIRouter(prefix="/sales", tags=["ingestion"])


@router.post("/batch", response_model=BatchResponse)
def ingest_batch(
    batch: BatchRequest,
    session: Session = Depends(get_session),
) -> BatchResponse:
    try:
        result = service.ingest_batch(session, batch)
    except UnknownStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    except service.InvalidBatchError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error

    return BatchResponse(
        store_id=batch.store_id,
        accepted=result.accepted,
        duplicates=result.duplicates,
        accepted_count=len(result.accepted),
        duplicate_count=len(result.duplicates),
    )
