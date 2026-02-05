from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ReportReason(str, Enum):
    inappropriate_content = "inappropriate_content"
    harassment = "harassment"
    fake_profile = "fake_profile"
    scam = "scam"
    spam = "spam"
    other = "other"


class ReportStatus(str, Enum):
    pending = "pending"
    reviewed = "reviewed"
    dismissed = "dismissed"
    action_taken = "action_taken"


# User-facing schemas
class ReportCreate(BaseModel):
    reported_user_id: UUID
    reason: ReportReason
    description: str | None = Field(None, max_length=1000)


class ReportResponse(BaseModel):
    id: UUID
    reported_user_id: UUID
    reason: str
    description: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# Admin schemas
class ReportAdminResponse(BaseModel):
    id: UUID
    reported_user_id: UUID
    reporter_user_id: UUID
    reason: str
    description: str | None
    status: str
    reviewed_by: UUID | None
    admin_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime
    # Include user emails for display
    reported_user_email: str | None = None
    reporter_user_email: str | None = None

    model_config = {"from_attributes": True}


class ReportAdminListResponse(BaseModel):
    reports: list[ReportAdminResponse]
    total: int
    page: int
    per_page: int


class ReportReview(BaseModel):
    status: ReportStatus
    admin_notes: str | None = None
    suspend_user: bool = False
