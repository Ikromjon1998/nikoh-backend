"""Search preference endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.database import get_db
from app.schemas.search_preference import (
    CompatibilityResponse,
    MatchSuggestionsResponse,
    SearchPreferenceCreate,
    SearchPreferenceResponse,
    WhoLikesMeResponse,
)
from app.schemas.user import UserResponse
from app.services import matching_service, search_preference_service

router = APIRouter(prefix="", tags=["preferences"])


@router.post("/", response_model=SearchPreferenceResponse)
async def create_or_update_preferences(
    preferences: SearchPreferenceCreate,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchPreferenceResponse:
    """
    Create or update search preferences.

    This is an upsert operation:
    - Creates new preferences if none exist
    - Updates existing preferences if already set

    Empty arrays (e.g., preferred_countries: []) mean "any" value is acceptable.
    """
    result = await search_preference_service.create_or_update_preferences(
        db, current_user.id, preferences
    )
    return SearchPreferenceResponse.model_validate(result)


@router.get("/", response_model=SearchPreferenceResponse)
async def get_my_preferences(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchPreferenceResponse:
    """Get current user's search preferences."""
    preferences = await search_preference_service.get_preferences_by_user_id(
        db, current_user.id
    )

    if not preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preferences set. Use POST /preferences/ to create.",
        )

    return SearchPreferenceResponse.model_validate(preferences)


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preferences(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete search preferences (reset to defaults).

    After deletion, the system will use default matching behavior.
    """
    deleted = await search_preference_service.delete_preferences(db, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preferences to delete",
        )


@router.get("/defaults")
async def get_default_preferences() -> dict:
    """Get default preference values for reference."""
    return search_preference_service.get_default_preferences()
