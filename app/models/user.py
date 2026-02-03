import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.interest import Interest
    from app.models.payment import Payment
    from app.models.profile import Profile
    from app.models.search_preference import SearchPreference
    from app.models.selfie import Selfie
    from app.models.verification import Verification


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
    )
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        default="ru",
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    verification_status: Mapped[str] = mapped_column(
        String(20),
        default="unverified",
    )
    verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    profile: Mapped["Profile | None"] = relationship(
        "Profile", back_populates="user", uselist=False
    )
    sent_interests: Mapped[list["Interest"]] = relationship(
        "Interest",
        foreign_keys="Interest.from_user_id",
        back_populates="from_user",
    )
    received_interests: Mapped[list["Interest"]] = relationship(
        "Interest",
        foreign_keys="Interest.to_user_id",
        back_populates="to_user",
    )
    verifications: Mapped[list["Verification"]] = relationship(
        "Verification",
        foreign_keys="Verification.user_id",
        back_populates="user",
    )
    selfie: Mapped["Selfie | None"] = relationship(
        "Selfie", back_populates="user", uselist=False
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="user"
    )
    search_preferences: Mapped["SearchPreference | None"] = relationship(
        "SearchPreference", back_populates="user", uselist=False
    )
