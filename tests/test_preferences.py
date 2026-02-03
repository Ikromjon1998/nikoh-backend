"""Tests for search preferences."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def create_user_with_profile(
    client: AsyncClient,
    email: str,
    gender: str = "male",
    seeking_gender: str = "female",
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
        json={
            "gender": gender,
            "seeking_gender": seeking_gender,
            "city": "Tashkent",
            "country": "Uzbekistan",
            "ethnicity": "uzbek",
            "education_level": "bachelors",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    return token, user_id


# ============== Create Preferences Tests ==============


@pytest.mark.asyncio
async def test_create_preferences(client: AsyncClient, db_session: AsyncSession):
    """Can create search preferences."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/preferences/",
        json={
            "min_age": 25,
            "max_age": 35,
            "preferred_countries": ["Uzbekistan", "Kazakhstan"],
            "must_be_verified": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["min_age"] == 25
    assert data["max_age"] == 35
    assert data["preferred_countries"] == ["Uzbekistan", "Kazakhstan"]
    assert data["must_be_verified"] is True


@pytest.mark.asyncio
async def test_create_preferences_with_defaults(client: AsyncClient, db_session: AsyncSession):
    """Preferences use defaults when not specified."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/preferences/",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["min_age"] == 18
    assert data["max_age"] == 99
    assert data["must_be_verified"] is True
    assert data["has_children_acceptable"] is True


@pytest.mark.asyncio
async def test_update_preferences(client: AsyncClient, db_session: AsyncSession):
    """Can update existing preferences."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Create initial preferences
    await client.post(
        "/api/v1/preferences/",
        json={"min_age": 20},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Update preferences
    response = await client.post(
        "/api/v1/preferences/",
        json={"min_age": 25, "max_age": 40},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["min_age"] == 25
    assert data["max_age"] == 40


# ============== Get Preferences Tests ==============


@pytest.mark.asyncio
async def test_get_preferences(client: AsyncClient, db_session: AsyncSession):
    """Can get saved preferences."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Create preferences first
    await client.post(
        "/api/v1/preferences/",
        json={"min_age": 22, "preferred_ethnicities": ["uzbek", "kazakh"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get preferences
    response = await client.get(
        "/api/v1/preferences/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["min_age"] == 22
    assert data["preferred_ethnicities"] == ["uzbek", "kazakh"]


@pytest.mark.asyncio
async def test_get_preferences_not_found(client: AsyncClient, db_session: AsyncSession):
    """Returns 404 when no preferences set."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/preferences/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


# ============== Delete Preferences Tests ==============


@pytest.mark.asyncio
async def test_delete_preferences(client: AsyncClient, db_session: AsyncSession):
    """Can delete preferences."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Create preferences
    await client.post(
        "/api/v1/preferences/",
        json={"min_age": 25},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Delete preferences
    response = await client.delete(
        "/api/v1/preferences/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    # Verify deleted
    response = await client.get(
        "/api/v1/preferences/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_preferences_not_found(client: AsyncClient, db_session: AsyncSession):
    """Cannot delete non-existent preferences."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.delete(
        "/api/v1/preferences/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


# ============== Get Defaults Tests ==============


@pytest.mark.asyncio
async def test_get_default_preferences(client: AsyncClient, db_session: AsyncSession):
    """Can get default preference values."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/preferences/defaults",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["min_age"] == 18
    assert data["max_age"] == 99
    assert data["must_be_verified"] is True


# ============== Validation Tests ==============


@pytest.mark.asyncio
async def test_preferences_age_validation(client: AsyncClient, db_session: AsyncSession):
    """Age must be within valid range."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # min_age too low
    response = await client.post(
        "/api/v1/preferences/",
        json={"min_age": 15},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # max_age too high
    response = await client.post(
        "/api/v1/preferences/",
        json={"max_age": 150},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_preferences_height_validation(client: AsyncClient, db_session: AsyncSession):
    """Height must be within valid range."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    # Height too low
    response = await client.post(
        "/api/v1/preferences/",
        json={"min_height_cm": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422

    # Height too high
    response = await client.post(
        "/api/v1/preferences/",
        json={"max_height_cm": 300},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ============== Array Preferences Tests ==============


@pytest.mark.asyncio
async def test_preferences_with_arrays(client: AsyncClient, db_session: AsyncSession):
    """Can set array preferences."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/preferences/",
        json={
            "preferred_countries": ["Uzbekistan", "Kazakhstan", "Russia"],
            "preferred_cities": ["Tashkent", "Almaty"],
            "preferred_ethnicities": ["uzbek", "kazakh", "russian"],
            "preferred_marital_statuses": ["single", "divorced"],
            "preferred_education_levels": ["bachelors", "masters", "phd"],
            "preferred_religious_practices": ["practicing", "cultural"],
            "preferred_smoking": ["never", "quit"],
            "preferred_alcohol": ["never", "rarely"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["preferred_countries"]) == 3
    assert len(data["preferred_ethnicities"]) == 3
    assert "practicing" in data["preferred_religious_practices"]


@pytest.mark.asyncio
async def test_empty_array_means_any(client: AsyncClient, db_session: AsyncSession):
    """Empty array means 'any' value acceptable."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.post(
        "/api/v1/preferences/",
        json={
            "preferred_countries": [],
            "preferred_ethnicities": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    # Empty arrays should be stored (meaning any is acceptable)
    assert data["preferred_countries"] == []
    assert data["preferred_ethnicities"] == []
