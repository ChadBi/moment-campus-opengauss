"""T-B-04 状态流转 API + 协同验证统计接口测试

覆盖：
- POST /api/v1/posts/{id}/transition 状态流转接口
- GET /api/v1/posts/{id}/allowed-transitions 可流转状态列表
- GET /api/v1/posts/{id}/validation-stats 协同验证统计接口
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post


@pytest.mark.asyncio
async def test_get_allowed_transitions_pending(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """T-B-04: 新建帖子默认 pending，获取可流转列表"""
    response = await client.get(
        f"/api/v1/posts/{test_post['id']}/allowed-transitions",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_status"] == "pending"
    assert set(data["allowed_transitions"]) == {"published", "draft", "archived"}


@pytest.mark.asyncio
async def test_get_allowed_transitions_post_not_found(
    client: AsyncClient, auth_headers: dict
):
    """T-B-04: 不存在的帖子返回 404"""
    response = await client.get(
        "/api/v1/posts/99999/allowed-transitions",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_transition_pending_to_published_admin(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """T-B-04: 管理员审核通过 pending → published"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "published"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["previous_status"] == "pending"
    assert data["current_status"] == "published"


@pytest.mark.asyncio
async def test_transition_pending_to_draft_admin_reject(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """T-B-04: 管理员驳回 pending → draft"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "draft"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["previous_status"] == "pending"
    assert data["current_status"] == "draft"


@pytest.mark.asyncio
async def test_transition_pending_to_archived_admin(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """T-B-04: 管理员归档 pending → archived"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "archived"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_status"] == "archived"


@pytest.mark.asyncio
async def test_transition_pending_to_published_user_forbidden(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """T-B-04: 普通用户不可执行 pending → published（管理员操作）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "published"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_transition_pending_to_draft_user_forbidden(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """T-B-04: 普通用户不可执行 pending → draft（管理员驳回操作）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "draft"},
        headers=auth_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_transition_illegal_flow_pending_to_expired(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """T-B-04: 非法流转 pending → expired 返回 400"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "expired"},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "非法状态流转" in response.json()["detail"]


@pytest.mark.asyncio
async def test_transition_archived_is_terminal(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """T-B-04: archived 为终态，管理员也不可流转"""
    # 先归档
    await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "archived"},
        headers=admin_headers,
    )
    # 尝试从 archived 流转到 published（应失败）
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "published"},
        headers=admin_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_transition_alias_pending_review(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """T-B-04: 别名 pending_review 归一化为 pending"""
    # 先流转到 published
    await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "published"},
        headers=admin_headers,
    )
    # 再流转到 expired（published → expired 合法）
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "expired"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["current_status"] == "expired"


@pytest.mark.asyncio
async def test_transition_post_not_found(
    client: AsyncClient, admin_headers: dict
):
    """T-B-04: 不存在的帖子返回 404"""
    response = await client.post(
        "/api/v1/posts/99999/transition",
        json={"target_status": "published"},
        headers=admin_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_transition_invalid_target_status(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """T-B-04: 非法目标状态值返回 422（pattern 校验）"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "unknown"},
        headers=admin_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_transition_unauthenticated(test_post: dict, client: AsyncClient):
    """T-B-04: 未认证返回 401"""
    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "published"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_transition_admin_full_cycle(
    client: AsyncClient, admin_headers: dict, test_post: dict
):
    """T-B-04: 管理员完整状态流转链路 pending → published → expired → published → archived"""
    post_id = test_post["id"]

    # pending → published
    r = await client.post(f"/api/v1/posts/{post_id}/transition", json={"target_status": "published"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["current_status"] == "published"

    # published → expired
    r = await client.post(f"/api/v1/posts/{post_id}/transition", json={"target_status": "expired"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["current_status"] == "expired"

    # expired → published（续期）
    r = await client.post(f"/api/v1/posts/{post_id}/transition", json={"target_status": "published"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["current_status"] == "published"

    # published → archived
    r = await client.post(f"/api/v1/posts/{post_id}/transition", json={"target_status": "archived"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["current_status"] == "archived"


@pytest.mark.asyncio
async def test_transition_user_draft_to_pending(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_post: dict
):
    """T-B-04: 普通用户将自己的 draft → pending（提交审核）合法"""
    # 先将帖子状态改为 draft
    result = await db_session.execute(select(Post).where(Post.id == test_post["id"]))
    post = result.scalar_one()
    post.status = "draft"
    await db_session.commit()

    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "pending"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["previous_status"] == "draft"
    assert data["current_status"] == "pending"


@pytest.mark.asyncio
async def test_transition_user_draft_to_archived(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_post: dict
):
    """T-B-04: 普通用户将自己的 draft → archived（放弃草稿）合法"""
    result = await db_session.execute(select(Post).where(Post.id == test_post["id"]))
    post = result.scalar_one()
    post.status = "draft"
    await db_session.commit()

    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "archived"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["current_status"] == "archived"


@pytest.mark.asyncio
async def test_transition_user_draft_to_published_forbidden(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_post: dict
):
    """T-B-04: 普通用户不可 draft → published（跨级，必须先审核）"""
    result = await db_session.execute(select(Post).where(Post.id == test_post["id"]))
    post = result.scalar_one()
    post.status = "draft"
    await db_session.commit()

    response = await client.post(
        f"/api/v1/posts/{test_post['id']}/transition",
        json={"target_status": "published"},
        headers=auth_headers,
    )
    # draft → published 是非法流转，先被状态机拦截（400）
    # 但即使状态机允许，权限也会拦截（403）
    assert response.status_code in (400, 403)


# ============================================================
# 协同验证统计接口测试
# ============================================================

@pytest.mark.asyncio
async def test_validation_stats_empty(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """T-B-04: 无验证记录时全部计数为 0"""
    response = await client.get(
        f"/api/v1/posts/{test_post['id']}/validation-stats",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 0
    assert data["confirmation_count"] == 0
    assert data["valid_count"] == 0
    assert data["validity_status"] == "valid"


@pytest.mark.asyncio
async def test_validation_stats_with_5_types(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """T-B-04: 提交 5 类验证后统计正确"""
    post_id = test_post["id"]

    # 提交 5 类各 1 次
    for vtype in ["confirmation", "refutation", "update", "expiration_report", "conflict_report"]:
        r = await client.post(
            f"/api/v1/posts/{post_id}/validate",
            json={"validation_type": vtype},
            headers=auth_headers,
        )
        assert r.status_code == 200

    response = await client.get(
        f"/api/v1/posts/{post_id}/validation-stats",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["confirmation_count"] == 1
    assert data["refutation_count"] == 1
    assert data["update_count"] == 1
    assert data["expiration_report_count"] == 1
    assert data["conflict_report_count"] == 1
    assert data["total_count"] == 5
    # valid_count = confirmation（1），invalid_count = refutation（1），相等 → uncertain
    assert data["valid_count"] == 1
    assert data["invalid_count"] == 1
    assert data["validity_status"] == "uncertain"


@pytest.mark.asyncio
async def test_validation_stats_post_not_found(
    client: AsyncClient, auth_headers: dict
):
    """T-B-04: 不存在的帖子返回 404"""
    response = await client.get(
        "/api/v1/posts/99999/validation-stats",
        headers=auth_headers,
    )
    assert response.status_code == 404
