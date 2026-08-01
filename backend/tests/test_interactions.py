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


# ============================================================
# 协同验证（2 类互斥、可切换、可取消）
# ============================================================

@pytest.mark.asyncio
async def test_validate_post_created(client: AsyncClient, second_auth_headers: dict, test_post: dict):
    """首次验证返回 created 和当前聚合。"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation", "comment": "确认有效"},
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["validation_type"] == "confirmation"
    assert data["action"] == "created"
    assert data["current_validation_type"] == "confirmation"
    assert data["confirmation_count"] == 1
    assert data["refutation_count"] == 0
    assert data["comment"] == "确认有效"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_validate_post_switch_type(client: AsyncClient, second_auth_headers: dict, test_post: dict):
    """异类再次提交原地切换并返回 switched。"""
    r1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    assert r1.status_code == 200
    assert r1.json()["validation_type"] == "confirmation"

    r2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "refutation"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == r1.json()["id"]
    assert data["action"] == "switched"
    assert data["current_validation_type"] == "refutation"
    assert data["confirmation_count"] == 0
    assert data["refutation_count"] == 1


@pytest.mark.asyncio
async def test_validate_post_cancel_by_repeat(client: AsyncClient, second_auth_headers: dict, test_post: dict):
    """同类再次提交取消，并用显式状态表示删除。"""
    await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "removed"
    assert data["current_validation_type"] is None
    assert data["confirmation_count"] == 0
    assert data["refutation_count"] == 0


@pytest.mark.asyncio
async def test_cancel_preserves_other_users_count(
    client: AsyncClient,
    db_session,
    test_user: dict,
    second_user: dict,
    second_auth_headers: dict,
    test_post: dict,
):
    from app.models.post import Post
    from app.models.validation_record import ValidationRecord
    from app.core.security import decode_token
    from sqlalchemy import select

    author_id = int(decode_token(test_user["access_token"])["sub"])
    voter_id = int(decode_token(second_user["access_token"])["sub"])

    db_session.add_all(
        [
            ValidationRecord(
                post_id=test_post["id"],
                user_id=author_id,
                validation_type="confirmation",
            ),
            ValidationRecord(
                post_id=test_post["id"],
                user_id=voter_id,
                validation_type="confirmation",
            ),
        ]
    )
    post = (await db_session.execute(select(Post).where(Post.id == test_post["id"]))).scalar_one()
    post.valid_count = 2
    await db_session.commit()

    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["action"] == "removed"
    assert response.json()["confirmation_count"] == 1


@pytest.mark.asyncio
async def test_author_cannot_validate_own_post(client: AsyncClient, auth_headers: dict, test_post: dict):
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    assert response.status_code == 403

    detail = await client.get(f"/api/v1/posts/{test_post['id']}", headers=auth_headers)
    assert detail.json()["governance"]["total_validation_count"] == 0


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
async def test_validate_post_deprecated_type_rejected(client: AsyncClient, auth_headers: dict, test_post: dict):
    """所有非正式验证类型均由 Schema 返回 422。"""
    for vtype in ("update", "expiration_report", "conflict_report", "valid", "invalid", "uncertain"):
        response = await client.post(
            f"/api/v1/posts/{test_post['id']}/validate",
            json={"validation_type": vtype},
            headers=auth_headers,
        )
        assert response.status_code == 422, f"废弃类型 {vtype} 应被拒绝"


@pytest.mark.asyncio
async def test_validate_post_unauthenticated(client: AsyncClient, test_post: dict):
    """Test validating a post without authentication returns 401."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_validate_nonexistent_post(client: AsyncClient, auth_headers: dict):
    """Test validating a non-existent post returns 404."""
    response = await client.post(
        "/api/v1/posts/99999/validate",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    assert response.status_code == 404
