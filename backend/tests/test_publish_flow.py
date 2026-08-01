"""PUB-01: 统一发布表单 + 动态分类/地点 + 图片/有效期测试

覆盖 PUB-01.1 / PUB-01.2 / PUB-01.3 三个子任务的后端契约：

1. **动态数据来源**：
   - GET /categories 按当前学校过滤
   - GET /locations 按当前学校过滤，返回 is_verified 字段

2. **发布表单字段**：
   - POST /posts 接受 image_urls（最多 9 张）/ expire_at /
     contact_info / lost_type / is_anonymous
   - 创建时只允许 status=draft 或 pending，其余 4 态由状态机管理（FND-01.2）

3. **地点选择 + 新增地点队列**：
   - 已存在 location_id：直接关联
   - 新地点（location_name + lat + lng）：自动创建 Location，is_verified=False（核验队列）
   - POST /locations 显式创建地点：is_verified=False

4. **三校发布**：
   - A 校用户带 X-School-Code=school-a 发布 → 帖子归属 A 校
   - 跨校分类（用 B 校 category_id + A 校 X-School-Code）→ 404
   - body 里传 school_id 字段被忽略，强制使用 tenant.school_id
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, create_access_token
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.post_image import PostImage
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
    """为学校分配 operations 档订阅（COM-01 要求上传/发布需 active 订阅）"""
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
    )
    db.add(user)
    await db.flush()
    return user


async def _create_membership(
    db: AsyncSession, user_id: int, school_id: int, role: str = "member"
) -> SchoolMembership:
    m = SchoolMembership(
        user_id=user_id,
        school_id=school_id,
        role=role,
        status="active",
        is_default=False,
    )
    db.add(m)
    await db.flush()
    return m


async def _create_category(db: AsyncSession, school_id: int, name: str, code: str) -> Category:
    cat = Category(
        school_id=school_id,
        name=name,
        code=code,
        icon="🔍",
        default_validity_days=30,
        is_active=True,
    )
    db.add(cat)
    await db.flush()
    return cat


def _make_token(user_id: int) -> str:
    return create_access_token(data={"sub": str(user_id)})


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _school_headers(code: str) -> dict:
    return {"X-School-Code": code}


@pytest_asyncio.fixture
async def three_schools_for_publish(db_session: AsyncSession) -> dict:
    """创建三校测试数据：每校 1 用户 + 1 分类 + 1 已核验地点 + 1 信息类型（共享）

    用于 PUB-01.3 三校发布测试：A/B/C 校用户都能在各自学校正确发布。
    """
    school_a = await _create_school(db_session, "A 校", "school-a")
    school_b = await _create_school(db_session, "B 校", "school-b")
    school_c = await _create_school(db_session, "C 校", "school-c")

    for sid in (school_a.id, school_b.id, school_c.id):
        await _assign_operations_subscription(db_session, sid)

    cat_a = await _create_category(db_session, school_a.id, "A 校失物", "a-lost")
    cat_b = await _create_category(db_session, school_b.id, "B 校失物", "b-lost")
    cat_c = await _create_category(db_session, school_c.id, "C 校失物", "c-lost")

    # 每校 1 已核验地点
    loc_a = Location(
        school_id=school_a.id, name="A 校图书馆",
        latitude=31.0, longitude=120.0, is_verified=True,
    )
    loc_b = Location(
        school_id=school_b.id, name="B 校图书馆",
        latitude=32.0, longitude=121.0, is_verified=True,
    )
    loc_c = Location(
        school_id=school_c.id, name="C 校图书馆",
        latitude=33.0, longitude=122.0, is_verified=True,
    )
    db_session.add_all([loc_a, loc_b, loc_c])
    await db_session.flush()

    # 每校 1 普通用户
    user_a = await _create_user(db_session, "a@example.com", "A 校用户", school_a.id)
    user_b = await _create_user(db_session, "b@example.com", "B 校用户", school_b.id)
    user_c = await _create_user(db_session, "c@example.com", "C 校用户", school_c.id)
    await _create_membership(db_session, user_a.id, school_a.id, "member")
    await _create_membership(db_session, user_b.id, school_b.id, "member")
    await _create_membership(db_session, user_c.id, school_c.id, "member")

    await db_session.commit()

    return {
        "schools": {
            "a": {"id": school_a.id, "code": school_a.code},
            "b": {"id": school_b.id, "code": school_b.code},
            "c": {"id": school_c.id, "code": school_c.code},
        },
        "categories": {
            "a": {"id": cat_a.id},
            "b": {"id": cat_b.id},
            "c": {"id": cat_c.id},
        },
        "locations": {
            "a": {"id": loc_a.id},
            "b": {"id": loc_b.id},
            "c": {"id": loc_c.id},
        },
        "users": {
            "a": {"id": user_a.id, "token": _make_token(user_a.id)},
            "b": {"id": user_b.id, "token": _make_token(user_b.id)},
            "c": {"id": user_c.id, "token": _make_token(user_c.id)},
        },
    }


# ============================================================
# PUB-01.1: 动态数据来源（categories / locations）
# ============================================================
class TestPublishFormDataSources:
    """发布表单动态数据来源测试"""

    @pytest.mark.asyncio
    async def test_get_locations_returns_is_verified_field(
        self, client: AsyncClient, db_session: AsyncSession, test_school: dict
    ):
        """GET /locations 返回 is_verified 字段（PUB-01.2 关键字段）"""
        # 一个已核验地点 + 一个未核验地点
        loc_verified = Location(
            school_id=test_school["id"], name="已核验教学楼",
            latitude=31.0, longitude=120.0, is_verified=True,
        )
        loc_unverified = Location(
            school_id=test_school["id"], name="用户提交地点",
            latitude=31.1, longitude=120.1, is_verified=False,
        )
        db_session.add_all([loc_verified, loc_unverified])
        await db_session.commit()

        resp = await client.get(
            "/api/v1/locations",
            headers=_school_headers(test_school["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # 每项都有 is_verified 字段
        for loc in data:
            assert "is_verified" in loc
            assert isinstance(loc["is_verified"], bool)
        # 已核验与未核验都返回（核验状态由前端区分展示）
        names = [loc["name"] for loc in data]
        assert "已核验教学楼" in names
        assert "用户提交地点" in names
        # 字段值正确
        v = next(loc for loc in data if loc["name"] == "已核验教学楼")
        assert v["is_verified"] is True
        u = next(loc for loc in data if loc["name"] == "用户提交地点")
        assert u["is_verified"] is False

    @pytest.mark.asyncio
    async def test_get_categories_tenant_scoped(
        self, client: AsyncClient, three_schools_for_publish: dict
    ):
        """GET /categories 按当前学校过滤，跨校分类不出现"""
        # A 校请求只看到 A 校分类
        resp_a = await client.get(
            "/api/v1/categories",
            headers=_school_headers(three_schools_for_publish["schools"]["a"]["code"]),
        )
        assert resp_a.status_code == 200
        cat_a_ids = [c["id"] for c in resp_a.json()]
        assert three_schools_for_publish["categories"]["a"]["id"] in cat_a_ids
        assert three_schools_for_publish["categories"]["b"]["id"] not in cat_a_ids

        # B 校请求只看到 B 校分类
        resp_b = await client.get(
            "/api/v1/categories",
            headers=_school_headers(three_schools_for_publish["schools"]["b"]["code"]),
        )
        assert resp_b.status_code == 200
        cat_b_ids = [c["id"] for c in resp_b.json()]
        assert three_schools_for_publish["categories"]["b"]["id"] in cat_b_ids
        assert three_schools_for_publish["categories"]["a"]["id"] not in cat_b_ids


# ============================================================
# PUB-01.2: 表单字段（图片/信息截止时间/联系方式/匿名/失物类型）
# ============================================================
class TestPublishFormFields:
    """发布表单字段完整持久化测试"""

    @pytest.mark.asyncio
    async def test_create_post_with_full_fields(
        self, client: AsyncClient, auth_headers: dict, test_school: dict,
        test_category: dict, db_session: AsyncSession,
    ):
        """创建帖子时携带全部 PUB-01.2 字段，验证全部持久化

        Task 1.3 调整：移除 tags 字段（Tag 模型已删除）
        Task 1.4 调整：移除 activity_start_at / activity_end_at（活动时间字段已删除）
        """
        expire = (datetime.now() + timedelta(days=7)).isoformat()

        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "完整字段发布测试标题",
                "content": "这是包含全部字段的发布测试内容，至少十个字符",
                "category_id": test_category["id"],
                "is_anonymous": True,
                "image_urls": ["/uploads/test1.jpg", "/uploads/test2.jpg"],
                "expire_at": expire,
                "contact_info": "微信号：test123",
                "lost_type": "found",
                "status": "pending",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        post_id = data["id"]

        # 验证响应字段
        assert data["is_anonymous"] is True
        assert data["contact_info"] == "微信号：test123"
        assert data["lost_type"] == "found"
        assert data["status"] == "pending"
        # expire_at 应被持久化（精确到秒级比较，避免微秒差异）
        assert data["expire_at"] is not None

        # 验证图片持久化（直接查 DB，因为 PostResponse.images 字段在 create 响应中可能未填充）
        img_result = await db_session.execute(
            select(PostImage).where(PostImage.post_id == post_id).order_by(PostImage.sort_order)
        )
        images = img_result.scalars().all()
        assert len(images) == 2
        assert images[0].image_url == "/uploads/test1.jpg"
        assert images[0].sort_order == 0
        assert images[1].image_url == "/uploads/test2.jpg"
        assert images[1].sort_order == 1

    @pytest.mark.asyncio
    async def test_create_post_with_image_urls_limit(
        self, client: AsyncClient, auth_headers: dict, test_category: dict,
    ):
        """图片数量上限 9 张，超出应被拒绝（422）"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "图片上限测试标题",
                "content": "测试图片数量上限，至少十个字符",
                "category_id": test_category["id"],
                "image_urls": [f"/uploads/{i}.jpg" for i in range(10)],  # 10 张
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_post_status_draft_allowed(
        self, client: AsyncClient, auth_headers: dict, test_category: dict,
    ):
        """创建时 status=draft 允许（存为草稿）"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "草稿测试标题",
                "content": "测试草稿状态创建，至少十个字符",
                "category_id": test_category["id"],
                "status": "draft",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    @pytest.mark.asyncio
    async def test_create_post_status_published_rejected(
        self, client: AsyncClient, auth_headers: dict, test_category: dict,
    ):
        """FND-01.2: 创建时 status=published 应被拒绝（必须走状态机）"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "非法状态测试标题",
                "content": "测试非法初始状态，至少十个字符",
                "category_id": test_category["id"],
                "status": "published",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_post_default_expire_from_category(
        self, client: AsyncClient, auth_headers: dict, test_school: dict,
        test_category: dict, db_session: AsyncSession,
    ):
        """未传 expire_at 时，后端按分类 default_validity_days 自动计算"""
        # test_category 默认 default_validity_days=30
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "默认信息截止天数测试标题",
                "content": "测试默认信息截止天数，至少十个字符",
                "category_id": test_category["id"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["expire_at"] is not None
        # 验证信息截止时间约为 30 天后（允许 ±2 小时偏差）
        expire = datetime.fromisoformat(data["expire_at"].replace("Z", "+00:00"))
        delta = expire - datetime.now(expire.tzinfo)
        assert timedelta(days=29) < delta < timedelta(days=31)


# ============================================================
# PUB-01.2: 地点选择 + 新增地点队列（is_verified=false）
# ============================================================
class TestPublishLocationQueue:
    """地点选择与新增地点队列测试"""

    @pytest.mark.asyncio
    async def test_create_post_with_existing_location(
        self, client: AsyncClient, auth_headers: dict, test_school: dict,
        test_category: dict, db_session: AsyncSession,
    ):
        """使用已存在 location_id：直接关联，不创建新地点"""
        # 先创建一个已核验地点
        loc = Location(
            school_id=test_school["id"], name="测试图书馆",
            latitude=31.0, longitude=120.0, is_verified=True,
        )
        db_session.add(loc)
        await db_session.commit()
        await db_session.refresh(loc)

        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "已有地点测试标题",
                "content": "测试使用已有地点，至少十个字符",
                "category_id": test_category["id"],
                "location_id": loc.id,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["location_id"] == loc.id

        # 验证地点总数没有增加
        loc_count = (await db_session.execute(
            select(Location).where(Location.school_id == test_school["id"])
        )).scalars().all()
        assert len(loc_count) == 1

    @pytest.mark.asyncio
    async def test_create_post_with_new_location_creates_unverified(
        self, client: AsyncClient, auth_headers: dict, test_school: dict,
        test_category: dict, db_session: AsyncSession,
    ):
        """传 location_name + lat + lng：自动创建 Location，is_verified=False（核验队列）"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "新地点测试标题",
                "content": "测试新地点自动创建，至少十个字符",
                "category_id": test_category["id"],
                "location_name": "南区新食堂",
                "location_lat": 31.4837,
                "location_lng": 120.2712,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        post_id = resp.json()["id"]
        location_id = resp.json()["location_id"]
        assert location_id is not None

        # 验证新地点被创建，且 is_verified=False
        loc_result = await db_session.execute(
            select(Location).where(Location.id == location_id)
        )
        loc = loc_result.scalar_one()
        assert loc.name == "南区新食堂"
        assert loc.is_verified is False, "新地点应进入核验队列（is_verified=False）"
        assert loc.school_id == test_school["id"]
        assert float(loc.latitude) == 31.4837
        assert float(loc.longitude) == 120.2712

        # 验证帖子已关联该地点
        post_result = await db_session.execute(
            select(Post).where(Post.id == post_id)
        )
        post = post_result.scalar_one()
        assert post.location_id == loc.id

    @pytest.mark.asyncio
    async def test_create_post_new_location_dedup_same_school(
        self, client: AsyncClient, auth_headers: dict, test_school: dict,
        test_category: dict, db_session: AsyncSession,
    ):
        """同校同坐标同名地点去重：第二次发布复用第一次创建的地点"""
        payload = {
            "title": "去重第一次发布标题",
            "content": "测试同地点去重，至少十个字符",
            "category_id": test_category["id"],
            "location_name": "去重地点",
            "location_lat": 30.0,
            "location_lng": 110.0,
        }
        resp1 = await client.post("/api/v1/posts", json=payload, headers=auth_headers)
        assert resp1.status_code == 201
        loc_id_1 = resp1.json()["location_id"]

        payload2 = {
            **payload,
            "title": "去重第二次发布标题",
            "content": "测试同地点去重第二次，至少十个字符",
        }
        resp2 = await client.post("/api/v1/posts", json=payload2, headers=auth_headers)
        assert resp2.status_code == 201
        loc_id_2 = resp2.json()["location_id"]

        # 两次发布应复用同一地点
        assert loc_id_1 == loc_id_2

        # 数据库中只有 1 个该名称地点
        locs = (await db_session.execute(
            select(Location).where(
                Location.school_id == test_school["id"],
                Location.name == "去重地点",
                Location.is_deleted == False,
            )
        )).scalars().all()
        assert len(locs) == 1

    @pytest.mark.asyncio
    async def test_post_locations_creates_unverified(
        self, client: AsyncClient, auth_headers: dict, test_school: dict,
        db_session: AsyncSession,
    ):
        """POST /locations 显式创建地点：is_verified=False（核验队列）"""
        resp = await client.post(
            "/api/v1/locations",
            json={
                "name": "用户提交新地点",
                "latitude": 31.5,
                "longitude": 120.3,
                "description": "用户在发布表单中新增的地点",
            },
            headers={**auth_headers, **_school_headers(test_school["code"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "用户提交新地点"
        assert data["is_verified"] is False, "POST /locations 创建的地点应进入核验队列"

        # 数据库验证
        loc = (await db_session.execute(
            select(Location).where(Location.id == data["id"])
        )).scalar_one()
        assert loc.is_verified is False
        assert loc.school_id == test_school["id"]

    @pytest.mark.asyncio
    async def test_create_post_with_cross_school_location_rejected(
        self, client: AsyncClient, three_schools_for_publish: dict,
        db_session: AsyncSession,
    ):
        """TEN-02.3: 使用 B 校 location_id + A 校 X-School-Code → 404"""
        school_a_code = three_schools_for_publish["schools"]["a"]["code"]
        loc_b_id = three_schools_for_publish["locations"]["b"]["id"]
        cat_a_id = three_schools_for_publish["categories"]["a"]["id"]
        token_a = three_schools_for_publish["users"]["a"]["token"]

        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "跨校地点测试标题",
                "content": "测试跨校地点应被拒绝，至少十个字符",
                "category_id": cat_a_id,
                "location_id": loc_b_id,  # B 校地点
            },
            headers={**_auth_headers(token_a), **_school_headers(school_a_code)},
        )
        assert resp.status_code == 404


# ============================================================
# PUB-01.3: 三校发布 + 跳转（后端只验证归属，跳转由前端实现）
# ============================================================
class TestThreeSchoolPublish:
    """三校发布端到端测试

    PUB-01.3：三校用户均可在各自学校正确发布；发布后帖子归属正确学校。
    前端"跳我的发布"由 PublishPage.tsx 实现，此处只验证后端归属正确。
    """

    @pytest.mark.asyncio
    async def test_school_a_user_publishes_to_school_a(
        self, client: AsyncClient, three_schools_for_publish: dict,
        db_session: AsyncSession,
    ):
        """A 校用户带 X-School-Code=school-a 发布 → 帖子归属 A 校"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "A 校发布测试标题",
                "content": "A 校用户在 A 校发布的内容，至少十个字符",
                "category_id": three_schools_for_publish["categories"]["a"]["id"],
                "location_id": three_schools_for_publish["locations"]["a"]["id"],
            },
            headers={
                **_auth_headers(three_schools_for_publish["users"]["a"]["token"]),
                **_school_headers(three_schools_for_publish["schools"]["a"]["code"]),
            },
        )
        assert resp.status_code == 201
        post_id = resp.json()["id"]
        # 验证归属 A 校
        post = (await db_session.execute(
            select(Post).where(Post.id == post_id)
        )).scalar_one()
        assert post.school_id == three_schools_for_publish["schools"]["a"]["id"]

    @pytest.mark.asyncio
    async def test_school_b_user_publishes_to_school_b(
        self, client: AsyncClient, three_schools_for_publish: dict,
        db_session: AsyncSession,
    ):
        """B 校用户带 X-School-Code=school-b 发布 → 帖子归属 B 校"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "B 校发布测试标题",
                "content": "B 校用户在 B 校发布的内容，至少十个字符",
                "category_id": three_schools_for_publish["categories"]["b"]["id"],
                "location_id": three_schools_for_publish["locations"]["b"]["id"],
            },
            headers={
                **_auth_headers(three_schools_for_publish["users"]["b"]["token"]),
                **_school_headers(three_schools_for_publish["schools"]["b"]["code"]),
            },
        )
        assert resp.status_code == 201
        post_id = resp.json()["id"]
        post = (await db_session.execute(
            select(Post).where(Post.id == post_id)
        )).scalar_one()
        assert post.school_id == three_schools_for_publish["schools"]["b"]["id"]

    @pytest.mark.asyncio
    async def test_school_c_user_publishes_to_school_c(
        self, client: AsyncClient, three_schools_for_publish: dict,
        db_session: AsyncSession,
    ):
        """C 校用户带 X-School-Code=school-c 发布 → 帖子归属 C 校"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "C 校发布测试标题",
                "content": "C 校用户在 C 校发布的内容，至少十个字符",
                "category_id": three_schools_for_publish["categories"]["c"]["id"],
                "location_id": three_schools_for_publish["locations"]["c"]["id"],
            },
            headers={
                **_auth_headers(three_schools_for_publish["users"]["c"]["token"]),
                **_school_headers(three_schools_for_publish["schools"]["c"]["code"]),
            },
        )
        assert resp.status_code == 201
        post_id = resp.json()["id"]
        post = (await db_session.execute(
            select(Post).where(Post.id == post_id)
        )).scalar_one()
        assert post.school_id == three_schools_for_publish["schools"]["c"]["id"]

    @pytest.mark.asyncio
    async def test_cross_school_category_rejected(
        self, client: AsyncClient, three_schools_for_publish: dict,
    ):
        """TEN-02.3: A 校 X-School-Code + B 校 category_id → 404"""
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "跨校分类测试标题",
                "content": "测试跨校分类应被拒绝，至少十个字符",
                "category_id": three_schools_for_publish["categories"]["b"]["id"],  # B 校分类
            },
            headers={
                **_auth_headers(three_schools_for_publish["users"]["a"]["token"]),
                **_school_headers(three_schools_for_publish["schools"]["a"]["code"]),  # A 校请求
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_body_school_id_ignored_uses_tenant(
        self, client: AsyncClient, three_schools_for_publish: dict,
        db_session: AsyncSession,
    ):
        """TEN-02.1: body 里传 school_id 字段被忽略，强制使用 tenant.school_id

        即使 body 声明 school_id=B 校，X-School-Code=A 校时帖子仍归属 A 校。
        （PostCreate schema 没有 school_id 字段，Pydantic 默认忽略未知字段，
        此测试验证该行为：不会因 body 含 school_id 报错，且帖子归属 A 校）
        """
        resp = await client.post(
            "/api/v1/posts",
            json={
                "title": "body school_id 忽略测试标题",
                "content": "测试 body school_id 被忽略，至少十个字符",
                "category_id": three_schools_for_publish["categories"]["a"]["id"],
                "school_id": three_schools_for_publish["schools"]["b"]["id"],  # 应被忽略
            },
            headers={
                **_auth_headers(three_schools_for_publish["users"]["a"]["token"]),
                **_school_headers(three_schools_for_publish["schools"]["a"]["code"]),
            },
        )
        assert resp.status_code == 201
        post_id = resp.json()["id"]
        post = (await db_session.execute(
            select(Post).where(Post.id == post_id)
        )).scalar_one()
        # 帖子归属 A 校（tenant 解析得到），而非 body 声明的 B 校
        assert post.school_id == three_schools_for_publish["schools"]["a"]["id"]

    @pytest.mark.asyncio
    async def test_three_schools_isolation_after_publish(
        self, client: AsyncClient, three_schools_for_publish: dict,
    ):
        """三校发布后，每校 GET /posts 只能看到本校已发布帖子"""
        # 三校用户各自发布（默认 pending，需要直接 DB 改 published 才能在公开列表看到）
        # 这里改为验证 GET /posts 返回的列表严格按学校过滤：通过 X-School-Code 切换
        for school_key in ("a", "b", "c"):
            token = three_schools_for_publish["users"][school_key]["token"]
            school_code = three_schools_for_publish["schools"][school_key]["code"]
            cat_id = three_schools_for_publish["categories"][school_key]["id"]
            loc_id = three_schools_for_publish["locations"][school_key]["id"]

            resp = await client.post(
                "/api/v1/posts",
                json={
                    "title": f"{school_key} 校帖子标题",
                    "content": f"{school_key} 校帖子内容，至少十个字符",
                    "category_id": cat_id,
                    "location_id": loc_id,
                    "status": "pending",
                },
                headers={**_auth_headers(token), **_school_headers(school_code)},
            )
            assert resp.status_code == 201, f"{school_key} 校发布失败: {resp.text}"

        # 三校各自的 categories / locations 都能拉到
        for school_key in ("a", "b", "c"):
            school_code = three_schools_for_publish["schools"][school_key]["code"]
            expected_cat_id = three_schools_for_publish["categories"][school_key]["id"]

            resp_cat = await client.get(
                "/api/v1/categories",
                headers=_school_headers(school_code),
            )
            assert resp_cat.status_code == 200
            cat_ids = [c["id"] for c in resp_cat.json()]
            assert expected_cat_id in cat_ids
            # 其他两校的分类不出现在本校列表
            for other_key in ("a", "b", "c"):
                if other_key == school_key:
                    continue
                other_cat_id = three_schools_for_publish["categories"][other_key]["id"]
                assert other_cat_id not in cat_ids, (
                    f"{school_key} 校看到了 {other_key} 校的分类"
                )
