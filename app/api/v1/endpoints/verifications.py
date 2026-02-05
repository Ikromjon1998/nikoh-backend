import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.v1.endpoints.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.schemas.selfie import SelfieResponse, SelfieStatusResponse
from app.schemas.user import UserResponse
from app.schemas.verification import (
    DocumentType,
    VerificationListResponse,
    VerificationResponse,
    VerificationStatusSummary,
)
from app.services import auto_verification_service, payment_service, selfie_service, verification_service

router = APIRouter(prefix="", tags=["verifications"])


@router.post("/selfie", response_model=SelfieResponse, status_code=status.HTTP_201_CREATED)
async def upload_selfie(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> SelfieResponse:
    """
    Upload a selfie for face verification.

    This selfie will be used to compare with passport photos during verification.
    Required before passport can be auto-verified.

    Accepted formats: JPEG, PNG
    Max file size: 10MB
    """
    # Validate file type
    is_valid, error_msg = selfie_service.validate_selfie_file(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Validate file size
    is_valid, error_msg = await selfie_service.validate_selfie_file_size(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    selfie = await selfie_service.upload_selfie(db, current_user.id, file)

    return SelfieResponse.model_validate(selfie)


@router.get("/selfie", response_model=SelfieResponse)
async def get_my_selfie(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SelfieResponse:
    """Get current user's selfie."""
    selfie = await selfie_service.get_selfie_by_user_id(db, current_user.id)

    if not selfie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No selfie uploaded",
        )

    return SelfieResponse.model_validate(selfie)


@router.get("/selfie/status", response_model=SelfieStatusResponse)
async def get_selfie_status(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SelfieStatusResponse:
    """Check selfie status and readiness for verification."""
    selfie = await selfie_service.get_selfie_by_user_id(db, current_user.id)

    if not selfie:
        return SelfieStatusResponse(
            has_selfie=False,
            status=None,
            error_message=None,
            can_verify_passport=False,
        )

    can_verify = selfie.status == "processed" and selfie.face_embedding is not None

    return SelfieStatusResponse(
        has_selfie=True,
        status=selfie.status,
        error_message=selfie.error_message,
        can_verify_passport=can_verify,
    )


@router.delete("/selfie", status_code=status.HTTP_204_NO_CONTENT)
async def delete_selfie(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete current user's selfie."""
    selfie = await selfie_service.get_selfie_by_user_id(db, current_user.id)

    if not selfie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No selfie uploaded",
        )

    await selfie_service.delete_selfie(db, selfie)


@router.post("/upload", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
async def upload_verification_document(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    document_country: str = Form(..., max_length=100),
) -> VerificationResponse:
    """
    Upload a document for verification.

    Prerequisites:
    1. Complete payment (POST /payments/create-intent)
    2. Upload selfie first for passports (POST /verifications/selfie)

    For passport verification:
    1. Complete payment
    2. Upload selfie
    3. Upload passport
    4. System will attempt auto-verification

    If auto-verification succeeds, status will be 'approved'.
    If uncertain, status will be 'pending' for manual review.

    Accepted formats: JPEG, PNG, PDF
    Max file size: 10MB
    """
    # Check for valid payment
    payment = await payment_service.get_valid_payment_for_verification(
        db, current_user.id
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment required before uploading verification documents. "
            "Please complete payment at POST /api/v1/payments/create-intent",
        )

    # Validate file type
    is_valid, error_msg = verification_service.validate_file(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Validate file size
    is_valid, error_msg = await verification_service.validate_file_size(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Create verification with initial status
    verification = await verification_service.create_verification(
        db,
        current_user.id,
        document_type.value,
        document_country,
        file,
    )

    # Link payment to verification
    await payment_service.link_payment_to_verification(
        db, payment.id, verification.id
    )

    # Attempt auto-verification if enabled
    if settings.ENABLE_AUTO_VERIFICATION:
        # Set status to processing
        verification.status = "processing"
        await db.commit()

        # Run auto-verification
        try:
            logger.info(f"Starting auto-verification for {verification.id}")
            result = await auto_verification_service.process_verification_automatically(
                db, verification.id
            )
            logger.info(
                f"Auto-verification result for {verification.id}: "
                f"auto_verified={result.auto_verified}, "
                f"needs_manual_review={result.needs_manual_review}, "
                f"failure_reason={result.failure_reason}"
            )
        except Exception as e:
            logger.error(f"Auto-verification failed for {verification.id}: {e}", exc_info=True)
            # Set status back to pending for manual review
            verification.status = "pending"
            await db.commit()

        # Refresh verification to get updated status
        await db.refresh(verification)

    return VerificationResponse.model_validate(verification)


@router.get("/", response_model=VerificationListResponse)
async def list_my_verifications(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    verification_status: str | None = Query(
        None,
        alias="status",
        pattern="^(pending|processing|approved|rejected|expired|cancelled)$",
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> VerificationListResponse:
    """List current user's verifications."""
    verifications, total = await verification_service.get_user_verifications(
        db, current_user.id, verification_status, page, per_page
    )

    return VerificationListResponse(
        verifications=[VerificationResponse.model_validate(v) for v in verifications],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/status", response_model=VerificationStatusSummary)
async def get_verification_status(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerificationStatusSummary:
    """Get summary of verification status."""
    summary = await verification_service.get_verification_status_summary(
        db, current_user.id
    )
    return VerificationStatusSummary(**summary)


@router.get("/{verification_id}", response_model=VerificationResponse)
async def get_verification(
    verification_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerificationResponse:
    """Get a specific verification."""
    verification = await verification_service.get_verification_by_id(db, verification_id)

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found",
        )

    if verification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your verification",
        )

    return VerificationResponse.model_validate(verification)


@router.post("/{verification_id}/cancel", response_model=VerificationResponse)
async def cancel_verification(
    verification_id: UUID,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerificationResponse:
    """Cancel a pending verification."""
    verification = await verification_service.get_verification_by_id(db, verification_id)

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found",
        )

    if verification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your verification",
        )

    if verification.status not in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel verification with status: {verification.status}",
        )

    updated = await verification_service.cancel_verification(db, verification)
    return VerificationResponse.model_validate(updated)
