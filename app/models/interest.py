import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


def default_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=14)


class Interest(Base):
    __tablename__ = "interests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Who sent the interest
    from_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Who receives the interest
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional message (max 200 chars)
    message: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Status: pending, accepted, declined, expired, cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # When the recipient responded
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Auto-expire after 14 days if no response
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=default_expires_at,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    from_user: Mapped["User"] = relationship(
        "User", foreign_keys=[from_user_id], back_populates="sent_interests"
    )
    to_user: Mapped["User"] = relationship(
        "User", foreign_keys=[to_user_id], back_populates="received_interests"
    )
