import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_like_post(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test liking a post for the first time."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/like",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["is_liked"] is True
    assert data["like_count"] >= 1


@pytest.mark.asyncio
async def test_unlike_post(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test toggling like off (unlike) after liking."""
    # First like
    await client.post(
        f"/api/v1/posts/{test_post['id']}/like",
        headers=auth_headers,
    )
    # Then unlike (toggle)
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/like",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_liked"] is False
    assert data["like_count"] == 0


@pytest.mark.asyncio
async def test_like_post_unauthenticated(client: AsyncClient, test_post: dict):
    """Test liking a post without authentication returns 401."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/like",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_like_nonexistent_post(client: AsyncClient, auth_headers: dict):
    """Test liking a non-existent post returns 404."""
    response = await client.post(
        "/api/v1/posts/99999/like",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_favorite_post(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test favoriting a post for the first time."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/favorite",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["is_favorited"] is True
    assert data["favorite_count"] >= 1


@pytest.mark.asyncio
async def test_unfavorite_post(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test toggling favorite off (unfavorite) after favoriting."""
    # First favorite
    await client.post(
        f"/api/v1/posts/{test_post['id']}/favorite",
        headers=auth_headers,
    )
    # Then unfavorite (toggle)
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/favorite",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_favorited"] is False
    assert data["favorite_count"] == 0


@pytest.mark.asyncio
async def test_favorite_post_unauthenticated(client: AsyncClient, test_post: dict):
    """Test favoriting a post without authentication returns 401."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/favorite",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_favorite_nonexistent_post(client: AsyncClient, auth_headers: dict):
    """Test favoriting a non-existent post returns 404."""
    response = await client.post(
        "/api/v1/posts/99999/favorite",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_validate_post_valid(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test validating a post as valid."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "valid", "comment": "确认有效"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["validation_type"] == "valid"
    assert data["comment"] == "确认有效"


@pytest.mark.asyncio
async def test_validate_post_invalid(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test validating a post as invalid."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "invalid", "comment": "信息已过期"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["validation_type"] == "invalid"


@pytest.mark.asyncio
async def test_validate_post_uncertain(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test validating a post as uncertain."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "uncertain"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["validation_type"] == "uncertain"


@pytest.mark.asyncio
async def test_validate_post_invalid_type(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test validating with an invalid validation_type returns 422."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "bad_type"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validate_post_unauthenticated(client: AsyncClient, test_post: dict):
    """Test validating a post without authentication returns 401."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "valid"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_validate_nonexistent_post(client: AsyncClient, auth_headers: dict):
    """Test validating a non-existent post returns 404."""
    response = await client.post(
        "/api/v1/posts/99999/validate",
        json={"validation_type": "valid"},
        headers=auth_headers,
    )
    assert response.status_code == 404
