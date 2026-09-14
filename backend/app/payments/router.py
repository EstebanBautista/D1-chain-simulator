"""HTTP surface for payments.

This layer only translates between HTTP and the service layer: it parses the
request, calls a service, and maps domain exceptions onto status codes. It
builds no queries.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.payments import service
from app.payments.gateway_client import PaymentGatewayUnavailableError
from app.payments.schemas import PaymentRequest, PaymentResponse
from app.products.service import ProductNotFoundError

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentResponse)
def create_payment(
    request: PaymentRequest,
    session: Session = Depends(get_session),
) -> PaymentResponse:
    try:
        result = service.process_payment(
            session=session,
            register_id=request.register_id,
            items=request.items,
        )
    except service.InvalidPaymentRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    except ProductNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error
    except PaymentGatewayUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The payment gateway is unavailable; no sale was recorded",
        ) from error

    return PaymentResponse(**result)
