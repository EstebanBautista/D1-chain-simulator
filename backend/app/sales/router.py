"""HTTP surface for recorded sales.

This layer only translates between HTTP and the service layer. It builds no
queries.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.sales import service
from app.sales.schemas import SaleResponse

router = APIRouter(prefix="/sales", tags=["sales"])


@router.get("/{sale_id}", response_model=SaleResponse)
def get_sale(
    sale_id: int,
    session: Session = Depends(get_session),
) -> SaleResponse:
    sale = service.get_sale(session, sale_id)
    if sale is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No sale with id {sale_id}"
        )
    return SaleResponse.model_validate(sale)
