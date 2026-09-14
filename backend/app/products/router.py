"""HTTP surface for the product catalog.

This layer only translates between HTTP and the service layer: it parses the
request, calls a service, and maps domain exceptions onto status codes. It
builds no queries.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.products import service
from app.products.schemas import ProductResponse

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{ean}", response_model=ProductResponse)
def get_product(
    ean: str,
    session: Session = Depends(get_session),
) -> ProductResponse:
    try:
        product = service.get_product(session, ean)
    except service.ProductNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    return ProductResponse.model_validate(product)
