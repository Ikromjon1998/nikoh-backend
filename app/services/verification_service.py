import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.models.user import User
from app.models.verification import Verification
from app.schemas.verification import DocumentType, VerificationApprove

# File upload settings
UPLOAD_DIR = Path("./uploads/verifications")
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Required documents for full verification
REQUIRED_DOCUMENTS = [DocumentType.passport]


async def create_verification(
    db: AsyncSession,
    user_id: UUID,
    document_type: str,
    document_country: str,
    file: UploadFile,
) -> Verification:
    """Create a new verification with uploaded file."""
    # Create verification record first to get ID
    verification = Verification(
        user_id=user_id,
        document_type=document_type,
        document_country=document_country,
        status="pending",
        original_filename=file.filename,
        mime_type=file.content_type,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(verification)
    await db.flush()  # Get the ID

    # Create upload directory
    upload_path = UPLOAD_DIR / str(user_id) / str(verification.id)
    upload_path.mkdir(parents=True, exist_ok=True)

    # Determine file extension
    ext = Path(file.filename).suffix if file.filename else ".bin"
    file_path = upload_path / f"document{ext}"

    # Save file
    file_content = await file.read()
    verification.file_size = len(file_content)

    with open(file_path, "wb") as f:
        f.write(file_content)

    # Store URL path for static file serving (remove leading ./)
    verification.file_path = "/" + str(file_path).lstrip("./")

    await db.commit()
    await db.refresh(verification)
    return verification


async def get_verification_by_id(
    db: AsyncSession,
    verification_id: UUID,
) -> Verification | None:
    """Get verification by ID."""
    result = await db.execute(
        select(Verification).where(Verification.id == verification_id)
    )
    return result.scalar_one_or_none()


async def get_user_verifications(
    db: AsyncSession,
    user_id: UUID,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Verification], int]:
    """Get all verifications for a user."""
    query = select(Verification).where(Verification.user_id == user_id)

    if status:
        query = query.where(Verification.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * per_page
    query = query.order_by(Verification.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    verifications = list(result.scalars().all())

    return verifications, total


async def get_pending_verifications(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Verification], int]:
    """Get all verifications awaiting admin review (for admin)."""
    # Include pending, processing (auto-verification running), and manual_review statuses
    reviewable_statuses = ("pending", "processing", "manual_review")
    query = select(Verification).where(Verification.status.in_(reviewable_statuses))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering (newest first)
    offset = (page - 1) * per_page
    query = query.order_by(Verification.submitted_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    verifications = list(result.scalars().all())

    return verifications, total


async def cancel_verification(
    db: AsyncSession,
    verification: Verification,
) -> Verification:
    """Cancel a pending verification."""
    verification.status = "cancelled"
    await db.commit()
    await db.refresh(verification)
    return verification


async def approve_verification(
    db: AsyncSession,
    verification: Verification,
    admin_user_id: UUID,
    approval_data: VerificationApprove,
) -> Verification:
    """Approve a verification and copy data to profile."""
    now = datetime.now(timezone.utc)

    verification.status = "approved"
    verification.extracted_data = approval_data.extracted_data
    verification.document_expiry_date = approval_data.document_expiry_date
    verification.verification_method = "manual"
    verification.verified_by = admin_user_id
    verification.verified_at = now

    # Get user and profile
    user_result = await db.execute(
        select(User).where(User.id == verification.user_id)
    )
    user = user_result.scalar_one()

    profile_result = await db.execute(
        select(Profile).where(Profile.user_id == verification.user_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Copy extracted data to profile based on document type
    if profile:
        await _copy_data_to_profile(
            profile,
            verification.document_type,
            approval_data.extracted_data,
        )

    # Update user verification status
    user.verification_status = "verified"
    if approval_data.document_expiry_date:
        # Convert date to datetime for the user field
        user.verification_expires_at = datetime.combine(
            approval_data.document_expiry_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

    await db.commit()
    await db.refresh(verification)
    return verification


async def _copy_data_to_profile(
    profile: Profile,
    document_type: str,
    extracted_data: dict,
) -> None:
    """Copy extracted data from verification to profile based on document type."""
    if document_type == DocumentType.passport.value:
        if "first_name" in extracted_data:
            profile.verified_first_name = extracted_data["first_name"]
        if "last_name" in extracted_data:
            profile.verified_last_initial = extracted_data["last_name"][0] if extracted_data["last_name"] else None
        if "birth_date" in extracted_data:
            birth_date = extracted_data["birth_date"]
            if isinstance(birth_date, str):
                profile.verified_birth_date = date.fromisoformat(birth_date)
            else:
                profile.verified_birth_date = birth_date
        if "birth_place" in extracted_data:
            # Parse birth place into country and city if possible
            birth_place = extracted_data["birth_place"]
            profile.verified_birthplace_city = birth_place
        if "nationality" in extracted_data:
            profile.verified_nationality = extracted_data["nationality"]

    elif document_type == DocumentType.residence_permit.value:
        if "country" in extracted_data:
            profile.verified_residence_country = extracted_data["country"]
        if "status" in extracted_data:
            profile.verified_residence_status = extracted_data["status"]

    elif document_type == DocumentType.divorce_certificate.value:
        profile.verified_marital_status = "divorced_once"

    elif document_type == DocumentType.diploma.value:
        if "degree" in extracted_data:
            profile.verified_education_level = extracted_data["degree"]


async def reject_verification(
    db: AsyncSession,
    verification: Verification,
    admin_user_id: UUID,
    reason: str,
) -> Verification:
    """Reject a verification with reason."""
    verification.status = "rejected"
    verification.rejection_reason = reason
    verification.verification_method = "manual"
    verification.verified_by = admin_user_id
    verification.verified_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(verification)
    return verification


async def get_verification_status_summary(
    db: AsyncSession,
    user_id: UUID,
) -> dict:
    """Get summary of user's verification status."""
    from app.services import payment_service

    # Get user
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()

    # Get all verifications
    result = await db.execute(
        select(Verification).where(Verification.user_id == user_id)
    )
    verifications = list(result.scalars().all())

    # Check for valid payment
    payment = await payment_service.get_valid_payment_for_verification(db, user_id)
    has_valid_payment = payment is not None

    # Categorize verifications
    verified_documents = []
    pending_documents = []

    for v in verifications:
        if v.status == "approved":
            verified_documents.append(v.document_type)
        elif v.status == "pending":
            pending_documents.append(v.document_type)

    # Determine missing required documents
    missing_required = []
    for doc_type in REQUIRED_DOCUMENTS:
        if doc_type.value not in verified_documents and doc_type.value not in pending_documents:
            missing_required.append(doc_type.value)

    # Determine overall status
    if len(verified_documents) == 0:
        overall_status = "unverified"
    elif len(missing_required) == 0:
        overall_status = "verified"
    else:
        overall_status = "partial"

    return {
        "overall_status": overall_status,
        "verified_documents": verified_documents,
        "pending_documents": pending_documents,
        "missing_required_documents": missing_required,
        "verification_expires_at": user.verification_expires_at,
        "has_valid_payment": has_valid_payment,
        "approved_verifications": len(verified_documents),
        "document_types_verified": verified_documents,
    }


def validate_file(file: UploadFile) -> tuple[bool, str]:
    """Validate uploaded file. Returns (is_valid, error_message)."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        return False, f"Invalid file type. Allowed types: JPEG, PNG, PDF"

    return True, ""


async def validate_file_size(file: UploadFile) -> tuple[bool, str]:
    """Validate file size. Returns (is_valid, error_message)."""
    # Read file to check size
    content = await file.read()
    await file.seek(0)  # Reset file position

    if len(content) > MAX_FILE_SIZE:
        return False, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"

    return True, ""


def _get_local_path(url_path: str) -> str:
    """Convert URL path to local filesystem path."""
    if url_path.startswith("/uploads"):
        return "." + url_path
    return url_path


async def delete_verification_file(verification: Verification) -> None:
    """Delete verification file from filesystem."""
    local_path = _get_local_path(verification.file_path) if verification.file_path else None
    if local_path and os.path.exists(local_path):
        os.remove(local_path)
        # Try to remove parent directories if empty
        parent_dir = Path(local_path).parent
        try:
            parent_dir.rmdir()
            parent_dir.parent.rmdir()
        except OSError:
            pass  # Directory not empty, that's ok
