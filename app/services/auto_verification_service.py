"""Automated document verification service."""

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.profile import Profile
from app.models.selfie import Selfie
from app.models.user import User
from app.models.verification import Verification
from app.services import face_service, mrz_service, ocr_service

logger = logging.getLogger(__name__)


class AutoVerificationResult:
    """Result of automatic verification attempt."""

    def __init__(
        self,
        auto_verified: bool = False,
        confidence: float = 0.0,
        extracted_data: dict | None = None,
        failure_reason: str | None = None,
        needs_manual_review: bool = True,
        face_match_score: float | None = None,
    ):
        self.auto_verified = auto_verified
        self.confidence = confidence
        self.extracted_data = extracted_data
        self.failure_reason = failure_reason
        self.needs_manual_review = needs_manual_review
        self.face_match_score = face_match_score

    def to_dict(self) -> dict:
        return {
            "auto_verified": self.auto_verified,
            "confidence": self.confidence,
            "extracted_data": self.extracted_data,
            "failure_reason": self.failure_reason,
            "needs_manual_review": self.needs_manual_review,
            "face_match_score": self.face_match_score,
        }


async def process_verification_automatically(
    db: AsyncSession,
    verification_id: UUID,
) -> AutoVerificationResult:
    """
    Attempt to verify a document automatically.

    This is the main entry point for auto-verification.
    It will attempt to extract data and verify the document,
    then update the verification status accordingly.

    Args:
        db: Database session
        verification_id: ID of the verification to process

    Returns:
        AutoVerificationResult with details of the attempt
    """
    if not settings.ENABLE_AUTO_VERIFICATION:
        return AutoVerificationResult(
            failure_reason="Auto-verification is disabled",
            needs_manual_review=True,
        )

    # Get verification
    result = await db.execute(
        select(Verification).where(Verification.id == verification_id)
    )
    verification = result.scalar_one_or_none()

    if not verification:
        return AutoVerificationResult(failure_reason="Verification not found")

    if verification.status != "processing":
        return AutoVerificationResult(
            failure_reason=f"Verification status is {verification.status}, expected 'processing'"
        )

    if not verification.file_path or not Path(verification.file_path).exists():
        return AutoVerificationResult(failure_reason="Document file not found")

    # Route to appropriate processor based on document type
    if verification.document_type == "passport":
        return await _process_passport(db, verification)
    else:
        return await _process_other_document(db, verification)


async def _process_passport(
    db: AsyncSession,
    verification: Verification,
) -> AutoVerificationResult:
    """Process passport document with MRZ extraction and face comparison."""
    file_path = verification.file_path

    # Convert PDF to image if needed
    if file_path.lower().endswith(".pdf"):
        # For PDFs, extract text but require manual review
        text = ocr_service.extract_text_from_pdf(file_path)
        return AutoVerificationResult(
            failure_reason="PDF passports require manual review",
            needs_manual_review=True,
            extracted_data={"raw_text": text[:1000] if text else None},
        )

    # Step 1: Extract MRZ
    logger.info(f"Extracting MRZ from {file_path}")
    mrz_data = mrz_service.extract_mrz(file_path)

    if not mrz_data or not mrz_data.get("valid"):
        # MRZ not found or invalid - try OCR fallback
        logger.info("MRZ extraction failed, attempting OCR fallback")
        text = ocr_service.extract_text(file_path)

        return AutoVerificationResult(
            failure_reason="Could not extract valid MRZ from passport",
            needs_manual_review=True,
            extracted_data={
                "raw_text": text[:1000] if text else None,
                "mrz_data": mrz_data,
            },
        )

    logger.info(f"MRZ extracted successfully: {mrz_data.get('first_name')} {mrz_data.get('last_name')}")

    # Step 2: Get user's selfie
    selfie_result = await db.execute(
        select(Selfie).where(Selfie.user_id == verification.user_id)
    )
    selfie = selfie_result.scalar_one_or_none()

    if not selfie or not selfie.face_embedding:
        # No selfie uploaded yet
        return AutoVerificationResult(
            confidence=0.5,  # MRZ is valid but no face to compare
            extracted_data=_mrz_to_extracted_data(mrz_data),
            failure_reason="No selfie uploaded for face comparison",
            needs_manual_review=True,
        )

    # Step 3: Extract face from passport
    logger.info("Extracting face from passport")
    passport_face = face_service.extract_face(file_path)

    if passport_face is None:
        return AutoVerificationResult(
            confidence=0.5,
            extracted_data=_mrz_to_extracted_data(mrz_data),
            failure_reason="Could not detect face in passport photo",
            needs_manual_review=True,
        )

    # Step 4: Compare faces
    selfie_embedding = face_service.bytes_to_embedding(selfie.face_embedding)
    face_similarity = face_service.compare_faces(passport_face, selfie_embedding)

    logger.info(f"Face comparison score: {face_similarity:.3f}")

    extracted_data = _mrz_to_extracted_data(mrz_data)

    # Step 5: Make decision based on face match score
    if face_similarity >= settings.FACE_MATCH_AUTO_APPROVE_THRESHOLD:
        # High confidence - auto approve
        await _auto_approve_verification(db, verification, extracted_data, mrz_data)

        return AutoVerificationResult(
            auto_verified=True,
            confidence=face_similarity,
            extracted_data=extracted_data,
            needs_manual_review=False,
            face_match_score=face_similarity,
        )

    elif face_similarity <= settings.FACE_MATCH_AUTO_REJECT_THRESHOLD:
        # Low confidence - auto reject
        await _auto_reject_verification(
            db,
            verification,
            f"Face match score too low ({face_similarity:.2f}). Possible identity mismatch.",
        )

        return AutoVerificationResult(
            auto_verified=False,
            confidence=face_similarity,
            extracted_data=extracted_data,
            failure_reason=f"Face match score too low: {face_similarity:.2f}",
            needs_manual_review=False,
            face_match_score=face_similarity,
        )

    else:
        # Medium confidence - manual review
        verification.status = "pending"
        verification.extracted_data = extracted_data
        await db.commit()

        return AutoVerificationResult(
            auto_verified=False,
            confidence=face_similarity,
            extracted_data=extracted_data,
            failure_reason=f"Face match score uncertain ({face_similarity:.2f}), needs manual review",
            needs_manual_review=True,
            face_match_score=face_similarity,
        )


async def _process_other_document(
    db: AsyncSession,
    verification: Verification,
) -> AutoVerificationResult:
    """Process non-passport documents with OCR."""
    file_path = verification.file_path

    # Extract text
    if file_path.lower().endswith(".pdf"):
        text = ocr_service.extract_text_from_pdf(file_path)
    else:
        text = ocr_service.extract_text(file_path)

    if not text:
        return AutoVerificationResult(
            failure_reason="Could not extract text from document",
            needs_manual_review=True,
        )

    # Try to detect document type from text
    detected_type = ocr_service.detect_document_type(text)

    # Extract any dates and names found
    dates = ocr_service.extract_dates_from_text(text)
    names = ocr_service.extract_names_from_text(text)

    extracted_data = {
        "raw_text": text[:2000],  # Truncate for storage
        "detected_type": detected_type,
        "found_dates": dates[:5],  # First 5 dates
        "found_names": names,
    }

    # Update verification with extracted data but keep as pending
    verification.status = "pending"
    verification.extracted_data = extracted_data
    await db.commit()

    return AutoVerificationResult(
        confidence=0.3,  # Low confidence for non-passport docs
        extracted_data=extracted_data,
        failure_reason="Non-passport documents require manual review",
        needs_manual_review=True,
    )


def _mrz_to_extracted_data(mrz_data: dict) -> dict:
    """Convert MRZ data to the extracted_data format."""
    return {
        "first_name": mrz_data.get("first_name"),
        "last_name": mrz_data.get("last_name"),
        "birth_date": mrz_data.get("birth_date").isoformat() if mrz_data.get("birth_date") else None,
        "expiry_date": mrz_data.get("expiry_date").isoformat() if mrz_data.get("expiry_date") else None,
        "nationality": mrz_service.get_country_name(mrz_data.get("nationality", "")),
        "document_number": mrz_data.get("document_number"),
        "sex": mrz_data.get("sex"),
        "country": mrz_service.get_country_name(mrz_data.get("country", "")),
    }


async def _auto_approve_verification(
    db: AsyncSession,
    verification: Verification,
    extracted_data: dict,
    mrz_data: dict,
) -> None:
    """Auto-approve a verification and update profile."""
    from app.services.verification_service import _copy_data_to_profile

    now = datetime.now(timezone.utc)

    verification.status = "approved"
    verification.extracted_data = extracted_data
    verification.verification_method = "automated"
    verification.verified_at = now

    # Set document expiry date
    if mrz_data.get("expiry_date"):
        verification.document_expiry_date = mrz_data["expiry_date"]

    # Get user and profile
    user_result = await db.execute(
        select(User).where(User.id == verification.user_id)
    )
    user = user_result.scalar_one()

    profile_result = await db.execute(
        select(Profile).where(Profile.user_id == verification.user_id)
    )
    profile = profile_result.scalar_one_or_none()

    # Copy data to profile
    if profile:
        await _copy_data_to_profile(profile, verification.document_type, extracted_data)

    # Update user verification status
    user.verification_status = "verified"
    if mrz_data.get("expiry_date"):
        user.verification_expires_at = datetime.combine(
            mrz_data["expiry_date"],
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

    await db.commit()
    logger.info(f"Auto-approved verification {verification.id} for user {verification.user_id}")


async def _auto_reject_verification(
    db: AsyncSession,
    verification: Verification,
    reason: str,
) -> None:
    """Auto-reject a verification."""
    verification.status = "rejected"
    verification.rejection_reason = reason
    verification.verification_method = "automated"
    verification.verified_at = datetime.now(timezone.utc)

    await db.commit()
    logger.info(f"Auto-rejected verification {verification.id}: {reason}")


async def check_verification_prerequisites(
    db: AsyncSession,
    user_id: UUID,
    document_type: str,
) -> tuple[bool, str | None]:
    """
    Check if user meets prerequisites for auto-verification.

    Args:
        db: Database session
        user_id: User ID
        document_type: Type of document being verified

    Returns:
        (can_auto_verify, reason_if_not)
    """
    if document_type != "passport":
        return False, "Only passports support auto-verification"

    # Check if user has uploaded a selfie
    selfie_result = await db.execute(
        select(Selfie).where(Selfie.user_id == user_id)
    )
    selfie = selfie_result.scalar_one_or_none()

    if not selfie:
        return False, "Please upload a selfie first for identity verification"

    if not selfie.face_embedding:
        return False, "Selfie processing incomplete, please re-upload"

    if selfie.status != "processed":
        return False, f"Selfie status is {selfie.status}, expected 'processed'"

    return True, None
