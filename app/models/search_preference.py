"""Search preference model for partner matching."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SearchPreference(Base):
    """User's saved search preferences for finding a partner."""

    __tablename__ = "search_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Age preferences
    min_age: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    max_age: Mapped[int] = mapped_column(Integer, default=99, nullable=False)

    # Location preferences
    preferred_countries: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
    )
    preferred_cities: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
    )
    willing_to_relocate: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    relocation_countries: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
    )

    # Background preferences
    preferred_ethnicities: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )
    preferred_marital_statuses: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )
    preferred_education_levels: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )

    # Religion preferences
    preferred_religious_practices: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )

    # Physical preferences
    min_height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Lifestyle preferences
    preferred_smoking: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )
    preferred_alcohol: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )
    preferred_diet: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )

    # Other preferences
    must_be_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    has_children_acceptable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    children_preference: Mapped[str | None] = mapped_column(
        String(50),
        default="no_preference",
        nullable=True,
    )  # wants_children, no_children, no_preference

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

    # Relationships
    user = relationship("User", back_populates="search_preferences")
