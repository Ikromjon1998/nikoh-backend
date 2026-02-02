import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Two users in the match (user_a_id < user_b_id for consistency)
    user_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Status: active, unmatched
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    # If unmatched, who did it
    unmatched_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    unmatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user_a: Mapped["User"] = relationship("User", foreign_keys=[user_a_id])
    user_b: Mapped["User"] = relationship("User", foreign_keys=[user_b_id])
    unmatched_by_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[unmatched_by]
    )

    __table_args__ = (
        CheckConstraint("user_a_id < user_b_id", name="user_order_check"),
    )
