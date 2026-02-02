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


@pytest.mark.asyncio
async def test_send_interest_success(client: AsyncClient, db_session):
    """User A can send interest to User B."""
    # Create User A (male seeking female)
    token_a, user_a_id = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )

    # Create User B (female seeking male)
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # User A sends interest to User B
    response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id, "message": "Hello!"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["from_user_id"] == user_a_id
    assert data["to_user_id"] == user_b_id
    assert data["message"] == "Hello!"
    assert data["status"] == "pending"
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_send_interest_to_self_fails(client: AsyncClient, db_session):
    """Cannot send interest to yourself."""
    token, user_id = await create_user_with_profile(
        client, "user@example.com", "male", "female"
    )

    response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "yourself" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_send_duplicate_interest_fails(client: AsyncClient, db_session):
    """Cannot send second pending interest to same user."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    _, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # First interest
    await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # Second interest should fail
    response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 400
    assert "already sent" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_send_interest_when_matched_fails(client: AsyncClient, db_session):
    """Cannot send interest if already matched."""
    token_a, user_a_id = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # Create interest and accept it to create match
    interest_response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    interest_id = interest_response.json()["id"]

    await client.post(
        f"/api/v1/interests/{interest_id}/respond",
        json={"action": "accept"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # Now try to send another interest
    response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 400
    assert "already matched" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_send_interest_to_invisible_profile_fails(client: AsyncClient, db_session):
    """Cannot send interest to user with invisible profile."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # User B makes profile invisible
    await client.put(
        "/api/v1/profiles/me",
        json={"is_visible": False},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # User A tries to send interest
    response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_received_interests(client: AsyncClient, db_session):
    """Can get list of received interests."""
    # Create User D who will receive interests
    token_d, user_d_id = await create_user_with_profile(
        client, "userd@example.com", "female", "male"
    )

    # Create Users A, B, C who will send interests
    senders = []
    for i, letter in enumerate(["a", "b", "c"]):
        token, user_id = await create_user_with_profile(
            client, f"user{letter}@example.com", "male", "female"
        )
        senders.append((token, user_id))
        # Send interest to D
        await client.post(
            "/api/v1/interests/",
            json={"to_user_id": user_d_id},
            headers={"Authorization": f"Bearer {token}"},
        )

    # User D gets received interests
    response = await client.get(
        "/api/v1/interests/received",
        headers={"Authorization": f"Bearer {token_d}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["interests"]) == 3


@pytest.mark.asyncio
async def test_get_received_interests_filter_status(client: AsyncClient, db_session):
    """Can filter received interests by status."""
    token_d, user_d_id = await create_user_with_profile(
        client, "userd@example.com", "female", "male"
    )

    # User A sends interest (will stay pending)
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_d_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # User B sends interest, D accepts
    token_b, _ = await create_user_with_profile(
        client, "userb@example.com", "male", "female"
    )
    interest_response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_d_id},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    interest_id = interest_response.json()["id"]
    await client.post(
        f"/api/v1/interests/{interest_id}/respond",
        json={"action": "accept"},
        headers={"Authorization": f"Bearer {token_d}"},
    )

    # Get only pending interests
    response = await client.get(
        "/api/v1/interests/received?status=pending",
        headers={"Authorization": f"Bearer {token_d}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["interests"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_sent_interests(client: AsyncClient, db_session):
    """Can get list of sent interests."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )

    # Create multiple users and send interests
    for letter in ["b", "c", "d"]:
        _, user_id = await create_user_with_profile(
            client, f"user{letter}@example.com", "female", "male"
        )
        await client.post(
            "/api/v1/interests/",
            json={"to_user_id": user_id},
            headers={"Authorization": f"Bearer {token_a}"},
        )

    # Get sent interests
    response = await client.get(
        "/api/v1/interests/sent",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["interests"]) == 3


@pytest.mark.asyncio
async def test_accept_interest_creates_match(client: AsyncClient, db_session):
    """Accepting interest creates a match."""
    token_a, user_a_id = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # User A sends interest
    interest_response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    interest_id = interest_response.json()["id"]

    # User B accepts
    response = await client.post(
        f"/api/v1/interests/{interest_id}/respond",
        json={"action": "accept"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    # Check match exists for both users
    matches_a = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    matches_b = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert matches_a.json()["total"] == 1
    assert matches_b.json()["total"] == 1


@pytest.mark.asyncio
async def test_decline_interest(client: AsyncClient, db_session):
    """Can decline an interest."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # User A sends interest
    interest_response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    interest_id = interest_response.json()["id"]

    # User B declines
    response = await client.post(
        f"/api/v1/interests/{interest_id}/respond",
        json={"action": "decline"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "declined"

    # No match should exist
    matches = await client.get(
        "/api/v1/matches/",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert matches.json()["total"] == 0


@pytest.mark.asyncio
async def test_respond_to_others_interest_fails(client: AsyncClient, db_session):
    """Cannot respond to interest sent to someone else."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )
    token_c, _ = await create_user_with_profile(
        client, "userc@example.com", "male", "female"
    )

    # User A sends interest to User B
    interest_response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    interest_id = interest_response.json()["id"]

    # User C tries to respond
    response = await client.post(
        f"/api/v1/interests/{interest_id}/respond",
        json={"action": "accept"},
        headers={"Authorization": f"Bearer {token_c}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_respond_to_non_pending_fails(client: AsyncClient, db_session):
    """Cannot respond to already responded interest."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

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

    # User B tries to decline same interest
    response = await client.post(
        f"/api/v1/interests/{interest_id}/respond",
        json={"action": "decline"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 400
    assert "not pending" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancel_sent_interest(client: AsyncClient, db_session):
    """Can cancel pending interest you sent."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    _, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # User A sends interest
    interest_response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    interest_id = interest_response.json()["id"]

    # User A cancels
    response = await client.delete(
        f"/api/v1/interests/{interest_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 204

    # Check it's gone from sent interests
    sent = await client.get(
        "/api/v1/interests/sent",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert sent.json()["total"] == 0


@pytest.mark.asyncio
async def test_cancel_others_interest_fails(client: AsyncClient, db_session):
    """Cannot cancel interest you didn't send."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    token_b, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # User A sends interest to User B
    interest_response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    interest_id = interest_response.json()["id"]

    # User B tries to cancel (they should respond, not cancel)
    response = await client.delete(
        f"/api/v1/interests/{interest_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_interest_includes_profile_info(client: AsyncClient, db_session):
    """Interest response includes other user's profile info."""
    token_a, _ = await create_user_with_profile(
        client, "usera@example.com", "male", "female"
    )
    _, user_b_id = await create_user_with_profile(
        client, "userb@example.com", "female", "male"
    )

    # User A sends interest
    response = await client.post(
        "/api/v1/interests/",
        json={"to_user_id": user_b_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "other_user_profile" in data
    assert data["other_user_profile"] is not None
    assert data["other_user_profile"]["gender"] == "female"
