"""HTTP surface for the chain's stores.

The dashboard builds its filter from this, rather than hardcoding the stores
in the page.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.stores import service
from app.stores.schemas import StoreResponse

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("", response_model=list[StoreResponse])
def list_stores(session: Session = Depends(get_session)) -> list[StoreResponse]:
    stores = service.list_stores(session)
    return [StoreResponse.model_validate(store) for store in stores]
