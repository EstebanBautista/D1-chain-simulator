"""HTTP surface for the dashboard's reports.

This layer only translates between HTTP and the service layer. It builds no
queries.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.reports import service
from app.reports.schemas import ProductTotalResponse, StoreTotalResponse
from app.stores.service import UnknownStoreError

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/sales-by-store", response_model=list[StoreTotalResponse])
def sales_by_store(
    session: Session = Depends(get_session),
) -> list[StoreTotalResponse]:
    return [
        StoreTotalResponse(
            store_id=row.store_id,
            store_name=row.store_name,
            total=row.total,
            invoice_count=row.invoice_count,
        )
        for row in service.sales_by_store(session)
    ]


@router.get("/top-products", response_model=list[ProductTotalResponse])
def top_products(
    store_id: str | None = None,
    session: Session = Depends(get_session),
) -> list[ProductTotalResponse]:
    try:
        rows = service.top_products(session, store_id=store_id)
    except UnknownStoreError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error

    return [
        ProductTotalResponse(
            ean=row.ean,
            product_name=row.product_name,
            units_sold=row.units_sold,
            revenue=row.revenue,
        )
        for row in rows
    ]
