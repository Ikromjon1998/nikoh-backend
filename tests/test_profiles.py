import pytest
from httpx import AsyncClient


@pytest.fixture
async def profile_data():
    return {
        "gender": "male",
        "seeking_gender": "female",
    }


@pytest.fixture
async def full_profile_data():
    return {
        "gender": "male",
        "seeking_gender": "female",
        "height_cm": 175,
        "weight_kg": 70,
        "build": "athletic",
        "ethnicity": "uzbek",
        "languages": [
            {"language": "uzbek", "proficiency": "native"},
            {"language": "russian", "proficiency": "fluent"},
            {"language": "english", "proficiency": "conversational"},
        ],
        "original_region": "Tashkent",
        "current_city": "New York",
        "living_situation": "alone",
        "religious_practice": "important",
        "smoking": "never",
        "alcohol": "never",
        "diet": "halal_only",
        "profession": "Software Engineer",
        "hobbies": ["reading", "hiking", "coding"],
        "about_me": "I am a software engineer passionate about building meaningful applications. I value family, honesty, and continuous learning. Looking for a life partner who shares similar values.",
        "family_meaning": "Family is the foundation of everything. I believe in strong family bonds and supporting each other through all of life's challenges.",
        "ideal_partner": "Someone who is kind, intelligent, and family-oriented. She should have her own goals and ambitions while also valuing partnership and mutual support.",
        "goals_dreams": "I want to build a successful career while maintaining a healthy work-life balance. Eventually, I hope to start a family and create a loving home.",
        "message_to_family": "I come from a good family and have been raised with strong values. I am financially stable and ready for the responsibilities of marriage.",
    }


@pytest.mark.asyncio
async def test_create_profile_success(
    client: AsyncClient, auth_token: str, profile_data: dict
):
    response = await client.post(
        "/api/v1/profiles/",
        json=profile_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["gender"] == profile_data["gender"]
    assert data["seeking_gender"] == profile_data["seeking_gender"]
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data
    assert data["is_visible"] is True
    assert "profile_score" in data


@pytest.mark.asyncio
async def test_create_profile_all_fields(
    client: AsyncClient, auth_token: str, full_profile_data: dict
):
    response = await client.post(
        "/api/v1/profiles/",
        json=full_profile_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["gender"] == full_profile_data["gender"]
    assert data["seeking_gender"] == full_profile_data["seeking_gender"]
    assert data["height_cm"] == full_profile_data["height_cm"]
    assert data["weight_kg"] == full_profile_data["weight_kg"]
    assert data["build"] == full_profile_data["build"]
    assert data["ethnicity"] == full_profile_data["ethnicity"]
    assert len(data["languages"]) == 3
    assert data["original_region"] == full_profile_data["original_region"]
    assert data["current_city"] == full_profile_data["current_city"]
    assert data["living_situation"] == full_profile_data["living_situation"]
    assert data["religious_practice"] == full_profile_data["religious_practice"]
    assert data["smoking"] == full_profile_data["smoking"]
    assert data["alcohol"] == full_profile_data["alcohol"]
    assert data["diet"] == full_profile_data["diet"]
    assert data["profession"] == full_profile_data["profession"]
    assert data["hobbies"] == full_profile_data["hobbies"]
    assert data["about_me"] == full_profile_data["about_me"]
    assert data["family_meaning"] == full_profile_data["family_meaning"]
    assert data["ideal_partner"] == full_profile_data["ideal_partner"]
    assert data["goals_dreams"] == full_profile_data["goals_dreams"]
    assert data["message_to_family"] == full_profile_data["message_to_family"]

    # Full profile should have high score
    assert data["profile_score"] >= 70


@pytest.mark.asyncio
async def test_create_profile_duplicate(
    client: AsyncClient, auth_token: str, profile_data: dict
):
    # Create first profile
    await client.post(
        "/api/v1/profiles/",
        json=profile_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # Try to create second profile
    response = await client.post(
        "/api/v1/profiles/",
        json=profile_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Profile already exists for this user"


@pytest.mark.asyncio
async def test_create_profile_unauthorized(client: AsyncClient, profile_data: dict):
    response = await client.post("/api/v1/profiles/", json=profile_data)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_my_profile(
    client: AsyncClient, auth_token: str, profile_data: dict
):
    # Create profile first
    await client.post(
        "/api/v1/profiles/",
        json=profile_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # Get profile
    response = await client.get(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["gender"] == profile_data["gender"]
    assert data["seeking_gender"] == profile_data["seeking_gender"]


@pytest.mark.asyncio
async def test_get_my_profile_not_found(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/profiles/me",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


@pytest.mark.asyncio
async def test_update_profile(
    client: AsyncClient, auth_token: str, profile_data: dict
):
    # Create profile first
    await client.post(
        "/api/v1/profiles/",
        json=profile_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # Update profile
    update_data = {
        "height_cm": 180,
        "profession": "Data Scientist",
        "about_me": "Updated about me section with enough characters to be meaningful and counted properly.",
    }

    response = await client.put(
        "/api/v1/profiles/me",
        json=update_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["height_cm"] == 180
    assert data["profession"] == "Data Scientist"
    assert "Updated about me" in data["about_me"]
    # Original fields should be unchanged
    assert data["gender"] == profile_data["gender"]


@pytest.mark.asyncio
async def test_update_profile_not_found(client: AsyncClient, auth_token: str):
    response = await client.put(
        "/api/v1/profiles/me",
        json={"height_cm": 180},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_profile_score_calculated(
    client: AsyncClient, auth_token: str, profile_data: dict
):
    # Create minimal profile
    create_response = await client.post(
        "/api/v1/profiles/",
        json=profile_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    initial_score = create_response.json()["profile_score"]

    # Update with more fields
    update_data = {
        "height_cm": 175,
        "weight_kg": 70,
        "build": "athletic",
        "ethnicity": "uzbek",
        "profession": "Engineer",
        "about_me": "A detailed about me section that describes who I am and what I'm looking for in life and in a partner.",
        "ideal_partner": "A detailed description of my ideal partner including her values, goals, and personality traits.",
    }

    response = await client.put(
        "/api/v1/profiles/me",
        json=update_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    new_score = response.json()["profile_score"]
    assert new_score > initial_score


@pytest.mark.asyncio
async def test_get_profile_by_id(client: AsyncClient, db_session):
    # Create two users with profiles
    user1_data = {"email": "user1@example.com", "password": "password123"}
    user2_data = {"email": "user2@example.com", "password": "password123"}

    # Register and login user 1
    await client.post("/api/v1/auth/register", json=user1_data)
    login1 = await client.post(
        "/api/v1/auth/login",
        data={"username": user1_data["email"], "password": user1_data["password"]},
    )
    token1 = login1.json()["access_token"]

    # Register and login user 2
    await client.post("/api/v1/auth/register", json=user2_data)
    login2 = await client.post(
        "/api/v1/auth/login",
        data={"username": user2_data["email"], "password": user2_data["password"]},
    )
    token2 = login2.json()["access_token"]

    # User 1 creates profile
    profile_response = await client.post(
        "/api/v1/profiles/",
        json={"gender": "male", "seeking_gender": "female"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    profile_id = profile_response.json()["id"]

    # User 2 gets User 1's profile
    response = await client.get(
        f"/api/v1/profiles/{profile_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == profile_id


@pytest.mark.asyncio
async def test_get_invisible_profile(client: AsyncClient, db_session):
    # Create two users
    user1_data = {"email": "user1@example.com", "password": "password123"}
    user2_data = {"email": "user2@example.com", "password": "password123"}

    # Register and login user 1
    await client.post("/api/v1/auth/register", json=user1_data)
    login1 = await client.post(
        "/api/v1/auth/login",
        data={"username": user1_data["email"], "password": user1_data["password"]},
    )
    token1 = login1.json()["access_token"]

    # Register and login user 2
    await client.post("/api/v1/auth/register", json=user2_data)
    login2 = await client.post(
        "/api/v1/auth/login",
        data={"username": user2_data["email"], "password": user2_data["password"]},
    )
    token2 = login2.json()["access_token"]

    # User 1 creates profile
    profile_response = await client.post(
        "/api/v1/profiles/",
        json={"gender": "male", "seeking_gender": "female"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    profile_id = profile_response.json()["id"]

    # User 1 makes profile invisible
    await client.put(
        "/api/v1/profiles/me",
        json={"is_visible": False},
        headers={"Authorization": f"Bearer {token1}"},
    )

    # User 2 tries to get User 1's profile
    response = await client.get(
        f"/api/v1/profiles/{profile_id}",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_search_profiles_basic(client: AsyncClient, db_session):
    # Create multiple users with profiles
    users = [
        {"email": f"user{i}@example.com", "password": "password123"}
        for i in range(5)
    ]

    tokens = []
    for user_data in users:
        await client.post("/api/v1/auth/register", json=user_data)
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": user_data["email"], "password": user_data["password"]},
        )
        tokens.append(login.json()["access_token"])

    # Create profiles for all users
    for i, token in enumerate(tokens):
        gender = "male" if i % 2 == 0 else "female"
        await client.post(
            "/api/v1/profiles/",
            json={"gender": gender, "seeking_gender": "female" if gender == "male" else "male"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Search from user 0's perspective
    response = await client.post(
        "/api/v1/profiles/search",
        json={"page": 1, "per_page": 20},
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "profiles" in data
    assert "total" in data
    assert data["total"] == 4  # Excludes self
    assert len(data["profiles"]) == 4


@pytest.mark.asyncio
async def test_search_profiles_with_filters(client: AsyncClient, db_session):
    # Create users with different ethnicities
    users = [
        {"email": f"user{i}@example.com", "password": "password123"}
        for i in range(4)
    ]

    tokens = []
    for user_data in users:
        await client.post("/api/v1/auth/register", json=user_data)
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": user_data["email"], "password": user_data["password"]},
        )
        tokens.append(login.json()["access_token"])

    # Create profiles with different ethnicities
    ethnicities = ["uzbek", "kazakh", "uzbek", "tajik"]
    for i, (token, ethnicity) in enumerate(zip(tokens, ethnicities)):
        await client.post(
            "/api/v1/profiles/",
            json={
                "gender": "male",
                "seeking_gender": "female",
                "ethnicity": ethnicity,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    # Search for uzbek ethnicity from user 3's perspective
    response = await client.post(
        "/api/v1/profiles/search",
        json={"ethnicities": ["uzbek"], "page": 1, "per_page": 20},
        headers={"Authorization": f"Bearer {tokens[3]}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # Two uzbek profiles (excluding self if applicable)
    for profile in data["profiles"]:
        assert profile["ethnicity"] == "uzbek"


@pytest.mark.asyncio
async def test_search_pagination(client: AsyncClient, db_session):
    # Create 25 users with profiles
    users = [
        {"email": f"user{i}@example.com", "password": "password123"}
        for i in range(26)  # 26 users so we have 25 others to search
    ]

    tokens = []
    for user_data in users:
        await client.post("/api/v1/auth/register", json=user_data)
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": user_data["email"], "password": user_data["password"]},
        )
        tokens.append(login.json()["access_token"])

    # Create profiles for all users
    for token in tokens:
        await client.post(
            "/api/v1/profiles/",
            json={"gender": "male", "seeking_gender": "female"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Search page 1 with per_page=10
    response = await client.post(
        "/api/v1/profiles/search",
        json={"page": 1, "per_page": 10},
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 25  # Excludes self
    assert len(data["profiles"]) == 10
    assert data["page"] == 1
    assert data["per_page"] == 10

    # Search page 2
    response = await client.post(
        "/api/v1/profiles/search",
        json={"page": 2, "per_page": 10},
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )

    data = response.json()
    assert len(data["profiles"]) == 10
    assert data["page"] == 2

    # Search page 3 (should have 5 remaining)
    response = await client.post(
        "/api/v1/profiles/search",
        json={"page": 3, "per_page": 10},
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )

    data = response.json()
    assert len(data["profiles"]) == 5
    assert data["page"] == 3


@pytest.mark.asyncio
async def test_search_by_gender(client: AsyncClient, db_session):
    # Create users with different genders
    users = [
        {"email": f"user{i}@example.com", "password": "password123"}
        for i in range(5)
    ]

    tokens = []
    for user_data in users:
        await client.post("/api/v1/auth/register", json=user_data)
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": user_data["email"], "password": user_data["password"]},
        )
        tokens.append(login.json()["access_token"])

    # Create profiles: 3 males, 2 females
    genders = ["male", "male", "male", "female", "female"]
    for token, gender in zip(tokens, genders):
        await client.post(
            "/api/v1/profiles/",
            json={"gender": gender, "seeking_gender": "female" if gender == "male" else "male"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Search for females from a male user's perspective
    response = await client.post(
        "/api/v1/profiles/search",
        json={"seeking_gender": "female", "page": 1, "per_page": 20},
        headers={"Authorization": f"Bearer {tokens[0]}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    for profile in data["profiles"]:
        assert profile["gender"] == "female"
