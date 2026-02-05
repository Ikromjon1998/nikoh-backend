import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Who is being reported
    reported_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Who is making the report
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Reason category: inappropriate_content, harassment, fake_profile, scam, other
    reason: Mapped[str] = mapped_column(String(50), nullable=False)

    # Optional detailed description
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status: pending, reviewed, dismissed, action_taken
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # Admin who reviewed this report
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Admin notes
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    reported_user: Mapped["User"] = relationship(
        "User", foreign_keys=[reported_user_id], backref="reports_received"
    )
    reporter_user: Mapped["User"] = relationship(
        "User", foreign_keys=[reporter_user_id], backref="reports_made"
    )
    reviewer: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by]
    )
