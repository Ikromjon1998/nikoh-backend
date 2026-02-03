from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.database import get_db
from app.schemas.match import MatchListResponse, MatchResponse
from app.schemas.profile import ProfileBrief
from app.schemas.search_preference import MatchSuggestionsResponse, WhoLikesMeResponse
from app.schemas.user import UserResponse
from app.services import match_service, matching_service, profile_service

router = APIRouter(prefix="", tags=["matches"])


async def _get_other_user_id(match: MatchResponse, current_user_id: UUID) -> UUID:
    """Get the ID of the other user in the match."""
    if match.user_a_id == current_user_id:
        return match.user_b_id
    return match.user_a_id


async def _enrich_match_with_profile(
    db: AsyncSession,
    match: MatchResponse,
    other_user_id: UUID,
) -> MatchResponse:
    """Add other user's profile info to match response."""
    profile = await profile_service.get_profile_by_user_id(db, other_user_id)
    if profile:
        match.other_user_profile = ProfileBrief.model_validate(profile).model_dump()
    return match


@router.get("/", response_model=MatchListResponse)
async def get_my_matches(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> MatchListResponse:
    """Get all active matches for current user."""
    matches, total = await match_service.get_user_matches(
        db, current_user.id, "active", page, per_page
    )

    match_responses = []
    for match in matches:
        response = MatchResponse.model_validate(match)
        other_user_id = await _get_other_user_id(response, current_user.id)
        response = await _enrich_match_with_profile(db, response, other_user_id)
        match_responses.append(response)

    return MatchListResponse(
        matches=match_responses,
        total=total,
        page=page,
        per_page=per_page,
    )


# NOTE: These specific routes MUST be defined before /{match_id} to avoid route conflicts
@router.get("/suggestions", response_model=MatchSuggestionsResponse)
async def get_match_suggestions(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
) -> MatchSuggestionsResponse:
    """
    Get match suggestions based on preferences and compatibility.

    Returns top profiles ranked by:
    1. User's search preferences
    2. Compatibility score
    3. Profile completeness
    4. Verification status
    5. Recent activity

    Excludes:
    - Already matched profiles
    - Profiles you've declined
    - Profiles you've already sent interest to
    """
    suggestions, total = await matching_service.get_suggestions(
        db, current_user.id, limit
    )

    return MatchSuggestionsResponse(
        suggestions=suggestions,
        total_available=total,
    )


@router.get("/who-likes-me", response_model=WhoLikesMeResponse)
async def get_who_likes_me(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(20, ge=1, le=100),
) -> WhoLikesMeResponse:
    """
    Find profiles where their preferences match your profile.

    These are users who:
    - Have set search preferences
    - Their preferences match your profile
    - Haven't sent you interest yet

    For verified users: Shows full list
    For non-verified users: Shows count only (verify to see who)
    """
    is_verified = current_user.verification_status == "verified"

    if is_verified:
        profiles, total = await matching_service.get_who_likes_me(
            db, current_user.id, limit
        )
    else:
        # Non-verified users only see the count
        _, total = await matching_service.get_who_likes_me(
            db, current_user.id, limit=1000
        )
        profiles = []

    return WhoLikesMeResponse(
        profiles=profiles,
        total_count=total,
        is_verified_user=is_verified,
    )


# Dynamic routes MUST come after specific routes to avoid conflicts
@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MatchResponse:
    """Get specific match details."""
    match = await match_service.get_match_by_id(db, match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    # Must be part of the match
    if match.user_a_id != current_user.id and match.user_b_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your match",
        )

    response = MatchResponse.model_validate(match)
    other_user_id = await _get_other_user_id(response, current_user.id)
    return await _enrich_match_with_profile(db, response, other_user_id)


@router.post("/{match_id}/unmatch", response_model=MatchResponse)
async def unmatch(
    match_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MatchResponse:
    """Unmatch with someone."""
    match = await match_service.get_match_by_id(db, match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    # Must be part of the match
    if match.user_a_id != current_user.id and match.user_b_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your match",
        )

    # Must be active
    if match.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match is already unmatched",
        )

    updated_match = await match_service.unmatch(db, match, current_user.id)

    response = MatchResponse.model_validate(updated_match)
    other_user_id = await _get_other_user_id(response, current_user.id)
    return await _enrich_match_with_profile(db, response, other_user_id)
