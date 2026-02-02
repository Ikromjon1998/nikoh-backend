"""Payment schemas for API requests and responses."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class PaymentStatus(str, Enum):
    """Payment status enumeration."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentType(str, Enum):
    """Payment type enumeration."""

    STANDARD_VERIFICATION = "standard_verification"
    PRIORITY_VERIFICATION = "priority_verification"
    RENEWAL_VERIFICATION = "renewal_verification"


class PaymentCreate(BaseModel):
    """Schema for creating a payment."""

    payment_type: PaymentType


class PaymentResponse(BaseModel):
    """Schema for payment response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    verification_id: uuid.UUID | None = None
    payment_type: PaymentType
    status: PaymentStatus
    amount: int
    currency: str
    description: str | None = None
    failure_reason: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class PaymentIntentResponse(BaseModel):
    """Response for creating a Stripe payment intent."""

    payment_id: uuid.UUID
    client_secret: str
    publishable_key: str
    amount: int
    currency: str


class PaymentListResponse(BaseModel):
    """Schema for listing payments."""

    payments: list[PaymentResponse]
    total: int


class PricingResponse(BaseModel):
    """Schema for pricing information."""

    standard_verification: int
    priority_verification: int
    renewal_verification: int
    currency: str


class PaymentStatusResponse(BaseModel):
    """Schema for checking payment status before verification."""

    has_valid_payment: bool
    payment_type: PaymentType | None = None
    payment_id: uuid.UUID | None = None
    expires_at: datetime | None = None
