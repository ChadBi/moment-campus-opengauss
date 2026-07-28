"""GOV-01: 协同治理完整语义与聚合详情测试

调整后：仅保留 2 类互斥投票（confirmation/refutation）
原 3 类问题报告（update/expiration_report/conflict_report）已移除（与评论/举报冲突）。

覆盖 GOV-01.2 ~ GOV-01.4：
- GOV-01.2: 禁止作者给自己投票；每用户每帖一条（替换语义）
- GOV-01.3: 重复投票限制
- GOV-01.4: 详情显示验证数量/时间/说明
"""
import pytest
from httpx import AsyncClient


# ============================================================
# GOV-01.2: 2 类互斥投票（POST /posts/{id}/validations）
# ============================================================

@pytest.mark.asyncio
async def test_create_confirmation_vote(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 第二用户对帖子投 confirmation（证实）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation", "comment": "信息属实"},
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["validation_type"] == "confirmation"
    assert data["comment"] == "信息属实"
    assert data["user"]["nickname"] == "第二用户"


@pytest.mark.asyncio
async def test_create_refutation_vote(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 第二用户对帖子投 refutation（证伪）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "refutation", "comment": "信息有误"},
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["validation_type"] == "refutation"
    assert data["comment"] == "信息有误"


@pytest.mark.asyncio
async def test_author_cannot_vote_own_post(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """GOV-01.2: 作者不能给自己的帖子投票（403）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_vote_legacy_alias_normalized(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 向后兼容旧值 valid→confirmation / invalid→refutation"""
    # valid → confirmation
    r1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "valid"},
        headers=second_auth_headers,
    )
    assert r1.status_code == 200
    assert r1.json()["validation_type"] == "confirmation"

    # invalid → refutation（替换）
    r2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "invalid"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["validation_type"] == "refutation"


@pytest.mark.asyncio
async def test_vote_replaces_existing(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2: 同一用户对同一帖子第二次投票=替换（同 id，类型更新）"""
    # 第一次 confirmation
    r1 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation", "comment": "第一次"},
        headers=second_auth_headers,
    )
    assert r1.status_code == 200
    first_id = r1.json()["id"]

    # 第二次 refutation（替换）
    r2 = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "refutation", "comment": "第二次"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == first_id  # 同一条记录，id 不变
    assert data["validation_type"] == "refutation"
    assert data["comment"] == "第二次"


@pytest.mark.asyncio
async def test_get_validation_aggregation(
    client: AsyncClient, second_auth_headers: dict, test_post: dict
):
    """GOV-01.2 + GOV-01.4: 聚合投票统计 GET /posts/{id}/validations"""
    # 先投 confirmation
    await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    # 再投 refutation（替换）
    await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "refutation"},
        headers=second_auth_headers,
    )

    response = await client.get(
        f"/api/v1/posts/{test_post['id']}/validations",
        headers=second_auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["post_id"] == test_post["id"]
    assert data["confirmation_count"] == 0  # 被 refutation 替换
    assert data["refutation_count"] == 1
    assert data["total_count"] == 1
    assert data["validity_status"] == "invalid"
    assert len(data["recent_records"]) == 1
    assert data["recent_records"][0]["validation_type"] == "refutation"


@pytest.mark.asyncio
async def test_vote_unauthenticated(client: AsyncClient, test_post: dict):
    """GOV-01.2: 未登录用户投票返回 401"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_vote_nonexistent_post(client: AsyncClient, second_auth_headers: dict):
    """GOV-01.2: 对不存在的帖子投票返回 404"""
    response = await client.post(
        "/api/v1/posts/99999/validations",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    assert response.status_code == 404


# ============================================================
# GOV-01.4: 详情聚合（GET /posts/{id} 返回 governance 字段）
# ============================================================

@pytest.mark.asyncio
async def test_post_detail_includes_governance_summary(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.4: 帖子详情返回 governance 聚合（验证数量）"""
    # 第二用户投票
    await client.post(
        f"/api/v1/posts/{test_post['id']}/validations",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )

    # 获取详情
    resp = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "governance" in data
    gov = data["governance"]
    assert gov is not None
    assert gov["confirmation_count"] >= 1
    assert gov["refutation_count"] >= 0
    assert gov["total_validation_count"] >= 1
    assert gov["validity_status"] in ("valid", "invalid", "uncertain")


@pytest.mark.asyncio
async def test_post_detail_governance_empty_when_no_activity(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """GOV-01.4: 无投票时 governance 聚合返回零值"""
    resp = await client.get(
        f"/api/v1/posts/{test_post['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    assert gov["confirmation_count"] == 0
    assert gov["refutation_count"] == 0
    assert gov["total_validation_count"] == 0


# ============================================================
# GOV-01.4: 投票 E2E 完整链路（confirmation / refutation 替换）
# ============================================================

@pytest.mark.asyncio
async def test_two_types_vote_e2e(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, test_post: dict
):
    """GOV-01.4: 两类投票完整 E2E

    2 类投票：confirmation + refutation（由 second_user 替换切换）
    详情聚合：验证数量/状态正确
    """
    post_id = test_post["id"]

    # === 2 类投票 ===
    # 1) confirmation
    r1 = await client.post(
        f"/api/v1/posts/{post_id}/validations",
        json={"validation_type": "confirmation", "comment": "证实"},
        headers=second_auth_headers,
    )
    assert r1.status_code == 200
    assert r1.json()["validation_type"] == "confirmation"

    # 2) refutation（替换 confirmation）
    r2 = await client.post(
        f"/api/v1/posts/{post_id}/validations",
        json={"validation_type": "refutation", "comment": "证伪"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["validation_type"] == "refutation"

    # === 详情聚合验证 ===
    resp = await client.get(
        f"/api/v1/posts/{post_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    # 投票：second_user 最终是 refutation（替换了 confirmation）
    assert gov["total_validation_count"] == 1
    assert gov["refutation_count"] == 1
    assert gov["confirmation_count"] == 0
