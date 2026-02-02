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
from app.schemas.user import UserResponse
from app.services import profile_service

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


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    """Get a profile by ID."""
    profile = await profile_service.get_profile_by_id(db, profile_id)

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
