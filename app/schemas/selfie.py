"""Selfie schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SelfieResponse(BaseModel):
    """Selfie details returned by API."""

    id: UUID
    user_id: UUID
    original_filename: str | None
    mime_type: str | None
    file_size: int | None
    status: str
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SelfieStatusResponse(BaseModel):
    """Selfie status check response."""

    has_selfie: bool
    status: str | None  # pending, processed, failed
    error_message: str | None
    can_verify_passport: bool
