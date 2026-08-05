"""ANA-02: 数据分析指标 + 零结果洞察 + 隐私阈值 测试

覆盖：
- ANA-02.1 校级分析接口：GET /api/v1/admin/analytics
  * 漏斗/留存/搜索成功率/零结果率/分享订阅/内容有效率/治理 SLA/AI 用量
  * 元数据透明：time_window / sample_size / last_updated_at / empty_state
  * 租户隔离：只看本校数据
  * 权限：普通用户 403；admin 及以上可访问
- ANA-02.1 零结果洞察：GET /api/v1/admin/analytics/zero-results
  * 隐私阈值：样本量 < 5 标记 hidden_for_privacy=true
- ANA-02.1 平台分析：GET /api/v1/platform/analytics
  * super_admin 专用，普通 admin 403
  * 只看学校级聚合，不暴露跨校用户轨迹
"""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.post_status import PostStatus as PS
from app.core.security import create_access_token, get_password_hash
from app.models.ai_invocation_log import AIInvocationLog
from app.models.admin_operation_log import AdminOperationLog
from app.models.post import Post
from app.models.product_event import ProductEvent
from app.models.report import Report
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.services.analytics_service import (
    SchoolAnalyticsService,
    PlatformAnalyticsService,
    PRIVACY_THRESHOLD,
    DEFAULT_WINDOW_DAYS,
)


# ============================================================
# 辅助函数与 fixtures
# ============================================================
def _make_token(user_id: int) -> str:
    return create_access_token(data={"sub": str(user_id)})


async def _create_school(db: AsyncSession, name: str, code: str) -> School:
    """直接创建学校（不走 API）。"""
    school = School(name=name, code=code, is_active=True)
    db.add(school)
    await db.flush()
    return school


async def _create_user(
    db: AsyncSession,
    email: str,
    nickname: str,
    school_id: int,
    role: str = "user",
) -> User:
    user = User(
        email=email,
        nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id,
        role=role,
        is_active=True,
        is_deleted=False,
        campus_verified=True,  # D4 门禁：默认已认证
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


async def _seed_event(
    db: AsyncSession,
    school_id: int,
    event_name: str,
    *,
    user_id: int | None = None,
    occurred_at: datetime | None = None,
    fields: dict | None = None,
    environment: str = "demo",
    event_id: str | None = None,
) -> None:
    """直接插入 product_event，绕过白名单（测试场景需要构造历史事件）。

    默认 environment='demo'，因为 analytics_service 设计上排除 test/seed 环境，
    避免测试数据污染真实指标。测试场景使用 demo 环境以验证指标计算逻辑。
    """
    import uuid as _uuid
    ev = ProductEvent(
        event_id=event_id or str(_uuid.uuid4()),
        event_name=event_name,
        school_id=school_id,
        user_id=user_id,
        occurred_at=occurred_at or datetime.now(),
        received_at=datetime.now(),
        environment=environment,
        fields_json=fields,
    )
    db.add(ev)
    await db.flush()


@pytest_asyncio.fixture
async def super_admin(db_session: AsyncSession, test_school: dict) -> dict:
    """平台超管（直接 DB 创建）。

    使用 db_session 创建可避免与 conftest.py 的 admin_user fixture 冲突（不同邮箱），
    且 super_admin 角色无 API 注册路径，直接 DB 写入 role='super_admin' 最简洁。
    conftest.py 的 override_get_db（独立 session）可见已 commit 的用户行。
    """
    # DEBUG: 验证 test_school 提供的 id 在 DB 中确实存在
    from sqlalchemy import select as _sel, text as _text
    from app.models.school import School as _School
    school_row = (await db_session.execute(
        _sel(_School).where(_School.id == test_school["id"])
    )).scalar_one_or_none()
    print(f"\n[DEBUG super_admin] BEFORE create user: test_school['id']={test_school['id']}, "
          f"school_row={'EXISTS' if school_row else 'NOT FOUND'}")
    sa = await _create_user(
        db_session, "sa-ana02@example.com", "平台超管", test_school["id"],
        role="super_admin",
    )
    await db_session.commit()
    # DEBUG: commit 后再次检查 school 是否存在
    school_after = (await db_session.execute(
        _text("SELECT id FROM schools WHERE id = :sid"), {"sid": test_school["id"]}
    )).first()
    print(f"[DEBUG super_admin] AFTER commit: school in DB={school_after}, sa.id={sa.id}")
    return {"id": sa.id, "headers": {"Authorization": f"Bearer {_make_token(sa.id)}"}}


@pytest_asyncio.fixture
async def seeded_events(
    db_session: AsyncSession,
    test_school: dict,
    test_category: dict,
    admin_user: dict,
) -> dict:
    """预置一组产品事件 + 帖子 + AI 日志，用于指标计算。"""
    school_id = test_school["id"]
    admin_id = admin_user["id"]
    now = datetime.now()
    # 漏斗事件（窗口内）
    for _ in range(10):
        await _seed_event(db_session, school_id, "school_viewed",
                          occurred_at=now - timedelta(days=1))
    for _ in range(6):
        await _seed_event(db_session, school_id, "search_started",
                          occurred_at=now - timedelta(days=1),
                          fields={"keyword_length": 5, "category_code": "lost-found"})
    for _ in range(4):
        await _seed_event(db_session, school_id, "search_succeeded",
                          occurred_at=now - timedelta(days=1))
    for _ in range(2):
        await _seed_event(db_session, school_id, "search_zero",
                          occurred_at=now - timedelta(days=1),
                          fields={"keyword_length": 3, "category_code": "lost-found"})
    for _ in range(3):
        await _seed_event(db_session, school_id, "post_submitted",
                          occurred_at=now - timedelta(days=1))
    for _ in range(5):
        await _seed_event(db_session, school_id, "share_clicked",
                          occurred_at=now - timedelta(days=1))
    for _ in range(2):
        await _seed_event(db_session, school_id, "subscribed",
                          occurred_at=now - timedelta(days=1))
    # 留存：8 天前 admin 触发过事件 → 在 7 日回访窗口内应该被计入基线但未回访
    await _seed_event(db_session, school_id, "school_viewed",
                      user_id=admin_id, occurred_at=now - timedelta(days=10))

    # 已发布帖子（窗口内创建，用于漏斗 published 阶段 + 内容有效率）
    for _ in range(3):
        post = Post(
            user_id=admin_id, school_id=school_id,
            category_id=test_category["id"],
            title="已发布", content="内容长度至少十个字符",
            status=PS.PUBLISHED, created_at=now - timedelta(days=1),
        )
        db_session.add(post)
        await db_session.flush()

    # 一条已过期帖子（content_valid_rate 计算为非有效）
    expired_post = Post(
        user_id=admin_id, school_id=school_id,
        category_id=test_category["id"],
        title="已过期", content="内容长度至少十个字符",
        status=PS.PUBLISHED, expire_at=now - timedelta(hours=1),
        created_at=now - timedelta(days=5),
    )
    db_session.add(expired_post)
    await db_session.flush()

    # AI 调用日志
    for i in range(5):
        db_session.add(AIInvocationLog(
            school_id=school_id, user_id=admin_id,
            scene="search_intent", model="mock-model", provider="mock",
            latency_ms=100 + i * 10, input_length=50,
            output_status="success", candidate_count=3, result_count=2,
            created_at=now - timedelta(days=1),
        ))
    for i in range(2):
        db_session.add(AIInvocationLog(
            school_id=school_id, user_id=admin_id,
            scene="search_intent", model="mock-model", provider="mock",
            latency_ms=200, input_length=50,
            output_status="error", fallback_reason="mock fallback",
            created_at=now - timedelta(days=1),
        ))
    await db_session.flush()

    # 审核日志 + 关联帖子（治理 SLA）
    pending_post = Post(
        user_id=admin_id, school_id=school_id,
        category_id=test_category["id"],
        title="审核中", content="内容长度至少十个字符",
        status=PS.PENDING, created_at=now - timedelta(hours=2),
    )
    db_session.add(pending_post)
    await db_session.flush()
    db_session.add(AdminOperationLog(
        admin_id=admin_id, action="approve_post",
        target_type="post", target_id=pending_post.id,
        created_at=now - timedelta(hours=1),
    ))
    await db_session.flush()

    # 举报 + 处理（治理 SLA）
    db_session.add(Report(
        post_id=pending_post.id, reporter_id=admin_id,
        report_type="spam", description="测试", status="handled",
        handler_id=admin_id, handled_at=now - timedelta(minutes=30),
        created_at=now - timedelta(hours=2),
    ))
    await db_session.flush()

    await db_session.commit()
    return {
        "school_views": 11,  # 10 + 1 留存基线
        "search_started": 6,
        "search_succeeded": 4,
        "search_zero": 2,
        "post_submitted": 3,
        "published_posts": 4,  # 3 published + 1 expired（status 仍为 PUBLISHED）
        "expired_posts": 1,
        "share_clicked": 5,
        "subscribed": 2,
        "ai_total": 7,
        "ai_success": 5,
        "ai_fallback": 2,
    }


# ============================================================
# 校级分析接口
# ============================================================
class TestSchoolAnalyticsAPI:
    """GET /api/v1/admin/analytics 校级分析接口。"""

    @pytest.mark.asyncio
    async def test_admin_can_get_school_analytics(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """admin 可访问校级分析接口，返回完整指标集合。"""
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        # 必备字段
        assert data["school_id"] == test_school["id"]
        assert data["school_code"] == test_school["code"]
        for key in (
            "funnel", "retention_7d", "search_success_rate", "search_zero_rate",
            "share_subscription_conversion", "content_valid_rate",
            "governance_sla", "ai_usage", "generated_at",
        ):
            assert key in data, f"缺失指标: {key}"

    @pytest.mark.asyncio
    async def test_normal_user_forbidden(
        self, client: AsyncClient, auth_headers: dict, test_school: dict,
    ):
        """普通用户访问 403。"""
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**auth_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 403, response.text

    @pytest.mark.asyncio
    async def test_guest_forbidden(self, client: AsyncClient, test_school: dict):
        """游客访问 401/403（无 token）。"""
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={"X-School-Code": test_school["code"]},
        )
        assert response.status_code in (401, 403), response.text

    @pytest.mark.asyncio
    async def test_funnel_stages_and_meta(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """漏斗 5 阶段 + 转化率 + 元数据。"""
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        funnel = response.json()["funnel"]
        # 5 阶段
        assert len(funnel["stages"]) == 5
        keys = [s["key"] for s in funnel["stages"]]
        assert keys == [
            "school_viewed", "search_started", "post_submitted",
            "pending_review", "published",
        ]
        # 计数正确（窗口内事件，可能含 fixture 留存基线）
        assert funnel["stages"][0]["count"] == seeded_events["school_views"]
        assert funnel["stages"][1]["count"] == seeded_events["search_started"]
        assert funnel["stages"][2]["count"] == seeded_events["post_submitted"]
        assert funnel["stages"][4]["count"] == seeded_events["published_posts"]
        # 转化率
        assert "overall" in funnel["conversion_rates"]
        # 元数据透明：time_window / sample_size / last_updated_at / empty_state
        meta = funnel["meta"]
        assert "time_window_start" in meta
        assert "time_window_end" in meta
        assert "sample_size" in meta
        assert "last_updated_at" in meta
        assert "empty_state" in meta
        assert meta["sample_size"] >= 0
        assert meta["empty_state"] is False  # 已预置数据

    @pytest.mark.asyncio
    async def test_search_rates(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """搜索成功率 + 零结果率。"""
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        data = response.json()
        # 成功率 = 4 / (4+2) = 0.6667
        assert data["search_success_rate"]["succeeded_searches"] == 4
        assert data["search_success_rate"]["zero_searches"] == 2
        assert data["search_success_rate"]["success_rate"] == round(4 / 6, 4)
        # 零结果率 = 2 / 6 = 0.3333
        assert data["search_zero_rate"]["zero_rate"] == round(2 / 6, 4)

    @pytest.mark.asyncio
    async def test_ai_usage_metrics(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """AI 用量指标。"""
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        ai = response.json()["ai_usage"]
        assert ai["total_calls"] == seeded_events["ai_total"]
        assert ai["success_calls"] == seeded_events["ai_success"]
        assert ai["fallback_calls"] == seeded_events["ai_fallback"]
        # 成功率 = 5/7 = 0.7143
        assert ai["success_rate"] == round(5 / 7, 4)
        # 降级率 = 2/7 = 0.2857
        assert ai["fallback_rate"] == round(2 / 7, 4)
        # 平均延迟 = (100+110+120+130+140+200+200) / 7
        assert ai["avg_latency_ms"] > 0

    @pytest.mark.asyncio
    async def test_content_valid_rate(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """内容有效率：published 且未过期 / 总内容。"""
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        cv = response.json()["content_valid_rate"]
        # 预置：3 已发布未过期 + 1 已发布已过期 + 1 pending = 5 总内容；有效率 = 3/5
        assert cv["total_posts"] == 5
        assert cv["valid_posts"] == 3
        assert cv["valid_rate"] == round(3 / 5, 4)

    @pytest.mark.asyncio
    async def test_governance_sla(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """治理 SLA：平均审核时长 + 平均举报处理时长。"""
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        sla = response.json()["governance_sla"]
        # 至少有一条审核记录（pending_post 被 approve_post）
        assert sla["reviewed_count"] >= 1
        # 平均审核时长 > 0（created_at - post.created_at = 2 小时 - 1 小时 = 1 小时 ≈ 3600 秒）
        assert sla["avg_review_seconds"] > 0
        # 举报处理时长 > 0（创建 2h 前，处理 30min 前 → 1.5h ≈ 5400 秒）
        assert sla["reports_handled_count"] >= 1
        assert sla["avg_report_handle_seconds"] > 0

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        seeded_events: dict,
        db_session: AsyncSession,
    ):
        """跨校数据不计入本校指标（TEN-02.3）。"""
        # 创建另一所学校 + 该校事件
        school_b = await _create_school(db_session, "B 校", "school-b-ana02")
        await _seed_event(db_session, school_b.id, "school_viewed",
                          occurred_at=datetime.now() - timedelta(days=1))
        await _seed_event(db_session, school_b.id, "search_started",
                          occurred_at=datetime.now() - timedelta(days=1))
        await db_session.commit()

        # 查询本校：不应看到 B 校事件
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        data = response.json()
        # 本校漏斗 stage[0] (school_viewed) 应仍为 seeded_events 计数，不含 B 校
        assert data["funnel"]["stages"][0]["count"] == seeded_events["school_views"]
        assert data["funnel"]["stages"][1]["count"] == seeded_events["search_started"]

    @pytest.mark.asyncio
    async def test_window_days_parameter(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """window_days 参数生效：2 天窗口可覆盖近 1 天事件。

        注：seeded_events 中事件 occurred_at=now-1day，使用 window_days=1 时
        由于 seed 与 query 之间存在毫秒级时差，事件可能刚好落在窗口边界之外。
        改用 window_days=2 保证覆盖。
        """
        response = await client.get(
            "/api/v1/admin/analytics?window_days=2",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        meta = response.json()["funnel"]["meta"]
        assert meta["empty_state"] is False

    @pytest.mark.asyncio
    async def test_empty_state_when_no_events(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
    ):
        """无数据时 empty_state=true。"""
        # 不使用 seeded_events，直接查询（仍有 test_school 创建）
        response = await client.get(
            "/api/v1/admin/analytics",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        data = response.json()
        # 漏斗空
        assert data["funnel"]["stages"][0]["count"] == 0
        assert data["funnel"]["meta"]["empty_state"] is True
        # 搜索成功率空
        assert data["search_success_rate"]["meta"]["empty_state"] is True
        assert data["search_success_rate"]["success_rate"] == 0.0


# ============================================================
# 零结果洞察 + 隐私阈值
# ============================================================
class TestZeroResultsInsight:
    """GET /api/v1/admin/analytics/zero-results"""

    @pytest.mark.asyncio
    async def test_privacy_threshold_applied(
        self,
        db_session: AsyncSession,
        test_school: dict,
    ):
        """样本量 < PRIVACY_THRESHOLD 的主题标记 hidden_for_privacy=true。"""
        school_id = test_school["id"]
        now = datetime.now()
        # 3 次 search_zero 同主题（< 5）→ 应标记 hidden
        for _ in range(3):
            await _seed_event(db_session, school_id, "search_zero",
                              occurred_at=now - timedelta(days=1),
                              fields={"keyword_length": 5, "category_code": "lost-found"})
        # 6 次 search_zero 另一主题（≥ 5）→ 不应标记 hidden
        for _ in range(6):
            await _seed_event(db_session, school_id, "search_zero",
                              occurred_at=now - timedelta(days=1),
                              fields={"keyword_length": 10, "category_code": "second-hand"})
        await db_session.commit()

        svc = SchoolAnalyticsService(db_session, school_id)
        insight = await svc.compute_zero_results_insight(window_days=30)
        topics = insight.topics
        # 2 个主题
        assert len(topics) == 2
        # 按出现次数降序
        assert topics[0].occurrences >= topics[1].occurrences
        # 高频主题不隐藏
        high = next(t for t in topics if t.occurrences == 6)
        assert high.hidden_for_privacy is False
        # 低频主题隐藏
        low = next(t for t in topics if t.occurrences == 3)
        assert low.hidden_for_privacy is True
        # 隐私阈值常量正确
        assert insight.privacy_threshold == PRIVACY_THRESHOLD
        # 总数 = 9
        assert insight.total_zero_searches == 9

    @pytest.mark.asyncio
    async def test_zero_results_via_api(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
        db_session: AsyncSession,
    ):
        """API 端点返回零结果洞察 + 隐私阈值字段。"""
        school_id = test_school["id"]
        now = datetime.now()
        # 2 次 search_zero（< 5）→ 应标记 hidden
        for _ in range(2):
            await _seed_event(db_session, school_id, "search_zero",
                              occurred_at=now - timedelta(days=1),
                              fields={"keyword_length": 4, "category_code": "lost-found"})
        await db_session.commit()

        response = await client.get(
            "/api/v1/admin/analytics/zero-results",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["school_id"] == school_id
        assert data["privacy_threshold"] == PRIVACY_THRESHOLD
        assert data["total_zero_searches"] == 2
        assert len(data["topics"]) == 1
        assert data["topics"][0]["hidden_for_privacy"] is True
        assert data["topics"][0]["occurrences"] == 2

    @pytest.mark.asyncio
    async def test_zero_results_empty_state(
        self,
        client: AsyncClient,
        admin_headers: dict,
        test_school: dict,
    ):
        """无零结果事件时返回空列表。"""
        response = await client.get(
            "/api/v1/admin/analytics/zero-results",
            headers={**admin_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_zero_searches"] == 0
        assert data["topics"] == []

    @pytest.mark.asyncio
    async def test_zero_results_user_forbidden(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_school: dict,
    ):
        """普通用户访问 403。"""
        response = await client.get(
            "/api/v1/admin/analytics/zero-results",
            headers={**auth_headers, "X-School-Code": test_school["code"]},
        )
        assert response.status_code == 403


# ============================================================
# 平台分析接口
# ============================================================
class TestPlatformAnalyticsAPI:
    """GET /api/v1/platform/analytics"""

    @pytest.mark.asyncio
    async def test_super_admin_can_access(
        self,
        client: AsyncClient,
        super_admin: dict,
        test_school: dict,
    ):
        """super_admin 可访问平台分析接口。"""
        response = await client.get(
            "/api/v1/platform/analytics",
            headers=super_admin["headers"],
        )
        assert response.status_code == 200, response.text
        data = response.json()
        # 必备字段
        for key in (
            "school_total", "school_active", "school_metrics",
            "platform_funnel", "platform_search",
            "platform_ai_usage", "platform_governance", "generated_at",
        ):
            assert key in data, f"缺失字段: {key}"

    @pytest.mark.asyncio
    async def test_admin_forbidden(
        self,
        client: AsyncClient,
        admin_headers: dict,
    ):
        """普通 admin 访问平台分析 403。"""
        response = await client.get(
            "/api/v1/platform/analytics",
            headers=admin_headers,
        )
        assert response.status_code == 403, response.text

    @pytest.mark.asyncio
    async def test_normal_user_forbidden(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """普通用户访问平台分析 403。"""
        response = await client.get(
            "/api/v1/platform/analytics",
            headers=auth_headers,
        )
        assert response.status_code == 403, response.text

    @pytest.mark.asyncio
    async def test_platform_only_school_level_aggregates(
        self,
        client: AsyncClient,
        super_admin: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """平台层只返回学校级聚合，不暴露跨校用户维度。"""
        response = await client.get(
            "/api/v1/platform/analytics",
            headers=super_admin["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        # school_metrics 是数组，每个元素是单校聚合
        assert isinstance(data["school_metrics"], list)
        assert len(data["school_metrics"]) >= 1
        # 每个学校聚合不应包含跨校用户维度字段
        for sm in data["school_metrics"]:
            assert "school_id" in sm
            assert "funnel_summary" in sm
            assert "search_success_rate" in sm
            assert "search_zero_rate" in sm
            assert "ai_calls" in sm
            # 不应有跨校用户轨迹字段
            assert "user_ids" not in sm
            assert "user_trajectories" not in sm
            assert "cross_school_users" not in sm

    @pytest.mark.asyncio
    async def test_platform_aggregates_across_schools(
        self,
        client: AsyncClient,
        super_admin: dict,
        test_school: dict,
        seeded_events: dict,
        db_session: AsyncSession,
    ):
        """平台聚合包含所有学校数据。"""
        # 创建第二所学校 + 该校事件
        school_b = await _create_school(db_session, "B 校", "plat-b-ana02")
        await _seed_event(db_session, school_b.id, "school_viewed",
                          occurred_at=datetime.now() - timedelta(days=1))
        await _seed_event(db_session, school_b.id, "search_succeeded",
                          occurred_at=datetime.now() - timedelta(days=1))
        await db_session.commit()

        response = await client.get(
            "/api/v1/platform/analytics",
            headers=super_admin["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        # 学校总数包含 B 校
        assert data["school_total"] >= 2
        # 平台级漏斗 stage[0] 应包含两校 school_viewed 总和
        assert data["platform_funnel"]["stages"][0]["count"] >= (
            seeded_events["school_views"] + 1
        )

    @pytest.mark.asyncio
    async def test_window_days_parameter(
        self,
        client: AsyncClient,
        super_admin: dict,
        test_school: dict,
        seeded_events: dict,
    ):
        """window_days 参数生效。"""
        response = await client.get(
            "/api/v1/platform/analytics?window_days=7",
            headers=super_admin["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        # 7 天窗口应覆盖近 1 天的事件
        assert data["platform_funnel"]["meta"]["empty_state"] is False

    @pytest.mark.asyncio
    async def test_invalid_window_days_rejected(
        self,
        client: AsyncClient,
        super_admin: dict,
    ):
        """非法 window_days 被 Query 校验拒绝。"""
        # 0 < 1（ge=1）
        r = await client.get(
            "/api/v1/platform/analytics?window_days=0",
            headers=super_admin["headers"],
        )
        assert r.status_code == 422
        # 181 > 180（le=180）
        r = await client.get(
            "/api/v1/platform/analytics?window_days=181",
            headers=super_admin["headers"],
        )
        assert r.status_code == 422


# ============================================================
# 服务层单元测试
# ============================================================
class TestSchoolAnalyticsService:
    """SchoolAnalyticsService 直接调用。"""

    @pytest.mark.asyncio
    async def test_compute_all_returns_all_metrics(
        self,
        db_session: AsyncSession,
        test_school: dict,
    ):
        """compute_all 返回所有指标字段。"""
        svc = SchoolAnalyticsService(db_session, test_school["id"])
        metrics = await svc.compute_all(window_days=30)
        d = metrics.to_dict()
        for key in (
            "school_id", "school_code", "school_name",
            "funnel", "retention_7d", "search_success_rate", "search_zero_rate",
            "share_subscription_conversion", "content_valid_rate",
            "governance_sla", "ai_usage", "generated_at",
        ):
            assert key in d

    @pytest.mark.asyncio
    async def test_compute_zero_results_insight(
        self,
        db_session: AsyncSession,
        test_school: dict,
    ):
        """compute_zero_results_insight 默认空。"""
        svc = SchoolAnalyticsService(db_session, test_school["id"])
        insight = await svc.compute_zero_results_insight(window_days=30)
        assert insight.total_zero_searches == 0
        assert insight.topics == []
        assert insight.privacy_threshold == PRIVACY_THRESHOLD


class TestPlatformAnalyticsService:
    """PlatformAnalyticsService 直接调用。"""

    @pytest.mark.asyncio
    async def test_compute_all_returns_school_metrics(
        self,
        db_session: AsyncSession,
        test_school: dict,
    ):
        """compute_all 返回各校聚合 + 平台聚合。"""
        svc = PlatformAnalyticsService(db_session)
        metrics = await svc.compute_all(window_days=30)
        d = metrics.to_dict()
        assert d["school_total"] >= 1
        assert isinstance(d["school_metrics"], list)
        assert len(d["school_metrics"]) == d["school_total"]
        # 每个学校聚合字段完整
        sm = d["school_metrics"][0]
        for key in (
            "school_id", "school_code", "school_name", "is_active",
            "funnel_summary", "search_success_rate", "search_zero_rate",
            "ai_calls", "ai_fallback_rate",
        ):
            assert key in sm
