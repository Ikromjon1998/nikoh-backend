"""Payment service for Stripe integration."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.payment import Payment, PaymentStatus, PaymentType

logger = logging.getLogger(__name__)

# Lazy load stripe to handle missing dependency
_stripe = None


def _get_stripe():
    """Get stripe module (lazy loading)."""
    global _stripe
    if _stripe is None:
        try:
            import stripe

            stripe.api_key = settings.STRIPE_SECRET_KEY
            _stripe = stripe
        except ImportError:
            logger.warning("Stripe not installed")
            return None
    return _stripe


def is_stripe_available() -> bool:
    """Check if Stripe is configured and available."""
    stripe = _get_stripe()
    return stripe is not None and bool(settings.STRIPE_SECRET_KEY)


def get_price_for_type(payment_type: PaymentType) -> int:
    """Get price in cents for a payment type."""
    prices = {
        PaymentType.STANDARD_VERIFICATION: settings.PRICE_STANDARD_VERIFICATION,
        PaymentType.PRIORITY_VERIFICATION: settings.PRICE_PRIORITY_VERIFICATION,
        PaymentType.RENEWAL_VERIFICATION: settings.PRICE_RENEWAL_VERIFICATION,
    }
    return prices.get(payment_type, settings.PRICE_STANDARD_VERIFICATION)


def get_description_for_type(payment_type: PaymentType) -> str:
    """Get description for a payment type."""
    descriptions = {
        PaymentType.STANDARD_VERIFICATION: "Standard ID Verification",
        PaymentType.PRIORITY_VERIFICATION: "Priority ID Verification (faster processing)",
        PaymentType.RENEWAL_VERIFICATION: "Annual Verification Renewal",
    }
    return descriptions.get(payment_type, "Verification Fee")


async def create_payment_intent(
    db: AsyncSession,
    user_id: uuid.UUID,
    payment_type: PaymentType,
) -> tuple[Payment, str]:
    """
    Create a Stripe payment intent and payment record.

    Args:
        db: Database session
        user_id: User ID
        payment_type: Type of payment

    Returns:
        Tuple of (Payment record, client_secret)

    Raises:
        ValueError: If Stripe is not available
    """
    stripe = _get_stripe()
    if stripe is None or not settings.STRIPE_SECRET_KEY:
        raise ValueError("Stripe is not configured")

    amount = get_price_for_type(payment_type)
    description = get_description_for_type(payment_type)

    # Create payment record first
    payment = Payment(
        user_id=user_id,
        payment_type=payment_type,
        status=PaymentStatus.PENDING,
        amount=amount,
        currency="eur",
        description=description,
    )
    db.add(payment)
    await db.flush()

    try:
        # Create Stripe payment intent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="eur",
            metadata={
                "payment_id": str(payment.id),
                "user_id": str(user_id),
                "payment_type": payment_type.value,
            },
            description=description,
        )

        payment.stripe_payment_intent_id = intent.id
        await db.commit()
        await db.refresh(payment)

        return payment, intent.client_secret

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating payment intent: {e}")
        payment.status = PaymentStatus.FAILED
        payment.failure_reason = str(e)
        await db.commit()
        raise ValueError(f"Payment creation failed: {e}")


async def handle_payment_succeeded(
    db: AsyncSession,
    payment_intent_id: str,
    charge_id: str | None = None,
) -> Payment | None:
    """
    Handle successful payment from webhook.

    Args:
        db: Database session
        payment_intent_id: Stripe payment intent ID
        charge_id: Stripe charge ID

    Returns:
        Updated payment record or None
    """
    result = await db.execute(
        select(Payment).where(Payment.stripe_payment_intent_id == payment_intent_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        logger.warning(f"Payment not found for intent: {payment_intent_id}")
        return None

    payment.status = PaymentStatus.COMPLETED
    payment.completed_at = datetime.utcnow()
    if charge_id:
        payment.stripe_charge_id = charge_id

    await db.commit()
    await db.refresh(payment)

    logger.info(f"Payment {payment.id} marked as completed")
    return payment


async def handle_payment_failed(
    db: AsyncSession,
    payment_intent_id: str,
    failure_reason: str | None = None,
) -> Payment | None:
    """
    Handle failed payment from webhook.

    Args:
        db: Database session
        payment_intent_id: Stripe payment intent ID
        failure_reason: Reason for failure

    Returns:
        Updated payment record or None
    """
    result = await db.execute(
        select(Payment).where(Payment.stripe_payment_intent_id == payment_intent_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        logger.warning(f"Payment not found for intent: {payment_intent_id}")
        return None

    payment.status = PaymentStatus.FAILED
    payment.failure_reason = failure_reason

    await db.commit()
    await db.refresh(payment)

    logger.info(f"Payment {payment.id} marked as failed: {failure_reason}")
    return payment


async def get_payment_by_id(
    db: AsyncSession,
    payment_id: uuid.UUID,
) -> Payment | None:
    """Get payment by ID."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()


async def get_user_payments(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Payment], int]:
    """
    Get all payments for a user.

    Returns:
        Tuple of (payments list, total count)
    """
    # Count query
    count_result = await db.execute(
        select(Payment).where(Payment.user_id == user_id)
    )
    total = len(count_result.scalars().all())

    # Data query
    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    payments = list(result.scalars().all())

    return payments, total


async def get_valid_payment_for_verification(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Payment | None:
    """
    Get a valid (completed, unused) payment for verification.

    A payment is valid if:
    - Status is COMPLETED
    - Not yet linked to a verification
    - Created within the last 30 days

    Returns:
        Valid payment or None
    """
    # Use timezone-aware datetime but strip tzinfo for comparison with naive DB timestamps
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)

    result = await db.execute(
        select(Payment)
        .where(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.COMPLETED,
            Payment.verification_id.is_(None),
            Payment.created_at >= cutoff,
        )
        .order_by(Payment.created_at.desc())
    )
    return result.scalar_one_or_none()


async def link_payment_to_verification(
    db: AsyncSession,
    payment_id: uuid.UUID,
    verification_id: uuid.UUID,
) -> Payment | None:
    """Link a payment to a verification."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()

    if not payment:
        return None

    payment.verification_id = verification_id
    await db.commit()
    await db.refresh(payment)

    return payment


async def refund_payment(
    db: AsyncSession,
    payment_id: uuid.UUID,
    reason: str | None = None,
) -> Payment | None:
    """
    Refund a payment via Stripe.

    Args:
        db: Database session
        payment_id: Payment ID to refund
        reason: Reason for refund

    Returns:
        Updated payment or None
    """
    stripe = _get_stripe()
    if stripe is None:
        raise ValueError("Stripe is not configured")

    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()

    if not payment:
        return None

    if payment.status != PaymentStatus.COMPLETED:
        raise ValueError("Can only refund completed payments")

    try:
        # Create refund in Stripe
        stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            reason="requested_by_customer" if not reason else None,
            metadata={"reason": reason} if reason else None,
        )

        payment.status = PaymentStatus.REFUNDED
        payment.refunded_at = datetime.utcnow()
        await db.commit()
        await db.refresh(payment)

        logger.info(f"Payment {payment.id} refunded")
        return payment

    except stripe.error.StripeError as e:
        logger.error(f"Failed to refund payment {payment_id}: {e}")
        raise ValueError(f"Refund failed: {e}")


def verify_webhook_signature(payload: bytes, signature: str) -> dict | None:
    """
    Verify Stripe webhook signature and return the event.

    Args:
        payload: Raw request body
        signature: Stripe-Signature header value

    Returns:
        Stripe event dict or None if verification fails
    """
    stripe = _get_stripe()
    if stripe is None:
        return None

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("Webhook secret not configured")
        return None

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
        return event
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        return None
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        return None
