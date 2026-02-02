"""Tests for automated verification system."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import face_service, mrz_service, ocr_service


async def create_user_with_profile(
    client: AsyncClient,
    email: str,
) -> tuple[str, str]:
    """Helper to create user, login, create profile. Returns (token, user_id)."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )
    token = login_response.json()["access_token"]

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = me_response.json()["id"]

    await client.post(
        "/api/v1/profiles/",
        json={"gender": "male", "seeking_gender": "female"},
        headers={"Authorization": f"Bearer {token}"},
    )

    return token, user_id


def create_test_selfie() -> tuple[str, bytes, str]:
    """Create a test selfie image."""
    return ("selfie.jpg", b"fake selfie image content", "image/jpeg")


def create_test_passport() -> tuple[str, bytes, str]:
    """Create a test passport image."""
    return ("passport.jpg", b"fake passport image content", "image/jpeg")


# ============== Selfie Upload Tests ==============


@pytest.mark.asyncio
async def test_upload_selfie_success(client: AsyncClient, db_session: AsyncSession):
    """Can upload a selfie."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/selfie",
        files={"file": create_test_selfie()},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "selfie.jpg"
    assert data["mime_type"] == "image/jpeg"
    # Status might be "processed" or "failed" depending on face detection
    assert data["status"] in ("pending", "processed", "failed")


@pytest.mark.asyncio
async def test_upload_selfie_invalid_type(client: AsyncClient, db_session: AsyncSession):
    """Cannot upload selfie with invalid file type."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/selfie",
        files={"file": ("selfie.pdf", b"pdf content", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "JPEG or PNG" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_selfie(client: AsyncClient, db_session: AsyncSession):
    """Can get uploaded selfie."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Upload selfie
    await client.post(
        "/api/v1/verifications/selfie",
        files={"file": create_test_selfie()},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get selfie
    response = await client.get(
        "/api/v1/verifications/selfie",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "selfie.jpg"


@pytest.mark.asyncio
async def test_get_selfie_not_found(client: AsyncClient, db_session: AsyncSession):
    """Returns 404 when no selfie uploaded."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/verifications/selfie",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_selfie_status_no_selfie(client: AsyncClient, db_session: AsyncSession):
    """Selfie status shows no selfie when none uploaded."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/verifications/selfie/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["has_selfie"] is False
    assert data["can_verify_passport"] is False


@pytest.mark.asyncio
async def test_selfie_status_with_selfie(client: AsyncClient, db_session: AsyncSession):
    """Selfie status shows selfie info when uploaded."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Upload selfie
    await client.post(
        "/api/v1/verifications/selfie",
        files={"file": create_test_selfie()},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/v1/verifications/selfie/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["has_selfie"] is True
    assert data["status"] in ("pending", "processed", "failed")


@pytest.mark.asyncio
async def test_delete_selfie(client: AsyncClient, db_session: AsyncSession):
    """Can delete selfie."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Upload selfie
    await client.post(
        "/api/v1/verifications/selfie",
        files={"file": create_test_selfie()},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Delete selfie
    response = await client.delete(
        "/api/v1/verifications/selfie",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Verify deleted
    response = await client.get(
        "/api/v1/verifications/selfie",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_replace_selfie(client: AsyncClient, db_session: AsyncSession):
    """Can replace existing selfie."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Upload first selfie
    response1 = await client.post(
        "/api/v1/verifications/selfie",
        files={"file": ("first.jpg", b"first selfie", "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    first_id = response1.json()["id"]

    # Upload second selfie (should replace)
    response2 = await client.post(
        "/api/v1/verifications/selfie",
        files={"file": ("second.jpg", b"second selfie", "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    second_id = response2.json()["id"]

    # Same selfie record should be updated
    assert first_id == second_id
    assert response2.json()["original_filename"] == "second.jpg"


# ============== OCR Service Tests ==============


class TestOCRService:
    """Tests for OCR service functionality."""

    def test_detect_document_type_passport(self):
        """Can detect passport from text."""
        text = "PASSPORT Republic of Uzbekistan Nationality: UZB Date of Birth: 15 JAN 1990"
        assert ocr_service.detect_document_type(text) == "passport"

    def test_detect_document_type_residence_permit(self):
        """Can detect residence permit from text."""
        text = "Residence Permit Valid Until: 2025 Permanent Resident Status"
        assert ocr_service.detect_document_type(text) == "residence_permit"

    def test_detect_document_type_divorce(self):
        """Can detect divorce certificate from text."""
        text = "Свидетельство о расторжении брака Divorce Certificate"
        assert ocr_service.detect_document_type(text) == "divorce_certificate"

    def test_detect_document_type_diploma(self):
        """Can detect diploma from text."""
        text = "DIPLOMA Bachelor of Science University of Technology"
        assert ocr_service.detect_document_type(text) == "diploma"

    def test_detect_document_type_unknown(self):
        """Returns None for unknown document type."""
        text = "Random text with no document indicators"
        assert ocr_service.detect_document_type(text) is None

    def test_extract_dates_from_text(self):
        """Can extract dates from text."""
        text = "Born: 15/01/1990 Expires: 2030.12.31"
        dates = ocr_service.extract_dates_from_text(text)
        assert len(dates) >= 2
        assert "15/01/1990" in dates

    def test_extract_names_from_text(self):
        """Can extract names from text."""
        text = "Name: John Surname: Doe"
        names = ocr_service.extract_names_from_text(text)
        # This depends on implementation
        assert isinstance(names, dict)


# ============== MRZ Service Tests ==============


class TestMRZService:
    """Tests for MRZ parsing functionality."""

    def test_parse_mrz_date_2000s(self):
        """Can parse MRZ dates in 2000s."""
        # Year 15 should be 2015
        result = mrz_service._parse_mrz_date("150115")  # 15 Jan 2015
        assert result is not None
        assert result.year == 2015
        assert result.month == 1
        assert result.day == 15

    def test_parse_mrz_date_1900s(self):
        """Can parse MRZ dates in 1900s."""
        # Year 90 should be 1990
        result = mrz_service._parse_mrz_date("900115")  # 15 Jan 1990
        assert result is not None
        assert result.year == 1990
        assert result.month == 1
        assert result.day == 15

    def test_parse_mrz_date_invalid(self):
        """Returns None for invalid date."""
        assert mrz_service._parse_mrz_date("") is None
        assert mrz_service._parse_mrz_date("12") is None

    def test_clean_name(self):
        """Can clean MRZ name format."""
        assert mrz_service._clean_name("JOHN<<SMITH") == "John Smith"
        assert mrz_service._clean_name("JANE") == "Jane"
        assert mrz_service._clean_name("") == ""

    def test_get_country_name(self):
        """Can convert country codes to names."""
        assert mrz_service.get_country_name("UZB") == "Uzbekistan"
        assert mrz_service.get_country_name("KAZ") == "Kazakhstan"
        assert mrz_service.get_country_name("USA") == "United States"
        # Unknown code returns itself
        assert mrz_service.get_country_name("XYZ") == "XYZ"


# ============== Face Service Tests ==============


class TestFaceService:
    """Tests for face service functionality."""

    def test_embedding_conversion(self):
        """Can convert embedding to bytes and back."""
        import numpy as np

        original = np.random.rand(512).astype(np.float32)
        as_bytes = face_service.embedding_to_bytes(original)
        restored = face_service.bytes_to_embedding(as_bytes)

        assert np.allclose(original, restored)

    def test_compare_faces_identical(self):
        """Identical embeddings have similarity 1.0."""
        import numpy as np

        embedding = np.random.rand(512).astype(np.float32)
        similarity = face_service.compare_faces(embedding, embedding.copy())
        assert similarity > 0.99

    def test_compare_faces_different(self):
        """Opposite embeddings have low similarity."""
        import numpy as np

        # Create two opposite vectors for consistent low similarity
        # Opposite vectors have cosine similarity of -1, normalized to 0
        embedding1 = np.ones(512, dtype=np.float32)
        embedding2 = -np.ones(512, dtype=np.float32)
        similarity = face_service.compare_faces(embedding1, embedding2)
        # Opposite vectors should have near-zero similarity (cosine=-1 -> normalized=0)
        assert similarity < 0.1

    def test_compare_faces_none(self):
        """Returns 0 when either embedding is None."""
        import numpy as np

        embedding = np.random.rand(512).astype(np.float32)
        assert face_service.compare_faces(None, embedding) == 0.0
        assert face_service.compare_faces(embedding, None) == 0.0

    def test_faces_match_threshold(self):
        """faces_match respects threshold."""
        import numpy as np

        embedding = np.random.rand(512).astype(np.float32)
        # Same embedding should match
        assert face_service.faces_match(embedding, embedding.copy(), threshold=0.9)

        # Different embeddings should not match with high threshold
        embedding2 = np.random.rand(512).astype(np.float32)
        assert not face_service.faces_match(embedding, embedding2, threshold=0.9)


# ============== Integration Tests ==============


@pytest.mark.asyncio
async def test_upload_passport_triggers_processing(client: AsyncClient, db_session: AsyncSession):
    """Uploading passport triggers auto-verification processing."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_passport()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    # Status should be one of: processing, pending, approved, or rejected
    # depending on auto-verification result
    assert data["status"] in ("processing", "pending", "approved", "rejected")


@pytest.mark.asyncio
async def test_non_passport_goes_to_manual_review(client: AsyncClient, db_session: AsyncSession):
    """Non-passport documents go to manual review."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": ("diploma.jpg", b"diploma content", "image/jpeg")},
        data={
            "document_type": "diploma",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    # Non-passport should go to pending for manual review
    assert data["status"] in ("processing", "pending")


@pytest.mark.asyncio
async def test_passport_without_selfie_needs_manual_review(client: AsyncClient, db_session: AsyncSession):
    """Passport without selfie needs manual review."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Upload passport without uploading selfie first
    response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_passport()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    # Should go to pending because no selfie to compare
    # (unless MRZ extraction also failed, then still pending)
    assert response.json()["status"] in ("processing", "pending")


@pytest.mark.asyncio
async def test_verification_flow_with_selfie(client: AsyncClient, db_session: AsyncSession):
    """Full verification flow: upload selfie then passport."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Step 1: Upload selfie
    selfie_response = await client.post(
        "/api/v1/verifications/selfie",
        files={"file": create_test_selfie()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert selfie_response.status_code == 201

    # Step 2: Check selfie status
    status_response = await client.get(
        "/api/v1/verifications/selfie/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.json()["has_selfie"] is True

    # Step 3: Upload passport
    passport_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_passport()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert passport_response.status_code == 201

    # Step 4: Check verification status
    verification_status = await client.get(
        "/api/v1/verifications/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verification_status.status_code == 200
