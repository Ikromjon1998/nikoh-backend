import io
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


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


async def make_user_admin(db: AsyncSession, user_id: str) -> None:
    """Make a user an admin."""
    await db.execute(
        update(User).where(User.id == UUID(user_id)).values(is_admin=True)
    )
    await db.commit()


def create_test_file(content: bytes = b"test content", filename: str = "test.jpg") -> tuple[str, bytes, str]:
    """Create a test file tuple for upload."""
    return (filename, content, "image/jpeg")


def create_large_file() -> tuple[str, bytes, str]:
    """Create a file larger than 10MB."""
    content = b"x" * (11 * 1024 * 1024)  # 11MB
    return ("large.jpg", content, "image/jpeg")


def create_invalid_type_file() -> tuple[str, bytes, str]:
    """Create a file with invalid type."""
    return ("test.exe", b"test content", "application/octet-stream")


@pytest.mark.asyncio
async def test_upload_verification_document(client: AsyncClient, db_session: AsyncSession):
    """Can upload a valid document for verification."""
    token, user_id = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == "passport"
    assert data["document_country"] == "Uzbekistan"
    # Status can be "pending" or "processing" depending on auto-verification
    assert data["status"] in ("pending", "processing")
    assert data["original_filename"] == "test.jpg"
    assert data["mime_type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_upload_invalid_file_type(client: AsyncClient, db_session: AsyncSession):
    """Cannot upload file with invalid type."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_invalid_type_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_file_too_large(client: AsyncClient, db_session: AsyncSession):
    """Cannot upload file larger than 10MB."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_large_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_verifications(client: AsyncClient, db_session: AsyncSession):
    """Can list user's verifications."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Upload multiple documents
    for doc_type in ["passport", "residence_permit"]:
        await client.post(
            "/api/v1/verifications/upload",
            files={"file": create_test_file()},
            data={
                "document_type": doc_type,
                "document_country": "Uzbekistan",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    response = await client.get(
        "/api/v1/verifications/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["verifications"]) == 2


@pytest.mark.asyncio
async def test_get_verification(client: AsyncClient, db_session: AsyncSession):
    """Can get a specific verification."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    upload_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    verification_id = upload_response.json()["id"]

    response = await client.get(
        f"/api/v1/verifications/{verification_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == verification_id


@pytest.mark.asyncio
async def test_get_other_users_verification_fails(client: AsyncClient, db_session: AsyncSession):
    """Cannot get another user's verification."""
    token_a, _ = await create_user_with_profile(client, "usera@example.com")
    token_b, _ = await create_user_with_profile(client, "userb@example.com")

    upload_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    verification_id = upload_response.json()["id"]

    response = await client.get(
        f"/api/v1/verifications/{verification_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cancel_pending_verification(client: AsyncClient, db_session: AsyncSession):
    """Can cancel a pending verification."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    upload_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    verification_id = upload_response.json()["id"]

    response = await client.post(
        f"/api/v1/verifications/{verification_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cannot_cancel_processed_verification(client: AsyncClient, db_session: AsyncSession):
    """Cannot cancel already processed verification."""
    token, user_id = await create_user_with_profile(client, "user@example.com")
    admin_token, admin_id = await create_user_with_profile(client, "admin@example.com")
    await make_user_admin(db_session, admin_id)

    # Upload document
    upload_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    verification_id = upload_response.json()["id"]

    # Admin approves
    await client.post(
        f"/api/v1/admin/verifications/{verification_id}/approve",
        json={
            "extracted_data": {
                "first_name": "John",
                "last_name": "Doe",
                "birth_date": "1990-01-15",
                "nationality": "Uzbek",
                "document_number": "AA1234567",
                "expiry_date": "2030-01-15",
            },
            "document_expiry_date": "2030-01-15",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # User tries to cancel
    response = await client.post(
        f"/api/v1/verifications/{verification_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    # Should indicate cannot cancel due to status
    assert "cannot cancel" in response.json()["detail"].lower() or "approved" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_verification_status(client: AsyncClient, db_session: AsyncSession):
    """Can get verification status summary."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/verifications/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["overall_status"] == "unverified"
    assert "passport" in data["missing_required_documents"]


@pytest.mark.asyncio
async def test_admin_list_pending_verifications(client: AsyncClient, db_session: AsyncSession):
    """Admin can list all pending verifications."""
    # Create regular user and upload doc
    token, _ = await create_user_with_profile(client, "user@example.com")
    await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Create admin
    admin_token, admin_id = await create_user_with_profile(client, "admin@example.com")
    await make_user_admin(db_session, admin_id)

    response = await client.get(
        "/api/v1/admin/verifications/pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_endpoints(client: AsyncClient, db_session: AsyncSession):
    """Non-admin users cannot access admin endpoints."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/admin/verifications/pending",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "admin" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_approve_verification(client: AsyncClient, db_session: AsyncSession):
    """Admin can approve verification and data is copied to profile."""
    token, user_id = await create_user_with_profile(client, "user@example.com")
    admin_token, admin_id = await create_user_with_profile(client, "admin@example.com")
    await make_user_admin(db_session, admin_id)

    # Upload document
    upload_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    verification_id = upload_response.json()["id"]

    # Admin approves
    response = await client.post(
        f"/api/v1/admin/verifications/{verification_id}/approve",
        json={
            "extracted_data": {
                "first_name": "John",
                "last_name": "Doe",
                "birth_date": "1990-01-15",
                "birth_place": "Tashkent",
                "nationality": "Uzbek",
                "document_number": "AA1234567",
                "expiry_date": "2030-01-15",
            },
            "document_expiry_date": "2030-01-15",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["verified_by"] == admin_id
    assert data["extracted_data"]["first_name"] == "John"

    # Check profile was updated
    profile_response = await client.get(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    profile_data = profile_response.json()
    assert profile_data["verified_first_name"] == "John"
    assert profile_data["verified_last_initial"] == "D"
    assert profile_data["verified_nationality"] == "Uzbek"

    # Check user verification status was updated
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_data = me_response.json()
    assert user_data["verification_status"] == "verified"


@pytest.mark.asyncio
async def test_admin_reject_verification(client: AsyncClient, db_session: AsyncSession):
    """Admin can reject verification with reason."""
    token, _ = await create_user_with_profile(client, "user@example.com")
    admin_token, admin_id = await create_user_with_profile(client, "admin@example.com")
    await make_user_admin(db_session, admin_id)

    # Upload document
    upload_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    verification_id = upload_response.json()["id"]

    # Admin rejects
    response = await client.post(
        f"/api/v1/admin/verifications/{verification_id}/reject",
        json={
            "reason": "Document is not readable. Please upload a clearer image.",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert "not readable" in data["rejection_reason"]


@pytest.mark.asyncio
async def test_admin_cannot_approve_non_pending(client: AsyncClient, db_session: AsyncSession):
    """Admin cannot approve already processed verification."""
    token, _ = await create_user_with_profile(client, "user@example.com")
    admin_token, admin_id = await create_user_with_profile(client, "admin@example.com")
    await make_user_admin(db_session, admin_id)

    # Upload and cancel
    upload_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    verification_id = upload_response.json()["id"]

    await client.post(
        f"/api/v1/verifications/{verification_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Admin tries to approve
    response = await client.post(
        f"/api/v1/admin/verifications/{verification_id}/approve",
        json={
            "extracted_data": {"first_name": "John"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_pdf_document(client: AsyncClient, db_session: AsyncSession):
    """Can upload PDF document."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": ("document.pdf", b"PDF content", "application/pdf")},
        data={
            "document_type": "diploma",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_upload_png_document(client: AsyncClient, db_session: AsyncSession):
    """Can upload PNG document."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": ("document.png", b"PNG content", "image/png")},
        data={
            "document_type": "divorce_certificate",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_verification_status_after_approval(client: AsyncClient, db_session: AsyncSession):
    """Verification status summary updates after approval."""
    token, user_id = await create_user_with_profile(client, "user@example.com")
    admin_token, admin_id = await create_user_with_profile(client, "admin@example.com")
    await make_user_admin(db_session, admin_id)

    # Check initial status
    status_response = await client.get(
        "/api/v1/verifications/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.json()["overall_status"] == "unverified"

    # Upload and approve passport
    upload_response = await client.post(
        "/api/v1/verifications/upload",
        files={"file": create_test_file()},
        data={
            "document_type": "passport",
            "document_country": "Uzbekistan",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    verification_id = upload_response.json()["id"]

    await client.post(
        f"/api/v1/admin/verifications/{verification_id}/approve",
        json={
            "extracted_data": {
                "first_name": "John",
                "last_name": "Doe",
                "birth_date": "1990-01-15",
                "nationality": "Uzbek",
                "document_number": "AA1234567",
                "expiry_date": "2030-01-15",
            },
            "document_expiry_date": "2030-01-15",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Check updated status
    status_response = await client.get(
        "/api/v1/verifications/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = status_response.json()
    assert data["overall_status"] == "verified"
    assert "passport" in data["verified_documents"]
    assert "passport" not in data["missing_required_documents"]
