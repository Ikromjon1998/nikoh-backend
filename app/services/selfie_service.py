"""Selfie upload and processing service."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.selfie import Selfie
from app.services import face_service

logger = logging.getLogger(__name__)

# File upload settings
UPLOAD_DIR = Path("./uploads/selfies")
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def upload_selfie(
    db: AsyncSession,
    user_id: UUID,
    file: UploadFile,
) -> Selfie:
    """
    Upload and process a selfie for a user.
    Extracts face embedding for later comparison.

    Args:
        db: Database session
        user_id: User ID
        file: Uploaded file

    Returns:
        Created or updated Selfie record
    """
    # Check if user already has a selfie
    result = await db.execute(select(Selfie).where(Selfie.user_id == user_id))
    existing_selfie = result.scalar_one_or_none()

    # Create upload directory
    upload_path = UPLOAD_DIR / str(user_id)
    upload_path.mkdir(parents=True, exist_ok=True)

    # Determine file extension
    ext = Path(file.filename).suffix if file.filename else ".jpg"
    file_path = upload_path / f"selfie{ext}"

    # Save file
    file_content = await file.read()
    file_size = len(file_content)

    with open(file_path, "wb") as f:
        f.write(file_content)

    if existing_selfie:
        # Update existing selfie
        selfie = existing_selfie
        # Delete old file if different path
        if selfie.file_path and selfie.file_path != str(file_path):
            old_path = Path(selfie.file_path)
            if old_path.exists():
                old_path.unlink()

        selfie.file_path = str(file_path)
        selfie.original_filename = file.filename
        selfie.mime_type = file.content_type
        selfie.file_size = file_size
        selfie.status = "pending"
        selfie.error_message = None
        selfie.face_embedding = None
        selfie.processed_at = None
    else:
        # Create new selfie
        selfie = Selfie(
            user_id=user_id,
            file_path=str(file_path),
            original_filename=file.filename,
            mime_type=file.content_type,
            file_size=file_size,
            status="pending",
        )
        db.add(selfie)

    await db.flush()

    # Process the selfie (extract face embedding)
    await _process_selfie(selfie)

    await db.commit()
    await db.refresh(selfie)

    return selfie


async def _process_selfie(selfie: Selfie) -> None:
    """
    Process selfie to extract face embedding.
    Updates the selfie record in place.
    """
    if not selfie.file_path or not Path(selfie.file_path).exists():
        selfie.status = "failed"
        selfie.error_message = "File not found"
        return

    try:
        # Check if face service is available
        if not face_service.is_face_service_available():
            selfie.status = "failed"
            selfie.error_message = "Face recognition service not available"
            return

        # Extract face embedding
        embedding = face_service.extract_face(selfie.file_path)

        if embedding is None:
            selfie.status = "failed"
            selfie.error_message = "No face detected in image"
            return

        # Check face count
        face_count = face_service.detect_faces_count(selfie.file_path)
        if face_count > 1:
            selfie.status = "failed"
            selfie.error_message = "Multiple faces detected, please upload a photo with only your face"
            return

        # Check face quality
        quality = face_service.get_face_quality_score(selfie.file_path)
        if quality < 0.3:
            selfie.status = "failed"
            selfie.error_message = "Face quality too low, please upload a clearer photo"
            return

        # Store embedding
        selfie.face_embedding = face_service.embedding_to_bytes(embedding)
        selfie.status = "processed"
        selfie.processed_at = datetime.now(timezone.utc)
        selfie.error_message = None

        logger.info(f"Selfie processed successfully for user {selfie.user_id}")

    except Exception as e:
        logger.error(f"Error processing selfie: {e}")
        selfie.status = "failed"
        selfie.error_message = f"Processing error: {str(e)}"


async def get_selfie_by_user_id(
    db: AsyncSession,
    user_id: UUID,
) -> Selfie | None:
    """Get selfie by user ID."""
    result = await db.execute(select(Selfie).where(Selfie.user_id == user_id))
    return result.scalar_one_or_none()


async def delete_selfie(
    db: AsyncSession,
    selfie: Selfie,
) -> None:
    """Delete a selfie and its file."""
    if selfie.file_path:
        file_path = Path(selfie.file_path)
        if file_path.exists():
            file_path.unlink()
        # Try to remove parent directory if empty
        try:
            file_path.parent.rmdir()
        except OSError:
            pass

    await db.delete(selfie)
    await db.commit()


def validate_selfie_file(file: UploadFile) -> tuple[bool, str]:
    """
    Validate selfie file type.

    Returns:
        (is_valid, error_message)
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        return False, "Invalid file type. Please upload a JPEG or PNG image."
    return True, ""


async def validate_selfie_file_size(file: UploadFile) -> tuple[bool, str]:
    """
    Validate selfie file size.

    Returns:
        (is_valid, error_message)
    """
    content = await file.read()
    await file.seek(0)

    if len(content) > MAX_FILE_SIZE:
        return False, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"
    return True, ""


async def reprocess_selfie(
    db: AsyncSession,
    selfie: Selfie,
) -> Selfie:
    """
    Reprocess an existing selfie (useful if face service was unavailable before).
    """
    selfie.status = "pending"
    selfie.error_message = None

    await _process_selfie(selfie)

    await db.commit()
    await db.refresh(selfie)

    return selfie
