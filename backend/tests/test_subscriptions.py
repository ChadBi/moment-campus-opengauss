"""SUB-01: 用户级内容订阅与四类通知测试

覆盖 SUB-01.1（订阅表 + API）与 SUB-01.2（四类通知场景）：

SUB-01.1：
1. 订阅 CRUD：POST/GET/list/check/targets/DELETE
2. 唯一约束：同用户同校同目标重复订阅 → 409
3. 跨校目标不可订阅：跨校 category_id → 404（不泄露存在性）
4. 跨校订阅不可见：A 校用户在 B 校 X-School-Code 下查询订阅列表为空
5. 校验：非法 target_type → 400；不存在的 target_id → 404
6. 仅可删除本人订阅：删除他人订阅 → 404

SUB-01.2 四类通知场景：
1. 新帖通知（subscription_new）：管理员审核通过 pending → published 时通知订阅者
2. 更新通知（subscription_update）：已发布帖子被实质修改回审 published → pending 时通知
3. 过期通知（subscription_expired）：GOV-02 自动过期任务 published → expired 时通知
4. 冲突通知（subscription_conflict）：管理员标记冲突时通知

SUB-01.2 边界：
- 排除作者：作者本人不接收自己帖子的订阅通知
- 跨校隔离：A 校订阅者不接收 B 校帖子通知
- 幂等性：重复触发不产生重复通知
- 偏好过滤：subscription_enabled=False 的订阅者不接收
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, create_access_token, create_refresh_token
from app.core.post_status import PostStatus
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.subscription import UserSubscription
from app.models.topic_collection import TopicCollection
from app.models.topic_collection_post import TopicCollectionPost
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription
from app.models.job_run_record import JobRunRecord
from app.jobs.expire_posts import expire_posts_job


# ============================================================
# 辅助函数
# ============================================================
async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    school = School(name=name, code=code, is_active=True)
    db.add(school)
    await db.flush()
    return school


async def _ensure_operations_plan(db: AsyncSession) -> ProductPlan:
    """确保 db_session 所在事务内存在 operations 档套餐，返回该套餐对象。

    背景：conftest.setup_database 通过 test_engine.begin()（独立连接）预置 3 档套餐，
    但 openGauss 跨连接可见性在某些时序下不稳定（ForeignKeyViolationError:
    Key (plan_id)=(N) is not present in table "product_plans"）。

    本函数采用三层防御策略：
    1. 优先 SELECT：若 db_session 能看到 conftest 预置的套餐，直接复用
    2. SELECT 未命中 → 通过 SAVEPOINT 尝试 INSERT：
       - INSERT 成功 → 套餐在本事务内创建，同事务可见性保证 FK 通过
       - INSERT 失败 (unique_violation) → conftest 已创建但本会话不可见，
         SAVEPOINT 回滚后重新 SELECT（READ COMMITTED 下新语句获得新快照，应能看到）
    3. 仍找不到 → 抛出断言错误（理论不应到达）
    """
    # 第 1 层：尝试 SELECT
    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == "operations")
    )).scalar_one_or_none()
    if plan is not None:
        return plan

    # 第 2 层：SAVEPOINT 内尝试 INSERT（处理跨连接不可见 + 唯一约束冲突）
    from sqlalchemy.exc import IntegrityError as _IntegrityError
    new_plan = ProductPlan(
        code="operations",
        name="运营档",
        description="operations desc",
        status="active",
        sort_order=30,
    )
    try:
        async with db.begin_nested():  # SAVEPOINT
            db.add(new_plan)
            await db.flush()
        return new_plan  # INSERT 成功
    except _IntegrityError:
        pass  # unique_violation → 进入第 3 层

    # 第 3 层：SAVEPOINT 回滚后重新 SELECT（新快照应能看到已提交的行）
    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == "operations")
    )).scalar_one_or_none()
    assert plan is not None, (
        "operations 套餐既无法 SELECT 也无法 INSERT："
        "请检查 conftest.setup_database 是否正确预置套餐数据"
    )
    return plan


async def _assign_operations_subscription(db: AsyncSession, school_id: int) -> None:
    """为学校分配 operations 档订阅（COM-01 要求发布需 active 订阅）

    使用 _ensure_operations_plan 在同事务内创建/获取套餐，避免跨连接可见性问题。
    """
    plan = await _ensure_operations_plan(db)
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
        is_active=True,
        is_deleted=False,
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


async def _create_location(db: AsyncSession, school_id: int, name: str) -> Location:
    loc = Location(
        school_id=school_id,
        name=name,
        latitude=30.0,
        longitude=120.0,
        is_verified=True,
        is_deleted=False,
    )
    db.add(loc)
    await db.flush()
    return loc


async def _create_topic(
    db: AsyncSession, school_id: int, creator_id: int, title: str, status: str = "published"
) -> TopicCollection:
    topic = TopicCollection(
        title=title,
        school_id=school_id,
        creator_id=creator_id,
        status=status,
        published_at=datetime.now() if status == "published" else None,
    )
    db.add(topic)
    await db.flush()
    return topic


async def _create_post(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    category_id: int,
    title: str = "测试帖子",
    status: str = PostStatus.PUBLISHED,
    expire_at: datetime | None = None,
    content: str = "这是测试内容，至少十个字符",
) -> Post:
    """直接在数据库中创建帖子（绕过 API，用于测试通知触发）"""
    post = Post(
        user_id=user_id,
        school_id=school_id,
        category_id=category_id,
        title=title,
        content=content,
        status=status,
        expire_at=expire_at,
        is_deleted=False,
        is_anonymous=False,
    )
    db.add(post)
    await db.flush()
    return post


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


def _auth_headers(user: dict) -> dict:
    return {
        "Authorization": f"Bearer {user['access_token']}",
        "X-School-Code": user["school_code"],
    }


async def _create_user_with_token(
    db: AsyncSession,
    email: str,
    nickname: str,
    school_id: int,
    school_code: str,
    role: str = "user",
    membership_role: str | None = None,
) -> dict:
    """直接在 DB 创建用户 + membership + 生成 token（单 session，避免跨连接可见性问题）

    openGauss 多连接场景下，db_session 创建的数据对 override_get_db 会话可能不可见
    （ForeignKeyViolationError / StaleDataError）。本函数在同一 db_session 中创建用户
    与 membership，并由调用方统一 commit；token 直接本地签发（JWT，无需查库）。

    Args:
        membership_role: membership 表中的角色（admin/member）。若为 None 则根据
            user.role 推断（admin → admin，其他 → member）。
    """
    user = User(
        email=email,
        nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id,
        role=role,
        is_active=True,
        is_deleted=False,
    )
    db.add(user)
    await db.flush()  # 获取 user.id

    # 创建 membership（注册接口无 invite_code 时不创建 membership，此处补充）
    if membership_role is None:
        membership_role = "admin" if role == "admin" else "member"
    m = SchoolMembership(
        user_id=user.id,
        school_id=school_id,
        role=membership_role,
        status="active",
        is_default=False,
    )
    db.add(m)
    await db.flush()

    # 直接签发 JWT token（无需查库，避免跨连接可见性问题）
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "id": user.id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "school_code": school_code,
    }


@pytest_asyncio.fixture
async def sub_01_two_school_setup(db_session: AsyncSession, client: AsyncClient) -> dict:
    """两校测试数据：A 校（含订阅者 + 帖子作者 + 管理员）+ B 校（含订阅者）

    用于 SUB-01.1 CRUD + 跨校隔离 + SUB-01.2 四类通知 + 跨校通知隔离。

    实现要点：
    - 所有数据（学校/分类/地点/帖子类型/学校订阅/用户/membership）均在同一 db_session
      中创建，统一 commit。避免 openGauss 跨连接可见性问题（ForeignKeyViolationError /
      StaleDataError）。
    - 用户 token 直接本地签发（JWT，无需查库），API 调用时 get_current_user 通过
      override_get_db 会话查询已 commit 的用户数据（可见）。
    - 不使用 /auth/register API，避免 db_session 与 override_get_db 跨连接可见性问题。
    - 死锁重试：setup_database 的 ALTER SEQUENCE 可能与 INSERT INTO users 死锁
      （ShareRowExclusiveLock vs RowExclusiveLock）。失败时 rollback + 短暂等待后重试。
    """
    import asyncio as _asyncio
    from sqlalchemy.exc import DBAPIError as _DBAPIError

    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await _build_sub_01_setup(db_session)
        except (_DBAPIError, ConnectionError) as e:
            # 死锁 / 连接中断：rollback 后重试
            try:
                await db_session.rollback()
            except Exception:
                pass
            if attempt < max_retries - 1:
                await _asyncio.sleep(0.5 * (attempt + 1))
                continue
            raise


async def _build_sub_01_setup(db_session: AsyncSession) -> dict:
    """实际构建两校测试数据（由 sub_01_two_school_setup 带重试调用）"""
    # ============================================================
    # Step 1: 创建学校、分类、地点、帖子类型
    # ============================================================
    school_a = await _create_school(db_session, "SUB-01 A 校", "sub01-a")
    cat_a = await _create_category(db_session, school_a.id, "A 校分类", "sub01-a-cat")
    loc_a = await _create_location(db_session, school_a.id, "A 校地点")

    school_b = await _create_school(db_session, "SUB-01 B 校", "sub01-b")
    cat_b = await _create_category(db_session, school_b.id, "B 校分类", "sub01-b-cat")

    # ============================================================
    # Step 2: 分配 operations 档订阅（COM-01 要求发布需 active 订阅）
    # ============================================================
    await _assign_operations_subscription(db_session, school_a.id)
    await _assign_operations_subscription(db_session, school_b.id)

    # ============================================================
    # Step 3: 直接在 DB 创建用户 + membership + 签发 token
    # （单 session 操作，避免跨连接可见性问题）
    # ============================================================
    author_a_info = await _create_user_with_token(
        db_session, "sub01author-a@example.com", "A 作者",
        school_a.id, "sub01-a", role="user",
    )
    subscriber_a_info = await _create_user_with_token(
        db_session, "sub01sub-a@example.com", "A 订阅者",
        school_a.id, "sub01-a", role="user",
    )
    subscriber_b_info = await _create_user_with_token(
        db_session, "sub01sub-b@example.com", "B 订阅者",
        school_b.id, "sub01-b", role="user",
    )
    admin_a_info = await _create_user_with_token(
        db_session, "sub01admin-a@example.com", "A 管理员",
        school_a.id, "sub01-a", role="admin",
    )

    # ============================================================
    # Step 4: 统一 commit（所有数据在同一事务中写入并可见）
    # ============================================================
    await db_session.commit()
    # refresh 获取最终 id（flush 已赋 id，commit 后 expire_on_commit=False 保持可用）
    await db_session.refresh(school_a)
    await db_session.refresh(school_b)

    return {
        "school_a": {"id": school_a.id, "code": school_a.code, "category_id": cat_a.id, "location_id": loc_a.id},
        "school_b": {"id": school_b.id, "code": school_b.code, "category_id": cat_b.id},
        "author_a": author_a_info,
        "subscriber_a": subscriber_a_info,
        "subscriber_b": subscriber_b_info,
        "admin_a": admin_a_info,
    }


# ============================================================
# SUB-01.1: 订阅 CRUD + 校验 + 跨校隔离
# ============================================================

@pytest.mark.asyncio
async def test_create_subscription_category(
    client: AsyncClient, sub_01_two_school_setup: dict
):
    """SUB-01.1: POST /subscriptions 创建分类订阅成功（201）"""
    setup = sub_01_two_school_setup
    cat_id = setup["school_a"]["category_id"]
    resp = await client.post(
        "/api/v1/subscriptions",
        json={"target_type": "category", "target_id": cat_id},
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["target_type"] == "category"
    assert data["target_id"] == cat_id
    assert data["school_id"] == setup["school_a"]["id"]
    assert data["target_name"] == "A 校分类"


@pytest.mark.asyncio
async def test_create_subscription_duplicate_returns_409(
    client: AsyncClient, sub_01_two_school_setup: dict
):
    """SUB-01.1: 重复订阅同一目标 → 409 Conflict（唯一约束生效）"""
    setup = sub_01_two_school_setup
    cat_id = setup["school_a"]["category_id"]
    payload = {"target_type": "category", "target_id": cat_id}
    headers = _auth_headers(setup["subscriber_a"])
    r1 = await client.post("/api/v1/subscriptions", json=payload, headers=headers)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/subscriptions", json=payload, headers=headers)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_subscription_invalid_target_type(
    client: AsyncClient, sub_01_two_school_setup: dict
):
    """SUB-01.1: 非法 target_type → 422（Pydantic 校验）"""
    setup = sub_01_two_school_setup
    resp = await client.post(
        "/api/v1/subscriptions",
        json={"target_type": "invalid_type", "target_id": 1},
        headers=_auth_headers(setup["subscriber_a"]),
    )
    # field_validator 抛 ValueError → Pydantic 422
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_create_subscription_nonexistent_target_404(
    client: AsyncClient, sub_01_two_school_setup: dict
):
    """SUB-01.1: 订阅不存在的目标 → 404（不泄露存在性）"""
    setup = sub_01_two_school_setup
    resp = await client.post(
        "/api/v1/subscriptions",
        json={"target_type": "category", "target_id": 999999},
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_subscription_cross_school_target_404(
    client: AsyncClient, sub_01_two_school_setup: dict
):
    """SUB-01.1: A 校用户订阅 B 校目标 → 404（不泄露存在性）"""
    setup = sub_01_two_school_setup
    b_cat_id = setup["school_b"]["category_id"]
    resp = await client.post(
        "/api/v1/subscriptions",
        json={"target_type": "category", "target_id": b_cat_id},
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_my_subscriptions(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.1: GET /subscriptions 返回当前用户在当前学校的订阅列表（带目标名）"""
    setup = sub_01_two_school_setup
    # 先在 DB 创建 2 条订阅（1 category + 1 location）
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "location", setup["school_a"]["location_id"],
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/subscriptions",
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    target_names = {it["target_name"] for it in data["items"]}
    assert "A 校分类" in target_names
    assert "A 校地点" in target_names


@pytest.mark.asyncio
async def test_list_my_subscriptions_filtered_by_target_type(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.1: GET /subscriptions?target_type=category 仅返回分类订阅"""
    setup = sub_01_two_school_setup
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "location", setup["school_a"]["location_id"],
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/subscriptions?target_type=category",
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(it["target_type"] == "category" for it in data["items"])
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_subscription_targets(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.1: GET /subscriptions/targets 按类型分组返回 ID 列表"""
    setup = sub_01_two_school_setup
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "location", setup["school_a"]["location_id"],
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/subscriptions/targets",
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert setup["school_a"]["category_id"] in data["category"]
    assert setup["school_a"]["location_id"] in data["location"]
    assert data["topic"] == []


@pytest.mark.asyncio
async def test_check_subscription_status(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.1: GET /subscriptions/check 返回订阅状态（前端按钮用）"""
    setup = sub_01_two_school_setup
    cat_id = setup["school_a"]["category_id"]
    # 未订阅
    resp = await client.get(
        f"/api/v1/subscriptions/check?target_type=category&target_id={cat_id}",
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 200
    assert resp.json()["subscribed"] is False

    # 订阅后
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", cat_id,
    )
    await db_session.commit()
    resp = await client.get(
        f"/api/v1/subscriptions/check?target_type=category&target_id={cat_id}",
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["subscribed"] is True
    assert body["subscription_id"] is not None


@pytest.mark.asyncio
async def test_delete_subscription_owner_only(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.1: DELETE /subscriptions/{id} 仅可删除本人订阅，他人订阅 → 404"""
    setup = sub_01_two_school_setup
    sub = await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await db_session.commit()

    # 作者尝试删除订阅者的订阅 → 404（不泄露存在性）
    resp = await client.delete(
        f"/api/v1/subscriptions/{sub.id}",
        headers=_auth_headers(setup["author_a"]),
    )
    assert resp.status_code == 404

    # 订阅者本人删除 → 200
    resp = await client.delete(
        f"/api/v1/subscriptions/{sub.id}",
        headers=_auth_headers(setup["subscriber_a"]),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_subscriptions_tenant_isolation(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.1: A 校订阅者在 B 校 X-School-Code 下查询订阅列表为空（跨校不可见）

    需先为 subscriber_a 添加 B 校 membership，否则 tenant context 会直接 404
    （无权访问该校），无法验证"订阅列表跨校隔离"语义。
    """
    setup = sub_01_two_school_setup
    # A 校订阅者订阅 A 校分类
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    # 给 A 校订阅者添加 B 校 membership（使其可访问 B 校上下文）
    await _create_membership(
        db_session, setup["subscriber_a"]["id"], setup["school_b"]["id"], "member"
    )
    await db_session.commit()

    # 用 B 校 X-School-Code 查询 → 列表为空（B 校视角下该用户无订阅）
    resp = await client.get(
        "/api/v1/subscriptions",
        headers={
            "Authorization": f"Bearer {setup['subscriber_a']['access_token']}",
            "X-School-Code": "sub01-b",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_subscription_requires_auth(client: AsyncClient, sub_01_two_school_setup: dict):
    """SUB-01.1: 未登录访问订阅接口 → 401"""
    setup = sub_01_two_school_setup
    resp = await client.get(
        "/api/v1/subscriptions",
        headers={"X-School-Code": setup["school_a"]["code"]},
    )
    assert resp.status_code == 401


# ============================================================
# SUB-01.2: 四类通知场景
# ============================================================

@pytest.mark.asyncio
async def test_notify_new_post_on_admin_approve(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.2 场景1：管理员审核通过 pending → published 时，订阅者收到 subscription_new 通知"""
    setup = sub_01_two_school_setup
    # 订阅者订阅 A 校分类
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await db_session.commit()

    # 作者创建 pending 帖子（通过 API）
    resp = await client.post(
        "/api/v1/posts",
        json={
            "title": "SUB-01 测试新帖通知",
            "content": "这是一条等待审核的帖子内容",
            "category_id": setup["school_a"]["category_id"],
            "is_anonymous": False,
            "status": "pending",
        },
        headers=_auth_headers(setup["author_a"]),
    )
    assert resp.status_code == 201, resp.text
    post_id = resp.json()["id"]

    # 管理员审核通过
    resp = await client.put(
        f"/api/v1/admin/posts/{post_id}/approve",
        json={"reason": "内容真实有效"},
        headers=_auth_headers(setup["admin_a"]),
    )
    assert resp.status_code == 200, resp.text

    # 订阅者应收到 subscription_new 通知
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["subscriber_a"]["id"],
            Notification.type == "subscription_new",
            Notification.target_type == "post",
            Notification.target_id == post_id,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None, "订阅者未收到 subscription_new 通知"
    assert "新发布" in notif.title
    assert notif.is_read is False


@pytest.mark.asyncio
async def test_notify_new_post_excludes_author(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.2 边界：作者本人不接收自己帖子的订阅通知（即使订阅了同一分类）"""
    setup = sub_01_two_school_setup
    # 作者订阅自己所在分类
    await _create_subscription(
        db_session, setup["author_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/posts",
        json={
            "title": "作者自订阅测试",
            "content": "作者订阅了自己的分类，不应收到自己的订阅通知",
            "category_id": setup["school_a"]["category_id"],
            "is_anonymous": False,
            "status": "pending",
        },
        headers=_auth_headers(setup["author_a"]),
    )
    post_id = resp.json()["id"]

    await client.put(
        f"/api/v1/admin/posts/{post_id}/approve",
        json={"reason": "通过"},
        headers=_auth_headers(setup["admin_a"]),
    )

    # 作者不应收到 subscription_new 通知（但仍会收到 audit 审核通过通知）
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["author_a"]["id"],
            Notification.type == "subscription_new",
            Notification.target_id == post_id,
        )
    )
    assert notif_result.scalar_one_or_none() is None, "作者不应收到自己的订阅通知"


@pytest.mark.asyncio
async def test_notify_new_post_cross_school_isolation(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.2 边界：A 校帖子发布，B 校订阅者不应收到通知（跨校隔离）"""
    setup = sub_01_two_school_setup
    # B 校订阅者订阅 B 校分类（不是 A 校的）
    await _create_subscription(
        db_session, setup["subscriber_b"]["id"], setup["school_b"]["id"],
        "category", setup["school_b"]["category_id"],
    )
    await db_session.commit()

    # A 校作者创建 pending 帖子
    resp = await client.post(
        "/api/v1/posts",
        json={
            "title": "A 校帖子，B 校不应收到",
            "content": "跨校通知隔离测试内容",
            "category_id": setup["school_a"]["category_id"],
            "is_anonymous": False,
            "status": "pending",
        },
        headers=_auth_headers(setup["author_a"]),
    )
    post_id = resp.json()["id"]

    await client.put(
        f"/api/v1/admin/posts/{post_id}/approve",
        json={"reason": "通过"},
        headers=_auth_headers(setup["admin_a"]),
    )

    # B 校订阅者不应收到 A 校帖子的 subscription_new 通知
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["subscriber_b"]["id"],
            Notification.type == "subscription_new",
            Notification.target_id == post_id,
        )
    )
    assert notif_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_notify_new_post_idempotent(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.2 边界：重复审核通过不重复发送 subscription_new（幂等性）"""
    setup = sub_01_two_school_setup
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await db_session.commit()

    # 直接在 DB 创建一条 published 帖子（绕过审核）
    post = await _create_post(
        db_session, setup["author_a"]["id"], setup["school_a"]["id"],
        setup["school_a"]["category_id"],
        title="幂等测试帖子",
        status=PostStatus.PUBLISHED,
    )
    await db_session.commit()

    # 直接调用通知服务两次（模拟重复触发）
    from app.services.subscription_notifier import notify_new_post
    n1 = await notify_new_post(db_session, post, actor_id=setup["admin_a"]["id"])
    await db_session.commit()
    n2 = await notify_new_post(db_session, post, actor_id=setup["admin_a"]["id"])
    await db_session.commit()

    # 第一次应有通知，第二次应为 0（幂等）
    assert n1 >= 1, "首次通知应发送"
    assert n2 == 0, "重复触发不应再次发送"

    # 数据库中只有一条 subscription_new 通知
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["subscriber_a"]["id"],
            Notification.type == "subscription_new",
            Notification.target_id == post.id,
        )
    )
    notifs = notif_result.scalars().all()
    assert len(notifs) == 1


@pytest.mark.asyncio
async def test_notify_post_updated_on_substantial_change(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.2 场景2：已发布帖子被实质修改（published → pending 回审）时通知订阅者"""
    setup = sub_01_two_school_setup
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await db_session.commit()

    # 直接创建 published 帖子
    post = await _create_post(
        db_session, setup["author_a"]["id"], setup["school_a"]["id"],
        setup["school_a"]["category_id"],
        title="原帖标题",
        status=PostStatus.PUBLISHED,
    )
    await db_session.commit()

    # 作者通过 API 修改 title（实质修改，触发回审）
    resp = await client.put(
        f"/api/v1/posts/{post.id}",
        json={"title": "已修改的标题（触发回审）"},
        headers=_auth_headers(setup["author_a"]),
    )
    assert resp.status_code == 200, resp.text

    # 订阅者应收到 subscription_update 通知
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["subscriber_a"]["id"],
            Notification.type == "subscription_update",
            Notification.target_type == "post",
            Notification.target_id == post.id,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None, "订阅者未收到 subscription_update 通知"
    assert "重要更新" in notif.title


@pytest.mark.asyncio
async def test_notify_post_expired_by_job(
    db_session: AsyncSession, sub_01_two_school_setup: dict
):
    """SUB-01.2 场景3：GOV-02 自动过期任务 published → expired 时通知订阅者"""
    setup = sub_01_two_school_setup
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await db_session.commit()

    # 直接创建已过期的 published 帖子（expire_at 在过去）
    post = await _create_post(
        db_session, setup["author_a"]["id"], setup["school_a"]["id"],
        setup["school_a"]["category_id"],
        title="即将过期的帖子",
        status=PostStatus.PUBLISHED,
        expire_at=datetime.now() - timedelta(hours=1),
    )
    await db_session.commit()

    # 运行过期任务
    record = await expire_posts_job(db_session, dry_run=False, triggered_by="test")
    assert record.status == "success"
    assert record.processed_count >= 1

    # 订阅者应收到 subscription_expired 通知
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["subscriber_a"]["id"],
            Notification.type == "subscription_expired",
            Notification.target_type == "post",
            Notification.target_id == post.id,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None, "订阅者未收到 subscription_expired 通知"
    assert "已过期" in notif.title


@pytest.mark.asyncio
async def test_notify_post_conflict_on_admin_mark(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.2 场景4：管理员标记冲突时通知订阅者

    通过 PUT /admin/posts/{id}/transition 直接走状态机 published → conflict 触发通知。
    """
    setup = sub_01_two_school_setup
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await db_session.commit()

    # 直接创建 published 帖子
    post = await _create_post(
        db_session, setup["author_a"]["id"], setup["school_a"]["id"],
        setup["school_a"]["category_id"],
        title="将标记冲突的帖子",
        status=PostStatus.PUBLISHED,
    )
    await db_session.commit()

    # 管理员通过状态机端点标记冲突
    resp = await client.post(
        f"/api/v1/posts/{post.id}/transition",
        json={"target_status": "conflict", "reason": "存在矛盾信息"},
        headers=_auth_headers(setup["admin_a"]),
    )
    assert resp.status_code == 200, resp.text

    # 订阅者应收到 subscription_conflict 通知
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["subscriber_a"]["id"],
            Notification.type == "subscription_conflict",
            Notification.target_type == "post",
            Notification.target_id == post.id,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None, "订阅者未收到 subscription_conflict 通知"
    assert "冲突" in notif.title


@pytest.mark.asyncio
async def test_notify_respects_subscription_preference(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.2 边界：subscription_enabled=False 的订阅者不接收订阅通知"""
    setup = sub_01_two_school_setup
    # 订阅者 A 关闭 subscription 类通知偏好
    pref = NotificationPreference(
        user_id=setup["subscriber_a"]["id"],
        subscription_enabled=False,
    )
    db_session.add(pref)
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "category", setup["school_a"]["category_id"],
    )
    await db_session.commit()

    # 作者创建 pending 帖子并审核通过
    resp = await client.post(
        "/api/v1/posts",
        json={
            "title": "偏好过滤测试",
            "content": "订阅者关闭了 subscription 类偏好，不应收到通知",
            "category_id": setup["school_a"]["category_id"],
            "is_anonymous": False,
            "status": "pending",
        },
        headers=_auth_headers(setup["author_a"]),
    )
    post_id = resp.json()["id"]

    await client.put(
        f"/api/v1/admin/posts/{post_id}/approve",
        json={"reason": "通过"},
        headers=_auth_headers(setup["admin_a"]),
    )

    # 关闭偏好的订阅者不应收到 subscription_new 通知
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["subscriber_a"]["id"],
            Notification.type == "subscription_new",
            Notification.target_id == post_id,
        )
    )
    assert notif_result.scalar_one_or_none() is None, "关闭偏好的订阅者不应收到通知"


@pytest.mark.asyncio
async def test_notify_topic_subscriber(
    client: AsyncClient, sub_01_two_school_setup: dict, db_session: AsyncSession
):
    """SUB-01.2: 专题订阅者在专题内帖子发布时也收到通知（订阅来源覆盖 category/location/topic）"""
    setup = sub_01_two_school_setup
    # 创建一个已发布专题
    topic = await _create_topic(
        db_session, setup["school_a"]["id"], setup["author_a"]["id"],
        title="SUB-01 专题",
        status="published",
    )
    # 订阅者订阅该专题
    await _create_subscription(
        db_session, setup["subscriber_a"]["id"], setup["school_a"]["id"],
        "topic", topic.id,
    )
    await db_session.commit()

    # 作者创建 pending 帖子
    resp = await client.post(
        "/api/v1/posts",
        json={
            "title": "专题内帖子",
            "content": "订阅了专题的用户应收到此帖的订阅通知",
            "category_id": setup["school_a"]["category_id"],
            "is_anonymous": False,
            "status": "pending",
        },
        headers=_auth_headers(setup["author_a"]),
    )
    post_id = resp.json()["id"]

    # 将帖子加入专题（直接 DB 操作）
    db_session.add(TopicCollectionPost(
        topic_collection_id=topic.id,
        post_id=post_id,
        sort_order=0,
    ))
    await db_session.commit()

    # 管理员审核通过
    await client.put(
        f"/api/v1/admin/posts/{post_id}/approve",
        json={"reason": "通过"},
        headers=_auth_headers(setup["admin_a"]),
    )

    # 专题订阅者应收到 subscription_new 通知
    notif_result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == setup["subscriber_a"]["id"],
            Notification.type == "subscription_new",
            Notification.target_id == post_id,
        )
    )
    assert notif_result.scalar_one_or_none() is not None, "专题订阅者应收到通知"
