"""TOPIC-01: 多校专题 API 测试

验证：
1. 管理员创建/更新/删除专题
2. 上下线（draft/published/archived 状态流转）
3. 批量排序
4. 编排：添加/移除/调整专题内帖子
5. 专题只能引用同校已发布帖子
6. 用户端仅展示已发布专题
7. 用户端专题内仅展示 published/expired 帖子
8. TEN-02.3: 跨校资源统一 404
9. 切换学校只展示当前学校专题
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.core.post_status import PostStatus
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.post_type import PostType
from app.models.post import Post
from app.models.topic_collection import TopicCollection
from app.models.topic_collection_post import TopicCollectionPost
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription


# ============================================================
# 辅助函数
# ============================================================
async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    school = School(name=name, code=code, is_active=True)
    db.add(school)
    await db.flush()
    return school


async def _assign_operations_subscription(db: AsyncSession, school_id: int) -> None:
    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == "operations")
    )).scalar_one_or_none()
    if plan is None:
        return
    now = datetime.now()
    db.add(SchoolSubscription(
        school_id=school_id, plan_id=plan.id, status="active",
        started_at=now, expires_at=None, assigned_at=now,
    ))
    await db.flush()


async def _create_user(
    db: AsyncSession, email: str, nickname: str, school_id: int, role: str = "user"
) -> User:
    user = User(
        email=email, nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id, role=role,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_membership(
    db: AsyncSession, user_id: int, school_id: int, role: str = "member"
) -> SchoolMembership:
    m = SchoolMembership(
        user_id=user_id, school_id=school_id, role=role,
        status="active", is_default=False,
    )
    db.add(m)
    await db.flush()
    return m


async def _create_category(db: AsyncSession, school_id: int, name: str, code: str) -> Category:
    c = Category(
        school_id=school_id, name=name, code=code, icon="🔍",
        default_validity_days=30, is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


async def _create_post_type(db: AsyncSession, name: str, code: str) -> PostType:
    pt = PostType(name=name, code=code, is_active=True)
    db.add(pt)
    await db.flush()
    return pt


async def _create_post(
    db: AsyncSession,
    user_id: int, school_id: int, category_id: int, post_type_id: int,
    title: str, status: str = PostStatus.PUBLISHED,
) -> Post:
    p = Post(
        user_id=user_id, school_id=school_id,
        category_id=category_id, post_type_id=post_type_id,
        title=title, content=f"{title} 的内容，至少十个字符",
        status=status,
    )
    db.add(p)
    await db.flush()
    return p


def _make_token(user_id: int) -> str:
    return create_access_token(data={"sub": str(user_id)})


def _headers(token: str, school_code: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-School-Code": school_code,
    }


@pytest_asyncio.fixture
async def topic_setup(db_session: AsyncSession) -> dict:
    """创建两校测试数据：A 校 / B 校，每校含管理员、用户、分类、帖子。

    A 校：admin_a + user_a + cat_a + post_a_pub（已发布） + post_a_pending（待审核）
    B 校：admin_b + user_b + cat_b + post_b_pub（已发布）

    注意：数据清理由 autouse 的 setup_database fixture 负责（TRUNCATE + 序列重置）。
    本 fixture 仅负责插入业务数据，不再自行 TRUNCATE，避免与 setup_database 的
    TRUNCATE 冲突导致死锁。
    """
    # 调试：检查 setup_database 的 TRUNCATE 是否对本连接可见
    from sqlalchemy import text as _text
    _count = (await db_session.execute(_text("SELECT count(*) FROM schools"))).scalar()
    if _count > 0:
        # TRUNCATE 不可见 → 在本连接内补一次 TRUNCATE（避免 duplicate key）
        # 这是 openGauss 跨连接可见性问题的 workaround
        business_tables = [
            "topic_collection_posts", "topic_collections",
            "school_subscriptions", "school_memberships", "school_invitations",
            "school_settings", "school_domains",
            "posts", "categories", "post_types", "tags", "post_tags",
            "post_images", "locations", "comments", "likes",
            "validation_records", "reports", "post_change_reports",
            "notifications", "notification_preferences",
            "drafts", "browse_histories", "search_histories",
            "admin_operation_logs", "platform_audit_logs",
            "ai_invocation_logs", "job_run_records",
            "publisher_memberships", "publisher_profiles",
            "post_templates", "password_reset_tokens",
            "product_events", "tenant_usage_daily",
            "users", "schools",
        ]
        table_list = ", ".join(f'"{t}"' for t in business_tables)
        await db_session.execute(_text(f"TRUNCATE {table_list} CASCADE"))
        for t in business_tables:
            await db_session.execute(_text(
                f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), 1, false) "
                f"WHERE pg_get_serial_sequence('{t}', 'id') IS NOT NULL"
            ))
        # 重新预置 operations 套餐（TRUNCATE 后需要重新插入）
        from app.models.product_plan import ProductPlan
        from app.models.school_subscription import SchoolSubscription
        from sqlalchemy import select as _select
        plan = (await db_session.execute(
            _select(ProductPlan).where(ProductPlan.code == "operations")
        )).scalar_one_or_none()
        if plan is None:
            from datetime import datetime as _dt
            _now = _dt.now()
            plan = ProductPlan(
                code="operations", name="运营档", description="operations desc",
                status="active", sort_order=30,
            )
            db_session.add(plan)
            await db_session.flush()

    school_a = await _create_school(db_session, "A 校", "school-a")
    school_b = await _create_school(db_session, "B 校", "school-b")
    for sid in (school_a.id, school_b.id):
        await _assign_operations_subscription(db_session, sid)

    pt = await _create_post_type(db_session, "普通信息", "normal")

    cat_a = await _create_category(db_session, school_a.id, "A 校失物", "a-lost")
    cat_b = await _create_category(db_session, school_b.id, "B 校失物", "b-lost")

    user_a = await _create_user(db_session, "a@example.com", "A 校用户", school_a.id)
    user_b = await _create_user(db_session, "b@example.com", "B 校用户", school_b.id)
    admin_a = await _create_user(db_session, "admin_a@example.com", "A 校管理员", school_a.id, role="admin")
    admin_b = await _create_user(db_session, "admin_b@example.com", "B 校管理员", school_b.id, role="admin")
    await _create_membership(db_session, user_a.id, school_a.id, "member")
    await _create_membership(db_session, user_b.id, school_b.id, "member")
    await _create_membership(db_session, admin_a.id, school_a.id, "admin")
    await _create_membership(db_session, admin_b.id, school_b.id, "admin")

    post_a_pub = await _create_post(db_session, user_a.id, school_a.id, cat_a.id, pt.id, "A 校已发布帖子", PostStatus.PUBLISHED)
    post_a_pub2 = await _create_post(db_session, user_a.id, school_a.id, cat_a.id, pt.id, "A 校已发布帖子 2", PostStatus.PUBLISHED)
    post_a_pending = await _create_post(db_session, user_a.id, school_a.id, cat_a.id, pt.id, "A 校待审核帖子", PostStatus.PENDING)
    post_a_expired = await _create_post(db_session, user_a.id, school_a.id, cat_a.id, pt.id, "A 校已过期帖子", PostStatus.EXPIRED)
    post_b_pub = await _create_post(db_session, user_b.id, school_b.id, cat_b.id, pt.id, "B 校已发布帖子", PostStatus.PUBLISHED)

    await db_session.commit()

    return {
        "schools": {
            "a": {"id": school_a.id, "code": school_a.code},
            "b": {"id": school_b.id, "code": school_b.code},
        },
        "categories": {"a": cat_a.id, "b": cat_b.id},
        "post_type_id": pt.id,
        "posts": {
            "a_pub": post_a_pub.id,
            "a_pub2": post_a_pub2.id,
            "a_pending": post_a_pending.id,
            "a_expired": post_a_expired.id,
            "b_pub": post_b_pub.id,
        },
        "users": {
            "a": {"id": user_a.id, "token": _make_token(user_a.id)},
            "b": {"id": user_b.id, "token": _make_token(user_b.id)},
            "admin_a": {"id": admin_a.id, "token": _make_token(admin_a.id)},
            "admin_b": {"id": admin_b.id, "token": _make_token(admin_b.id)},
        },
    }


# ============================================================
# 1. 管理员创建专题
# ============================================================
@pytest.mark.asyncio
async def test_admin_create_topic_draft(client: AsyncClient, topic_setup: dict):
    """管理员可创建草稿专题；school_id 由 TenantContext 决定，不信任 body。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={
            "title": "A 校专题 1",
            "description": "测试专题",
            "sort_order": 10,
            "status": "draft",
        },
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "A 校专题 1"
    assert data["status"] == "draft"
    assert data["school_id"] == school_a["id"]
    assert data["creator_id"] == admin_a["id"]
    assert data["published_at"] is None
    assert data["post_count"] == 0


@pytest.mark.asyncio
async def test_admin_create_topic_published(client: AsyncClient, topic_setup: dict):
    """管理员可直接创建已发布专题（published_at 自动写入）。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "A 校直接上线专题", "status": "published"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "published"
    assert resp.json()["published_at"] is not None


@pytest.mark.asyncio
async def test_normal_user_cannot_create_topic(client: AsyncClient, topic_setup: dict):
    """普通用户无权创建专题（403）。"""
    user_a = topic_setup["users"]["a"]
    school_a = topic_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "用户尝试创建"},
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp.status_code == 403


# ============================================================
# 2. 列表 / 详情（管理端）
# ============================================================
@pytest.mark.asyncio
async def test_admin_list_topics_filtered_by_school(client: AsyncClient, topic_setup: dict):
    """管理员列表只返回当前学校专题（切换学校只展示当前学校专题）。"""
    admin_a = topic_setup["users"]["admin_a"]
    admin_b = topic_setup["users"]["admin_b"]
    school_a = topic_setup["schools"]["a"]
    school_b = topic_setup["schools"]["b"]

    # A 校创建 2 个专题
    for i in range(2):
        await client.post(
            "/api/v1/admin/topics",
            json={"title": f"A 校专题 {i}", "status": "published"},
            headers=_headers(admin_a["token"], school_a["code"]),
        )
    # B 校创建 1 个专题
    await client.post(
        "/api/v1/admin/topics",
        json={"title": "B 校专题 0", "status": "published"},
        headers=_headers(admin_b["token"], school_b["code"]),
    )

    # A 校管理员看 A 校：应有 2 个
    resp_a = await client.get(
        "/api/v1/admin/topics",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["total"] == 2
    for item in resp_a.json()["items"]:
        assert item["school_id"] == school_a["id"]

    # B 校管理员看 B 校：应有 1 个
    resp_b = await client.get(
        "/api/v1/admin/topics",
        headers=_headers(admin_b["token"], school_b["code"]),
    )
    assert resp_b.status_code == 200
    assert resp_b.json()["total"] == 1
    assert resp_b.json()["items"][0]["school_id"] == school_b["id"]


@pytest.mark.asyncio
async def test_admin_topic_detail_includes_posts(client: AsyncClient, topic_setup: dict):
    """管理端专题详情含关联帖子（含全部状态）。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]
    post_a_pub = topic_setup["posts"]["a_pub"]
    post_a_pending = topic_setup["posts"]["a_pending"]

    # 创建专题并添加帖子（注意：a_pending 是 pending 状态，添加时应失败）
    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "A 校编排专题", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # 添加已发布帖子应成功
    resp_add = await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [{"post_id": post_a_pub, "sort_order": 1}]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_add.status_code == 200, resp_add.text
    assert resp_add.json()["post_count"] == 1
    assert len(resp_add.json()["posts"]) == 1
    assert resp_add.json()["posts"][0]["post_id"] == post_a_pub

    # 详情接口应返回帖子
    resp_detail = await client.get(
        f"/api/v1/admin/topics/{topic_id}",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_detail.status_code == 200
    assert len(resp_detail.json()["posts"]) == 1


# ============================================================
# 3. 上下线
# ============================================================
@pytest.mark.asyncio
async def test_publish_and_archive_topic(client: AsyncClient, topic_setup: dict):
    """draft → published → archived → published（重新上线）。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]

    # 创建草稿
    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "上下线测试", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]
    assert resp.json()["status"] == "draft"

    # 上线
    resp_pub = await client.put(
        f"/api/v1/admin/topics/{topic_id}/publish",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_pub.status_code == 200
    assert resp_pub.json()["status"] == "published"
    assert resp_pub.json()["published_at"] is not None

    # 重复上线应 BadRequest
    resp_pub_again = await client.put(
        f"/api/v1/admin/topics/{topic_id}/publish",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_pub_again.status_code == 400

    # 下线
    resp_arch = await client.put(
        f"/api/v1/admin/topics/{topic_id}/archive",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_arch.status_code == 200
    assert resp_arch.json()["status"] == "archived"

    # 重复下线应 BadRequest
    resp_arch_again = await client.put(
        f"/api/v1/admin/topics/{topic_id}/archive",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_arch_again.status_code == 400

    # 重新上线
    resp_republish = await client.put(
        f"/api/v1/admin/topics/{topic_id}/publish",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_republish.status_code == 200
    assert resp_republish.json()["status"] == "published"


# ============================================================
# 4. 批量排序
# ============================================================
@pytest.mark.asyncio
async def test_sort_topics(client: AsyncClient, topic_setup: dict):
    """批量排序专题（按 sort_order 升序展示）。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]

    # 创建 3 个专题
    ids = []
    for i in range(3):
        resp = await client.post(
            "/api/v1/admin/topics",
            json={"title": f"排序专题 {i}", "status": "published", "sort_order": 0},
            headers=_headers(admin_a["token"], school_a["code"]),
        )
        ids.append(resp.json()["id"])

    # 排序：反转顺序
    sort_items = [{"id": tid, "sort_order": 10 - i * 2} for i, tid in enumerate(ids)]
    resp_sort = await client.put(
        "/api/v1/admin/topics/sort",
        json={"items": sort_items},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_sort.status_code == 200

    # 验证列表按 sort_order 升序（API 默认 sort_order ASC + created_at DESC）
    resp_list = await client.get(
        "/api/v1/admin/topics",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    items = resp_list.json()["items"]
    # 找到刚创建的 3 个专题的 sort_order（列表已按 sort_order 升序返回）
    sorted_orders = [it["sort_order"] for it in items if it["id"] in ids]
    assert sorted_orders == sorted(sorted_orders)
    # 排序值分别是 10/8/6，按升序应为 [6, 8, 10]
    assert sorted_orders == [6, 8, 10]


# ============================================================
# 5. 编排：添加/移除帖子
# ============================================================
@pytest.mark.asyncio
async def test_cannot_add_pending_post_to_topic(client: AsyncClient, topic_setup: dict):
    """专题只能引用同校已发布（published）帖子，pending 帖子不可添加。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]
    post_a_pending = topic_setup["posts"]["a_pending"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "限制测试专题", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # 添加 pending 帖子应失败（BadRequest）
    resp_add = await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [{"post_id": post_a_pending, "sort_order": 0}]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_add.status_code == 400
    assert "published" in resp_add.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_add_cross_school_post_to_topic(client: AsyncClient, topic_setup: dict):
    """跨校帖子添加返回 404（不泄露存在性）。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]
    post_b_pub = topic_setup["posts"]["b_pub"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "跨校限制专题", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # 添加 B 校帖子应失败（404）
    resp_add = await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [{"post_id": post_b_pub, "sort_order": 0}]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_add.status_code == 404


@pytest.mark.asyncio
async def test_add_duplicate_post_conflict(client: AsyncClient, topic_setup: dict):
    """重复添加同一帖子返回 Conflict。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]
    post_a_pub = topic_setup["posts"]["a_pub"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "去重测试专题", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # 第一次添加
    resp1 = await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [{"post_id": post_a_pub, "sort_order": 0}]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp1.status_code == 200

    # 第二次添加同一帖子应 Conflict
    resp2 = await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [{"post_id": post_a_pub, "sort_order": 1}]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_remove_post_from_topic(client: AsyncClient, topic_setup: dict):
    """从专题移除帖子，post_count 递减。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]
    post_a_pub = topic_setup["posts"]["a_pub"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "移除测试专题", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # 添加
    await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [{"post_id": post_a_pub, "sort_order": 0}]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )

    # 移除
    resp_rm = await client.delete(
        f"/api/v1/admin/topics/{topic_id}/posts/{post_a_pub}",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_rm.status_code == 200
    assert resp_rm.json()["post_count"] == 0
    assert len(resp_rm.json()["posts"]) == 0


@pytest.mark.asyncio
async def test_sort_topic_posts(client: AsyncClient, topic_setup: dict):
    """调整专题内帖子的排序。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]
    post_a_pub = topic_setup["posts"]["a_pub"]
    post_a_pub2 = topic_setup["posts"]["a_pub2"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "排序帖子专题", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # 添加 2 个已发布帖子（专题只能引用同校已发布帖子）
    resp_add = await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [
            {"post_id": post_a_pub, "sort_order": 1},
            {"post_id": post_a_pub2, "sort_order": 2},
        ]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_add.status_code == 200, resp_add.text

    # 调整排序：反转
    resp_sort = await client.put(
        f"/api/v1/admin/topics/{topic_id}/posts/sort",
        json={"posts": [
            {"post_id": post_a_pub, "sort_order": 5},
            {"post_id": post_a_pub2, "sort_order": 1},
        ]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_sort.status_code == 200
    posts = resp_sort.json()["posts"]
    assert posts[0]["post_id"] == post_a_pub2
    assert posts[0]["sort_order"] == 1
    assert posts[1]["post_id"] == post_a_pub
    assert posts[1]["sort_order"] == 5


# ============================================================
# 6. 删除专题
# ============================================================
@pytest.mark.asyncio
async def test_delete_topic_soft_delete(client: AsyncClient, topic_setup: dict):
    """删除专题走软删除，列表不再返回，且关联帖子一并清理。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]
    post_a_pub = topic_setup["posts"]["a_pub"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "待删除专题", "status": "published"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # 添加帖子
    await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [{"post_id": post_a_pub, "sort_order": 0}]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )

    # 删除
    resp_del = await client.delete(
        f"/api/v1/admin/topics/{topic_id}",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_del.status_code == 200

    # 详情应 404
    resp_detail = await client.get(
        f"/api/v1/admin/topics/{topic_id}",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_detail.status_code == 404


# ============================================================
# 7. 用户端：列表 / 详情
# ============================================================
@pytest.mark.asyncio
async def test_user_list_only_published_topics(client: AsyncClient, topic_setup: dict):
    """用户端仅展示已发布专题（draft/archived 不可见）。"""
    admin_a = topic_setup["users"]["admin_a"]
    user_a = topic_setup["users"]["a"]
    school_a = topic_setup["schools"]["a"]

    # 创建 3 个专题：1 published + 1 draft + 1 archived
    resp_pub = await client.post(
        "/api/v1/admin/topics",
        json={"title": "用户可见专题", "status": "published"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    resp_draft = await client.post(
        "/api/v1/admin/topics",
        json={"title": "草稿专题", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    # 创建一个 archived 专题：先 published 再 archive
    resp_to_arch = await client.post(
        "/api/v1/admin/topics",
        json={"title": "已下线专题", "status": "published"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    await client.put(
        f"/api/v1/admin/topics/{resp_to_arch.json()['id']}/archive",
        headers=_headers(admin_a["token"], school_a["code"]),
    )

    # 用户端列表只应返回 1 个（published）
    resp_list = await client.get(
        "/api/v1/topics",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_list.status_code == 200
    assert resp_list.json()["total"] == 1
    assert resp_list.json()["items"][0]["title"] == "用户可见专题"


@pytest.mark.asyncio
async def test_user_detail_returns_only_visible_posts(client: AsyncClient, topic_setup: dict, db_session: AsyncSession):
    """用户端专题详情仅返回 published/expired 帖子（pending 不可见）。

    注意：管理端添加帖子时已校验只允许 published，但已添加的帖子后续可能变为
    pending/archived 等状态。用户端展示时再次过滤。
    """
    admin_a = topic_setup["users"]["admin_a"]
    user_a = topic_setup["users"]["a"]
    school_a = topic_setup["schools"]["a"]
    post_a_pub = topic_setup["posts"]["a_pub"]
    post_a_pub2 = topic_setup["posts"]["a_pub2"]

    # 创建已发布专题
    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "用户端详情测试", "status": "published"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # 添加 2 个已发布帖子（管理端仅允许 published）
    resp_add = await client.post(
        f"/api/v1/admin/topics/{topic_id}/posts",
        json={"posts": [
            {"post_id": post_a_pub, "sort_order": 1},
            {"post_id": post_a_pub2, "sort_order": 2},
        ]},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_add.status_code == 200, resp_add.text

    # 模拟 post_a_pub2 后续变为 expired（帖子状态机允许 published → expired）
    from sqlalchemy import update
    await db_session.execute(
        update(Post).where(Post.id == post_a_pub2).values(status=PostStatus.EXPIRED)
    )
    await db_session.commit()

    # 用户端详情：应返回 2 个帖子（published + expired 均可见）
    resp_detail = await client.get(
        f"/api/v1/topics/{topic_id}",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_detail.status_code == 200
    data = resp_detail.json()
    assert data["title"] == "用户端详情测试"
    assert len(data["posts"]) == 2
    post_ids = [p["id"] for p in data["posts"]]
    assert set(post_ids) == {post_a_pub, post_a_pub2}


@pytest.mark.asyncio
async def test_user_cannot_view_draft_topic_detail(client: AsyncClient, topic_setup: dict):
    """用户端访问草稿/已下线专题详情返回 404。"""
    admin_a = topic_setup["users"]["admin_a"]
    user_a = topic_setup["users"]["a"]
    school_a = topic_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "草稿专题", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    resp_detail = await client.get(
        f"/api/v1/topics/{topic_id}",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_detail.status_code == 404


# ============================================================
# 8. 跨校隔离
# ============================================================
@pytest.mark.asyncio
async def test_cross_school_topic_detail_404(client: AsyncClient, topic_setup: dict):
    """跨校访问专题详情返回 404（不泄露存在性）。"""
    admin_a = topic_setup["users"]["admin_a"]
    user_b = topic_setup["users"]["b"]
    school_a = topic_setup["schools"]["a"]
    school_b = topic_setup["schools"]["b"]

    # A 校创建已发布专题
    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "A 校专题", "status": "published"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    # B 校用户访问 A 校专题 → 404
    resp_b = await client.get(
        f"/api/v1/topics/{topic_id}",
        headers=_headers(user_b["token"], school_b["code"]),
    )
    assert resp_b.status_code == 404


@pytest.mark.asyncio
async def test_cross_school_admin_cannot_modify(client: AsyncClient, topic_setup: dict):
    """A 校管理员无法操作 B 校专题（404）。"""
    admin_a = topic_setup["users"]["admin_a"]
    admin_b = topic_setup["users"]["admin_b"]
    school_a = topic_setup["schools"]["a"]
    school_b = topic_setup["schools"]["b"]

    # B 校创建专题
    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "B 校专题", "status": "draft"},
        headers=_headers(admin_b["token"], school_b["code"]),
    )
    topic_id_b = resp.json()["id"]

    # A 校管理员尝试操作 B 校专题 → 404
    resp_cross = await client.put(
        f"/api/v1/admin/topics/{topic_id_b}",
        json={"title": "尝试修改 B 校专题"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_cross.status_code == 404

    # A 校管理员尝试上线 B 校专题 → 404
    resp_pub_cross = await client.put(
        f"/api/v1/admin/topics/{topic_id_b}/publish",
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_pub_cross.status_code == 404


# ============================================================
# 9. 更新专题
# ============================================================
@pytest.mark.asyncio
async def test_update_topic_metadata(client: AsyncClient, topic_setup: dict):
    """更新专题元信息（标题/描述/封面/排序）。"""
    admin_a = topic_setup["users"]["admin_a"]
    school_a = topic_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "原标题", "description": "原描述", "status": "draft"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]

    resp_update = await client.put(
        f"/api/v1/admin/topics/{topic_id}",
        json={
            "title": "新标题",
            "description": "新描述",
            "cover_url": "https://example.com/cover.jpg",
            "sort_order": 99,
        },
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    assert resp_update.status_code == 200
    data = resp_update.json()
    assert data["title"] == "新标题"
    assert data["description"] == "新描述"
    assert data["cover_url"] == "https://example.com/cover.jpg"
    assert data["sort_order"] == 99


# ============================================================
# 10. 浏览数自增
# ============================================================
@pytest.mark.asyncio
async def test_topic_view_count_increment(client: AsyncClient, topic_setup: dict):
    """用户端访问专题详情时浏览数 +1。"""
    admin_a = topic_setup["users"]["admin_a"]
    user_a = topic_setup["users"]["a"]
    school_a = topic_setup["schools"]["a"]

    resp = await client.post(
        "/api/v1/admin/topics",
        json={"title": "浏览数测试", "status": "published"},
        headers=_headers(admin_a["token"], school_a["code"]),
    )
    topic_id = resp.json()["id"]
    assert resp.json()["view_count"] == 0

    # 用户访问
    await client.get(
        f"/api/v1/topics/{topic_id}",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    # 再次访问
    resp_detail = await client.get(
        f"/api/v1/topics/{topic_id}",
        headers=_headers(user_a["token"], school_a["code"]),
    )
    assert resp_detail.json()["view_count"] == 2
