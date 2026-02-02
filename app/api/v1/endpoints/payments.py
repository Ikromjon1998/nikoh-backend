"""Payment endpoints for Stripe integration."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.schemas.payment import (
    PaymentCreate,
    PaymentIntentResponse,
    PaymentListResponse,
    PaymentResponse,
    PaymentStatusResponse,
    PricingResponse,
)
from app.schemas.user import UserResponse
from app.services import payment_service

router = APIRouter(prefix="", tags=["payments"])


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing() -> PricingResponse:
    """Get current pricing for verification services."""
    return PricingResponse(
        standard_verification=settings.PRICE_STANDARD_VERIFICATION,
        priority_verification=settings.PRICE_PRIORITY_VERIFICATION,
        renewal_verification=settings.PRICE_RENEWAL_VERIFICATION,
        currency="eur",
    )


@router.post("/create-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    payment_data: PaymentCreate,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentIntentResponse:
    """
    Create a payment intent for verification fee.

    Returns client_secret to complete payment on frontend with Stripe.js.
    """
    if not payment_service.is_stripe_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service is not configured",
        )

    try:
        payment, client_secret = await payment_service.create_payment_intent(
            db,
            current_user.id,
            payment_data.payment_type,
        )

        return PaymentIntentResponse(
            payment_id=payment.id,
            client_secret=client_secret,
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
            amount=payment.amount,
            currency=payment.currency,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/status", response_model=PaymentStatusResponse)
async def get_payment_status(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentStatusResponse:
    """
    Check if user has a valid payment for verification.

    A valid payment allows document upload for verification.
    """
    payment = await payment_service.get_valid_payment_for_verification(
        db, current_user.id
    )

    if not payment:
        return PaymentStatusResponse(
            has_valid_payment=False,
            payment_type=None,
            payment_id=None,
            expires_at=None,
        )

    from datetime import timedelta

    expires_at = payment.created_at + timedelta(days=30)

    return PaymentStatusResponse(
        has_valid_payment=True,
        payment_type=payment.payment_type,
        payment_id=payment.id,
        expires_at=expires_at,
    )


@router.get("/", response_model=PaymentListResponse)
async def list_my_payments(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> PaymentListResponse:
    """List current user's payments."""
    offset = (page - 1) * per_page
    payments, total = await payment_service.get_user_payments(
        db, current_user.id, per_page, offset
    )

    return PaymentListResponse(
        payments=[PaymentResponse.model_validate(p) for p in payments],
        total=total,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentResponse:
    """Get a specific payment."""
    payment = await payment_service.get_payment_by_id(db, payment_id)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your payment",
        )

    return PaymentResponse.model_validate(payment)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
) -> dict:
    """
    Handle Stripe webhook events.

    This endpoint is called by Stripe when payment events occur.
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    payload = await request.body()
    event = payment_service.verify_webhook_signature(payload, stripe_signature)

    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    if event_type == "payment_intent.succeeded":
        payment_intent_id = data.get("id")
        charge_id = None
        if "latest_charge" in data:
            charge_id = data["latest_charge"]

        await payment_service.handle_payment_succeeded(
            db, payment_intent_id, charge_id
        )

    elif event_type == "payment_intent.payment_failed":
        payment_intent_id = data.get("id")
        failure_message = data.get("last_payment_error", {}).get("message")

        await payment_service.handle_payment_failed(
            db, payment_intent_id, failure_message
        )

    return {"status": "ok"}
