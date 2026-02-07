from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.database import get_db
from app.schemas.profile import (
    ProfileBrief,
    ProfileCreate,
    ProfileResponse,
    ProfileSearch,
    ProfileSearchResponse,
    ProfileUpdate,
)
from app.schemas.search_preference import CompatibilityResponse
from app.schemas.user import UserResponse
from app.services import matching_service, profile_service

router = APIRouter(prefix="", tags=["profiles"])


@router.post("/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile_data: ProfileCreate,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Create a new profile for the current user."""
    existing_profile = await profile_service.get_profile_by_user_id(db, current_user.id)
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists for this user",
        )

    profile = await profile_service.create_profile(db, current_user.id, profile_data)
    return ProfileResponse.model_validate(profile)


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Get the current user's profile."""
    profile = await profile_service.get_profile_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return ProfileResponse.model_validate(profile)


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    profile_data: ProfileUpdate,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Update the current user's profile."""
    profile = await profile_service.get_profile_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    updated_profile = await profile_service.update_profile(db, profile, profile_data)
    return ProfileResponse.model_validate(updated_profile)


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(
    user_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Get a profile by user ID."""
    profile = await profile_service.get_profile_by_user_id(db, user_id)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # Allow access to own profile even if not visible
    if profile.user_id != current_user.id and not profile.is_visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return ProfileResponse.model_validate(profile)


@router.post("/search", response_model=ProfileSearchResponse)
async def search_profiles(
    search_params: ProfileSearch,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileSearchResponse:
    """Search profiles with filters."""
    profiles, total = await profile_service.search_profiles(
        db, search_params, current_user.id
    )

    profile_briefs = [ProfileBrief.model_validate(p) for p in profiles]

    return ProfileSearchResponse(
        profiles=profile_briefs,
        total=total,
        page=search_params.page,
        per_page=search_params.per_page,
    )


@router.get("/{user_id}/compatibility", response_model=CompatibilityResponse)
async def get_profile_compatibility(
    user_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CompatibilityResponse:
    """
    Get compatibility score with a specific profile.

    Returns:
    - Overall score (0-100)
    - Breakdown by category
    - Whether it's a mutual match

    Useful for showing "85% compatible" on profile views.
    """
    # Check profile exists
    profile = await profile_service.get_profile_by_user_id(db, user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # Don't allow checking compatibility with own profile
    if profile.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot check compatibility with your own profile",
        )

    # Profile must be visible
    if not profile.is_visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    compatibility = await matching_service.get_compatibility_with_profile(
        db, current_user.id, profile.id
    )

    if not compatibility:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot calculate compatibility. Make sure you have a profile.",
        )

    return compatibility
