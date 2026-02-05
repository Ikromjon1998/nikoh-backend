from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.config import settings
from app.database import check_db_connection, get_db
from app.models.report import Report
from app.models.user import User
from app.models.verification import Verification
from app.schemas.report import (
    ReportAdminListResponse,
    ReportAdminResponse,
    ReportReview,
)
from app.schemas.user import (
    AdminDashboardResponse,
    AdminDashboardStats,
    SystemHealthStatus,
    UserAdminListResponse,
    UserAdminResponse,
    UserBan,
    UserResponse,
    UserUnban,
)
from app.schemas.verification import (
    VerificationAdminListResponse,
    VerificationAdminResponse,
    VerificationApprove,
    VerificationReject,
)
from app.services import auto_verification_service, verification_service

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


# ==================== Dashboard Stats Endpoints ====================


@router.get("/stats", response_model=AdminDashboardResponse)
async def get_dashboard_stats(
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDashboardResponse:
    """Get admin dashboard statistics (admin only)."""
    # Count total users (excluding admins)
    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_admin == False)
    )
    total_users = total_users_result.scalar() or 0

    # Count verified users (excluding admins)
    verified_users_result = await db.execute(
        select(func.count(User.id)).where(
            User.is_admin == False,
            User.verification_status == "verified",
        )
    )
    verified_users = verified_users_result.scalar() or 0

    # Count pending verifications (pending, processing, or manual_review)
    pending_verifications_result = await db.execute(
        select(func.count(Verification.id)).where(
            Verification.status.in_(["pending", "processing", "manual_review"])
        )
    )
    pending_verifications = pending_verifications_result.scalar() or 0

    # Count open reports (pending status)
    open_reports_result = await db.execute(
        select(func.count(Report.id)).where(Report.status == "pending")
    )
    open_reports = open_reports_result.scalar() or 0

    # Check system status
    db_connected = await check_db_connection()

    stats = AdminDashboardStats(
        total_users=total_users,
        verified_users=verified_users,
        pending_verifications=pending_verifications,
        open_reports=open_reports,
    )

    system_status = SystemHealthStatus(
        database="connected" if db_connected else "disconnected",
        payment_system="online" if settings.STRIPE_SECRET_KEY else "offline",
        auto_verification="enabled" if settings.ENABLE_AUTO_VERIFICATION else "disabled",
    )

    return AdminDashboardResponse(stats=stats, system_status=system_status)


# ==================== Verification Management Endpoints ====================


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


@router.post("/verifications/{verification_id}/run-ocr", response_model=VerificationAdminResponse)
async def run_ocr_on_verification(
    verification_id: UUID,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerificationAdminResponse:
    """
    Manually run OCR extraction on a verification document (admin only).

    This is useful when:
    - The initial auto-verification failed or didn't run
    - The document needs re-processing
    - Extracted data is missing or incomplete

    Returns the verification with updated extracted_data.
    """
    from pathlib import Path

    from app.services import mrz_service, ocr_service

    verification = await verification_service.get_verification_by_id(db, verification_id)

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found",
        )

    if not verification.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file associated with this verification",
        )

    # Convert URL path to local path
    local_path = verification.file_path
    if local_path.startswith("/uploads"):
        local_path = "." + local_path

    if not Path(local_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file not found: {verification.file_path}",
        )

    # Run OCR based on document type
    extracted_data = {}

    if verification.document_type == "passport":
        # Try MRZ extraction first
        if local_path.lower().endswith(".pdf"):
            # Convert PDF to image for MRZ
            temp_image = auto_verification_service._convert_pdf_to_image(local_path)
            if temp_image:
                mrz_data = mrz_service.extract_mrz(temp_image)
                Path(temp_image).unlink(missing_ok=True)
            else:
                mrz_data = None
        else:
            mrz_data = mrz_service.extract_mrz(local_path)

        if mrz_data and mrz_data.get("valid"):
            # Use MRZ data
            extracted_data = auto_verification_service._mrz_to_extracted_data(mrz_data)
        else:
            # Fallback to OCR
            if local_path.lower().endswith(".pdf"):
                text = ocr_service.extract_text_from_pdf(local_path)
            else:
                text = ocr_service.extract_text(local_path)

            dates = ocr_service.extract_dates_from_text(text) if text else []
            names = ocr_service.extract_names_from_text(text) if text else {}

            extracted_data = {
                "raw_text": text[:2000] if text else None,
                "found_dates": dates[:5],
                "found_names": names,
                "mrz_data": mrz_data,
            }
    else:
        # Non-passport documents: use OCR
        if local_path.lower().endswith(".pdf"):
            text = ocr_service.extract_text_from_pdf(local_path)
        else:
            text = ocr_service.extract_text(local_path)

        detected_type = ocr_service.detect_document_type(text) if text else None
        dates = ocr_service.extract_dates_from_text(text) if text else []
        names = ocr_service.extract_names_from_text(text) if text else {}

        extracted_data = {
            "raw_text": text[:2000] if text else None,
            "detected_type": detected_type,
            "found_dates": dates[:5],
            "found_names": names,
        }

    # Update verification with extracted data
    verification.extracted_data = extracted_data
    await db.commit()
    await db.refresh(verification)

    return VerificationAdminResponse.model_validate(verification)


# ==================== User Management Endpoints ====================


@router.get("/users", response_model=UserAdminListResponse)
async def list_users(
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Search by email"),
    filter: str | None = Query(None, description="Filter: verified, unverified, suspended, banned"),
) -> UserAdminListResponse:
    """List all users with optional search and filter (admin only)."""
    query = select(User).where(User.is_admin == False)  # Exclude admin users

    # Apply search filter
    if search:
        query = query.where(
            or_(
                User.email.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
            )
        )

    # Apply status/verification filter
    if filter == "verified":
        query = query.where(User.verification_status == "verified")
    elif filter == "unverified":
        query = query.where(User.verification_status == "unverified")
    elif filter == "suspended":
        query = query.where(User.status == "suspended")
    elif filter == "banned":
        query = query.where(User.status == "banned")

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * per_page
    query = query.order_by(User.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    users = list(result.scalars().all())

    return UserAdminListResponse(
        users=[UserAdminResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/users/{user_id}", response_model=UserAdminResponse)
async def get_user_admin(
    user_id: UUID,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserAdminResponse:
    """Get user details (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserAdminResponse.model_validate(user)


@router.post("/users/{user_id}/ban", response_model=UserAdminResponse)
async def ban_user(
    user_id: UUID,
    ban_data: UserBan,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserAdminResponse:
    """Ban a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ban admin users",
        )

    if user.status == "banned":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already banned",
        )

    user.status = "suspended"
    await db.commit()
    await db.refresh(user)

    return UserAdminResponse.model_validate(user)


@router.post("/users/{user_id}/unban", response_model=UserAdminResponse)
async def unban_user(
    user_id: UUID,
    unban_data: UserUnban,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserAdminResponse:
    """Unban a user (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.status not in ("suspended", "banned"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not suspended or banned",
        )

    user.status = "active"
    await db.commit()
    await db.refresh(user)

    return UserAdminResponse.model_validate(user)


# ==================== Reports Management Endpoints ====================


@router.get("/reports", response_model=ReportAdminListResponse)
async def list_reports(
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status", description="Filter: pending, reviewed, dismissed, action_taken"),
) -> ReportAdminListResponse:
    """List all user reports (admin only)."""
    from datetime import timezone

    query = select(Report)

    # Apply status filter
    if status_filter:
        query = query.where(Report.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering (pending first, then by date)
    offset = (page - 1) * per_page
    query = query.order_by(
        # Pending reports first
        (Report.status != "pending"),
        Report.created_at.desc()
    ).offset(offset).limit(per_page)

    result = await db.execute(query)
    reports = list(result.scalars().all())

    # Fetch user emails for each report
    report_responses = []
    for report in reports:
        # Get reported user email
        reported_user_result = await db.execute(
            select(User.email).where(User.id == report.reported_user_id)
        )
        reported_email = reported_user_result.scalar_one_or_none()

        # Get reporter user email
        reporter_user_result = await db.execute(
            select(User.email).where(User.id == report.reporter_user_id)
        )
        reporter_email = reporter_user_result.scalar_one_or_none()

        report_data = ReportAdminResponse.model_validate(report)
        report_data.reported_user_email = reported_email
        report_data.reporter_user_email = reporter_email
        report_responses.append(report_data)

    return ReportAdminListResponse(
        reports=report_responses,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/reports/{report_id}", response_model=ReportAdminResponse)
async def get_report_admin(
    report_id: UUID,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportAdminResponse:
    """Get report details (admin only)."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Get user emails
    reported_user_result = await db.execute(
        select(User.email).where(User.id == report.reported_user_id)
    )
    reported_email = reported_user_result.scalar_one_or_none()

    reporter_user_result = await db.execute(
        select(User.email).where(User.id == report.reporter_user_id)
    )
    reporter_email = reporter_user_result.scalar_one_or_none()

    report_data = ReportAdminResponse.model_validate(report)
    report_data.reported_user_email = reported_email
    report_data.reporter_user_email = reporter_email

    return report_data


@router.post("/reports/{report_id}/review", response_model=ReportAdminResponse)
async def review_report(
    report_id: UUID,
    review_data: ReportReview,
    admin_user: Annotated[UserResponse, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportAdminResponse:
    """Review a report and optionally suspend the reported user (admin only)."""
    from datetime import datetime, timezone

    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Update report
    report.status = review_data.status.value
    report.admin_notes = review_data.admin_notes
    report.reviewed_by = admin_user.id
    report.reviewed_at = datetime.now(timezone.utc)

    # Optionally suspend the reported user
    if review_data.suspend_user:
        user_result = await db.execute(
            select(User).where(User.id == report.reported_user_id)
        )
        reported_user = user_result.scalar_one_or_none()

        if reported_user and not reported_user.is_admin:
            reported_user.status = "suspended"

    await db.commit()
    await db.refresh(report)

    # Get user emails for response
    reported_user_result = await db.execute(
        select(User.email).where(User.id == report.reported_user_id)
    )
    reported_email = reported_user_result.scalar_one_or_none()

    reporter_user_result = await db.execute(
        select(User.email).where(User.id == report.reporter_user_id)
    )
    reporter_email = reporter_user_result.scalar_one_or_none()

    report_data = ReportAdminResponse.model_validate(report)
    report_data.reported_user_email = reported_email
    report_data.reporter_user_email = reporter_email

    return report_data
