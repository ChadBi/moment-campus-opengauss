"""PRF-01: 个人中心、草稿、真实统计、未读与浏览历史 测试

覆盖 PRF-01.1 / PRF-01.2 / PRF-01.3 三个子任务的后端契约：

1. **PRF-01.2 真实统计**：GET /users/me/stats
   - 按状态分组的帖子数（published/draft/pending/expired/conflict/archived/total）
   - 贡献验证数（confirmation 类型 ValidationRecord 计数）
   - 按当前学校过滤（跨校帖子/验证不计入）

2. **PRF-01.2 未读通知数**：GET /notifications/unread-count
   - 返回 unread_count 与 has_unread
   - 仅统计当前用户的未读通知（user_id 隔离）

3. **PRF-01.3 浏览历史**：
   - 帖子详情访问写入 BrowseHistory（带 school_id 隔离）
   - 同一用户在同一学校对同一帖子只保留一条记录（再次访问更新 viewed_at）
   - GET /users/me/view-history 按当前学校过滤
   - DELETE /users/me/view-history 清除当前学校全部历史
   - DELETE /users/me/view-history/{post_id} 删除单条历史
   - 跨校访问其它学校的历史 → 404（不泄露存在性）

4. **PRF-01.1 我的帖子按状态筛选**：
   - GET /users/me/posts?status= 按当前学校过滤
   - 已在 test_pub02_draft_review_flow.py 覆盖，本文件补充跨校隔离校验
"""
import pytest
import pytest_asyncio
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.post_status import PostStatus
from app.core.security import create_access_token, get_password_hash
from app.models.browse_history import BrowseHistory
from app.models.category import Category
from app.models.location import Location
from app.models.notification import Notification
from app.models.post import Post
from app.models.product_plan import ProductPlan
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.school_subscription import SchoolSubscription
from app.models.user import User
from app.models.validation_record import ValidationRecord


# ============================================================
# 辅助函数：创建两校测试数据（用于跨校隔离测试）
# ============================================================
async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    school = School(name=name, code=code, is_active=True)
    db.add(school)
    await db.flush()
    return school


async def _assign_operations_subscription(db: AsyncSession, school_id: int) -> None:
    """为学校分配 operations 档订阅（避免 EntitlementService 校验拒绝）"""
    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == "operations")
    )).scalar_one_or_none()
    if plan is None:
        return
    now = datetime.now()
    sub = SchoolSubscription(
        school_id=school_id,
        plan_id=plan.id,
        status="active",
        started_at=now,
        expires_at=None,
        assigned_at=now,
    )
    db.add(sub)
    await db.flush()


async def _create_user(
    db: AsyncSession, email: str, nickname: str, school_id: int, role: str = "user"
) -> User:
    user = User(
        email=email,
        nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id,
        role=role,
        campus_verified=True,  # D4 门禁：默认已认证
    )
    db.add(user)
    await db.flush()
    return user


async def _create_membership(
    db: AsyncSession, user_id: int, school_id: int, role: str = "member",
    is_default: bool = False,
) -> SchoolMembership:
    membership = SchoolMembership(
        user_id=user_id,
        school_id=school_id,
        role=role,
        status="active",
        is_default=is_default,
    )
    db.add(membership)
    await db.flush()
    return membership


async def _create_category(db: AsyncSession, school_id: int, name: str, code: str) -> Category:
    category = Category(
        school_id=school_id,
        name=name,
        code=code,
        icon="🔍",
        default_validity_days=30,
        is_active=True,
    )
    db.add(category)
    await db.flush()
    return category


async def _create_post(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    category_id: int,
    title: str,
    status: str = PostStatus.PUBLISHED,
) -> Post:
    post = Post(
        user_id=user_id,
        school_id=school_id,
        category_id=category_id,
        title=title,
        content=f"{title} 的内容，至少十个字符",
        status=status,
    )
    db.add(post)
    await db.flush()
    return post


async def _create_notification(
    db: AsyncSession,
    user_id: int,
    type: str = "audit",
    title: str = "测试通知",
    is_read: bool = False,
) -> Notification:
    n = Notification(
        user_id=user_id,
        type=type,
        title=title,
        is_read=is_read,
    )
    db.add(n)
    await db.flush()
    return n


def _make_token(user_id: int) -> str:
    return create_access_token(data={"sub": str(user_id)})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _school(code: str) -> dict:
    return {"X-School-Code": code}


@pytest_asyncio.fixture
async def two_schools_setup() -> dict:
    """创建两校测试数据，每校 1 用户 + 1 分类 + 多状态帖子

    用于 PRF-01.2 / PRF-01.3 跨校隔离测试。
    user_ab 同时是 A 校和 B 校成员，便于切换学校视角测试。

    注意：使用独立 session（test_session_maker）进行数据预置，commit 后立即关闭，
    避免 openGauss 跨连接可见性问题（db_session 长连接会阻塞 API 侧查询）。
    """
    from tests.conftest import test_session_maker

    async with test_session_maker() as session:
        school_a = await _create_school(session, "甲校", "school-a")
        school_b = await _create_school(session, "乙校", "school-b")

        for sid in (school_a.id, school_b.id):
            await _assign_operations_subscription(session, sid)

        cat_a = await _create_category(session, school_a.id, "甲校失物", "a-lost")
        cat_b = await _create_category(session, school_b.id, "乙校失物", "b-lost")

        # user_a：甲校默认成员（默认学校 = 甲校）
        user_a = await _create_user(session, "a@example.com", "甲校用户", school_a.id)
        await _create_membership(
            session, user_a.id, school_a.id, "member", is_default=True
        )

        # user_b：乙校默认成员
        user_b = await _create_user(session, "b@example.com", "乙校用户", school_b.id)
        await _create_membership(
            session, user_b.id, school_b.id, "member", is_default=True
        )

        # user_ab：super_admin（UC-01 一对一，普通用户仅一条 active membership；
        # super_admin 可跨校访问，用于浏览历史跨校隔离测试）
        user_ab = await _create_user(session, "ab@example.com", "双校用户", school_a.id, role="super_admin")
        await _create_membership(
            session, user_ab.id, school_a.id, "member", is_default=True
        )

        # 甲校帖子：1 published + 1 draft + 1 pending + 1 expired
        post_a_pub = await _create_post(
            session, user_a.id, school_a.id, cat_a.id,
            "甲校已发布帖子", PostStatus.PUBLISHED,
        )
        post_a_draft = await _create_post(
            session, user_a.id, school_a.id, cat_a.id,
            "甲校草稿帖子", PostStatus.DRAFT,
        )
        post_a_pending = await _create_post(
            session, user_a.id, school_a.id, cat_a.id,
            "甲校待审核帖子", PostStatus.PENDING,
        )
        post_a_expired = await _create_post(
            session, user_a.id, school_a.id, cat_a.id,
            "甲校已过期帖子", PostStatus.EXPIRED,
        )

        # 乙校帖子：1 published + 1 draft（用于验证跨校不计入统计）
        post_b_pub = await _create_post(
            session, user_b.id, school_b.id, cat_b.id,
            "乙校已发布帖子", PostStatus.PUBLISHED,
        )
        post_b_draft = await _create_post(
            session, user_b.id, school_b.id, cat_b.id,
            "乙校草稿帖子", PostStatus.DRAFT,
        )

        await session.commit()

        result = {
            "schools": {
                "a": {"id": school_a.id, "code": school_a.code, "name": school_a.name},
                "b": {"id": school_b.id, "code": school_b.code, "name": school_b.name},
            },
            "users": {
                "a": {"id": user_a.id, "token": _make_token(user_a.id)},
                "b": {"id": user_b.id, "token": _make_token(user_b.id)},
                "ab": {"id": user_ab.id, "token": _make_token(user_ab.id)},
            },
            "posts": {
                "a_pub": {"id": post_a_pub.id, "school_id": school_a.id, "status": PostStatus.PUBLISHED},
                "a_draft": {"id": post_a_draft.id, "school_id": school_a.id, "status": PostStatus.DRAFT},
                "a_pending": {"id": post_a_pending.id, "school_id": school_a.id, "status": PostStatus.PENDING},
                "a_expired": {"id": post_a_expired.id, "school_id": school_a.id, "status": PostStatus.EXPIRED},
                "b_pub": {"id": post_b_pub.id, "school_id": school_b.id, "status": PostStatus.PUBLISHED},
                "b_draft": {"id": post_b_draft.id, "school_id": school_b.id, "status": PostStatus.DRAFT},
            },
            "category_ids": {"a": cat_a.id, "b": cat_b.id},
        }
    # session 已关闭，连接已释放，避免阻塞 API 侧查询
    return result


# ============================================================
# PRF-01.2: GET /users/me/stats 真实统计
# ============================================================
class TestMyStats:
    """PRF-01.2: /users/me/stats 真实统计接口"""

    @pytest.mark.asyncio
    async def test_stats_returns_correct_counts_by_status(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """统计接口返回各状态真实计数（按当前学校过滤）"""
        setup = two_schools_setup
        user_a_token = setup["users"]["a"]["token"]
        school_a_code = setup["schools"]["a"]["code"]

        # user_a 在甲校有 4 个帖子：1 published + 1 draft + 1 pending + 1 expired
        r = await client.get(
            "/api/v1/users/me/stats",
            headers={**_auth(user_a_token), **_school(school_a_code)},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["school_id"] == setup["schools"]["a"]["id"]
        assert data["published_count"] == 1
        assert data["draft_count"] == 1
        assert data["pending_count"] == 1
        assert data["expired_count"] == 1
        assert data["conflict_count"] == 0
        assert data["archived_count"] == 0
        assert data["total_count"] == 4
        assert data["confirmation_count"] == 0

    @pytest.mark.asyncio
    async def test_stats_filters_by_current_school(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.2 + TEN-02.3：统计按当前学校过滤，跨校帖子不计入"""
        setup = two_schools_setup
        # 给 user_a 在乙校也加一个 published 帖子（跨校）
        # 注意：user_a 不是乙校成员，这里直接 DB 写入模拟历史数据
        post_b_for_a = await _create_post(
            db_session,
            user_id=setup["users"]["a"]["id"],
            school_id=setup["schools"]["b"]["id"],
            category_id=setup["category_ids"]["b"],
            title="user_a 在乙校的帖子",
            status=PostStatus.PUBLISHED,
        )
        await db_session.commit()

        # user_a 切换到甲校视角：不应计入乙校帖子
        r = await client.get(
            "/api/v1/users/me/stats",
            headers={
                **_auth(setup["users"]["a"]["token"]),
                **_school(setup["schools"]["a"]["code"]),
            },
        )
        assert r.status_code == 200
        data = r.json()
        # 甲校仍是 1 published（乙校的不计入）
        assert data["published_count"] == 1
        assert data["total_count"] == 4

    @pytest.mark.asyncio
    async def test_stats_confirmation_count_excludes_refutation(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.2: 贡献验证数只统计 confirmation，不含 refutation"""
        setup = two_schools_setup
        user_a_id = setup["users"]["a"]["id"]
        user_b_id = setup["users"]["b"]["id"]
        post_a_pub_id = setup["posts"]["a_pub"]["id"]
        school_a_code = setup["schools"]["a"]["code"]

        # 给甲校已发布帖子加 2 个 confirmation + 1 个 refutation
        db_session.add(ValidationRecord(
            post_id=post_a_pub_id, user_id=user_b_id,
            validation_type="confirmation", comment="确认有效",
        ))
        db_session.add(ValidationRecord(
            post_id=post_a_pub_id, user_id=setup["users"]["ab"]["id"],
            validation_type="confirmation", comment="我也确认",
        ))
        # refutation 不应计入 confirmation_count
        # 注意：每用户对每帖只能有一条记录（unique 约束），需用另一用户
        db_session.add(ValidationRecord(
            post_id=post_a_pub_id, user_id=user_a_id,
            validation_type="refutation", comment="我觉得无效",
        ))
        await db_session.commit()

        r = await client.get(
            "/api/v1/users/me/stats",
            headers={**_auth(setup["users"]["a"]["token"]), **_school(school_a_code)},
        )
        assert r.status_code == 200
        data = r.json()
        # user_a 的甲校已发布帖子收到 2 票 confirmation（不含自己投的 refutation）
        assert data["confirmation_count"] == 2

    @pytest.mark.asyncio
    async def test_stats_requires_auth(self, client: AsyncClient, two_schools_setup: dict):
        """未登录访问 /users/me/stats 返回 401"""
        r = await client.get(
            "/api/v1/users/me/stats",
            headers=_school(two_schools_setup["schools"]["a"]["code"]),
        )
        assert r.status_code == 401


# ============================================================
# PRF-01.2: GET /notifications/unread-count 未读数
# ============================================================
class TestUnreadCount:
    """PRF-01.2: /notifications/unread-count 未读通知数量"""

    @pytest.mark.asyncio
    async def test_unread_count_returns_zero_when_no_notifications(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """无通知时返回 unread_count=0, has_unread=False"""
        setup = two_schools_setup
        r = await client.get(
            "/api/v1/notifications/unread-count",
            headers={**_auth(setup["users"]["a"]["token"]), **_school(setup["schools"]["a"]["code"])},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["unread_count"] == 0
        assert data["has_unread"] is False

    @pytest.mark.asyncio
    async def test_unread_count_returns_correct_value(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """有未读通知时返回正确数量"""
        setup = two_schools_setup
        user_a_id = setup["users"]["a"]["id"]

        # 创建 3 条未读 + 1 条已读
        await _create_notification(db_session, user_a_id, "audit", "未读1", is_read=False)
        await _create_notification(db_session, user_a_id, "comment", "未读2", is_read=False)
        await _create_notification(db_session, user_a_id, "system", "未读3", is_read=False)
        await _create_notification(db_session, user_a_id, "audit", "已读1", is_read=True)
        await db_session.commit()

        r = await client.get(
            "/api/v1/notifications/unread-count",
            headers={**_auth(setup["users"]["a"]["token"]), **_school(setup["schools"]["a"]["code"])},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["unread_count"] == 3
        assert data["has_unread"] is True

    @pytest.mark.asyncio
    async def test_unread_count_isolated_by_user(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.2: 未读数按 user_id 隔离，A 的通知不计入 B"""
        setup = two_schools_setup
        user_a_id = setup["users"]["a"]["id"]
        user_b_id = setup["users"]["b"]["id"]

        # 给 user_a 创建 2 条未读
        await _create_notification(db_session, user_a_id, "audit", "A 的未读1", is_read=False)
        await _create_notification(db_session, user_a_id, "audit", "A 的未读2", is_read=False)
        await db_session.commit()

        # user_b 应该是 0
        r = await client.get(
            "/api/v1/notifications/unread-count",
            headers={**_auth(setup["users"]["b"]["token"]), **_school(setup["schools"]["b"]["code"])},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["unread_count"] == 0
        assert data["has_unread"] is False

    @pytest.mark.asyncio
    async def test_unread_count_excludes_deleted(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.2: 软删除的通知不计入未读数"""
        setup = two_schools_setup
        user_a_id = setup["users"]["a"]["id"]

        # 1 条正常未读 + 1 条软删除未读
        await _create_notification(db_session, user_a_id, "audit", "正常未读", is_read=False)
        deleted_n = await _create_notification(db_session, user_a_id, "audit", "已删除未读", is_read=False)
        deleted_n.is_deleted = True
        deleted_n.deleted_at = datetime.now()
        await db_session.commit()

        r = await client.get(
            "/api/v1/notifications/unread-count",
            headers={**_auth(setup["users"]["a"]["token"]), **_school(setup["schools"]["a"]["code"])},
        )
        assert r.status_code == 200
        assert r.json()["unread_count"] == 1

    @pytest.mark.asyncio
    async def test_unread_count_requires_auth(self, client: AsyncClient, two_schools_setup: dict):
        """未登录访问返回 401"""
        r = await client.get(
            "/api/v1/notifications/unread-count",
            headers=_school(two_schools_setup["schools"]["a"]["code"]),
        )
        assert r.status_code == 401


# ============================================================
# PRF-01.3: 浏览历史 - 详情访问写入 + 学校隔离
# ============================================================
class TestBrowseHistoryTracking:
    """PRF-01.3: 帖子详情访问写入 BrowseHistory（按学校隔离）"""

    @pytest.mark.asyncio
    async def test_viewing_post_creates_browse_history(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """登录用户访问帖子详情 → 写入 BrowseHistory（带 school_id）"""
        setup = two_schools_setup
        post_a_pub_id = setup["posts"]["a_pub"]["id"]
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]
        user_ab_id = setup["users"]["ab"]["id"]
        school_a_id = setup["schools"]["a"]["id"]

        r = await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r.status_code == 200

        # 验证 DB 中写入了浏览历史
        history = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == user_ab_id,
                BrowseHistory.post_id == post_a_pub_id,
            )
        )).scalar_one_or_none()
        assert history is not None
        assert history.school_id == school_a_id
        assert history.viewed_at is not None

    @pytest.mark.asyncio
    async def test_repeated_viewing_updates_viewed_at_not_insert(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.3: 同一用户在同一学校对同一帖子重复访问 → 更新 viewed_at，不新增记录"""
        setup = two_schools_setup
        post_a_pub_id = setup["posts"]["a_pub"]["id"]
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]
        user_ab_id = setup["users"]["ab"]["id"]

        # 第一次访问
        r1 = await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r1.status_code == 200
        first_history = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == user_ab_id,
                BrowseHistory.post_id == post_a_pub_id,
            )
        )).scalar_one()
        first_viewed_at = first_history.viewed_at

        # 等待一小段时间确保 viewed_at 可区分
        import asyncio
        await asyncio.sleep(0.05)

        # 第二次访问
        r2 = await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r2.status_code == 200

        # 仍只有一条记录，viewed_at 被更新
        await db_session.rollback()  # 清掉 session 缓存
        histories = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == user_ab_id,
                BrowseHistory.post_id == post_a_pub_id,
            )
        )).scalars().all()
        assert len(histories) == 1
        assert histories[0].viewed_at > first_viewed_at

    @pytest.mark.asyncio
    async def test_anonymous_view_does_not_create_history(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.3: 游客访问不写浏览历史"""
        setup = two_schools_setup
        post_a_pub_id = setup["posts"]["a_pub"]["id"]
        school_a_code = setup["schools"]["a"]["code"]

        # 游客访问（不携带 Authorization）
        r = await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers=_school(school_a_code),
        )
        assert r.status_code == 200

        # DB 中不应有任何浏览历史
        count = (await db_session.execute(
            select(BrowseHistory).where(BrowseHistory.post_id == post_a_pub_id)
        )).scalars().all()
        assert len(count) == 0

    @pytest.mark.asyncio
    async def test_history_isolated_by_school_context(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.3: 同一用户在 A 校访问 A 校帖子 → 历史记 A 校；切换到 B 校视角访问 B 校帖子 → 历史记 B 校

        关键：school_id 取自 TenantContext（X-School-Code），不是 Post.school_id。
        虽然 Post 自带 school_id，但 TenantContext 决定当前会话属于哪所学校。
        """
        setup = two_schools_setup
        post_a_pub_id = setup["posts"]["a_pub"]["id"]
        post_b_pub_id = setup["posts"]["b_pub"]["id"]
        user_ab_token = setup["users"]["ab"]["token"]
        user_ab_id = setup["users"]["ab"]["id"]
        school_a_code = setup["schools"]["a"]["code"]
        school_b_code = setup["schools"]["b"]["code"]
        school_a_id = setup["schools"]["a"]["id"]
        school_b_id = setup["schools"]["b"]["id"]

        # 在 A 校视角访问 A 校帖子 → 历史记 A 校
        r1 = await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r1.status_code == 200

        # 在 B 校视角访问 B 校帖子 → 历史记 B 校
        r2 = await client.get(
            f"/api/v1/posts/{post_b_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_b_code)},
        )
        assert r2.status_code == 200

        # 两条历史，分别属于不同学校
        histories = (await db_session.execute(
            select(BrowseHistory).where(BrowseHistory.user_id == user_ab_id)
        )).scalars().all()
        assert len(histories) == 2
        school_ids = {h.school_id for h in histories}
        assert school_a_id in school_ids
        assert school_b_id in school_ids


# ============================================================
# PRF-01.3: GET /users/me/view-history 浏览历史列表（学校隔离）
# ============================================================
class TestViewHistoryList:
    """PRF-01.3: /users/me/view-history 浏览历史列表"""

    @pytest.mark.asyncio
    async def test_view_history_returns_only_current_school(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """PRF-01.3: 切换到 A 校视角只看到 A 校浏览历史，跨校历史不出现"""
        setup = two_schools_setup
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]
        school_b_code = setup["schools"]["b"]["code"]
        post_a_pub_id = setup["posts"]["a_pub"]["id"]
        post_b_pub_id = setup["posts"]["b_pub"]["id"]

        # 在 A 校视角访问 A 校帖子
        await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        # 在 B 校视角访问 B 校帖子
        await client.get(
            f"/api/v1/posts/{post_b_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_b_code)},
        )

        # 切换到 A 校视角查看历史：只看到 A 校的 1 条
        r = await client.get(
            "/api/v1/users/me/view-history",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["post_id"] == post_a_pub_id

        # 切换到 B 校视角查看历史：只看到 B 校的 1 条
        r = await client.get(
            "/api/v1/users/me/view-history",
            headers={**_auth(user_ab_token), **_school(school_b_code)},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["post_id"] == post_b_pub_id

    @pytest.mark.asyncio
    async def test_view_history_ordered_by_viewed_at_desc(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """PRF-01.3: 浏览历史按 viewed_at DESC 排序（最近浏览在前）"""
        setup = two_schools_setup
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]
        post_a_pub_id = setup["posts"]["a_pub"]["id"]
        post_a_expired_id = setup["posts"]["a_expired"]["id"]

        # 先访问 a_pub，再访问 a_expired（后者 viewed_at 更新）
        await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        import asyncio
        await asyncio.sleep(0.05)
        await client.get(
            f"/api/v1/posts/{post_a_expired_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )

        r = await client.get(
            "/api/v1/users/me/view-history",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 2
        # 最近浏览的（a_expired）应在前
        assert items[0]["post_id"] == post_a_expired_id
        assert items[1]["post_id"] == post_a_pub_id

    @pytest.mark.asyncio
    async def test_view_history_paginated(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """PRF-01.3: 浏览历史支持分页"""
        setup = two_schools_setup
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]

        # 访问甲校的 4 个帖子（pub/draft/pending/expired）
        # 注意：draft/pending 对非作者非管理员不可见 → 404，不会写入历史
        # 因此只有 published 和 expired 会写入历史
        post_ids = [
            setup["posts"]["a_pub"]["id"],
            setup["posts"]["a_expired"]["id"],
        ]
        for pid in post_ids:
            await client.get(
                f"/api/v1/posts/{pid}",
                headers={**_auth(user_ab_token), **_school(school_a_code)},
            )

        # page_size=1，应分 2 页
        r = await client.get(
            "/api/v1/users/me/view-history",
            params={"page": 1, "page_size": 1},
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1
        assert data["page"] == 1
        assert data["page_size"] == 1

        r2 = await client.get(
            "/api/v1/users/me/view-history",
            params={"page": 2, "page_size": 1},
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert len(data2["items"]) == 1
        assert data2["page"] == 2

    @pytest.mark.asyncio
    async def test_view_history_excludes_deleted_posts(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.3: 软删除帖子的浏览历史不在列表中展示（避免泄露存在性）"""
        setup = two_schools_setup
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]
        post_a_pub_id = setup["posts"]["a_pub"]["id"]

        # 访问帖子产生历史
        await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )

        # 软删除该帖子
        post = (await db_session.execute(
            select(Post).where(Post.id == post_a_pub_id)
        )).scalar_one()
        post.is_deleted = True
        await db_session.commit()

        # 浏览历史应不展示该帖子
        r = await client.get(
            "/api/v1/users/me/view-history",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    @pytest.mark.asyncio
    async def test_view_history_requires_auth(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """未登录访问 /users/me/view-history 返回 401"""
        r = await client.get(
            "/api/v1/users/me/view-history",
            headers=_school(two_schools_setup["schools"]["a"]["code"]),
        )
        assert r.status_code == 401


# ============================================================
# PRF-01.3: DELETE /users/me/view-history 清除浏览历史
# ============================================================
class TestClearViewHistory:
    """PRF-01.3: 清除当前学校下的全部浏览历史"""

    @pytest.mark.asyncio
    async def test_clear_history_only_affects_current_school(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.3: 清除 A 校历史不影响 B 校历史"""
        setup = two_schools_setup
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]
        school_b_code = setup["schools"]["b"]["code"]
        post_a_pub_id = setup["posts"]["a_pub"]["id"]
        post_b_pub_id = setup["posts"]["b_pub"]["id"]
        user_ab_id = setup["users"]["ab"]["id"]

        # 在 A、B 两校都产生浏览历史
        await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        await client.get(
            f"/api/v1/posts/{post_b_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_b_code)},
        )

        # 切换到 A 校视角清除历史
        r = await client.delete(
            "/api/v1/users/me/view-history",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r.status_code == 200
        assert "已清除" in r.json()["message"]
        assert r.json()["data"]["deleted_count"] == 1

        # A 校历史已清空
        await db_session.rollback()
        a_histories = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == user_ab_id,
                BrowseHistory.school_id == setup["schools"]["a"]["id"],
            )
        )).scalars().all()
        assert len(a_histories) == 0

        # B 校历史仍保留
        b_histories = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == user_ab_id,
                BrowseHistory.school_id == setup["schools"]["b"]["id"],
            )
        )).scalars().all()
        assert len(b_histories) == 1

    @pytest.mark.asyncio
    async def test_clear_history_when_empty_returns_zero(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """PRF-01.3: 无历史时清除返回 deleted_count=0"""
        setup = two_schools_setup
        r = await client.delete(
            "/api/v1/users/me/view-history",
            headers={**_auth(setup["users"]["a"]["token"]), **_school(setup["schools"]["a"]["code"])},
        )
        assert r.status_code == 200
        assert r.json()["data"]["deleted_count"] == 0


# ============================================================
# PRF-01.3: DELETE /users/me/view-history/{post_id} 删除单条
# ============================================================
class TestDeleteViewHistoryItem:
    """PRF-01.3: 删除单条浏览历史"""

    @pytest.mark.asyncio
    async def test_delete_single_history_item(
        self, client: AsyncClient, two_schools_setup: dict, db_session: AsyncSession
    ):
        """PRF-01.3: 删除单条浏览历史成功"""
        setup = two_schools_setup
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]
        post_a_pub_id = setup["posts"]["a_pub"]["id"]

        # 产生历史
        await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )

        # 删除单条
        r = await client.delete(
            f"/api/v1/users/me/view-history/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )
        assert r.status_code == 200
        assert r.json()["message"] == "已删除该条浏览历史"

        # DB 中已无该条
        await db_session.rollback()
        history = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == setup["users"]["ab"]["id"],
                BrowseHistory.post_id == post_a_pub_id,
            )
        )).scalar_one_or_none()
        assert history is None

    @pytest.mark.asyncio
    async def test_delete_cross_school_history_returns_404(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """PRF-01.3: 跨校删除其它学校的历史 → 404（不泄露存在性）"""
        setup = two_schools_setup
        user_ab_token = setup["users"]["ab"]["token"]
        school_a_code = setup["schools"]["a"]["code"]
        school_b_code = setup["schools"]["b"]["code"]
        post_a_pub_id = setup["posts"]["a_pub"]["id"]

        # 在 A 校视角访问 A 校帖子，产生 A 校历史
        await client.get(
            f"/api/v1/posts/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_a_code)},
        )

        # 切换到 B 校视角尝试删除 A 校的帖子历史 → 404
        r = await client.delete(
            f"/api/v1/users/me/view-history/{post_a_pub_id}",
            headers={**_auth(user_ab_token), **_school(school_b_code)},
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_history_returns_404(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """PRF-01.3: 删除不存在的历史 → 404"""
        setup = two_schools_setup
        r = await client.delete(
            f"/api/v1/users/me/view-history/99999",
            headers={**_auth(setup["users"]["a"]["token"]), **_school(setup["schools"]["a"]["code"])},
        )
        assert r.status_code == 404


# ============================================================
# PRF-01.1: GET /users/me/posts 跨校隔离补充
# ============================================================
class TestMyPostsSchoolIsolation:
    """PRF-01.1 + TEN-02.3: /users/me/posts 按当前学校过滤"""

    @pytest.mark.asyncio
    async def test_my_posts_only_returns_current_school(
        self, client: AsyncClient, two_schools_setup: dict
    ):
        """PRF-01.1: user_a 切换到甲校视角只看到甲校帖子（不含跨校帖子）"""
        setup = two_schools_setup
        user_a_token = setup["users"]["a"]["token"]
        school_a_code = setup["schools"]["a"]["code"]

        # 在乙校给 user_a 也加一个帖子（跨校，不应在甲校视角出现）
        # 注意：使用独立 session（test_session_maker）进行数据预置，commit 后立即关闭，
        # 避免 openGauss 跨连接可见性问题（db_session 长连接会阻塞 API 侧查询）。
        from tests.conftest import test_session_maker

        async with test_session_maker() as session:
            await _create_post(
                session,
                user_id=setup["users"]["a"]["id"],
                school_id=setup["schools"]["b"]["id"],
                category_id=setup["category_ids"]["b"],
                title="user_a 在乙校的跨校帖子",
                status=PostStatus.PUBLISHED,
            )
            await session.commit()

        r = await client.get(
            "/api/v1/users/me/posts",
            headers={**_auth(user_a_token), **_school(school_a_code)},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        # user_a 在甲校有 4 个帖子（pub/draft/pending/expired），跨校帖子不计入
        assert len(items) == 4
        # 通过查询 DB 验证返回的帖子 id 全部属于甲校
        returned_ids = {item["id"] for item in items}
        a_school_post_ids = {
            setup["posts"]["a_pub"]["id"],
            setup["posts"]["a_draft"]["id"],
            setup["posts"]["a_pending"]["id"],
            setup["posts"]["a_expired"]["id"],
        }
        assert returned_ids == a_school_post_ids
