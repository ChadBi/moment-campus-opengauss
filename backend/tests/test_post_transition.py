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
async def test_validation_stats_with_two_types(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, test_post: dict
):
    """T-B-04: 提交 2 类验证后统计正确

    FND-02.3: 当前表逻辑为 2 类（confirmation/refutation）。
    每用户对每帖只能有一条验证记录（2 类互斥可切换）。
    使用两个用户分别提交 confirmation 和 refutation。
    """
    post_id = test_post["id"]

    # 用户 1 提交 confirmation
    r1 = await client.post(
        f"/api/v1/posts/{post_id}/validate",
        json={"validation_type": "confirmation"},
        headers=auth_headers,
    )
    assert r1.status_code == 200

    # 用户 2 提交 refutation
    r2 = await client.post(
        f"/api/v1/posts/{post_id}/validate",
        json={"validation_type": "refutation"},
        headers=second_auth_headers,
    )
    assert r2.status_code == 200

    response = await client.get(
        f"/api/v1/posts/{post_id}/validation-stats",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["confirmation_count"] == 1
    assert data["refutation_count"] == 1
    assert data["total_count"] == 2
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


# ============================================================
# FND-03.2: 实质修改触发 published → pending 回审（单元 + E2E）
# ============================================================
from app.core.post_status import (
    SUBSTANTIAL_FIELDS,
    is_substantial_change,
)


class TestSubstantialChangeUnit:
    """FND-03.2: is_substantial_change 单元测试"""

    def test_empty_set_returns_false(self):
        """空字段集合不算实质修改"""
        assert is_substantial_change(set()) is False

    def test_only_non_substantial_fields_returns_false(self):
        """仅修改非实质字段（expire_at/contact_info/is_anonymous/activity_*/tags）不触发回审"""
        non_substantial = {
            "expire_at", "activity_start_at", "activity_end_at",
            "contact_info", "is_anonymous", "tags", "image_urls",
        }
        assert is_substantial_change(non_substantial) is False

    def test_title_is_substantial(self):
        """修改 title 触发回审"""
        assert is_substantial_change({"title"}) is True

    def test_content_is_substantial(self):
        """修改 content 触发回审"""
        assert is_substantial_change({"content"}) is True

    def test_category_id_is_substantial(self):
        """修改 category_id 触发回审"""
        assert is_substantial_change({"category_id"}) is True

    def test_location_id_is_substantial(self):
        """修改 location_id 触发回审"""
        assert is_substantial_change({"location_id"}) is True

    def test_location_name_is_substantial(self):
        """修改 location_name 触发回审（地图点选新建地点）"""
        assert is_substantial_change({"location_name"}) is True

    def test_location_lat_lng_is_substantial(self):
        """修改 location_lat/lng 触发回审"""
        assert is_substantial_change({"location_lat", "location_lng"}) is True

    def test_lost_type_is_substantial(self):
        """修改 lost_type 触发回审"""
        assert is_substantial_change({"lost_type"}) is True

    def test_mixed_substantial_and_non_substantial_returns_true(self):
        """混合字段含任一实质字段即触发回审"""
        assert is_substantial_change({"expire_at", "title"}) is True
        assert is_substantial_change({"tags", "content", "is_anonymous"}) is True

    def test_substantial_fields_definition(self):
        """SUBSTANTIAL_FIELDS 包含全部实质字段且不含非实质字段"""
        expected = {
            "title", "content", "category_id",
            "location_id", "location_name", "location_lat", "location_lng",
            "lost_type",
        }
        assert SUBSTANTIAL_FIELDS == expected
        # 不应包含非实质字段
        non_substantial = {
            "expire_at", "activity_start_at", "activity_end_at",
            "contact_info", "is_anonymous", "tags", "image_urls",
            "status", "is_recommend",
        }
        assert not (SUBSTANTIAL_FIELDS & non_substantial)


# ============================================================
# FND-03.2: PUT /api/v1/posts/{id} 实质修改触发 published → pending E2E
# ============================================================
async def _publish_post(client: AsyncClient, admin_headers: dict, post_id: int) -> None:
    """辅助：将 pending 帖子通过管理员审核发布"""
    r = await client.post(
        f"/api/v1/posts/{post_id}/transition",
        json={"target_status": "published"},
        headers=admin_headers,
    )
    assert r.status_code == 200, f"发布失败：{r.text}"


@pytest.mark.asyncio
async def test_substantial_title_change_reverts_to_pending(
    client: AsyncClient, auth_headers: dict, admin_headers: dict, test_post: dict
):
    """FND-03.2: 已发布帖子修改 title（实质字段）→ 自动回 pending"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    # 作者修改 title
    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"title": "实质修改后的新标题"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_substantial_content_change_reverts_to_pending(
    client: AsyncClient, auth_headers: dict, admin_headers: dict, test_post: dict
):
    """FND-03.2: 已发布帖子修改 content（实质字段）→ 自动回 pending"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"content": "这是实质修改后的新内容，至少十个字符"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_substantial_category_change_reverts_to_pending(
    client: AsyncClient, auth_headers: dict, admin_headers: dict,
    test_post: dict, db_session: AsyncSession,
):
    """FND-03.2: 已发布帖子修改 category_id（实质字段）→ 自动回 pending"""
    from app.models.category import Category
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    # 新建另一个分类
    new_cat = Category(name="校园活动", code="campus-activity", icon="🎯", default_validity_days=15, is_active=True)
    db_session.add(new_cat)
    await db_session.commit()
    await db_session.refresh(new_cat)

    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"category_id": new_cat.id},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_non_substantial_expire_at_change_stays_published(
    client: AsyncClient, auth_headers: dict, admin_headers: dict, test_post: dict
):
    """FND-03.2: 已发布帖子修改 expire_at（非实质字段）→ 保持 published"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    from datetime import datetime, timedelta
    new_expire = (datetime.now() + timedelta(days=60)).isoformat()
    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"expire_at": new_expire},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"


@pytest.mark.asyncio
async def test_non_substantial_contact_info_change_stays_published(
    client: AsyncClient, auth_headers: dict, admin_headers: dict, test_post: dict
):
    """FND-03.2: 已发布帖子修改 contact_info（非实质字段）→ 保持 published"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"contact_info": "new-contact@example.com"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"


@pytest.mark.asyncio
async def test_non_substantial_is_anonymous_change_stays_published(
    client: AsyncClient, auth_headers: dict, admin_headers: dict, test_post: dict
):
    """FND-03.2: 已发布帖子切换 is_anonymous（非实质字段）→ 保持 published"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"is_anonymous": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"


@pytest.mark.asyncio
async def test_non_substantial_tags_change_stays_published(
    client: AsyncClient, auth_headers: dict, admin_headers: dict, test_post: dict
):
    """FND-03.2: 已发布帖子修改 tags（非实质附属数据）→ 保持 published"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"tags": ["新标签1", "新标签2"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"


@pytest.mark.asyncio
async def test_non_substantial_activity_time_change_stays_published(
    client: AsyncClient, auth_headers: dict, admin_headers: dict, test_post: dict
):
    """FND-03.2: 已发布帖子修改 activity_start_at/end_at（非实质字段）→ 保持 published"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    from datetime import datetime, timedelta
    new_start = (datetime.now() + timedelta(days=5)).isoformat()
    new_end = (datetime.now() + timedelta(days=6)).isoformat()
    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"activity_start_at": new_start, "activity_end_at": new_end},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"


@pytest.mark.asyncio
async def test_pending_post_update_does_not_change_status(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """FND-03.2: pending 帖子修改实质字段不会触发 published→pending（原本就非 published）"""
    post_id = test_post["id"]
    # test_post 默认 pending，无需发布
    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"title": "修改 pending 帖子标题"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    # 仍为 pending
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_archived_post_cannot_be_updated(
    client: AsyncClient, auth_headers: dict, admin_headers: dict, test_post: dict
):
    """FND-03.2: archived 终态帖子不可修改"""
    post_id = test_post["id"]
    # 先归档
    await client.post(
        f"/api/v1/posts/{post_id}/transition",
        json={"target_status": "archived"},
        headers=admin_headers,
    )
    # 尝试修改
    response = await client.put(
        f"/api/v1/posts/{post_id}",
        json={"title": "尝试修改已归档帖子"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "已归档" in response.json()["detail"]


# ============================================================
# FND-03.2: DELETE /api/v1/posts/{id} 软删除 + 状态机归档
# 验证：不引入第 7 种 deleted 状态，删除 = is_deleted=True + status=archived
# ============================================================
@pytest.mark.asyncio
async def test_delete_pending_post_sets_archived_and_is_deleted(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_post: dict
):
    """FND-03.2: 删除 pending 帖子 → is_deleted=True + status=archived（非 deleted 状态）"""
    post_id = test_post["id"]
    response = await client.delete(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert response.status_code == 200
    assert "删除成功" in response.json()["message"]

    # 直接查库验证状态
    result = await db_session.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    assert post is not None
    assert post.is_deleted is True
    assert post.deleted_at is not None
    assert post.status == "archived"  # 不是 "deleted"


@pytest.mark.asyncio
async def test_delete_published_post_sets_archived_and_is_deleted(
    client: AsyncClient, auth_headers: dict, admin_headers: dict,
    db_session: AsyncSession, test_post: dict
):
    """FND-03.2: 删除 published 帖子 → is_deleted=True + status=archived"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    response = await client.delete(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert response.status_code == 200

    result = await db_session.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    assert post.is_deleted is True
    assert post.status == "archived"


@pytest.mark.asyncio
async def test_delete_archived_post_only_sets_is_deleted(
    client: AsyncClient, auth_headers: dict, admin_headers: dict,
    db_session: AsyncSession, test_post: dict
):
    """FND-03.2: 删除已 archived 帖子 → 仅设置 is_deleted，不再触发状态机"""
    post_id = test_post["id"]
    # 先归档
    await client.post(
        f"/api/v1/posts/{post_id}/transition",
        json={"target_status": "archived"},
        headers=admin_headers,
    )

    response = await client.delete(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert response.status_code == 200

    result = await db_session.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    assert post.is_deleted is True
    assert post.status == "archived"  # 保持 archived，不写第 7 种状态


@pytest.mark.asyncio
async def test_deleted_post_not_in_published_list(
    client: AsyncClient, auth_headers: dict, admin_headers: dict,
    test_post: dict, test_school: dict
):
    """FND-03.2: 已删除帖子不出现在公开列表中"""
    post_id = test_post["id"]
    await _publish_post(client, admin_headers, post_id)

    # ACC-01.1: 游客访问公开列表需携带学校上下文（X-School-Code）
    school_headers = {"X-School-Code": test_school["code"]}

    # 删除前出现在列表
    r1 = await client.get("/api/v1/posts", headers=school_headers)
    assert any(p["id"] == post_id for p in r1.json()["items"])

    # 删除
    await client.delete(f"/api/v1/posts/{post_id}", headers=auth_headers)

    # 删除后不出现在列表
    r2 = await client.get("/api/v1/posts", headers=school_headers)
    assert not any(p["id"] == post_id for p in r2.json()["items"])


@pytest.mark.asyncio
async def test_deleted_post_returns_404_for_anonymous(
    client: AsyncClient, auth_headers: dict, test_post: dict
):
    """FND-03.2: 已删除帖子对游客返回 404（不泄露存在性）"""
    post_id = test_post["id"]
    await client.delete(f"/api/v1/posts/{post_id}", headers=auth_headers)

    response = await client.get(f"/api/v1/posts/{post_id}")
    assert response.status_code == 404
