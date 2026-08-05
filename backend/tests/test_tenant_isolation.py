"""TEN-02.4: 三校 API 隔离测试

验证多租户隔离完整性：
1. A 校请求只返回 A 校数据（列表 / 分类 / 地点 / 搜索 / 地图）
2. 跨校创建 / 读取 / 更新 / 审核统一返回 404（不泄露存在性）
3. TenantContext 从 X-School-Code 头或 ?school= 参数解析
4. get_effective_role 按租户成员关系正确计算有效角色
5. 写请求忽略 body 里的 school_id，强制使用 TenantContext 解析的学校
6. 普通管理员只能管理本校；super_admin 可跨校但资源级校验仍生效
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from datetime import datetime
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import (
    TenantContext,
    get_effective_role,
    check_resource_in_tenant,
)
from app.core.permissions import Role
from app.core.exceptions import NotFoundException
from app.core.post_status import PostStatus
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.post import Post
from app.models.location import Location
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription
from app.core.security import get_password_hash, create_access_token


# ============================================================
# 辅助函数：创建三校测试数据
# ============================================================
async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    """创建一所学校"""
    school = School(name=name, code=code, is_active=True)
    db.add(school)
    await db.flush()
    return school


async def _assign_operations_subscription(db: AsyncSession, school_id: int) -> None:
    """为学校分配 operations 档订阅（若套餐存在则分配，否则跳过）

    conftest.py 的 setup_database 预置了 3 档套餐，但不同 session 可见性可能有时序问题，
    这里用 scalar_one_or_none 容错：套餐不存在时直接跳过（posts.py 不依赖 EntitlementService）。
    """
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
    """直接在 DB 创建用户（不走注册接口，避免触发额外逻辑）

    D4 门禁：默认已完成校园身份认证（campus_verified=True），
    使写操作测试不受「未认证只读」限制；未认证场景由 test_campus_gate 覆盖。
    """
    user = User(
        email=email,
        nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id,
        role=role,
        campus_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_membership(
    db: AsyncSession, user_id: int, school_id: int, role: str = "member"
) -> SchoolMembership:
    """创建学校成员关系"""
    membership = SchoolMembership(
        user_id=user_id,
        school_id=school_id,
        role=role,
        status="active",
        is_default=False,
    )
    db.add(membership)
    await db.flush()
    return membership


async def _create_category(db: AsyncSession, school_id: int, name: str, code: str) -> Category:
    """创建分类"""
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


async def _create_location(
    db: AsyncSession, school_id: int, name: str, lat: float, lng: float
) -> Location:
    """创建地点"""
    loc = Location(
        school_id=school_id,
        name=name,
        latitude=lat,
        longitude=lng,
        is_verified=True,
    )
    db.add(loc)
    await db.flush()
    return loc


async def _create_post(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    category_id: int,
    title: str,
    status: str = PostStatus.PUBLISHED,
    location_id: int | None = None,
) -> Post:
    """直接在 DB 创建帖子（不走 API，避免审核流程）"""
    post = Post(
        user_id=user_id,
        school_id=school_id,
        category_id=category_id,
        location_id=location_id,
        title=title,
        content=f"{title} 的内容，至少十个字符",
        status=status,
    )
    db.add(post)
    await db.flush()
    return post


def _make_token(user_id: int) -> str:
    """为用户生成 access_token"""
    return create_access_token(data={"sub": str(user_id)})


@pytest_asyncio.fixture
async def three_schools(db_session: AsyncSession) -> dict:
    """创建三校测试数据：每校 1 用户 + 1 分类 + 1 地点 + 1 已发布帖子 + 1 待审核帖子

    额外：
    - user_ab：同时是 A 校和 B 校成员（用于跨校资源访问测试）
    - admin_a：A 校管理员（有 A 校 admin membership）
    - super_admin：平台超管（user.role=super_admin，可跨校）
    """
    # 三所学校
    school_a = await _create_school(db_session, "A 校", "school-a")
    school_b = await _create_school(db_session, "B 校", "school-b")
    school_c = await _create_school(db_session, "C 校", "school-c")

    # 为每所学校分配 operations 订阅
    for sid in (school_a.id, school_b.id, school_c.id):
        await _assign_operations_subscription(db_session, sid)

    # 每校 1 分类 + 1 地点
    cat_a = await _create_category(db_session, school_a.id, "A 校失物", "a-lost")
    cat_b = await _create_category(db_session, school_b.id, "B 校失物", "b-lost")
    cat_c = await _create_category(db_session, school_c.id, "C 校失物", "c-lost")

    loc_a = await _create_location(db_session, school_a.id, "A 校图书馆", 31.0, 120.0)
    loc_b = await _create_location(db_session, school_b.id, "B 校图书馆", 32.0, 121.0)
    loc_c = await _create_location(db_session, school_c.id, "C 校图书馆", 33.0, 122.0)

    # 每校 1 普通用户（同时是该校默认成员）
    user_a = await _create_user(db_session, "a@example.com", "A 校用户", school_a.id)
    user_b = await _create_user(db_session, "b@example.com", "B 校用户", school_b.id)
    user_c = await _create_user(db_session, "c@example.com", "C 校用户", school_c.id)
    await _create_membership(db_session, user_a.id, school_a.id, "member")
    await _create_membership(db_session, user_b.id, school_b.id, "member")
    await _create_membership(db_session, user_c.id, school_c.id, "member")

    # user_ab：A 校用户（UC-01 一对一，仅一条 active membership；用于跨校资源测试）
    user_ab = await _create_user(db_session, "ab@example.com", "AB 双校用户", school_a.id)
    await _create_membership(db_session, user_ab.id, school_a.id, "member")

    # admin_a：A 校管理员
    admin_a = await _create_user(db_session, "admin_a@example.com", "A 校管理员", school_a.id, role="admin")
    await _create_membership(db_session, admin_a.id, school_a.id, "admin")

    # super_admin：平台超管
    super_admin = await _create_user(db_session, "super@example.com", "超管", school_a.id, role="super_admin")

    # 每校 1 已发布帖子 + 1 待审核帖子
    post_a_pub = await _create_post(db_session, user_a.id, school_a.id, cat_a.id, "A 校已发布帖子", PostStatus.PUBLISHED, loc_a.id)
    post_a_pending = await _create_post(db_session, user_a.id, school_a.id, cat_a.id, "A 校待审核帖子", PostStatus.PENDING, loc_a.id)
    post_b_pub = await _create_post(db_session, user_b.id, school_b.id, cat_b.id, "B 校已发布帖子", PostStatus.PUBLISHED, loc_b.id)
    post_b_pending = await _create_post(db_session, user_b.id, school_b.id, cat_b.id, "B 校待审核帖子", PostStatus.PENDING, loc_b.id)
    post_c_pub = await _create_post(db_session, user_c.id, school_c.id, cat_c.id, "C 校已发布帖子", PostStatus.PUBLISHED, loc_c.id)

    await db_session.commit()

    return {
        "schools": {
            "a": {"id": school_a.id, "code": school_a.code, "name": school_a.name},
            "b": {"id": school_b.id, "code": school_b.code, "name": school_b.name},
            "c": {"id": school_c.id, "code": school_c.code, "name": school_c.name},
        },
        "categories": {
            "a": {"id": cat_a.id, "school_id": school_a.id},
            "b": {"id": cat_b.id, "school_id": school_b.id},
            "c": {"id": cat_c.id, "school_id": school_c.id},
        },
        "locations": {
            "a": {"id": loc_a.id, "school_id": school_a.id, "lat": 31.0, "lng": 120.0},
            "b": {"id": loc_b.id, "school_id": school_b.id, "lat": 32.0, "lng": 121.0},
            "c": {"id": loc_c.id, "school_id": school_c.id, "lat": 33.0, "lng": 122.0},
        },
        "posts": {
            "a_pub": {"id": post_a_pub.id, "school_id": school_a.id, "status": PostStatus.PUBLISHED},
            "a_pending": {"id": post_a_pending.id, "school_id": school_a.id, "status": PostStatus.PENDING},
            "b_pub": {"id": post_b_pub.id, "school_id": school_b.id, "status": PostStatus.PUBLISHED},
            "b_pending": {"id": post_b_pending.id, "school_id": school_b.id, "status": PostStatus.PENDING},
            "c_pub": {"id": post_c_pub.id, "school_id": school_c.id, "status": PostStatus.PUBLISHED},
        },
        "users": {
            "a": {"id": user_a.id, "token": _make_token(user_a.id), "school_id": school_a.id},
            "b": {"id": user_b.id, "token": _make_token(user_b.id), "school_id": school_b.id},
            "c": {"id": user_c.id, "token": _make_token(user_c.id), "school_id": school_c.id},
            "ab": {"id": user_ab.id, "token": _make_token(user_ab.id), "school_id": school_a.id},
            "admin_a": {"id": admin_a.id, "token": _make_token(admin_a.id), "school_id": school_a.id},
            "super": {"id": super_admin.id, "token": _make_token(super_admin.id), "school_id": school_a.id},
        },
    }


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _school_headers(code: str) -> dict:
    return {"X-School-Code": code}


# ============================================================
# TEN-02.1: TenantContext 解析测试
# ============================================================
class TestTenantContextResolution:
    """TenantContext 从 header / query / 默认学校解析"""

    @pytest.mark.asyncio
    async def test_guest_uses_header_school_code(
        self, client: AsyncClient, three_schools: dict
    ):
        """游客通过 X-School-Code 头指定学校"""
        resp = await client.get(
            "/api/v1/posts",
            headers=_school_headers("school-a"),
        )
        assert resp.status_code == 200
        data = resp.json()
        # 只返回 A 校已发布帖子
        post_ids = [p["id"] for p in data["items"]]
        assert three_schools["posts"]["a_pub"]["id"] in post_ids
        assert three_schools["posts"]["b_pub"]["id"] not in post_ids
        assert three_schools["posts"]["c_pub"]["id"] not in post_ids

    @pytest.mark.asyncio
    async def test_guest_uses_query_school_param(
        self, client: AsyncClient, three_schools: dict
    ):
        """游客通过 ?school= 参数指定学校"""
        resp = await client.get(
            "/api/v1/posts?school=school-b",
        )
        assert resp.status_code == 200
        post_ids = [p["id"] for p in resp.json()["items"]]
        assert three_schools["posts"]["b_pub"]["id"] in post_ids
        assert three_schools["posts"]["a_pub"]["id"] not in post_ids

    @pytest.mark.asyncio
    async def test_guest_without_school_code_returns_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """游客未提供 school code → 404（不泄露学校列表）"""
        resp = await client.get("/api/v1/posts")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_guest_nonexistent_school_returns_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """游客提供不存在的 school code → 404"""
        resp = await client.get(
            "/api/v1/posts",
            headers=_school_headers("nonexistent"),
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_logged_in_user_defaults_to_own_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """登录用户未指定 school code → 使用 user.school_id"""
        headers = _auth_headers(three_schools["users"]["a"]["token"])
        resp = await client.get("/api/v1/posts", headers=headers)
        assert resp.status_code == 200
        post_ids = [p["id"] for p in resp.json()["items"]]
        assert three_schools["posts"]["a_pub"]["id"] in post_ids
        assert three_schools["posts"]["b_pub"]["id"] not in post_ids

    @pytest.mark.asyncio
    async def test_header_overrides_user_default_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """X-School-Code 头覆盖用户默认学校（super_admin 可跨校）"""
        # super_admin 默认学校是 A，通过头切换到 B 校上下文
        headers = {
            **_auth_headers(three_schools["users"]["super"]["token"]),
            **_school_headers("school-b"),
        }
        resp = await client.get("/api/v1/posts", headers=headers)
        assert resp.status_code == 200
        post_ids = [p["id"] for p in resp.json()["items"]]
        assert three_schools["posts"]["b_pub"]["id"] in post_ids
        assert three_schools["posts"]["a_pub"]["id"] not in post_ids

    @pytest.mark.asyncio
    async def test_user_without_membership_cannot_access_other_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """普通用户无 membership 不能访问其他学校 → 404"""
        # user_a 只有 A 校 membership，尝试访问 B 校
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-b"),
        }
        resp = await client.get("/api/v1/posts", headers=headers)
        assert resp.status_code == 404


# ============================================================
# TEN-02.2: get_effective_role + 资源级校验测试
# ============================================================
class TestEffectiveRoleAndResourceCheck:
    """get_effective_role 与 check_resource_in_tenant 单元测试"""

    def test_guest_effective_role(self):
        """游客 → guest"""
        tenant = TenantContext(
            school_id=1, school_code="a", user=None,
            effective_role="guest", is_guest=True,
        )
        assert get_effective_role(None, tenant) == "guest"

    def test_super_admin_effective_role(self):
        """super_admin → 跨校仍为 super_admin"""
        sa = SimpleNamespace(id=1, role="super_admin", school_id=1)
        tenant = TenantContext(
            school_id=2, school_code="b", user=sa,
            effective_role=Role.SUPER_ADMIN, is_guest=False,
        )
        assert get_effective_role(sa, tenant) == Role.SUPER_ADMIN

    def test_admin_member_effective_role(self):
        """membership.role=admin → admin"""
        admin_user = SimpleNamespace(id=1, role="user", school_id=1)
        membership = SimpleNamespace(role="admin", status="active")
        tenant = TenantContext(
            school_id=1, school_code="a", user=admin_user,
            effective_role=Role.ADMIN, is_guest=False,
            membership=membership,
        )
        assert get_effective_role(admin_user, tenant) == Role.ADMIN

    def test_member_effective_role(self):
        """membership.role=member → user"""
        member_user = SimpleNamespace(id=1, role="user", school_id=1)
        membership = SimpleNamespace(role="member", status="active")
        tenant = TenantContext(
            school_id=1, school_code="a", user=member_user,
            effective_role=Role.USER, is_guest=False,
            membership=membership,
        )
        assert get_effective_role(member_user, tenant) == Role.USER

    def test_legacy_user_effective_role(self):
        """旧用户（无 membership，user.school_id 匹配）→ user"""
        legacy_user = SimpleNamespace(id=1, role="user", school_id=1)
        tenant = TenantContext(
            school_id=1, school_code="a", user=legacy_user,
            effective_role=Role.USER, is_guest=False,
            membership=None,
        )
        assert get_effective_role(legacy_user, tenant) == Role.USER

    def test_check_resource_in_tenant_same_school(self):
        """资源属于当前租户 → 不抛异常"""
        tenant = TenantContext(
            school_id=1, school_code="a", user=None,
            effective_role="guest", is_guest=True,
        )
        # 不应抛异常
        check_resource_in_tenant(1, tenant)

    def test_check_resource_in_tenant_cross_school_404(self):
        """资源不属于当前租户 → 404"""
        tenant = TenantContext(
            school_id=1, school_code="a", user=None,
            effective_role="guest", is_guest=True,
        )
        with pytest.raises(NotFoundException):
            check_resource_in_tenant(2, tenant)


# ============================================================
# TEN-02.3: 查询隔离测试（列表 / 分类 / 地点 / 搜索 / 地图）
# ============================================================
class TestQueryIsolation:
    """各列表接口按当前学校过滤，跨校数据不出现"""

    @pytest.mark.asyncio
    async def test_posts_list_only_returns_current_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """A 校请求帖子列表只返回 A 校已发布帖子"""
        resp = await client.get(
            "/api/v1/posts",
            headers=_school_headers("school-a"),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert three_schools["posts"]["a_pub"]["id"] in post_ids
        assert three_schools["posts"]["b_pub"]["id"] not in post_ids
        assert three_schools["posts"]["c_pub"]["id"] not in post_ids

    @pytest.mark.asyncio
    async def test_categories_only_returns_current_school(
        self, client: AsyncClient, three_schools: dict, db_session: AsyncSession
    ):
        """A 校请求分类列表只返回 A 校分类"""
        # 诊断：确认学校在 DB 中存在
        from sqlalchemy import select as _sel
        db_school = (await db_session.execute(
            _sel(School).where(School.code == "school-a")
        )).scalar_one_or_none()
        assert db_school is not None, "school-a 未在 DB 中创建"
        assert db_school.is_active is True, f"school-a is_active={db_school.is_active}"

        resp = await client.get(
            "/api/v1/categories",
            headers=_school_headers("school-a"),
        )
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        cat_ids = {c["id"] for c in resp.json()}
        assert three_schools["categories"]["a"]["id"] in cat_ids
        assert three_schools["categories"]["b"]["id"] not in cat_ids
        assert three_schools["categories"]["c"]["id"] not in cat_ids

    @pytest.mark.asyncio
    async def test_locations_only_returns_current_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """A 校请求地点列表只返回 A 校地点"""
        resp = await client.get(
            "/api/v1/locations",
            headers=_school_headers("school-a"),
        )
        assert resp.status_code == 200
        loc_ids = {loc["id"] for loc in resp.json()}
        assert three_schools["locations"]["a"]["id"] in loc_ids
        assert three_schools["locations"]["b"]["id"] not in loc_ids

    @pytest.mark.asyncio
    async def test_search_only_returns_current_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """搜索只返回当前学校的已发布帖子"""
        # 搜索关键词"已发布"应命中所有学校的已发布帖子，但只返回 A 校
        resp = await client.get(
            "/api/v1/search?keyword=已发布",
            headers=_school_headers("school-a"),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert three_schools["posts"]["a_pub"]["id"] in post_ids
        assert three_schools["posts"]["b_pub"]["id"] not in post_ids
        assert three_schools["posts"]["c_pub"]["id"] not in post_ids

    @pytest.mark.asyncio
    async def test_map_markers_only_returns_current_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """地图标记只返回当前学校（用大边界覆盖所有坐标）"""
        resp = await client.get(
            "/api/v1/map/markers?north=35&south=30&east=125&west=119",
            headers=_school_headers("school-a"),
        )
        assert resp.status_code == 200
        markers = resp.json()["markers"]
        post_ids = {m["post_id"] for m in markers}
        assert three_schools["posts"]["a_pub"]["id"] in post_ids
        assert three_schools["posts"]["b_pub"]["id"] not in post_ids
        assert three_schools["posts"]["c_pub"]["id"] not in post_ids

    @pytest.mark.asyncio
    async def test_three_schools_each_isolated(
        self, client: AsyncClient, three_schools: dict
    ):
        """三校各自请求只返回自己学校的数据"""
        for school_key, school_code, expected_post_key in [
            ("a", "school-a", "a_pub"),
            ("b", "school-b", "b_pub"),
            ("c", "school-c", "c_pub"),
        ]:
            resp = await client.get(
                "/api/v1/posts",
                headers=_school_headers(school_code),
            )
            assert resp.status_code == 200, f"school {school_key} failed"
            post_ids = {p["id"] for p in resp.json()["items"]}
            assert three_schools["posts"][expected_post_key]["id"] in post_ids
            # 确保其他学校的帖子不出现
            for other_key, other_post in three_schools["posts"].items():
                if other_key != expected_post_key and other_post["status"] == PostStatus.PUBLISHED:
                    assert other_post["id"] not in post_ids, (
                        f"school {school_key} leaked post from {other_key}"
                    )


# ============================================================
# TEN-02.3: 资源级校验测试（跨校详情 → 404）
# ============================================================
class TestResourceLevelIsolation:
    """跨校访问资源详情统一返回 404"""

    @pytest.mark.asyncio
    async def test_cross_school_post_detail_returns_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """A 校上下文访问 B 校帖子 → 404"""
        # user_a 是 A 校用户，在 A 校上下文访问 B 校帖子
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.get(
            f"/api/v1/posts/{three_schools['posts']['b_pub']['id']}",
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_school_post_detail_same_user_returns_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """同一用户在 B 校上下文访问自己在 A 校发的帖子 → 404"""
        # super_admin 可跨校访问 B 校上下文，但资源级校验仍隔离 A 校帖子
        headers = {
            **_auth_headers(three_schools["users"]["super"]["token"]),
            **_school_headers("school-b"),
        }
        resp = await client.get(
            f"/api/v1/posts/{three_schools['posts']['a_pub']['id']}",
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_same_school_post_detail_ok(
        self, client: AsyncClient, three_schools: dict
    ):
        """A 校上下文访问 A 校帖子 → 200"""
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.get(
            f"/api/v1/posts/{three_schools['posts']['a_pub']['id']}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == three_schools["posts"]["a_pub"]["id"]


# ============================================================
# TEN-02.1: 写请求忽略 body school_id
# ============================================================
class TestWriteIgnoresBodySchoolId:
    """写请求忽略 body 里的 school_id，强制使用 TenantContext 解析的学校"""

    @pytest.mark.asyncio
    async def test_create_post_ignores_body_school_id(
        self, client: AsyncClient, three_schools: dict
    ):
        """创建帖子时 body 里的 school_id 被忽略，使用 X-School-Code 解析的学校"""
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        # body 里传 school_id=B 校 ID，应被忽略
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "新帖子测试隔离",
                "content": "这是测试内容，至少十个字符",
                "category_id": three_schools["categories"]["a"]["id"],
                "is_anonymous": False,
                "school_id": three_schools["schools"]["b"]["id"],  # 应被忽略
            },
            headers=headers,
        )
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        # 验证帖子确实属于 A 校而非 B 校
        resp_detail = await client.get(
            f"/api/v1/posts/{created_id}",
            headers={
                **_auth_headers(three_schools["users"]["a"]["token"]),
                **_school_headers("school-a"),
            },
        )
        assert resp_detail.status_code == 200

        # B 校上下文应看不到该帖子（普通用户无 B 校 membership → 404）
        resp_b = await client.get(
            f"/api/v1/posts/{created_id}",
            headers={
                **_auth_headers(three_schools["users"]["a"]["token"]),
                **_school_headers("school-b"),
            },
        )
        assert resp_b.status_code == 404

    @pytest.mark.asyncio
    async def test_create_post_with_cross_school_category_returns_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """A 校上下文使用 B 校分类创建帖子 → 404（跨校分类不存在）"""
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "跨校分类测试",
                "content": "这是测试内容，至少十个字符",
                "category_id": three_schools["categories"]["b"]["id"],  # B 校分类
                "is_anonymous": False,
            },
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_location_ignores_body_school_id(
        self, client: AsyncClient, three_schools: dict
    ):
        """创建地点时 body 里的 school_id 被忽略"""
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.post(
            "/api/v1/locations",
            json={
                "name": "新地点",
                "latitude": 31.5,
                "longitude": 120.5,
                "school_id": three_schools["schools"]["b"]["id"],  # 应被忽略
            },
            headers=headers,
        )
        assert resp.status_code == 200
        loc_id = resp.json()["id"]

        # A 校能看到该地点
        resp_a = await client.get(
            "/api/v1/locations",
            headers=_school_headers("school-a"),
        )
        assert loc_id in {loc["id"] for loc in resp_a.json()}

        # B 校看不到该地点
        resp_b = await client.get(
            "/api/v1/locations",
            headers=_school_headers("school-b"),
        )
        assert loc_id not in {loc["id"] for loc in resp_b.json()}


# ============================================================
# TEN-02.3: 管理员隔离测试
# ============================================================
class TestAdminIsolation:
    """管理员只能管理本校，跨校管理操作返回 404"""

    @pytest.mark.asyncio
    async def test_admin_sees_own_school_pending_posts(
        self, client: AsyncClient, three_schools: dict
    ):
        """A 校管理员只看到 A 校待审核帖子"""
        headers = {
            **_auth_headers(three_schools["users"]["admin_a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.get("/api/v1/admin/posts/pending", headers=headers)
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert three_schools["posts"]["a_pending"]["id"] in post_ids
        assert three_schools["posts"]["b_pending"]["id"] not in post_ids

    @pytest.mark.asyncio
    async def test_admin_cannot_access_other_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """A 校管理员尝试访问 B 校 → 404（无 B 校 membership）"""
        headers = {
            **_auth_headers(three_schools["users"]["admin_a"]["token"]),
            **_school_headers("school-b"),
        }
        resp = await client.get("/api/v1/admin/posts/pending", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_cross_school_approve_returns_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """A 校管理员尝试审核 B 校帖子 → 404"""
        headers = {
            **_auth_headers(three_schools["users"]["admin_a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.put(
            f"/api/v1/admin/posts/{three_schools['posts']['b_pending']['id']}/approve",
            json={"reason": "审核通过"},
            headers=headers,
        )
        assert resp.status_code == 404


# ============================================================
# TEN-02.2: super_admin 跨校访问测试
# ============================================================
class TestSuperAdminCrossSchool:
    """super_admin 可跨校访问，但资源级校验仍生效"""

    @pytest.mark.asyncio
    async def test_super_admin_can_access_any_school(
        self, client: AsyncClient, three_schools: dict
    ):
        """super_admin 可访问 B 校（跳过 membership 校验）"""
        headers = {
            **_auth_headers(three_schools["users"]["super"]["token"]),
            **_school_headers("school-b"),
        }
        resp = await client.get("/api/v1/posts", headers=headers)
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert three_schools["posts"]["b_pub"]["id"] in post_ids

    @pytest.mark.asyncio
    async def test_super_admin_cross_school_resource_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """super_admin 在 A 校上下文访问 B 校帖子 → 404（资源级校验）"""
        headers = {
            **_auth_headers(three_schools["users"]["super"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.get(
            f"/api/v1/posts/{three_schools['posts']['b_pub']['id']}",
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_can_access_same_school_resource(
        self, client: AsyncClient, three_schools: dict
    ):
        """super_admin 在 B 校上下文访问 B 校帖子 → 200"""
        headers = {
            **_auth_headers(three_schools["users"]["super"]["token"]),
            **_school_headers("school-b"),
        }
        resp = await client.get(
            f"/api/v1/posts/{three_schools['posts']['b_pub']['id']}",
            headers=headers,
        )
        assert resp.status_code == 200


# ============================================================
# TEN-02.3: 互动隔离测试（点赞 / 评论）
# ============================================================
class TestInteractionIsolation:
    """跨校互动（点赞 / 评论）返回 404"""

    @pytest.mark.asyncio
    async def test_cross_school_like_returns_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """user_a 在 A 校上下文对 B 校帖子点赞 → 404"""
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.post(
            f"/api/v1/posts/{three_schools['posts']['b_pub']['id']}/like",
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_school_comment_returns_404(
        self, client: AsyncClient, three_schools: dict
    ):
        """user_a 在 A 校上下文对 B 校帖子评论 → 404"""
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.post(
            f"/api/v1/posts/{three_schools['posts']['b_pub']['id']}/comments",
            json={"content": "跨校评论测试"},
            headers=headers,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_same_school_like_ok(
        self, client: AsyncClient, three_schools: dict
    ):
        """user_a 在 A 校上下文对 A 校帖子点赞 → 200"""
        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.post(
            f"/api/v1/posts/{three_schools['posts']['a_pub']['id']}/like",
            headers=headers,
        )
        assert resp.status_code == 200


# ============================================================
# TEN-02.4: 跨校数据库无写入验证
# ============================================================
class TestNoCrossSchoolWrite:
    """跨校操作返回 404 且数据库无写入"""

    @pytest.mark.asyncio
    async def test_cross_school_create_no_db_write(
        self, client: AsyncClient, three_schools: dict, db_session: AsyncSession
    ):
        """A 校上下文使用 B 校分类创建帖子失败后，DB 中不新增帖子"""
        from sqlalchemy import func

        # 统计当前帖子数
        count_before = (await db_session.execute(select(func.count(Post.id)))).scalar()

        headers = {
            **_auth_headers(three_schools["users"]["a"]["token"]),
            **_school_headers("school-a"),
        }
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "跨校分类不应创建",
                "content": "这是测试内容，至少十个字符",
                "category_id": three_schools["categories"]["b"]["id"],
            },
            headers=headers,
        )
        assert resp.status_code == 404

        # 用全新 session 统计，确保看到 API session 提交后的真实数据
        from tests.conftest import test_session_maker
        async with test_session_maker() as fresh_session:
            count_after = (await fresh_session.execute(select(func.count(Post.id)))).scalar()
        assert count_after == count_before, "跨校创建失败后不应在 DB 写入新帖子"
