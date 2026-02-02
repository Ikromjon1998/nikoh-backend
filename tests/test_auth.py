import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    user_data = {
        "email": "newuser@example.com",
        "password": "securepassword123",
        "phone": "+9876543210",
        "preferred_language": "ru",
    }

    response = await client.post("/api/v1/auth/register", json=user_data)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == user_data["email"]
    assert data["phone"] == user_data["phone"]
    assert data["preferred_language"] == user_data["preferred_language"]
    assert data["status"] == "pending"
    assert data["email_verified"] is False
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, registered_user: dict):
    user_data = {
        "email": registered_user["email"],
        "password": "anotherpassword123",
    }

    response = await client.post("/api/v1/auth/register", json=user_data)

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    user_data = {
        "email": "invalid-email",
        "password": "securepassword123",
    }

    response = await client.post("/api/v1/auth/register", json=user_data)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    user_data = {
        "email": "test@example.com",
        "password": "short",
    }

    response = await client.post("/api/v1/auth/register", json=user_data)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, registered_user: dict):
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, registered_user: dict):
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": registered_user["email"],
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "nonexistent@example.com",
            "password": "somepassword123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_get_me_with_token(client: AsyncClient, registered_user: dict, auth_token: str):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == registered_user["email"]
    assert data["phone"] == registered_user["phone"]
    assert "id" in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_get_me_without_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
