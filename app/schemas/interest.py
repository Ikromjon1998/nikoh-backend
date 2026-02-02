from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InterestStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    cancelled = "cancelled"


class InterestCreate(BaseModel):
    """Send interest to another user"""

    to_user_id: UUID
    message: str | None = Field(None, max_length=200)


class InterestRespond(BaseModel):
    """Accept or decline an interest"""

    action: str = Field(..., pattern="^(accept|decline)$")


class InterestResponse(BaseModel):
    """Interest details returned by API"""

    id: UUID
    from_user_id: UUID
    to_user_id: UUID
    message: str | None
    status: str
    responded_at: datetime | None
    expires_at: datetime
    created_at: datetime

    # Include basic profile info of the other person
    other_user_profile: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class InterestListResponse(BaseModel):
    """Paginated list of interests"""

    interests: list[InterestResponse]
    total: int
    page: int
    per_page: int
