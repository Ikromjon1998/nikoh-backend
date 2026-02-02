import pytest
from httpx import AsyncClient


async def create_user_with_profile(
    client: AsyncClient,
    email: str,
    gender: str,
    seeking: str,
) -> tuple[str, str]:
    """Helper to create user, login, create profile. Returns (token, user_id)."""
    # Register
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Get user ID
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = me_response.json()["id"]

    # Create profile
    await client.post(
        "/api/v1/profiles/",
        json={"gender": gender, "seeking_gender": seeking},
        headers={"Authorization": f"Bearer {token}"},
    )

    return token, user_id


async def create_match(
    client: AsyncClient,
    token_a: str,
    user_b_id: str,
    token_b: str,
) -> str:
    """Helper to create a match between two users. Returns match_id."""
    # User A sends interest
    interest_response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    interest_id = interest_response.json()["id"]

    # User B accepts
    await client.post(
        f"/api/v1/interests/{interest_id}/respond",
        json={"action": "accept"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # Get match ID
    matches_response = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    return matches_response.json()["matches"][0]["id"]


@pytest.mark.asyncio
async def test_get_matches_empty(client: AsyncClient, db_session):
    """No matches returns empty list."""
    token, _ = await create_user_with_profile(
        client, "user@example.com", "male", "female"
    )

    response = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["matches"] == []


@pytest.mark.asyncio
async def test_get_matches_after_interest_accepted(client: AsyncClient, db_session):
    """Match appears after interest is accepted."""
    token_a, user_a_id = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # Create match
    await create_match(client, token_a, user_b_id, token_b)

    # User A gets matches
    matches_a = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert matches_a.status_code == 200
    assert matches_a.json()["total"] == 1

    # User B gets matches
    matches_b = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert matches_b.status_code == 200
    assert matches_b.json()["total"] == 1

    # Both see the same match
    assert matches_a.json()["matches"][0]["id"] == matches_b.json()["matches"][0]["id"]


@pytest.mark.asyncio
async def test_get_match_by_id(client: AsyncClient, db_session):
    """Can get specific match by ID."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    match_id = await create_match(client, token_a, user_b_id, token_b)

    response = await client.get(
        f"/api/v1/matches/{match_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == match_id
    assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_get_others_match_fails(client: AsyncClient, db_session):
    """Cannot get match you're not part of."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )
    token_c, _ = await create_user_with_profile(
        client, "userc@example.com", "male", "female"
    )

    match_id = await create_match(client, token_a, user_b_id, token_b)

    # User C tries to get match
    response = await client.get(
        f"/api/v1/matches/{match_id}",
        headers={"Authorization": f"Bearer {token_c}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unmatch(client: AsyncClient, db_session):
    """Can unmatch from someone."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    match_id = await create_match(client, token_a, user_b_id, token_b)

    # User A unmatches
    response = await client.post(
        f"/api/v1/matches/{match_id}/unmatch",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unmatched"

    # Match no longer appears in active matches
    matches = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert matches.json()["total"] == 0


@pytest.mark.asyncio
async def test_unmatch_twice_fails(client: AsyncClient, db_session):
    """Cannot unmatch already unmatched."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    match_id = await create_match(client, token_a, user_b_id, token_b)

    # First unmatch
    await client.post(
        f"/api/v1/matches/{match_id}/unmatch",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Second unmatch should fail
    response = await client.post(
        f"/api/v1/matches/{match_id}/unmatch",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 400
    assert "already unmatched" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_match_includes_profile_info(client: AsyncClient, db_session):
    """Match response includes other user's profile info."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    match_id = await create_match(client, token_a, user_b_id, token_b)

    # User A gets match
    response = await client.get(
        f"/api/v1/matches/{match_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "other_user_profile" in data
    assert data["other_user_profile"] is not None
    # User A should see User B's profile (female)
    assert data["other_user_profile"]["gender"] == "female"

    # User B gets same match
    response = await client.get(
        f"/api/v1/matches/{match_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    data = response.json()
    # User B should see User A's profile (male)
    assert data["other_user_profile"]["gender"] == "male"


@pytest.mark.asyncio
async def test_match_pagination(client: AsyncClient, db_session):
    """Matches are paginated correctly."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )

    # Create multiple matches
    for i in range(5):
        token_other, user_other_id = await create_user_with_profile(
            client, f"user{i}@example.com", "female", "male"
        )
        await create_match(client, token_a, user_other_id, token_other)

    # Get first page
    response = await client.get(
        "/api/v1/matches/?page=1&per_page=2",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["matches"]) == 2
    assert data["page"] == 1
    assert data["per_page"] == 2

    # Get second page
    response = await client.get(
        "/api/v1/matches/?page=2&per_page=2",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    data = response.json()
    assert len(data["matches"]) == 2
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_unmatch_by_either_user(client: AsyncClient, db_session):
    """Either user in a match can unmatch."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    match_id = await create_match(client, token_a, user_b_id, token_b)

    # User B unmatches (instead of User A who initiated)
    response = await client.post(
        f"/api/v1/matches/{match_id}/unmatch",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unmatched"

    # Neither user sees the match anymore
    matches_a = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    matches_b = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert matches_a.json()["total"] == 0
    assert matches_b.json()["total"] == 0
