import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Document type: passport, residence_permit, divorce_certificate, diploma, employment_proof
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Issuing country
    document_country: Mapped[str] = mapped_column(String(100), nullable=False)

    # Status: pending, processing, approved, rejected, expired, cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # Rejection reason (if rejected)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extracted data (varies by document type)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Document expiry date (from document)
    document_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # File storage path
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Original filename
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # File mime type
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # File size in bytes
    file_size: Mapped[int | None] = mapped_column(nullable=True)

    # Verification method: automated, manual
    verification_method: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Verified by (admin user_id, if manual)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="verifications",
    )
    verified_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[verified_by],
    )
