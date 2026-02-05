"""Automated document verification service."""

import logging
import tempfile
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


def _get_local_path(url_path: str) -> str:
    """Convert URL path to local filesystem path."""
    # URL path is like /uploads/verifications/... -> ./uploads/verifications/...
    if url_path.startswith("/uploads"):
        return "." + url_path
    return url_path


def _convert_pdf_to_image(pdf_path: str) -> str | None:
    """
    Convert first page of PDF to a temporary image file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Path to temporary image file, or None if conversion failed
    """
    try:
        from pdf2image import convert_from_path

        if not Path(pdf_path).exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None

        # Convert first page of PDF to image at high DPI for better MRZ detection
        logger.info(f"Converting PDF to image: {pdf_path}")
        images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=1)

        if not images:
            logger.error("PDF conversion returned no images")
            return None

        # Save to a temporary file
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        images[0].save(tmp.name, "PNG")
        logger.info(f"PDF converted to image: {tmp.name}")
        return tmp.name

    except ImportError:
        logger.warning("pdf2image not installed, PDF conversion disabled")
        return None
    except Exception as e:
        logger.error(f"Error converting PDF to image: {e}")
        return None


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

    # Convert URL path to local path for file existence check
    local_file_path = _get_local_path(verification.file_path) if verification.file_path else None
    if not local_file_path or not Path(local_file_path).exists():
        logger.error(f"Document file not found: {verification.file_path} (local: {local_file_path})")
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
    file_path = _get_local_path(verification.file_path)
    temp_image_path = None

    # Convert PDF to image if needed
    if file_path.lower().endswith(".pdf"):
        logger.info(f"Processing PDF passport: {file_path}")
        temp_image_path = _convert_pdf_to_image(file_path)
        if temp_image_path is None:
            # Fallback to text extraction if PDF conversion fails
            text = ocr_service.extract_text_from_pdf(file_path)
            return AutoVerificationResult(
                failure_reason="Failed to convert PDF to image for processing",
                needs_manual_review=True,
                extracted_data={"raw_text": text[:1000] if text else None},
            )
        # Use the converted image for processing
        image_for_processing = temp_image_path
    else:
        image_for_processing = file_path

    try:
        # Step 1: Extract MRZ
        logger.info(f"Extracting MRZ from {image_for_processing}")
        mrz_data = mrz_service.extract_mrz(image_for_processing)

        if not mrz_data or not mrz_data.get("valid"):
            # MRZ not found or invalid - try OCR fallback
            logger.info("MRZ extraction failed, attempting OCR fallback")
            if temp_image_path:
                text = ocr_service.extract_text(temp_image_path)
            else:
                text = ocr_service.extract_text(file_path)

            extracted_data = {
                "raw_text": text[:1000] if text else None,
                "mrz_data": mrz_data,
            }
            # Save extracted data and set to pending for manual review
            verification.status = "pending"
            verification.extracted_data = extracted_data
            await db.commit()

            return AutoVerificationResult(
                failure_reason="Could not extract valid MRZ from passport",
                needs_manual_review=True,
                extracted_data=extracted_data,
            )

        logger.info(f"MRZ extracted successfully: {mrz_data.get('first_name')} {mrz_data.get('last_name')}")

        # Step 2: Get user's selfie
        selfie_result = await db.execute(
            select(Selfie).where(Selfie.user_id == verification.user_id)
        )
        selfie = selfie_result.scalar_one_or_none()

        if not selfie or not selfie.face_embedding:
            # No selfie uploaded yet - save extracted data for manual review
            extracted_data = _mrz_to_extracted_data(mrz_data)
            verification.status = "pending"
            verification.extracted_data = extracted_data
            await db.commit()

            return AutoVerificationResult(
                confidence=0.5,  # MRZ is valid but no face to compare
                extracted_data=extracted_data,
                failure_reason="No selfie uploaded for face comparison",
                needs_manual_review=True,
            )

        # Step 3: Extract face from passport (use the converted image for PDFs)
        logger.info("Extracting face from passport")
        passport_face = face_service.extract_face(image_for_processing)

        if passport_face is None:
            # Face not detected - save extracted data for manual review
            extracted_data = _mrz_to_extracted_data(mrz_data)
            verification.status = "pending"
            verification.extracted_data = extracted_data
            await db.commit()

            return AutoVerificationResult(
                confidence=0.5,
                extracted_data=extracted_data,
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
    finally:
        # Clean up temporary image file if created
        if temp_image_path:
            try:
                Path(temp_image_path).unlink(missing_ok=True)
                logger.info(f"Cleaned up temporary image: {temp_image_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_image_path}: {e}")


async def _process_other_document(
    db: AsyncSession,
    verification: Verification,
) -> AutoVerificationResult:
    """Process non-passport documents with OCR."""
    file_path = _get_local_path(verification.file_path)

    # Extract text
    if file_path.lower().endswith(".pdf"):
        text = ocr_service.extract_text_from_pdf(file_path)
    else:
        text = ocr_service.extract_text(file_path)

    if not text:
        # No text extracted - set to pending for manual review
        verification.status = "pending"
        await db.commit()

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
