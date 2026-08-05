"""REC-01: 租户级推荐与隐私开关 测试

覆盖 REC-01.1 / REC-01.2 两个子任务的后端契约：

1. **REC-01.1 首页推荐** GET /recommendations
   - 游客：cold_start_guest 模式
   - 登录用户开启个性化但历史不足：cold_start_no_history 模式
   - 登录用户关闭个性化：cold_start_disabled 模式
   - 登录用户开启个性化且有足够历史：personalized 模式
   - 多租户隔离：跨校帖子不会出现
   - 推荐原因 reason 字段非空
   - 仅返回 published/expired 状态（draft/pending 不出现）
   - 管理员推荐（is_recommend=True）在冷启动优先

2. **REC-01.2 隐私偏好**
   - GET /users/me/recommendation-preferences 首次访问 upsert 默认行（True）
   - PUT /users/me/recommendation-preferences 更新开关（关闭时清除浏览历史）
   - PUT 开启个性化不影响历史数据
   - DELETE /users/me/recommendation-history 清除浏览+搜索历史
   - 偏好按 user_id 隔离
   - 未登录访问偏好接口 → 401
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.post_status import PostStatus
from app.core.security import create_access_token, get_password_hash
from app.models.browse_history import BrowseHistory
from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.product_plan import ProductPlan
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.school_subscription import SchoolSubscription
from app.models.search_history import SearchHistory
from app.models.subscription import UserSubscription
from app.models.user import User
from app.models.user_recommendation_preference import UserRecommendationPreference
from app.models.validation_record import ValidationRecord


# ============================================================
# 辅助函数：创建两校测试数据
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
    is_recommend: bool = False,
    view_count: int = 0,
    like_count: int = 0,
) -> Post:
    post = Post(
        user_id=user_id,
        school_id=school_id,
        category_id=category_id,
        title=title,
        content=f"{title} 的内容，至少十个字符",
        status=status,
        is_recommend=is_recommend,
        view_count=view_count,
        like_count=like_count,
    )
    db.add(post)
    await db.flush()
    return post


async def _create_browse_history(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    post_id: int,
    viewed_at: datetime = None,
) -> BrowseHistory:
    bh = BrowseHistory(
        user_id=user_id,
        school_id=school_id,
        post_id=post_id,
        viewed_at=viewed_at or datetime.now(),
        created_at=datetime.now(),
    )
    db.add(bh)
    await db.flush()
    return bh


async def _create_search_history(
    db: AsyncSession, user_id: int, keyword: str
) -> SearchHistory:
    sh = SearchHistory(
        user_id=user_id,
        keyword=keyword,
        created_at=datetime.now(),
    )
    db.add(sh)
    await db.flush()
    return sh


async def _create_subscription(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    target_type: str,
    target_id: int,
) -> UserSubscription:
    sub = UserSubscription(
        user_id=user_id,
        school_id=school_id,
        target_type=target_type,
        target_id=target_id,
    )
    db.add(sub)
    await db.flush()
    return sub


async def _create_validation_record(
    db: AsyncSession,
    post_id: int,
    user_id: int,
    validation_type: str = "confirmation",
) -> ValidationRecord:
    vr = ValidationRecord(
        post_id=post_id,
        user_id=user_id,
        validation_type=validation_type,
    )
    db.add(vr)
    await db.flush()
    return vr


def _make_token(user_id: int) -> str:
    return create_access_token(data={"sub": str(user_id)})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _school(code: str) -> dict:
    return {"X-School-Code": code}


@pytest_asyncio.fixture
async def rec_setup(client: AsyncClient) -> dict:
    """创建两校测试数据，用于 REC-01 推荐测试

    甲校：3 published + 1 draft + 1 expired + 1 admin-recommended
    乙校：1 published（用于验证跨校不污染）
    user_a：甲校成员，浏览历史 3 条（满足个性化阈值）
    user_b：甲校成员，无浏览历史（冷启动）
    user_guest：游客视角（无 token）

    依赖 client fixture 确保 setup_database（autouse）先执行清理，
    避免残留数据导致 UniqueViolationError。

    注意：不使用 async with test_session_maker()（async generator + async with
    组合在 pytest-asyncio 事件循环切换时可能延迟 close），改为手动管理 session。
    commit 后立即 close，确保连接归还（NullPool 即销毁），不残留锁。
    """
    from tests.conftest import test_session_maker

    session = test_session_maker()
    try:
        school_a = await _create_school(session, "甲校", "school-a")
        school_b = await _create_school(session, "乙校", "school-b")

        for sid in (school_a.id, school_b.id):
            await _assign_operations_subscription(session, sid)

        cat_a1 = await _create_category(session, school_a.id, "甲校失物", "a-lost")
        cat_a2 = await _create_category(session, school_a.id, "甲校活动", "a-event")
        cat_b = await _create_category(session, school_b.id, "乙校失物", "b-lost")

        # 用户
        user_a = await _create_user(session, "a@example.com", "甲校活跃用户", school_a.id)
        await _create_membership(session, user_a.id, school_a.id, "member", is_default=True)

        user_b = await _create_user(session, "b@example.com", "甲校新用户", school_a.id)
        await _create_membership(session, user_b.id, school_a.id, "member", is_default=True)

        user_admin = await _create_user(
            session, "admin@example.com", "甲校管理员", school_a.id, role="admin"
        )
        await _create_membership(session, user_admin.id, school_a.id, "admin", is_default=True)

        # 甲校帖子（user_admin 是作者，避免 user_a 自己的帖子被排除）
        # 3 published + 1 expired + 1 admin-recommended published + 1 draft
        post_a1 = await _create_post(
            session, user_admin.id, school_a.id, cat_a1.id,
            "甲校失物招领一", PostStatus.PUBLISHED, view_count=10, like_count=2,
        )
        post_a2 = await _create_post(
            session, user_admin.id, school_a.id, cat_a1.id,
            "甲校失物招领二", PostStatus.PUBLISHED, view_count=5, like_count=1,
        )
        post_a3 = await _create_post(
            session, user_admin.id, school_a.id, cat_a2.id,
            "甲校活动一", PostStatus.PUBLISHED, view_count=20, like_count=5,
        )
        post_a_expired = await _create_post(
            session, user_admin.id, school_a.id, cat_a1.id,
            "甲校已过期失物", PostStatus.EXPIRED, view_count=2,
        )
        post_a_rec = await _create_post(
            session, user_admin.id, school_a.id, cat_a2.id,
            "甲校管理员精选活动", PostStatus.PUBLISHED, is_recommend=True,
            view_count=8, like_count=3,
        )
        post_a_draft = await _create_post(
            session, user_admin.id, school_a.id, cat_a1.id,
            "甲校草稿帖子", PostStatus.DRAFT,
        )

        # 乙校帖子（用于跨校隔离测试）
        post_b1 = await _create_post(
            session, user_admin.id, school_b.id, cat_b.id,
            "乙校失物招领", PostStatus.PUBLISHED, view_count=100,
        )

        # user_a 的浏览历史：浏览 3 个甲校帖子（满足个性化阈值 MIN_HISTORY_FOR_PERSONALIZATION=3）
        await _create_browse_history(
            session, user_a.id, school_a.id, post_a1.id, datetime.now() - timedelta(days=1)
        )
        await _create_browse_history(
            session, user_a.id, school_a.id, post_a2.id, datetime.now() - timedelta(days=2)
        )
        await _create_browse_history(
            session, user_a.id, school_a.id, post_a3.id, datetime.now() - timedelta(days=3)
        )

        # user_a 的搜索历史
        await _create_search_history(session, user_a.id, "失物")
        await _create_search_history(session, user_a.id, "失物")

        # user_a 的订阅（订阅 cat_a2 分类）
        await _create_subscription(
            session, user_a.id, school_a.id, "category", cat_a2.id
        )

        # 给 post_a3 加 confirmation 票（验证结果加分）
        await _create_validation_record(
            session, post_a3.id, user_b.id, "confirmation"
        )
        await _create_validation_record(
            session, post_a3.id, user_admin.id, "confirmation"
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
                "admin": {"id": user_admin.id, "token": _make_token(user_admin.id)},
            },
            "categories": {"a1": cat_a1.id, "a2": cat_a2.id, "b": cat_b.id},
            "posts": {
                "a1": post_a1.id,
                "a2": post_a2.id,
                "a3": post_a3.id,
                "a_expired": post_a_expired.id,
                "a_rec": post_a_rec.id,
                "a_draft": post_a_draft.id,
                "b1": post_b1.id,
            },
        }
    finally:
        try:
            await session.close()
        except Exception:
            pass
    return result


# ============================================================
# REC-01.1: GET /recommendations 推荐接口
# ============================================================
class TestGetRecommendations:
    """REC-01.1: /recommendations 首页推荐接口"""

    @pytest.mark.asyncio
    async def test_guest_returns_cold_start_guest_mode(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 游客访问推荐 → cold_start_guest 模式"""
        setup = rec_setup
        resp = await client.get(
            "/api/v1/recommendations",
            headers=_school(setup["schools"]["a"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"]["personalized"] is False
        assert data["mode"]["reason_code"] == "cold_start_guest"
        # 游客仍能看到冷启动内容（本校热门/最新/管理员推荐）
        assert isinstance(data["items"], list)
        # 每条结果都有推荐原因
        for item in data["items"]:
            assert "reason" in item
            assert isinstance(item["reason"], str)
            assert len(item["reason"]) > 0

    @pytest.mark.asyncio
    async def test_logged_in_no_history_returns_cold_start_no_history(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 登录用户无浏览历史 → cold_start_no_history 模式"""
        setup = rec_setup
        user_b_token = setup["users"]["b"]["token"]  # user_b 无浏览历史
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_b_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"]["personalized"] is False
        assert data["mode"]["reason_code"] == "cold_start_no_history"

    @pytest.mark.asyncio
    async def test_personalized_mode_with_enough_history(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 登录用户有足够历史 → personalized 模式"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]  # user_a 有 3 条浏览历史
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"]["personalized"] is True
        assert data["mode"]["reason_code"] == "personalized"
        # 应有推荐结果（甲校至少有 3 个 published + 1 expired + 1 admin-rec 共 5 个候选）
        assert len(data["items"]) > 0
        # 已浏览的帖子不应出现在个性化推荐中（a1/a2/a3 都被 user_a 浏览过）
        # 但 a_expired / a_rec 没被浏览过，应出现
        recommended_ids = {item["id"] for item in data["items"]}
        assert setup["posts"]["a1"] not in recommended_ids
        assert setup["posts"]["a2"] not in recommended_ids
        assert setup["posts"]["a3"] not in recommended_ids

    @pytest.mark.asyncio
    async def test_personalized_excludes_viewed_posts(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 个性化推荐排除已浏览帖子（避免重复推荐）"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        # user_a 已浏览 a1/a2/a3，不应出现在推荐中
        recommended_ids = {item["id"] for item in data["items"]}
        viewed_ids = {
            setup["posts"]["a1"],
            setup["posts"]["a2"],
            setup["posts"]["a3"],
        }
        assert not (recommended_ids & viewed_ids), "已浏览帖子不应出现在个性化推荐中"

    @pytest.mark.asyncio
    async def test_tenant_isolation_cross_school_posts_not_shown(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 多租户隔离——甲校推荐不出现乙校帖子"""
        setup = rec_setup
        # user_a 在甲校视角查询
        user_a_token = setup["users"]["a"]["token"]
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        recommended_ids = {item["id"] for item in data["items"]}
        # 乙校帖子 b1 不应出现
        assert setup["posts"]["b1"] not in recommended_ids

        # 游客视角同样隔离
        resp2 = await client.get(
            "/api/v1/recommendations",
            headers=_school(setup["schools"]["a"]["code"]),
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        recommended_ids2 = {item["id"] for item in data2["items"]}
        assert setup["posts"]["b1"] not in recommended_ids2

    @pytest.mark.asyncio
    async def test_only_published_and_expired_visible(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 推荐仅返回 published / expired 状态（draft/pending 不出现）"""
        setup = rec_setup
        # 游客冷启动：所有可见帖子都应是 published / expired
        resp = await client.get(
            "/api/v1/recommendations",
            headers=_school(setup["schools"]["a"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] in ("published", "expired")
        # 草稿帖子不应出现
        recommended_ids = {item["id"] for item in data["items"]}
        assert setup["posts"]["a_draft"] not in recommended_ids

    @pytest.mark.asyncio
    async def test_admin_recommend_appears_in_cold_start(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 冷启动时管理员推荐（is_recommend=True）应出现且优先"""
        setup = rec_setup
        # 游客冷启动
        resp = await client.get(
            "/api/v1/recommendations",
            headers=_school(setup["schools"]["a"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        recommended_ids = [item["id"] for item in data["items"]]
        # 管理员精选帖子应出现
        assert setup["posts"]["a_rec"] in recommended_ids
        # 找到管理员精选的那一项，验证推荐原因
        rec_item = next(
            item for item in data["items"] if item["id"] == setup["posts"]["a_rec"]
        )
        assert rec_item["reason"] == "管理员精选"
        # 管理员精选应排在首位（冷启动里 score 最高）
        assert recommended_ids[0] == setup["posts"]["a_rec"]

    @pytest.mark.asyncio
    async def test_recommendation_items_have_reason_and_score(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 每条推荐项都有 reason 与 score 字段"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert "reason" in item
            assert "score" in item
            assert isinstance(item["score"], (int, float))
            assert item["score"] >= 0

    @pytest.mark.asyncio
    async def test_pagination_metadata(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 分页元数据 page/page_size/total/total_pages/has_more 正确"""
        setup = rec_setup
        resp = await client.get(
            "/api/v1/recommendations?page=1&page_size=2",
            headers=_school(setup["schools"]["a"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] >= 1
        assert data["total_pages"] >= 1
        assert isinstance(data["has_more"], bool)
        # 第一页最多 page_size 条
        assert len(data["items"]) <= 2


# ============================================================
# REC-01.2: 隐私偏好接口
# ============================================================
class TestRecommendationPreferences:
    """REC-01.2: /users/me/recommendation-preferences 隐私偏好接口"""

    @pytest.mark.asyncio
    async def test_get_preferences_first_time_creates_default(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.2: 首次访问 GET 偏好 → upsert 默认行（personalization_enabled=True）"""
        setup = rec_setup
        user_b_token = setup["users"]["b"]["token"]  # user_b 还没访问过偏好
        resp = await client.get(
            "/api/v1/users/me/recommendation-preferences",
            headers={**_auth(user_b_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["personalization_enabled"] is True
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_preferences_requires_auth(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.2: 未登录访问 GET 偏好 → 401"""
        setup = rec_setup
        resp = await client.get(
            "/api/v1/users/me/recommendation-preferences",
            headers=_school(setup["schools"]["a"]["code"]),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_update_preferences_disable_clears_browse_history(
        self, client: AsyncClient, rec_setup: dict,
        db_session: AsyncSession,
    ):
        """REC-01.2: 关闭个性化 → 同步清除该用户在所有学校的浏览历史"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        user_a_id = setup["users"]["a"]["id"]

        # 确认 user_a 有浏览历史
        before_count = (await db_session.execute(
            select(BrowseHistory).where(BrowseHistory.user_id == user_a_id)
        )).scalars().all()
        assert len(before_count) >= 3, "前置条件：user_a 应有浏览历史"

        # 关闭个性化
        resp = await client.put(
            "/api/v1/users/me/recommendation-preferences",
            json={"personalization_enabled": False},
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["personalization_enabled"] is False

        # 验证浏览历史已被清除
        db_session.expire_all()
        after_count = (await db_session.execute(
            select(BrowseHistory).where(BrowseHistory.user_id == user_a_id)
        )).scalars().all()
        assert len(after_count) == 0, "关闭个性化后应清除浏览历史"

    @pytest.mark.asyncio
    async def test_update_preferences_enable_does_not_clear_history(
        self, client: AsyncClient, rec_setup: dict,
        db_session: AsyncSession,
    ):
        """REC-01.2: 开启个性化 → 不影响历史数据"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        user_a_id = setup["users"]["a"]["id"]

        # 先关闭（清除历史），再添加新历史，最后开启
        resp = await client.put(
            "/api/v1/users/me/recommendation-preferences",
            json={"personalization_enabled": False},
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200

        # 添加新浏览历史
        new_bh = BrowseHistory(
            user_id=user_a_id,
            school_id=setup["schools"]["a"]["id"],
            post_id=setup["posts"]["a_rec"],
            viewed_at=datetime.now(),
            created_at=datetime.now(),
        )
        db_session.add(new_bh)
        await db_session.commit()

        # 开启个性化
        resp = await client.put(
            "/api/v1/users/me/recommendation-preferences",
            json={"personalization_enabled": True},
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        assert resp.json()["personalization_enabled"] is True

        # 验证浏览历史未被清除
        db_session.expire_all()
        after_count = (await db_session.execute(
            select(BrowseHistory).where(BrowseHistory.user_id == user_a_id)
        )).scalars().all()
        assert len(after_count) == 1, "开启个性化不应清除浏览历史"

    @pytest.mark.asyncio
    async def test_disabled_preference_returns_cold_start_disabled_mode(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.2: 关闭个性化后访问推荐 → cold_start_disabled 模式"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]

        # 关闭个性化
        resp = await client.put(
            "/api/v1/users/me/recommendation-preferences",
            json={"personalization_enabled": False},
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200

        # 再次访问推荐：应走冷启动且 reason_code=cold_start_disabled
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"]["personalized"] is False
        assert data["mode"]["reason_code"] == "cold_start_disabled"
        # 关闭后仍能看冷启动内容（普通热门/最新可用）
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_preferences_isolated_per_user(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.2: 偏好按 user_id 隔离——A 关闭不影响 B"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        user_b_token = setup["users"]["b"]["token"]

        # A 关闭个性化
        resp = await client.put(
            "/api/v1/users/me/recommendation-preferences",
            json={"personalization_enabled": False},
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200

        # B 查询偏好：应为默认值 True
        resp = await client.get(
            "/api/v1/users/me/recommendation-preferences",
            headers={**_auth(user_b_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        assert resp.json()["personalization_enabled"] is True

    @pytest.mark.asyncio
    async def test_update_preferences_requires_auth(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.2: 未登录访问 PUT 偏好 → 401"""
        setup = rec_setup
        resp = await client.put(
            "/api/v1/users/me/recommendation-preferences",
            json={"personalization_enabled": False},
            headers=_school(setup["schools"]["a"]["code"]),
        )
        assert resp.status_code == 401


# ============================================================
# REC-01.2: 清除推荐画像历史
# ============================================================
class TestClearRecommendationHistory:
    """REC-01.2: DELETE /users/me/recommendation-history 清除画像历史"""

    @pytest.mark.asyncio
    async def test_clear_history_deletes_browse_and_search(
        self, client: AsyncClient, rec_setup: dict,
        db_session: AsyncSession,
    ):
        """REC-01.2: 清除历史 → 删除当前学校浏览历史 + 全部搜索历史"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        user_a_id = setup["users"]["a"]["id"]

        # 确认前置条件：有浏览历史与搜索历史
        before_bh = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == user_a_id,
                BrowseHistory.school_id == setup["schools"]["a"]["id"],
            )
        )).scalars().all()
        before_sh = (await db_session.execute(
            select(SearchHistory).where(SearchHistory.user_id == user_a_id)
        )).scalars().all()
        assert len(before_bh) >= 3
        assert len(before_sh) >= 1

        # 清除历史
        resp = await client.delete(
            "/api/v1/users/me/recommendation-history",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 返回结构与 MessageResponse 对齐：message + data
        assert "message" in data
        assert data["data"]["browse_deleted"] >= 3
        assert data["data"]["search_deleted"] >= 1

        # 验证浏览历史已清除（当前学校）
        db_session.expire_all()
        after_bh = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == user_a_id,
                BrowseHistory.school_id == setup["schools"]["a"]["id"],
            )
        )).scalars().all()
        assert len(after_bh) == 0

        # 验证搜索历史已清除（全部）
        after_sh = (await db_session.execute(
            select(SearchHistory).where(SearchHistory.user_id == user_a_id)
        )).scalars().all()
        assert len(after_sh) == 0

    @pytest.mark.asyncio
    async def test_clear_history_does_not_disable_personalization(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.2: 清除历史不影响个性化开关"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]

        # 清除历史
        resp = await client.delete(
            "/api/v1/users/me/recommendation-history",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200

        # 偏好仍为开启状态（默认值）
        resp = await client.get(
            "/api/v1/users/me/recommendation-preferences",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        assert resp.json()["personalization_enabled"] is True

    @pytest.mark.asyncio
    async def test_clear_history_then_recommendations_use_cold_start(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.2: 清除历史后 → 推荐改用冷启动（no_history）"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]

        # 清除历史
        resp = await client.delete(
            "/api/v1/users/me/recommendation-history",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200

        # 再次访问推荐：因历史已清空，应走 cold_start_no_history
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"]["personalized"] is False
        assert data["mode"]["reason_code"] == "cold_start_no_history"

    @pytest.mark.asyncio
    async def test_clear_history_requires_auth(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.2: 未登录访问 DELETE 历史 → 401"""
        setup = rec_setup
        resp = await client.delete(
            "/api/v1/users/me/recommendation-history",
            headers=_school(setup["schools"]["a"]["code"]),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_clear_history_isolated_per_user(
        self, client: AsyncClient, rec_setup: dict,
        db_session: AsyncSession,
    ):
        """REC-01.2: 清除历史按用户隔离——A 清除不影响 B"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        user_b_token = setup["users"]["b"]["token"]
        user_b_id = setup["users"]["b"]["id"]

        # 给 user_b 也加一条浏览历史
        bh_b = BrowseHistory(
            user_id=user_b_id,
            school_id=setup["schools"]["a"]["id"],
            post_id=setup["posts"]["a1"],
            viewed_at=datetime.now(),
            created_at=datetime.now(),
        )
        db_session.add(bh_b)
        await db_session.commit()

        # A 清除历史
        resp = await client.delete(
            "/api/v1/users/me/recommendation-history",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200

        # B 的浏览历史应不受影响
        db_session.expire_all()
        b_bh = (await db_session.execute(
            select(BrowseHistory).where(
                BrowseHistory.user_id == user_b_id,
                BrowseHistory.school_id == setup["schools"]["a"]["id"],
            )
        )).scalars().all()
        assert len(b_bh) == 1, "B 的浏览历史不应被 A 的清除操作影响"


# ============================================================
# REC-01.1: 个性化打分逻辑
# ============================================================
class TestPersonalizationScoring:
    """REC-01.1: 个性化打分逻辑——验证画像与打分的核心契约"""

    @pytest.mark.asyncio
    async def test_personalized_recommendation_includes_subscribed_category(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 个性化推荐包含订阅分类的帖子（订阅画像匹配）"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        # user_a 订阅了 cat_a2，post_a_rec 属于 cat_a2 且未被浏览过
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        recommended_ids = {item["id"] for item in data["items"]}
        # post_a_rec 属于 cat_a2（user_a 订阅的分类）且未被浏览，应被推荐
        assert setup["posts"]["a_rec"] in recommended_ids

    @pytest.mark.asyncio
    async def test_personalized_recommendation_admin_rec_priority(
        self, client: AsyncClient, rec_setup: dict
    ):
        """REC-01.1: 个性化推荐中管理员精选帖子优先（reason='管理员精选'）"""
        setup = rec_setup
        user_a_token = setup["users"]["a"]["token"]
        resp = await client.get(
            "/api/v1/recommendations",
            headers={**_auth(user_a_token), **_school(setup["schools"]["a"]["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        # post_a_rec 是管理员精选，应在推荐结果中且 reason='管理员精选'
        rec_items = [i for i in data["items"] if i["id"] == setup["posts"]["a_rec"]]
        assert len(rec_items) == 1
        assert rec_items[0]["reason"] == "管理员精选"
