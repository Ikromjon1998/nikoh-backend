import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Verified information (filled by verification system later)
    verified_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_last_initial: Mapped[str | None] = mapped_column(String(1), nullable=True)
    verified_birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified_birthplace_country: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    verified_birthplace_city: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    verified_nationality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_residence_country: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    verified_residence_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    verified_marital_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    verified_education_level: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # Self-declared required
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    seeking_gender: Mapped[str] = mapped_column(String(20), nullable=False)

    # Self-declared optional
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    build: Mapped[str | None] = mapped_column(String(30), nullable=True)

    ethnicity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ethnicity_other: Mapped[str | None] = mapped_column(String(100), nullable=True)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    original_region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    living_situation: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Religious practice
    religious_practice: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Lifestyle
    smoking: Mapped[str | None] = mapped_column(String(30), nullable=True)
    alcohol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    diet: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Professional
    profession: Mapped[str | None] = mapped_column(String(200), nullable=True)
    hobbies: Mapped[list] = mapped_column(ARRAY(String), default=list)

    # Essays
    about_me: Mapped[str | None] = mapped_column(Text, nullable=True)
    family_meaning: Mapped[str | None] = mapped_column(Text, nullable=True)
    ideal_partner: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals_dreams: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_to_family: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Profile status
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    profile_score: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="profile")
