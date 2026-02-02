from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.database import get_db
from app.schemas.interest import (
    InterestCreate,
    InterestListResponse,
    InterestRespond,
    InterestResponse,
)
from app.schemas.profile import ProfileBrief
from app.schemas.user import UserResponse
from app.services import interest_service, profile_service

router = APIRouter(prefix="", tags=["interests"])


async def _enrich_interest_with_profile(
    db: AsyncSession,
    interest: InterestResponse,
    other_user_id: UUID,
) -> InterestResponse:
    """Add other user's profile info to interest response."""
    profile = await profile_service.get_profile_by_user_id(db, other_user_id)
    if profile:
        interest.other_user_profile = ProfileBrief.model_validate(profile).model_dump()
    return interest


@router.post("/", response_model=InterestResponse, status_code=status.HTTP_201_CREATED)
async def send_interest(
    data: InterestCreate,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InterestResponse:
    """
    Send interest to another user.

    Validations:
    - Cannot send interest to yourself
    - Cannot send if you already have pending interest to this user
    - Cannot send if you're already matched with this user
    - Target user must have a visible profile
    """
    # Cannot send to yourself
    if data.to_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send interest to yourself",
        )

    # Check target user has visible profile
    target_profile = await profile_service.get_profile_by_user_id(db, data.to_user_id)
    if not target_profile or not target_profile.is_visible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found or not visible",
        )

    # Check for existing pending interest
    existing = await interest_service.get_pending_interest_between_users(
        db, current_user.id, data.to_user_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already sent pending interest to this user",
        )

    # Check if already matched
    already_matched = await interest_service.check_already_matched(
        db, current_user.id, data.to_user_id
    )
    if already_matched:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already matched with this user",
        )

    interest = await interest_service.create_interest(db, current_user.id, data)
    response = InterestResponse.model_validate(interest)
    return await _enrich_interest_with_profile(db, response, data.to_user_id)


@router.get("/received", response_model=InterestListResponse)
async def get_received_interests(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    interest_status: str | None = Query(
        None,
        alias="status",
        pattern="^(pending|accepted|declined|expired|cancelled)$",
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> InterestListResponse:
    """Get interests received by current user."""
    interests, total = await interest_service.get_received_interests(
        db, current_user.id, interest_status, page, per_page
    )

    interest_responses = []
    for interest in interests:
        response = InterestResponse.model_validate(interest)
        response = await _enrich_interest_with_profile(
            db, response, interest.from_user_id
        )
        interest_responses.append(response)

    return InterestListResponse(
        interests=interest_responses,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/sent", response_model=InterestListResponse)
async def get_sent_interests(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    interest_status: str | None = Query(
        None,
        alias="status",
        pattern="^(pending|accepted|declined|expired|cancelled)$",
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> InterestListResponse:
    """Get interests sent by current user."""
    interests, total = await interest_service.get_sent_interests(
        db, current_user.id, interest_status, page, per_page
    )

    interest_responses = []
    for interest in interests:
        response = InterestResponse.model_validate(interest)
        response = await _enrich_interest_with_profile(db, response, interest.to_user_id)
        interest_responses.append(response)

    return InterestListResponse(
        interests=interest_responses,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/{interest_id}/respond", response_model=InterestResponse)
async def respond_to_interest(
    interest_id: UUID,
    data: InterestRespond,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InterestResponse:
    """
    Accept or decline an interest.

    If accepted, a Match is created.
    """
    interest = await interest_service.get_interest_by_id(db, interest_id)
    if not interest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interest not found",
        )

    # Must be the recipient to respond
    if interest.to_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your interest to respond to",
        )

    # Must be pending
    if interest.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interest is not pending (status: {interest.status})",
        )

    updated_interest, match = await interest_service.respond_to_interest(
        db, interest, data.action
    )

    response = InterestResponse.model_validate(updated_interest)
    return await _enrich_interest_with_profile(db, response, interest.from_user_id)


@router.delete("/{interest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_interest(
    interest_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Cancel a pending interest you sent."""
    interest = await interest_service.get_interest_by_id(db, interest_id)
    if not interest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interest not found",
        )

    # Must be the sender to cancel
    if interest.from_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your interest to cancel",
        )

    # Must be pending
    if interest.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interest is not pending (status: {interest.status})",
        )

    await interest_service.delete_interest(db, interest)
