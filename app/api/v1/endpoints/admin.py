from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.schemas.verification import (
    VerificationAdminListResponse,
    VerificationAdminResponse,
    VerificationApprove,
    VerificationReject,
)
from app.services import verification_service

router = APIRouter(prefix="", tags=["admin"])


async def get_current_admin_user(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Dependency that checks if current user is admin."""
    # Fetch full user to check is_admin
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


@router.get("/verifications/pending", response_model=VerificationAdminListResponse)
async def list_pending_verifications(
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> VerificationAdminListResponse:
    """List all pending verifications (admin only)."""
    verifications, total = await verification_service.get_pending_verifications(
        db, page, per_page
    )

    return VerificationAdminListResponse(
        verifications=[VerificationAdminResponse.model_validate(v) for v in verifications],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/verifications/{verification_id}", response_model=VerificationAdminResponse)
async def get_verification_admin(
    verification_id: UUID,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerificationAdminResponse:
    """Get verification details including file path (admin only)."""
    verification = await verification_service.get_verification_by_id(db, verification_id)

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found",
        )

    return VerificationAdminResponse.model_validate(verification)


@router.post("/verifications/{verification_id}/approve", response_model=VerificationAdminResponse)
async def approve_verification(
    verification_id: UUID,
    approval_data: VerificationApprove,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerificationAdminResponse:
    """
    Approve a verification with extracted data (admin only).

    The extracted data will be copied to the user's profile based on document type.
    """
    verification = await verification_service.get_verification_by_id(db, verification_id)

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found",
        )

    # Allow approve for pending, processing (auto-verification), and manual_review statuses
    reviewable_statuses = ("pending", "processing", "manual_review")
    if verification.status not in reviewable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve verification with status: {verification.status}",
        )

    updated = await verification_service.approve_verification(
        db, verification, admin_user.id, approval_data
    )

    return VerificationAdminResponse.model_validate(updated)


@router.post("/verifications/{verification_id}/reject", response_model=VerificationAdminResponse)
async def reject_verification(
    verification_id: UUID,
    rejection_data: VerificationReject,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerificationAdminResponse:
    """Reject a verification with reason (admin only)."""
    verification = await verification_service.get_verification_by_id(db, verification_id)

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found",
        )

    # Allow reject for pending, processing (auto-verification), and manual_review statuses
    reviewable_statuses = ("pending", "processing", "manual_review")
    if verification.status not in reviewable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject verification with status: {verification.status}",
        )

    updated = await verification_service.reject_verification(
        db, verification, admin_user.id, rejection_data.reason
    )

    return VerificationAdminResponse.model_validate(updated)
