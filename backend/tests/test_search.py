"""DSC-01: 搜索筛选、N+1、分页、错误状态与地图联动 测试

覆盖：
    DSC-01.1: 搜索/列表支持分类/地点/帖子类型/有效状态/时间/排序，分页 total/total_pages/has_more
    DSC-01.2: 列表查询预加载关联，无 N+1（通过查询计数验证）
    DSC-01.3: 三校发现路径只返回当前学校（与 test_tenant_isolation 互补）
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import event as sqla_event

from app.core.security import create_access_token, get_password_hash
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.post import Post
from app.models.location import Location
from app.models.post_image import PostImage
from app.models.tag import Tag
from app.models.post_tag import PostTag
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription
from app.core.post_status import PostStatus


# ============================================================
# 辅助：复用 test_tenant_isolation 的三校夹具模式
# ============================================================
async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    s = School(name=name, code=code, is_active=True)
    db.add(s)
    await db.flush()
    return s


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


async def _create_user(db: AsyncSession, email: str, nickname: str, school_id: int) -> User:
    u = User(
        email=email, nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id, role="user",
    )
    db.add(u)
    await db.flush()
    return u


async def _create_membership(db: AsyncSession, user_id: int, school_id: int) -> None:
    db.add(SchoolMembership(
        user_id=user_id, school_id=school_id,
        role="member", status="active", is_default=False,
    ))
    await db.flush()


async def _create_category(db: AsyncSession, school_id: int, name: str, code: str) -> Category:
    c = Category(
        school_id=school_id, name=name, code=code, icon="🔍",
        default_validity_days=30, is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


async def _create_location(db: AsyncSession, school_id: int, name: str, lat: float, lng: float) -> Location:
    loc = Location(school_id=school_id, name=name, latitude=lat, longitude=lng, is_verified=True)
    db.add(loc)
    await db.flush()
    return loc


async def _create_post(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    category_id: int,
    title: str,
    content: str = "默认内容至少十个字符",
    status: str = PostStatus.PUBLISHED,
    location_id: int | None = None,
    like_count: int = 0,
    created_at: datetime | None = None,
) -> Post:
    p = Post(
        user_id=user_id, school_id=school_id,
        category_id=category_id,
        location_id=location_id, title=title, content=content,
        status=status, like_count=like_count,
        created_at=created_at or datetime.now(),
    )
    db.add(p)
    await db.flush()
    return p


async def _add_image(db: AsyncSession, post_id: int, url: str, sort_order: int = 0) -> None:
    db.add(PostImage(post_id=post_id, image_url=url, sort_order=sort_order))
    await db.flush()


async def _add_tag(db: AsyncSession, post_id: int, name: str, slug: str) -> None:
    tag = Tag(name=name, slug=slug)
    db.add(tag)
    await db.flush()
    db.add(PostTag(post_id=post_id, tag_id=tag.id))
    await db.flush()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _school(code: str) -> dict:
    return {"X-School-Code": code}


@pytest_asyncio.fixture
async def search_setup(db_session: AsyncSession) -> dict:
    """DSC-01 测试夹具：单校（test-uni），多帖子覆盖各筛选维度

    帖子矩阵（共 5 条已发布 + 1 条已过期）：
        - p1: cat_a / loc_a / type_a / published / 5 赞 / 有封面图 / 有标签
        - p2: cat_a / loc_b / type_a / published / 3 赞 / 无图
        - p3: cat_b / loc_a / type_b / published / 10 赞 / 有图
        - p4: cat_b / loc_b / type_b / published / 0 赞 / 无图
        - p5: cat_a / loc_a / type_a / expired / 1 赞 / 有图（已过期仍可见）
        - p6: cat_a / loc_a / type_a / pending / 0 赞（不可见）
    """
    school = await _create_school(db_session, "搜索测试大学", "search-uni")
    await _assign_operations_subscription(db_session, school.id)

    user = await _create_user(db_session, "searchuser@example.com", "搜索用户", school.id)
    await _create_membership(db_session, user.id, school.id)

    cat_a = await _create_category(db_session, school.id, "失物", "lost")
    cat_b = await _create_category(db_session, school.id, "活动", "event")
    loc_a = await _create_location(db_session, school.id, "图书馆", 31.0, 120.0)
    loc_b = await _create_location(db_session, school.id, "食堂", 31.001, 120.001)

    base_time = datetime(2026, 1, 1, 12, 0, 0)
    p1 = await _create_post(
        db_session, user.id, school.id, cat_a.id,
        "图书馆失物招领钱包", "钱包内容描述", PostStatus.PUBLISHED,
        location_id=loc_a.id, like_count=5, created_at=base_time,
    )
    p2 = await _create_post(
        db_session, user.id, school.id, cat_a.id,
        "食堂失物钥匙", "钥匙内容描述", PostStatus.PUBLISHED,
        location_id=loc_b.id, like_count=3, created_at=base_time + timedelta(hours=1),
    )
    p3 = await _create_post(
        db_session, user.id, school.id, cat_b.id,
        "图书馆读书会活动", "读书会活动内容", PostStatus.PUBLISHED,
        location_id=loc_a.id, like_count=10, created_at=base_time + timedelta(hours=2),
    )
    p4 = await _create_post(
        db_session, user.id, school.id, cat_b.id,
        "食堂美食节活动", "美食节活动内容", PostStatus.PUBLISHED,
        location_id=loc_b.id, like_count=0, created_at=base_time + timedelta(hours=3),
    )
    p5 = await _create_post(
        db_session, user.id, school.id, cat_a.id,
        "已过期图书馆失物", "已过期内容", PostStatus.EXPIRED,
        location_id=loc_a.id, like_count=1, created_at=base_time + timedelta(hours=4),
    )
    p6 = await _create_post(
        db_session, user.id, school.id, cat_a.id,
        "待审核图书馆失物", "待审核内容", PostStatus.PENDING,
        location_id=loc_a.id, like_count=0, created_at=base_time + timedelta(hours=5),
    )

    # 给 p1 添加封面图与标签
    await _add_image(db_session, p1.id, "https://example.com/p1.jpg", 0)
    await _add_tag(db_session, p1.id, "钱包", "wallet")
    # p3 添加图片
    await _add_image(db_session, p3.id, "https://example.com/p3.jpg", 0)
    # p5 添加图片
    await _add_image(db_session, p5.id, "https://example.com/p5.jpg", 0)

    await db_session.commit()

    return {
        "school": {"id": school.id, "code": school.code, "name": school.name},
        "user": {"id": user.id, "token": create_access_token(data={"sub": str(user.id)})},
        "categories": {"a": cat_a, "b": cat_b},
        "locations": {"a": loc_a, "b": loc_b},
        "posts": {
            "p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5, "p6": p6,
        },
        "base_time": base_time,
    }


# ============================================================
# DSC-01.1: 搜索筛选维度测试
# ============================================================
class TestSearchFilters:
    """验证 GET /api/v1/search 支持全部筛选维度"""

    @pytest.mark.asyncio
    async def test_search_no_filter_returns_all_visible(
        self, client: AsyncClient, search_setup: dict
    ):
        """无筛选时返回 published + expired（不含 pending）"""
        resp = await client.get(
            "/api/v1/search", headers=_school(search_setup["school"]["code"])
        )
        assert resp.status_code == 200
        data = resp.json()
        post_ids = {p["id"] for p in data["items"]}
        # p1-p5 可见，p6 pending 不可见
        visible_ids = {search_setup["posts"][k].id for k in ("p1", "p2", "p3", "p4", "p5")}
        assert visible_ids.issubset(post_ids)
        assert search_setup["posts"]["p6"].id not in post_ids
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_search_filter_by_category(
        self, client: AsyncClient, search_setup: dict
    ):
        """按分类筛选"""
        cat_a_id = search_setup["categories"]["a"].id
        resp = await client.get(
            f"/api/v1/search?category_id={cat_a_id}",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        # cat_a 包含 p1, p2, p5（expired 可见），不含 p6（pending 不可见）
        assert search_setup["posts"]["p1"].id in post_ids
        assert search_setup["posts"]["p2"].id in post_ids
        assert search_setup["posts"]["p5"].id in post_ids
        assert search_setup["posts"]["p3"].id not in post_ids  # cat_b
        assert search_setup["posts"]["p4"].id not in post_ids  # cat_b
        assert search_setup["posts"]["p6"].id not in post_ids  # pending

    @pytest.mark.asyncio
    async def test_search_filter_by_location(
        self, client: AsyncClient, search_setup: dict
    ):
        """按地点筛选"""
        loc_a_id = search_setup["locations"]["a"].id
        resp = await client.get(
            f"/api/v1/search?location_id={loc_a_id}",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        # loc_a 包含 p1, p3, p5（expired）
        assert search_setup["posts"]["p1"].id in post_ids
        assert search_setup["posts"]["p3"].id in post_ids
        assert search_setup["posts"]["p5"].id in post_ids
        assert search_setup["posts"]["p2"].id not in post_ids  # loc_b
        assert search_setup["posts"]["p4"].id not in post_ids  # loc_b

    @pytest.mark.asyncio
    async def test_search_filter_by_post_type(
        self, client: AsyncClient, search_setup: dict
    ):
        """按帖子类型筛选"""
        pytest.skip("Task 1.2: PostType 已删除")

    @pytest.mark.asyncio
    async def test_search_filter_by_status_published(
        self, client: AsyncClient, search_setup: dict
    ):
        """status=published 仅返回已发布"""
        resp = await client.get(
            "/api/v1/search?status=published",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert search_setup["posts"]["p5"].id not in post_ids  # expired 被过滤
        assert search_setup["posts"]["p1"].id in post_ids  # published

    @pytest.mark.asyncio
    async def test_search_filter_by_status_expired(
        self, client: AsyncClient, search_setup: dict
    ):
        """status=expired 仅返回已过期"""
        resp = await client.get(
            "/api/v1/search?status=expired",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        post_ids = {p["id"] for p in data["items"]}
        assert search_setup["posts"]["p5"].id in post_ids
        assert search_setup["posts"]["p1"].id not in post_ids

    @pytest.mark.asyncio
    async def test_search_filter_by_date_range(
        self, client: AsyncClient, search_setup: dict
    ):
        """按时间范围筛选"""
        base = search_setup["base_time"]
        # 仅查询 base_time+2h 到 base_time+4h 之间，应该命中 p3, p4, p5
        date_from = (base + timedelta(hours=2)).isoformat()
        date_to = (base + timedelta(hours=4, minutes=1)).isoformat()
        resp = await client.get(
            f"/api/v1/search?date_from={date_from}&date_to={date_to}",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert search_setup["posts"]["p3"].id in post_ids
        assert search_setup["posts"]["p4"].id in post_ids
        assert search_setup["posts"]["p5"].id in post_ids
        assert search_setup["posts"]["p1"].id not in post_ids
        assert search_setup["posts"]["p2"].id not in post_ids

    @pytest.mark.asyncio
    async def test_search_keyword_match(
        self, client: AsyncClient, search_setup: dict
    ):
        """关键词搜索匹配 title/content"""
        resp = await client.get(
            "/api/v1/search?keyword=钱包",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        # 标题包含"钱包"的只有 p1
        assert search_setup["posts"]["p1"].id in post_ids
        assert len(post_ids) == 1

    @pytest.mark.asyncio
    async def test_search_combined_filters(
        self, client: AsyncClient, search_setup: dict
    ):
        """组合筛选：分类 + 地点 + 状态"""
        cat_a_id = search_setup["categories"]["a"].id
        loc_a_id = search_setup["locations"]["a"].id
        resp = await client.get(
            f"/api/v1/search?category_id={cat_a_id}&location_id={loc_a_id}&status=published",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        # cat_a + loc_a + published：p1（排除 p5 expired 与 p6 pending）
        assert search_setup["posts"]["p1"].id in post_ids
        assert search_setup["posts"]["p5"].id not in post_ids  # expired
        assert search_setup["posts"]["p6"].id not in post_ids  # pending


# ============================================================
# DSC-01.1: 排序测试
# ============================================================
class TestSearchSort:
    """验证 sort 参数生效"""

    @pytest.mark.asyncio
    async def test_sort_latest(
        self, client: AsyncClient, search_setup: dict
    ):
        """latest 按 created_at 降序"""
        resp = await client.get(
            "/api/v1/search?sort=latest",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # p5 是最后创建的（base_time+4h），应排第一
        assert items[0]["id"] == search_setup["posts"]["p5"].id

    @pytest.mark.asyncio
    async def test_sort_hottest(
        self, client: AsyncClient, search_setup: dict
    ):
        """hottest 按 like_count 降序"""
        resp = await client.get(
            "/api/v1/search?sort=hottest",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # p3 like_count=10 最高
        assert items[0]["id"] == search_setup["posts"]["p3"].id

    @pytest.mark.asyncio
    async def test_sort_invalid_returns_422(
        self, client: AsyncClient, search_setup: dict
    ):
        """非法 sort 参数返回 422"""
        resp = await client.get(
            "/api/v1/search?sort=invalid",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 422


# ============================================================
# DSC-01.1: 分页与响应格式测试
# ============================================================
class TestSearchPagination:
    """验证分页响应包含 total/total_pages/has_more"""

    @pytest.mark.asyncio
    async def test_pagination_response_shape(
        self, client: AsyncClient, search_setup: dict
    ):
        """响应包含所有分页字段"""
        resp = await client.get(
            "/api/v1/search?page=1&page_size=2",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        # FND-01.1: 分页字段统一
        assert "items" in data
        assert "total" in data
        assert "total_pages" in data
        assert "has_more" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3  # ceil(5/2)
        assert data["has_more"] is True

    @pytest.mark.asyncio
    async def test_pagination_second_page(
        self, client: AsyncClient, search_setup: dict
    ):
        """第二页数据不重复"""
        resp1 = await client.get(
            "/api/v1/search?page=1&page_size=2&sort=latest",
            headers=_school(search_setup["school"]["code"]),
        )
        resp2 = await client.get(
            "/api/v1/search?page=2&page_size=2&sort=latest",
            headers=_school(search_setup["school"]["code"]),
        )
        page1_ids = {p["id"] for p in resp1.json()["items"]}
        page2_ids = {p["id"] for p in resp2.json()["items"]}
        assert page1_ids.isdisjoint(page2_ids)  # 无交集
        assert resp2.json()["page"] == 2

    @pytest.mark.asyncio
    async def test_pagination_last_page_no_more(
        self, client: AsyncClient, search_setup: dict
    ):
        """最后一页 has_more=False"""
        resp = await client.get(
            "/api/v1/search?page=3&page_size=2&sort=latest",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_more"] is False


# ============================================================
# DSC-01.2: N+1 查询计数测试
# ============================================================
class TestSearchNoNPlusOne:
    """验证搜索/列表查询数固定，不随结果数线性增长

    使用 SQLAlchemy event 监听 before_cursor_execute，统计查询数。
    20 条结果应只触发固定数量的查询（预加载 6 关联：1 主查询 + 5 selectinload）。
    """

    @staticmethod
    async def _count_queries_for_search(
        client: AsyncClient, school_code: str, page_size: int
    ) -> tuple[int, int]:
        """发起一次搜索请求，返回 (查询数, 结果数)"""
        from tests.conftest import test_engine
        from sqlalchemy import event as sqla_event

        query_count = 0

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        # 监听测试引擎的 sync_engine
        sync_engine = test_engine.sync_engine
        sqla_event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)

        try:
            resp = await client.get(
                f"/api/v1/search?page=1&page_size={page_size}&sort=latest",
                headers=_school(school_code),
            )
            assert resp.status_code == 200
            items_count = len(resp.json()["items"])
        finally:
            sqla_event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)

        return query_count, items_count

    @pytest.mark.asyncio
    async def test_search_query_count_does_not_grow_with_results(
        self, client: AsyncClient, search_setup: dict
    ):
        """20 条 vs 5 条结果，查询数应相同（不随结果数线性增长）

        预期查询数（参考）：
            - 1 条 count 查询（total）
            - 1 条主查询（含 joinedload）
            - 2 条 selectinload（post_tags->tag, post_images）
            合计约 4-6 条固定查询，与结果数无关。

        验收：page_size=1 与 page_size=5 的查询数差不应超过 2 条（容差）。
        """
        school_code = search_setup["school"]["code"]

        # 5 条结果
        count_5, items_5 = await self._count_queries_for_search(client, school_code, 5)
        assert items_5 == 5, f"预期 5 条结果，实际 {items_5}"

        # 1 条结果
        count_1, items_1 = await self._count_queries_for_search(client, school_code, 1)
        assert items_1 == 1, f"预期 1 条结果，实际 {items_1}"

        # 关键断言：5 条结果不应比 1 条结果显著增加查询数
        # 旧实现每条结果 4 次额外查询，5 条 = 20+ 次；新实现应固定 ~4-6 次
        assert count_5 < count_1 + 3, (
            f"N+1 检测失败：1 条结果 {count_1} 次查询，"
            f"5 条结果 {count_5} 次查询，差值 {count_5 - count_1} 应小于 3"
        )
        # 且总数控制在合理范围（< 15 次）
        assert count_5 < 15, f"5 条结果查询数 {count_5} 过多，可能存在 N+1"


# ============================================================
# DSC-01.3: 三校发现路径只返回当前学校
# ============================================================
class TestSearchTenantIsolation:
    """验证三校搜索路径互不串数据（与 test_tenant_isolation 互补）

    覆盖 DSC-01.3: 三校发现路径只返回当前学校（已由 TEN-02 保证，但需验证搜索筛选仍生效）
    """

    @pytest_asyncio.fixture
    async def three_schools_search(self, db_session: AsyncSession) -> dict:
        """三校夹具：每校 2 已发布帖子"""
        schools = {}
        for code, name, lat in [("sch-a", "A 校", 31.0), ("sch-b", "B 校", 32.0), ("sch-c", "C 校", 33.0)]:
            s = await _create_school(db_session, name, code)
            await _assign_operations_subscription(db_session, s.id)
            u = await _create_user(db_session, f"{code}@example.com", name, s.id)
            await _create_membership(db_session, u.id, s.id)
            cat = await _create_category(db_session, s.id, f"{code}-cat", f"{code}-code")
            loc = await _create_location(db_session, s.id, f"{code}-loc", lat, 120.0)
            p1 = await _create_post(
                db_session, u.id, s.id, cat.id,
                f"{name}-帖1", f"{name}内容1", PostStatus.PUBLISHED, location_id=loc.id,
            )
            p2 = await _create_post(
                db_session, u.id, s.id, cat.id,
                f"{name}-帖2", f"{name}内容2", PostStatus.PUBLISHED, location_id=loc.id,
            )
            schools[code] = {
                "id": s.id, "code": s.code, "name": name,
                "user_token": create_access_token(data={"sub": str(u.id)}),
                "category_id": cat.id, "location_id": loc.id,
                "post_ids": {p1.id, p2.id},
            }
        await db_session.commit()
        return schools

    @pytest.mark.asyncio
    async def test_a_school_search_only_a(
        self, client: AsyncClient, three_schools_search: dict
    ):
        """A 校搜索只返回 A 校帖子，无 B/C 校"""
        schools = three_schools_search
        resp = await client.get(
            "/api/v1/search", headers=_school("sch-a")
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        # 只含 A 校帖子
        assert post_ids == schools["sch-a"]["post_ids"]
        # 不含 B/C 校帖子
        assert post_ids.isdisjoint(schools["sch-b"]["post_ids"])
        assert post_ids.isdisjoint(schools["sch-c"]["post_ids"])

    @pytest.mark.asyncio
    async def test_cross_school_filter_id_no_leak(
        self, client: AsyncClient, three_schools_search: dict
    ):
        """A 校用 B 校的 category_id 筛选 → 返回空（不泄露 B 校数据）"""
        schools = three_schools_search
        b_cat_id = schools["sch-b"]["category_id"]
        resp = await client.get(
            f"/api/v1/search?category_id={b_cat_id}",
            headers=_school("sch-a"),
        )
        assert resp.status_code == 200
        data = resp.json()
        # A 校上下文下，B 校 category_id 不匹配任何 A 校帖子
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_three_schools_each_search_isolated(
        self, client: AsyncClient, three_schools_search: dict
    ):
        """三校各自搜索只返回自己学校的帖子"""
        schools = three_schools_search
        for code in ("sch-a", "sch-b", "sch-c"):
            resp = await client.get(
                "/api/v1/search", headers=_school(code)
            )
            assert resp.status_code == 200
            post_ids = {p["id"] for p in resp.json()["items"]}
            assert post_ids == schools[code]["post_ids"], (
                f"{code} 搜索结果应只含本校帖子"
            )


# ============================================================
# DSC-01.2: /posts 列表端点 N+1 与筛选验证
# ============================================================
class TestPostsListNoNPlusOne:
    """验证 GET /api/v1/posts 列表筛选 + 无 N+1"""

    @pytest.mark.asyncio
    async def test_posts_list_filter_by_location(
        self, client: AsyncClient, search_setup: dict
    ):
        """GET /posts 支持 location_id 筛选"""
        loc_a_id = search_setup["locations"]["a"].id
        resp = await client.get(
            f"/api/v1/posts?location_id={loc_a_id}",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert search_setup["posts"]["p1"].id in post_ids
        assert search_setup["posts"]["p2"].id not in post_ids  # loc_b

    @pytest.mark.asyncio
    async def test_posts_list_filter_by_date_range(
        self, client: AsyncClient, search_setup: dict
    ):
        """GET /posts 支持 date_from / date_to 筛选"""
        base = search_setup["base_time"]
        date_from = (base + timedelta(hours=2)).isoformat()
        resp = await client.get(
            f"/api/v1/posts?date_from={date_from}",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert search_setup["posts"]["p3"].id in post_ids
        assert search_setup["posts"]["p1"].id not in post_ids  # 早于 date_from

    @pytest.mark.asyncio
    async def test_posts_list_status_filter(
        self, client: AsyncClient, search_setup: dict
    ):
        """GET /posts status=published 仅返回 published"""
        resp = await client.get(
            "/api/v1/posts?status=published",
            headers=_school(search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        post_ids = {p["id"] for p in resp.json()["items"]}
        assert search_setup["posts"]["p5"].id not in post_ids  # expired
        assert search_setup["posts"]["p1"].id in post_ids

    @pytest.mark.asyncio
    async def test_posts_list_no_n_plus_one(
        self, client: AsyncClient, search_setup: dict
    ):
        """GET /posts 列表查询数固定（DSC-01.2）"""
        from tests.conftest import test_engine
        from sqlalchemy import event as sqla_event

        query_count = 0

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        sync_engine = test_engine.sync_engine
        sqla_event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
        try:
            resp = await client.get(
                "/api/v1/posts?page=1&page_size=20",
                headers=_school(search_setup["school"]["code"]),
            )
            assert resp.status_code == 200
            items_count = len(resp.json()["items"])
        finally:
            sqla_event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)

        # 5 条结果应 < 15 次查询（旧 N+1 实现下每条 4 次额外查询 = 20+）
        assert items_count >= 3, "测试数据不足"
        assert query_count < 15, (
            f"列表查询数 {query_count} 过多，{items_count} 条结果应固定 ~5 次查询，可能存在 N+1"
        )


# ============================================================
# DSC-01.3: 地图端点 N+1 验证
# ============================================================
class TestMapNoNPlusOne:
    """验证 GET /api/v1/map/markers 查询数固定"""

    @pytest.mark.asyncio
    async def test_map_markers_no_n_plus_one(
        self, client: AsyncClient, search_setup: dict
    ):
        """地图 markers 查询数固定，不随 marker 数线性增长"""
        from tests.conftest import test_engine
        from sqlalchemy import event as sqla_event

        query_count = 0

        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        sync_engine = test_engine.sync_engine
        sqla_event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
        try:
            resp = await client.get(
                "/api/v1/map/markers?north=35&south=30&east=125&west=119",
                headers=_school(search_setup["school"]["code"]),
            )
            assert resp.status_code == 200
            markers_count = len(resp.json())
        finally:
            sqla_event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)

        # markers 仅返回 published（p1, p2, p3, p4 共 4 个；p5 expired 不返回）
        assert markers_count >= 3
        # 旧实现：1 主查询 + N 次封面图查询（N=markers_count）
        # 新实现：1 主查询 + 1 selectinload（post_images）
        assert query_count <= 5, (
            f"地图 markers 查询数 {query_count} 过多，{markers_count} 个 marker 应固定 2-3 次查询，可能存在 N+1"
        )
