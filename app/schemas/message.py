"""Message schemas for API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    """Create a new message."""
    content: str = Field(..., min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    """Message response."""
    id: UUID
    match_id: UUID
    sender_id: UUID
    content: str
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatPreview(BaseModel):
    """Preview of a chat for the chat list."""
    match_id: UUID
    partner_name: str
    last_message: str | None
    last_message_at: datetime | None
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Unread messages count."""
    count: int
