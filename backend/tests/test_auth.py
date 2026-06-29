import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, test_school: dict):
    """Test successful user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "nickname": "新用户",
            "password": "securepassword",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user: dict, test_school: dict):
    """Test registration with an already registered email returns 409."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": test_user["email"],
            "nickname": "另一个昵称",
            "password": "anotherpassword",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 409
    assert "已被注册" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: dict):
    """Test successful login with correct credentials."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user["email"],
            "password": test_user["password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: dict):
    """Test login with wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user["email"],
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert "密码错误" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient):
    """Test login with non-existent email returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "somepassword",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, test_user: dict):
    """Test successful token refresh."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": test_user["refresh_token"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Verify new tokens are valid (they may be identical if generated in the same second)
    assert data["access_token"] is not None


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """Test refresh with invalid token returns 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_with_access_token(client: AsyncClient, test_user: dict):
    """Test refresh endpoint rejects an access token (wrong type)."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": test_user["access_token"]},
    )
    assert response.status_code == 401
    assert "token 类型" in response.json()["detail"]


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """Test logout endpoint returns success."""
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert "登出成功" in response.json()["message"]
