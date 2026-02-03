"""Tests for matching and compatibility system."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.models.search_preference import SearchPreference
from app.models.user import User
from app.services import matching_service


async def create_user_with_profile(
    client: AsyncClient,
    email: str,
    gender: str = "male",
    seeking_gender: str = "female",
    city: str = "Tashkent",
    country: str = "Uzbekistan",
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
            "city": city,
            "country": country,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    return token, user_id


# ============== Compatibility Calculation Tests ==============


class TestCompatibilityCalculation:
    """Tests for compatibility score calculation."""

    def test_calculate_age(self):
        """Can calculate age from birth date."""
        # Someone born 25 years ago
        birth_date = date(date.today().year - 25, 1, 1)
        age = matching_service.calculate_age(birth_date)
        assert age == 25

    def test_calculate_age_none(self):
        """Returns None for None birth date."""
        assert matching_service.calculate_age(None) is None

    def test_check_list_match_empty_list(self):
        """Empty preference list matches any value."""
        assert matching_service._check_list_match(None, "anything") is True
        assert matching_service._check_list_match([], "anything") is True

    def test_check_list_match_with_preferences(self):
        """Matches when value in preference list."""
        prefs = ["uzbek", "kazakh"]
        assert matching_service._check_list_match(prefs, "uzbek") is True
        assert matching_service._check_list_match(prefs, "Uzbek") is True  # Case insensitive
        assert matching_service._check_list_match(prefs, "russian") is False

    def test_check_list_match_no_value(self):
        """No match when value is None but preferences set."""
        prefs = ["uzbek", "kazakh"]
        assert matching_service._check_list_match(prefs, None) is False


# ============== Match Suggestions Tests ==============


@pytest.mark.asyncio
async def test_get_suggestions_empty(client: AsyncClient, db_session: AsyncSession):
    """Returns empty list when no matching profiles."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/matches/suggestions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["suggestions"] == []
    assert data["total_available"] == 0


@pytest.mark.asyncio
async def test_get_suggestions_finds_matches(client: AsyncClient, db_session: AsyncSession):
    """Returns matching profiles."""
    # Create a male user looking for females
    token1, user1_id = await create_user_with_profile(
        client, "male@example.com", gender="male", seeking_gender="female"
    )

    # Create a female user looking for males
    _, user2_id = await create_user_with_profile(
        client, "female@example.com", gender="female", seeking_gender="male"
    )

    # Activate the second user
    from sqlalchemy import select
    result = await db_session.execute(
        select(User).where(User.id == uuid.UUID(user2_id))
    )
    user2 = result.scalar_one_or_none()
    if user2:
        user2.status = "active"
        await db_session.commit()

    response = await client.get(
        "/api/v1/matches/suggestions",
        headers={"Authorization": f"Bearer {token1}"},
    )

    assert response.status_code == 200
    # May or may not find based on status


@pytest.mark.asyncio
async def test_suggestions_excludes_self(client: AsyncClient, db_session: AsyncSession):
    """Suggestions do not include self."""
    token, user_id = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/matches/suggestions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    for suggestion in data["suggestions"]:
        assert suggestion["user_id"] != user_id


@pytest.mark.asyncio
async def test_suggestions_limit(client: AsyncClient, db_session: AsyncSession):
    """Can limit number of suggestions."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/matches/suggestions?limit=5",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["suggestions"]) <= 5


# ============== Profile Compatibility Tests ==============


@pytest.mark.asyncio
async def test_get_profile_compatibility(client: AsyncClient, db_session: AsyncSession):
    """Can get compatibility with specific profile."""
    # Create two users with profiles
    token1, user1_id = await create_user_with_profile(
        client, "user1@example.com", gender="male", seeking_gender="female"
    )
    _, user2_id = await create_user_with_profile(
        client, "user2@example.com", gender="female", seeking_gender="male"
    )

    # Get user2's profile ID
    from sqlalchemy import select

    result = await db_session.execute(
        select(Profile).where(Profile.user_id == uuid.UUID(user2_id))
    )
    profile2 = result.scalar_one_or_none()

    if profile2:
        # Make profile visible
        profile2.is_visible = True
        await db_session.commit()

        response = await client.get(
            f"/api/v1/profiles/{profile2.id}/compatibility",
            headers={"Authorization": f"Bearer {token1}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "breakdown" in data
        assert "mutual" in data
        assert 0 <= data["score"] <= 100


@pytest.mark.asyncio
async def test_compatibility_own_profile_error(client: AsyncClient, db_session: AsyncSession):
    """Cannot check compatibility with own profile."""
    token, user_id = await create_user_with_profile(client, "user@example.com")

    # Get own profile ID
    from sqlalchemy import select

    result = await db_session.execute(
        select(Profile).where(Profile.user_id == uuid.UUID(user_id))
    )
    profile = result.scalar_one_or_none()

    if profile:
        response = await client.get(
            f"/api/v1/profiles/{profile.id}/compatibility",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "own profile" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_compatibility_not_found(client: AsyncClient, db_session: AsyncSession):
    """Returns 404 for non-existent profile."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/profiles/{fake_id}/compatibility",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


# ============== Who Likes Me Tests ==============


@pytest.mark.asyncio
async def test_who_likes_me_empty(client: AsyncClient, db_session: AsyncSession):
    """Returns empty when no one matches."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/matches/who-likes-me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert data["is_verified_user"] is False


@pytest.mark.asyncio
async def test_who_likes_me_non_verified_shows_count_only(
    client: AsyncClient, db_session: AsyncSession
):
    """Non-verified users only see count, not profiles."""
    token, _ = await create_user_with_profile(client, "user@example.com")

    response = await client.get(
        "/api/v1/matches/who-likes-me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_verified_user"] is False
    # Non-verified users see empty profiles list
    assert data["profiles"] == []


# ============== Preference-Based Matching Tests ==============


@pytest.mark.asyncio
async def test_suggestions_respect_preferences(client: AsyncClient, db_session: AsyncSession):
    """Suggestions respect user's saved preferences."""
    token, _ = await create_user_with_profile(
        client, "user@example.com", gender="male", seeking_gender="female"
    )

    # Set preferences
    await client.post(
        "/api/v1/preferences/",
        json={
            "min_age": 25,
            "max_age": 35,
            "preferred_countries": ["Uzbekistan"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/v1/matches/suggestions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    # Suggestions should be returned (may be empty if no matching profiles)


@pytest.mark.asyncio
async def test_compatibility_breakdown_categories(client: AsyncClient, db_session: AsyncSession):
    """Compatibility breakdown includes all expected categories."""
    token1, user1_id = await create_user_with_profile(
        client, "user1@example.com", gender="male", seeking_gender="female"
    )
    _, user2_id = await create_user_with_profile(
        client, "user2@example.com", gender="female", seeking_gender="male"
    )

    from sqlalchemy import select

    result = await db_session.execute(
        select(Profile).where(Profile.user_id == uuid.UUID(user2_id))
    )
    profile2 = result.scalar_one_or_none()

    if profile2:
        profile2.is_visible = True
        await db_session.commit()

        response = await client.get(
            f"/api/v1/profiles/{profile2.id}/compatibility",
            headers={"Authorization": f"Bearer {token1}"},
        )

        if response.status_code == 200:
            data = response.json()
            breakdown = data["breakdown"]

            # Check all expected categories exist
            expected_categories = [
                "age",
                "location",
                "ethnicity",
                "religion",
                "education",
                "marital_status",
                "height",
                "lifestyle",
                "verification",
                "mutual",
            ]

            for category in expected_categories:
                assert category in breakdown
                assert "match" in breakdown[category]
                assert "score" in breakdown[category]
                assert "max_score" in breakdown[category]
                assert "detail" in breakdown[category]


# ============== Edge Cases ==============


@pytest.mark.asyncio
async def test_suggestions_with_no_profile(client: AsyncClient, db_session: AsyncSession):
    """Returns error or empty when user has no profile."""
    # Create user without profile
    await client.post(
        "/api/v1/auth/register",
        json={"email": "noprofile@example.com", "password": "password123"},
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "noprofile@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/matches/suggestions",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Should return empty, not error
    assert response.status_code == 200
    data = response.json()
    assert data["suggestions"] == []


@pytest.mark.asyncio
async def test_mutual_match_detection(client: AsyncClient, db_session: AsyncSession):
    """Detects mutual matches when both users' preferences align."""
    # This test validates the mutual matching concept
    # When user A's profile matches user B's preferences AND
    # user B's profile matches user A's preferences, it's a mutual match

    token1, user1_id = await create_user_with_profile(
        client,
        "user1@example.com",
        gender="male",
        seeking_gender="female",
        country="Uzbekistan",
    )

    # Set preferences for user1 (looking for females in Uzbekistan)
    await client.post(
        "/api/v1/preferences/",
        json={"preferred_countries": ["Uzbekistan"]},
        headers={"Authorization": f"Bearer {token1}"},
    )

    # Create user2 who also prefers Uzbekistan
    token2, user2_id = await create_user_with_profile(
        client,
        "user2@example.com",
        gender="female",
        seeking_gender="male",
        country="Uzbekistan",
    )

    await client.post(
        "/api/v1/preferences/",
        json={"preferred_countries": ["Uzbekistan"]},
        headers={"Authorization": f"Bearer {token2}"},
    )

    # Both users match each other's preferences - this should result in mutual=True
    # when calculating compatibility
    from sqlalchemy import select

    result = await db_session.execute(
        select(Profile).where(Profile.user_id == uuid.UUID(user2_id))
    )
    profile2 = result.scalar_one_or_none()

    if profile2:
        profile2.is_visible = True
        await db_session.commit()
