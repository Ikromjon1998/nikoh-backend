"""Search preference schemas for API requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SearchPreferenceCreate(BaseModel):
    """Schema for creating/updating search preferences."""

    # Age preferences
    min_age: int = Field(default=18, ge=18, le=99)
    max_age: int = Field(default=99, ge=18, le=99)

    # Location preferences
    preferred_countries: list[str] | None = None
    preferred_cities: list[str] | None = None
    willing_to_relocate: bool = False
    relocation_countries: list[str] | None = None

    # Background preferences
    preferred_ethnicities: list[str] | None = None
    preferred_marital_statuses: list[str] | None = None
    preferred_education_levels: list[str] | None = None

    # Religion preferences
    preferred_religious_practices: list[str] | None = None

    # Physical preferences
    min_height_cm: int | None = Field(default=None, ge=100, le=250)
    max_height_cm: int | None = Field(default=None, ge=100, le=250)

    # Lifestyle preferences
    preferred_smoking: list[str] | None = None
    preferred_alcohol: list[str] | None = None
    preferred_diet: list[str] | None = None

    # Other preferences
    must_be_verified: bool = True
    has_children_acceptable: bool = True
    children_preference: str | None = "no_preference"


class SearchPreferenceResponse(BaseModel):
    """Schema for search preference response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID

    # Age preferences
    min_age: int
    max_age: int

    # Location preferences
    preferred_countries: list[str] | None = None
    preferred_cities: list[str] | None = None
    willing_to_relocate: bool
    relocation_countries: list[str] | None = None

    # Background preferences
    preferred_ethnicities: list[str] | None = None
    preferred_marital_statuses: list[str] | None = None
    preferred_education_levels: list[str] | None = None

    # Religion preferences
    preferred_religious_practices: list[str] | None = None

    # Physical preferences
    min_height_cm: int | None = None
    max_height_cm: int | None = None

    # Lifestyle preferences
    preferred_smoking: list[str] | None = None
    preferred_alcohol: list[str] | None = None
    preferred_diet: list[str] | None = None

    # Other preferences
    must_be_verified: bool
    has_children_acceptable: bool
    children_preference: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime


class CompatibilityBreakdown(BaseModel):
    """Breakdown of compatibility for a single factor."""

    match: bool
    score: int
    max_score: int
    detail: str


class CompatibilityResponse(BaseModel):
    """Schema for compatibility score response."""

    score: int = Field(ge=0, le=100)
    breakdown: dict[str, CompatibilityBreakdown]
    mutual: bool
    mutual_score: int | None = None


class MatchSuggestion(BaseModel):
    """Schema for a match suggestion."""

    model_config = ConfigDict(from_attributes=True)

    profile_id: uuid.UUID
    user_id: uuid.UUID
    display_name: str | None
    age: int | None
    city: str | None
    country: str | None
    compatibility_score: int
    is_mutual_match: bool
    is_verified: bool
    photo_url: str | None = None


class MatchSuggestionsResponse(BaseModel):
    """Schema for match suggestions list."""

    suggestions: list[MatchSuggestion]
    total_available: int


class WhoLikesMeResponse(BaseModel):
    """Schema for who likes me response."""

    profiles: list[MatchSuggestion]
    total_count: int
    is_verified_user: bool
