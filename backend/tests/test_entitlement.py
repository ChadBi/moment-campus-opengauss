"""COM-01: 套餐、权益、订阅、用量日汇总测试

覆盖：
- COM-01.2 EntitlementService 硬限制拒绝 / 软限制告警 / 80% 阈值 / 无订阅 / 不限
- COM-01.2 ai_allowed 降级
- COM-01.3 usage_summary 幂等任务（重复运行不翻倍 AI 计数）
- COM-01.3 increment_ai_calls 累加
- COM-01.4 super_admin 分配/续期/暂停套餐
- COM-01.4 普通用户访问 platform 路由被拒
- COM-01.2 upload_image 无订阅被拒
"""
import pytest
import pytest_asyncio
from datetime import datetime, date
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entitlement import (
    EntitlementService, EntitlementKey, EntitlementReason,
)
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription
from app.models.school_membership import SchoolMembership
from app.models.tenant_usage_daily import TenantUsageDaily
from app.models.user import User
from app.models.post import Post


# ============================================================
# 测试辅助
# ============================================================
async def _assign_plan_to_school(
    db: AsyncSession, school_id: int, plan_code: str
) -> SchoolSubscription:
    """覆盖式分配：把旧 active 订阅置 expired，新建指定 plan 的 active 订阅。"""
    # 旧 active 置 expired
    existing = (await db.execute(
        select(SchoolSubscription).where(
            SchoolSubscription.school_id == school_id,
            SchoolSubscription.status == "active",
        )
    )).scalars().all()
    for s in existing:
        s.status = "expired"
    await db.flush()

    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == plan_code)
    )).scalar_one()
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
    await db.commit()
    await db.refresh(sub)
    return sub


async def _create_test_user_in_school(
    db: AsyncSession, school_id: int, email: str = "u@example.com"
) -> User:
    """直接在数据库创建一个 active 成员（绕开 register API，便于批量构造）。"""
    from app.core.security import get_password_hash
    user = User(
        email=email,
        nickname=email.split("@")[0],
        password_hash=get_password_hash("pass123"),
        school_id=school_id,
        role="user",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    membership = SchoolMembership(
        user_id=user.id,
        school_id=school_id,
        role="member",
        status="active",
        is_default=True,
    )
    db.add(membership)
    await db.commit()
    return user


@pytest_asyncio.fixture
async def super_admin_user(
    client: AsyncClient, db_session: AsyncSession, test_school: dict
) -> dict:
    """注册一名 super_admin 用户并返回其 token。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "superadmin@example.com",
            "nickname": "超管",
            "password": "superpassword123",
            "school_id": test_school["id"],
        },
    )
    assert response.status_code == 200
    data = response.json()

    result = await db_session.execute(
        select(User).where(User.email == "superadmin@example.com")
    )
    user = result.scalar_one()
    user.role = "super_admin"
    await db_session.commit()

    return {
        "email": "superadmin@example.com",
        "password": "superpassword123",
        "school_id": test_school["id"],
        "access_token": data["access_token"],
        "id": user.id,
    }


@pytest_asyncio.fixture
async def super_admin_headers(super_admin_user: dict) -> dict:
    return {"Authorization": f"Bearer {super_admin_user['access_token']}"}


# ============================================================
# COM-01.2: EntitlementService 单元测试
# ============================================================
class TestEntitlementServiceHardLimit:
    """硬限制超额 → 拒绝。"""

    @pytest.mark.asyncio
    async def test_hard_limit_reject_members(
        self, db_session: AsyncSession, test_school: dict
    ):
        """trial members_max=20 硬限制：构造 20 个成员后第 21 个被拒。"""
        school_id = test_school["id"]
        await _assign_plan_to_school(db_session, school_id, "trial")

        # 构造 20 个 active 成员
        for i in range(20):
            await _create_test_user_in_school(
                db_session, school_id, email=f"m{i}@x.com"
            )

        svc = await EntitlementService.create(db_session, school_id)
        reason = await svc.check_members_count()
        assert reason.allowed is False
        assert reason.code == "ENT_LIMIT_HARD_EXCEEDED"
        assert reason.limit_value == 20
        assert reason.current_value == 20

    @pytest.mark.asyncio
    async def test_hard_limit_below_threshold_passes(
        self, db_session: AsyncSession, test_school: dict
    ):
        """trial members_max=20：未达 80%（< 16）→ 通过。"""
        school_id = test_school["id"]
        await _assign_plan_to_school(db_session, school_id, "trial")

        for i in range(5):
            await _create_test_user_in_school(
                db_session, school_id, email=f"p{i}@x.com"
            )

        svc = await EntitlementService.create(db_session, school_id)
        reason = await svc.check_members_count()
        assert reason.allowed is True
        assert reason.code == "ENT_OK"
        assert reason.current_value == 5


class TestEntitlementServiceSoftLimit:
    """软限制超额 → 允许并返回告警。"""

    @pytest.mark.asyncio
    async def test_soft_limit_warning_on_exceed(
        self, db_session: AsyncSession, test_school: dict
    ):
        """standard storage_mb=2048 软限制：current_value=2048 → 允许但告警。"""
        school_id = test_school["id"]
        await _assign_plan_to_school(db_session, school_id, "standard")

        svc = await EntitlementService.create(db_session, school_id)
        reason = await svc.check_storage(current_storage_mb=2048)
        assert reason.allowed is True
        assert reason.code == "ENT_WARNING_SOFT_EXCEEDED"
        assert reason.limit_value == 2048
        assert reason.current_value == 2048


class TestEntitlementServiceWarning80:
    """达 80% 阈值告警。"""

    @pytest.mark.asyncio
    async def test_warning_80_threshold(
        self, db_session: AsyncSession, test_school: dict
    ):
        """trial posts_max=50：current_value=40 → 80% 告警，但允许。"""
        school_id = test_school["id"]
        await _assign_plan_to_school(db_session, school_id, "trial")

        svc = await EntitlementService.create(db_session, school_id)
        reason = await svc.check(EntitlementKey.POSTS_MAX, current_value=40)
        assert reason.allowed is True
        assert reason.code == "ENT_WARNING_80"
        assert reason.limit_value == 50
        assert reason.current_value == 40

    @pytest.mark.asyncio
    async def test_warning_80_just_below_threshold(
        self, db_session: AsyncSession, test_school: dict
    ):
        """trial posts_max=50：current_value=39 → 仍为 ENT_OK。"""
        school_id = test_school["id"]
        await _assign_plan_to_school(db_session, school_id, "trial")

        svc = await EntitlementService.create(db_session, school_id)
        reason = await svc.check(EntitlementKey.POSTS_MAX, current_value=39)
        assert reason.allowed is True
        assert reason.code == "ENT_OK"


class TestEntitlementServiceNoSubscription:
    """学校无 active 订阅 → 拒绝。"""

    @pytest.mark.asyncio
    async def test_no_subscription_reject(
        self, db_session: AsyncSession, test_school: dict
    ):
        school_id = test_school["id"]
        # 删除 test_school fixture 自动分配的订阅
        subs = (await db_session.execute(
            select(SchoolSubscription).where(
                SchoolSubscription.school_id == school_id
            )
        )).scalars().all()
        for s in subs:
            await db_session.delete(s)
        await db_session.commit()

        svc = await EntitlementService.create(db_session, school_id)
        assert svc.has_active_subscription is False
        reason = await svc.check(EntitlementKey.MEMBERS_MAX, current_value=0)
        assert reason.allowed is False
        assert reason.code == "ENT_NO_SUBSCRIPTION"


class TestEntitlementServiceUnlimited:
    """operations 档：members_max / posts_max 不限（NULL）。"""

    @pytest.mark.asyncio
    async def test_operations_unlimited(
        self, db_session: AsyncSession, test_school: dict
    ):
        """operations 默认订阅（由 test_school fixture 自动分配）。"""
        school_id = test_school["id"]
        svc = await EntitlementService.create(db_session, school_id)
        assert svc.has_active_subscription is True

        reason = await svc.check(EntitlementKey.MEMBERS_MAX, current_value=999999)
        assert reason.allowed is True
        # 不限的场景返回 ENT_OK
        assert reason.code == "ENT_OK"

        reason2 = await svc.check(EntitlementKey.POSTS_MAX, current_value=999999)
        assert reason2.allowed is True
        assert reason2.code == "ENT_OK"


class TestEntitlementServiceAiAllowed:
    """ai_allowed 方法：硬限制超限 → False。"""

    @pytest.mark.asyncio
    async def test_ai_allowed_within_limit(
        self, db_session: AsyncSession, test_school: dict
    ):
        """operations ai_calls_daily=2000：调用 1999 次仍允许。"""
        school_id = test_school["id"]
        svc = await EntitlementService.create(db_session, school_id)
        ok = await svc.ai_allowed(today_ai_calls=1999)
        assert ok is True

    @pytest.mark.asyncio
    async def test_ai_allowed_at_limit_returns_false(
        self, db_session: AsyncSession, test_school: dict
    ):
        """operations ai_calls_daily=2000：调用 2000 次 → False（应降级）。"""
        school_id = test_school["id"]
        svc = await EntitlementService.create(db_session, school_id)
        ok = await svc.ai_allowed(today_ai_calls=2000)
        assert ok is False

    @pytest.mark.asyncio
    async def test_ai_allowed_trial_rejects_at_20(
        self, db_session: AsyncSession, test_school: dict
    ):
        """trial ai_calls_daily=20：调用 20 次 → False。"""
        school_id = test_school["id"]
        await _assign_plan_to_school(db_session, school_id, "trial")
        svc = await EntitlementService.create(db_session, school_id)
        ok = await svc.ai_allowed(today_ai_calls=20)
        assert ok is False


# ============================================================
# COM-01.3: usage_summary 幂等任务
# ============================================================
class TestUsageSummaryIdempotent:
    """summarize_usage 重复运行不翻倍 AI 调用计数。"""

    @pytest.mark.asyncio
    async def test_summarize_usage_idempotent_posts_count(
        self, db_session: AsyncSession, test_school: dict
    ):
        """重复运行 summarize_usage 同一天数值不翻倍。"""
        from app.jobs.usage_summary import summarize_usage, get_ai_calls_count
        school_id = test_school["id"]
        today = date.today()

        # 第一次运行
        row1 = await summarize_usage(db_session, school_id, today, ai_calls_count=5)
        assert row1.posts_count == 0
        assert row1.ai_calls_count == 5

        # 第二次运行（用相同 ai_calls_count=5）
        row2 = await summarize_usage(db_session, school_id, today, ai_calls_count=5)
        # posts_count 不变（仍为 0）
        assert row2.posts_count == 0
        # ai_calls_count 覆盖为 5，不累加为 10
        assert row2.ai_calls_count == 5

        # 验证表里只有一行
        rows = (await db_session.execute(
            select(TenantUsageDaily).where(
                TenantUsageDaily.school_id == school_id,
                TenantUsageDaily.usage_date == today,
            )
        )).scalars().all()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_summarize_usage_recalcs_members_count(
        self, db_session: AsyncSession, test_school: dict
    ):
        """summarize_usage 基于实际 count 重算并覆盖（不累加）。"""
        from app.jobs.usage_summary import summarize_usage
        school_id = test_school["id"]
        today = date.today()

        # 初始 0 成员
        row1 = await summarize_usage(db_session, school_id, today, ai_calls_count=0)
        assert row1.members_count == 0

        # 创建 3 个成员
        for i in range(3):
            await _create_test_user_in_school(
                db_session, school_id, email=f"sm{i}@x.com"
            )

        # 重新运行 summarize_usage（ai_calls_count=None 保留原值 0）
        row2 = await summarize_usage(db_session, school_id, today, ai_calls_count=None)
        assert row2.members_count == 3  # 重算覆盖
        assert row2.ai_calls_count == 0  # 保留原值


class TestIncrementAiCalls:
    """increment_ai_calls 累加。"""

    @pytest.mark.asyncio
    async def test_increment_ai_calls_accumulates(
        self, db_session: AsyncSession, test_school: dict
    ):
        """每次调用 +1，三次调用后 = 3。"""
        from app.jobs.usage_summary import increment_ai_calls, get_ai_calls_count
        school_id = test_school["id"]
        today = date.today()

        # 初始 0
        assert await get_ai_calls_count(db_session, school_id, today) == 0

        # 调用 3 次
        c1 = await increment_ai_calls(db_session, school_id, today)
        c2 = await increment_ai_calls(db_session, school_id, today)
        c3 = await increment_ai_calls(db_session, school_id, today)
        assert c1 == 1
        assert c2 == 2
        assert c3 == 3

        # 重新读取仍是 3（幂等：未重复累加）
        assert await get_ai_calls_count(db_session, school_id, today) == 3


# ============================================================
# COM-01.4: super_admin 平台路由测试
# ============================================================
class TestPlatformRoutes:
    """platform 路由测试。"""

    @pytest.mark.asyncio
    async def test_list_plans(
        self, client: AsyncClient, super_admin_headers: dict
    ):
        """super_admin 可获取 3 档套餐及权益项。"""
        r = await client.get("/api/v1/platform/plans", headers=super_admin_headers)
        assert r.status_code == 200
        plans = r.json()
        assert len(plans) == 3
        codes = {p["code"] for p in plans}
        assert codes == {"trial", "standard", "operations"}
        # 每档 4 个权益项
        for p in plans:
            assert len(p["entitlements"]) == 4
            keys = {e["key"] for e in p["entitlements"]}
            assert keys == {
                "members_max", "posts_max", "storage_mb", "ai_calls_daily"
            }

    @pytest.mark.asyncio
    async def test_non_super_admin_forbidden(
        self, client: AsyncClient, auth_headers: dict
    ):
        """普通 user 访问 platform 路由应 403。"""
        r = await client.get("/api/v1/platform/plans", headers=auth_headers)
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_assign_subscription_to_school(
        self, client: AsyncClient, super_admin_headers: dict,
        super_admin_user: dict, test_school: dict,
    ):
        """super_admin 给 test_school 分配 trial 套餐。

        test_school fixture 已自动分配 operations，本用例模拟续期/切换到 trial。
        """
        r = await client.post(
            f"/api/v1/platform/schools/{test_school['id']}/subscription",
            headers=super_admin_headers,
            json={
                "plan_code": "trial",
                "expires_at": None,
                "note": "测试分配 trial",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "active"
        assert data["plan_code"] == "trial"
        # note 应包含续期信息
        assert "续期" in data["note"] or "测试分配 trial" in data["note"]

    @pytest.mark.asyncio
    async def test_list_subscriptions(
        self, client: AsyncClient, super_admin_headers: dict, test_school: dict
    ):
        """super_admin 获取订阅列表。"""
        # 先确保 test_school 有订阅（fixture 自动分配 operations）
        r = await client.get(
            "/api/v1/platform/subscriptions", headers=super_admin_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        items = data["items"]
        assert any(it["school_id"] == test_school["id"] for it in items)

    @pytest.mark.asyncio
    async def test_update_subscription_suspend(
        self, client: AsyncClient, super_admin_headers: dict, test_school: dict
    ):
        """super_admin 暂停当前 active 订阅。"""
        # 先获取当前订阅
        r = await client.get(
            "/api/v1/platform/subscriptions",
            headers=super_admin_headers,
            params={"school_id": test_school["id"], "status": "active"},
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        sub_id = items[0]["id"]

        # 暂停
        r2 = await client.put(
            f"/api/v1/platform/subscriptions/{sub_id}",
            headers=super_admin_headers,
            json={"status": "suspended", "note": "测试暂停"},
        )
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert data["status"] == "suspended"
        assert "测试暂停" in data["note"]
        assert "[update]" in data["note"]

    @pytest.mark.asyncio
    async def test_assign_invalid_plan_code(
        self, client: AsyncClient, super_admin_headers: dict, test_school: dict
    ):
        """无效 plan_code 应返回 400。"""
        r = await client.post(
            f"/api/v1/platform/schools/{test_school['id']}/subscription",
            headers=super_admin_headers,
            json={"plan_code": "nonexistent_plan", "expires_at": None},
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_assign_to_nonexistent_school(
        self, client: AsyncClient, super_admin_headers: dict
    ):
        """给不存在的学校分配应 404。"""
        r = await client.post(
            "/api/v1/platform/schools/999999/subscription",
            headers=super_admin_headers,
            json={"plan_code": "trial", "expires_at": None},
        )
        assert r.status_code == 404


# ============================================================
# COM-01.2: upload 入口权益校验（最小化接入）
# ============================================================
class TestUploadEntitlementGuard:
    """upload_image 在无订阅时拒绝上传。"""

    @pytest.mark.asyncio
    async def test_upload_blocked_without_subscription(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
        test_school: dict, test_user: dict,
    ):
        """删除 test_school 的订阅后，上传应被拒绝。"""
        # 删除该校全部订阅
        subs = (await db_session.execute(
            select(SchoolSubscription).where(
                SchoolSubscription.school_id == test_school["id"]
            )
        )).scalars().all()
        for s in subs:
            await db_session.delete(s)
        await db_session.commit()

        # 用一个最小的 PNG 上传（应该被前置校验拦截，不需要真实图片）
        # 构造 1x1 PNG 的最小字节
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
            b"\xfe\xa3Uv\x9e\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        r = await client.post(
            "/api/v1/upload/image",
            headers=auth_headers,
            files={"file": ("test.png", png_bytes, "image/png")},
        )
        assert r.status_code == 400
        assert "未开通有效套餐" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_passes_with_subscription(
        self, client: AsyncClient, auth_headers: dict, test_user: dict
    ):
        """有 operations 订阅时上传应通过前置权益校验。"""
        # test_school fixture 自动分配了 operations 订阅
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
            b"\xfe\xa3Uv\x9e\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        r = await client.post(
            "/api/v1/upload/image",
            headers=auth_headers,
            files={"file": ("test.png", png_bytes, "image/png")},
        )
        # 权益校验通过；上传本身可能成功（200）或因其它原因失败
        # 这里只验证不会被权益校验拦截（即 detail 不包含"未开通有效套餐"）
        if r.status_code != 200:
            detail = r.json().get("detail", "")
            # 不能因为权益校验被拒
            assert "未开通有效套餐" not in detail, f"不应被权益校验拦截：{detail}"
        else:
            assert r.status_code == 200
