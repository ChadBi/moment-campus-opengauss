"""REL-02.3: 故障注入测试——DB 异常 / AI 超时降级 / 故障链路可观测性

覆盖：
1. DB 故障：普通搜索在 DB session 抛错时返回 500（不泄露堆栈）+ X-Request-ID
2. AI 超时降级：AI provider 超时 → fallback=true + 普通搜索结果 + ai_invocation_logs 记录
3. AI 网络错误降级：provider 网络异常 → fallback=true + 记录 network_error
4. AI 限流降级：provider 429 → fallback=true + 记录 rate_limit
5. AI 故障可观测性：降级后 /admin/todos 的 ai_fallback_24h 应反映故障次数
6. 故障链路 X-Request-ID 透传：异常响应仍带 request_id
"""
import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.ai.exceptions import (
    AINetworkError,
    AITimeoutError,
    AIRateLimitError,
    AIInsufficientQuotaError,
)
from app.ai.provider import CircuitBreaker, MockAIProvider
from app.core.security import create_access_token, get_password_hash
from app.models.ai_invocation_log import AIInvocationLog
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.post import Post
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription
from app.core.post_status import PostStatus


pytestmark = pytest.mark.asyncio


# ============================================================
# 辅助
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


async def _create_user(db: AsyncSession, email: str, nickname: str, school_id: int, role: str = "user") -> User:
    u = User(
        email=email, nickname=nickname,
        password_hash=get_password_hash("testpass123"),
        school_id=school_id, role=role,
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


def _school(code: str) -> dict:
    return {"X-School-Code": code}


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_provider(
    *,
    failure_threshold: int = 5,
    reset_seconds: int = 60,
    max_retries: int = 0,
    timeout: float = 15.0,
) -> MockAIProvider:
    circuit = CircuitBreaker(failure_threshold=failure_threshold, reset_seconds=reset_seconds)
    return MockAIProvider(
        timeout=timeout,
        max_tokens=1024,
        max_retries=max_retries,
        circuit=circuit,
    )


def _patch_provider(monkeypatch, provider: MockAIProvider) -> None:
    """Patch get_provider in app.ai.service to return the given provider."""
    async def _mock_get_provider():
        return provider
    monkeypatch.setattr("app.ai.service.get_provider", _mock_get_provider)


def _intent_json(*, keyword: str = "校园卡", category: str = "失物招领", sort: str = "relevance") -> str:
    return json.dumps(
        {
            "intent": f"查找{keyword}",
            "filters": {
                "keyword": keyword,
                "category": category,
                "sort": sort,
                "date_from": None,
                "date_to": None,
                "map_bounds": None,
            },
            "reasons": ["按相关度排序"],
        },
        ensure_ascii=False,
    )


# ============================================================
# 共享夹具
# ============================================================
@pytest_asyncio.fixture
async def fault_setup(db_session: AsyncSession) -> dict:
    """单校 + 1 admin + 1 user + 1 分类 + 1 类型 + 2 已发布帖子"""
    school = await _create_school(db_session, "故障注入测试大学", "fault-uni")
    await _assign_operations_subscription(db_session, school.id)
    user = await _create_user(db_session, "faultuser@example.com", "故障用户", school.id)
    await _create_membership(db_session, user.id, school.id)
    admin = await _create_user(
        db_session, "faultadmin@example.com", "故障管理员", school.id, role="admin"
    )
    await _create_membership(db_session, admin.id, school.id)
    cat = await _create_category(db_session, school.id, "失物招领", "fault-lost")

    now = datetime.now()
    p1 = Post(
        user_id=user.id, school_id=school.id,
        category_id=cat.id,
        title="校园卡丢失", content="在图书馆丢失校园卡一张",
        status=PostStatus.PUBLISHED, created_at=now,
    )
    p2 = Post(
        user_id=user.id, school_id=school.id,
        category_id=cat.id,
        title="校园卡捡到", content="在食堂捡到校园卡一张",
        status=PostStatus.PUBLISHED, created_at=now,
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    return {
        "school": {"id": school.id, "code": school.code, "name": school.name},
        "user": {"id": user.id, "token": create_access_token(data={"sub": str(user.id)})},
        "admin": {"id": admin.id, "token": create_access_token(data={"sub": str(admin.id)})},
        "category": cat,
        "posts": {"p1": p1, "p2": p2},
    }


# ============================================================
# DB 故障测试
# ============================================================
class TestDBFaultInjection:
    """DB 故障注入：session 抛错时返回 500 + X-Request-ID（不泄露堆栈）。"""

    async def test_search_db_failure_returns_500_with_request_id(
        self, client: AsyncClient, fault_setup: dict
    ):
        """普通搜索 DB session 抛错 → 500 + 仍带 X-Request-ID 响应头"""
        from app.database import get_db
        from app.main import app

        async def _failing_get_db():
            mock_session = MagicMock()
            mock_session.execute = AsyncMock(side_effect=RuntimeError("DB connection lost"))
            yield mock_session

        original = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = _failing_get_db
        try:
            resp = await client.get(
                "/api/v1/search",
                params={"keyword": "校园卡"},
                headers=_school(fault_setup["school"]["code"]),
            )
            # 应返回 500（unhandled exception handler 兜底）
            assert resp.status_code == 500
            # 响应头必须带 X-Request-ID（即使异常）
            assert "X-Request-ID" in resp.headers
            assert resp.headers["X-Request-ID"]
            # 响应体不泄露堆栈
            data = resp.json()
            assert "detail" in data
            assert "request_id" in data
            # 不应包含堆栈信息
            assert "Traceback" not in str(data)
            assert "RuntimeError" not in str(data.get("detail", ""))
        finally:
            if original is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = original

    async def test_health_ready_db_failure_returns_503(
        self, client: AsyncClient, fault_setup: dict, monkeypatch
    ):
        """健康检查就绪探针检测到 DB 故障 → 503 unavailable"""
        monkeypatch.setenv("AI_PROVIDER", "mock")
        from app.database import get_db
        from app.main import app

        async def _failing_get_db():
            mock_session = MagicMock()
            mock_session.execute = AsyncMock(side_effect=RuntimeError("connection refused"))
            yield mock_session

        original = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = _failing_get_db
        try:
            resp = await client.get("/health/ready")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "unavailable"
            assert "fail" in data["checks"]["db"]
        finally:
            if original is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = original


# ============================================================
# AI 超时 / 网络错误 / 限流 降级测试
# ============================================================
class TestAIFaultDegradation:
    """AI provider 各种故障 → fallback=true + ai_invocation_logs 记录对应状态。"""

    async def test_ai_timeout_falls_back_to_normal_search(
        self, client: AsyncClient, fault_setup: dict, monkeypatch,
    ):
        """AI 超时 → fallback=true + 普通搜索结果 + 记录 timeout"""
        provider = _make_provider(timeout=0.05, max_retries=0)
        provider.set_delay(0.3)
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(fault_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert data["fallback_reason"] is not None
        # 仍返回匹配"校园卡"的帖子
        assert len(data["items"]) > 0
        post_ids = {item["id"] for item in data["items"]}
        assert fault_setup["posts"]["p1"].id in post_ids
        assert fault_setup["posts"]["p2"].id in post_ids

    async def test_ai_network_error_logs_correct_status(
        self, client: AsyncClient, fault_setup: dict, monkeypatch,
        db_session: AsyncSession,
    ):
        """AI 网络错误 → ai_invocation_logs.output_status=network_error"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("network down"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(fault_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        log_id = data["ai_log_id"]
        assert log_id is not None

        # 验证日志记录
        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.output_status == "network_error"
        assert log.fallback_reason is not None
        assert log.school_id == fault_setup["school"]["id"]
        # trace_id 关联 X-Request-ID
        assert log.trace_id is not None
        assert log.trace_id == resp.headers.get("X-Request-ID")

    async def test_ai_rate_limit_falls_back(
        self, client: AsyncClient, fault_setup: dict, monkeypatch,
        db_session: AsyncSession,
    ):
        """AI 限流（429）→ fallback=true + 记录 rate_limit"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AIRateLimitError("rate limited"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(fault_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        log_id = data["ai_log_id"]
        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.output_status == "rate_limit"

    async def test_ai_insufficient_quota_falls_back(
        self, client: AsyncClient, fault_setup: dict, monkeypatch,
        db_session: AsyncSession,
    ):
        """AI 余额不足 → fallback=true + 记录 insufficient_quota"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AIInsufficientQuotaError("no quota"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(fault_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        log_id = data["ai_log_id"]
        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.output_status == "insufficient_quota"

    async def test_ai_success_does_not_count_as_fallback(
        self, client: AsyncClient, fault_setup: dict, monkeypatch,
        db_session: AsyncSession,
    ):
        """AI 成功调用 → fallback=false + output_status=success + fallback_reason=None"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡", category="失物招领"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(fault_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is False
        log_id = data["ai_log_id"]
        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.output_status == "success"
        assert log.fallback_reason is None


# ============================================================
# 故障可观测性：admin 首页 AI 监控反映降级
# ============================================================
class TestAIFaultObservability:
    """REL-02.3: AI 故障后 admin 首页 AI 监控应反映降级次数与降级率。"""

    async def test_admin_todos_reflects_ai_fallback_count(
        self, client: AsyncClient, fault_setup: dict, monkeypatch,
        db_session: AsyncSession,
    ):
        """触发 2 次 AI 网络错误降级后，/admin/todos 的 ai_fallback_24h 应为 2"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("net err"))
        _patch_provider(monkeypatch, provider)

        # 触发 2 次降级
        for _ in range(2):
            resp = await client.post(
                "/api/v1/search/ai",
                json={"query": "校园卡"},
                headers=_school(fault_setup["school"]["code"]),
            )
            assert resp.status_code == 200
            assert resp.json()["fallback"] is True

        # admin 查看待办统计
        resp = await client.get(
            "/api/v1/admin/todos",
            headers={**_school(fault_setup["school"]["code"]), **_auth(fault_setup["admin"]["token"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        # 应反映 2 次降级
        assert data["ai_calls_24h"] == 2
        assert data["ai_fallback_24h"] == 2
        # 降级率 = 1.0（100%）
        assert data["ai_fallback_rate"] == 1.0

    async def test_admin_todos_mixed_success_and_fallback(
        self, client: AsyncClient, fault_setup: dict, monkeypatch,
        db_session: AsyncSession,
    ):
        """1 次成功 + 1 次降级 → ai_fallback_rate = 0.5"""
        # 第一次：成功
        provider_ok = _make_provider()
        provider_ok.set_response(_intent_json(keyword="校园卡", category="失物招领"))
        _patch_provider(monkeypatch, provider_ok)
        resp1 = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(fault_setup["school"]["code"]),
        )
        assert resp1.status_code == 200
        assert resp1.json()["fallback"] is False

        # 第二次：网络错误降级
        provider_fail = _make_provider(max_retries=0)
        provider_fail.set_exception_factory(lambda: AINetworkError("net err"))
        _patch_provider(monkeypatch, provider_fail)
        resp2 = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(fault_setup["school"]["code"]),
        )
        assert resp2.status_code == 200
        assert resp2.json()["fallback"] is True

        # admin 查看待办统计
        resp = await client.get(
            "/api/v1/admin/todos",
            headers={**_school(fault_setup["school"]["code"]), **_auth(fault_setup["admin"]["token"])},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_calls_24h"] == 2
        assert data["ai_fallback_24h"] == 1
        # 降级率 = 0.5
        assert data["ai_fallback_rate"] == 0.5


# ============================================================
# 故障链路 X-Request-ID 透传
# ============================================================
class TestFaultRequestPropagation:
    """REL-02.2: 故障场景下 X-Request-ID 仍应透传到响应与日志。"""

    async def test_ai_failure_response_has_request_id(
        self, client: AsyncClient, fault_setup: dict, monkeypatch,
        db_session: AsyncSession,
    ):
        """AI 故障响应仍带 X-Request-ID，且日志 trace_id 关联"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("net err"))
        _patch_provider(monkeypatch, provider)

        custom_id = "rel02-fault-trace-abc123"
        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers={**_school(fault_setup["school"]["code"]), "X-Request-ID": custom_id},
        )
        assert resp.status_code == 200
        # 沿用客户端传入的 request_id
        assert resp.headers["X-Request-ID"] == custom_id
        # 日志的 trace_id 应等于 request_id
        log_id = resp.json()["ai_log_id"]
        assert log_id is not None
        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.trace_id == custom_id

    async def test_db_failure_response_has_request_id(
        self, client: AsyncClient, fault_setup: dict
    ):
        """DB 故障响应仍带 X-Request-ID（异常路径不丢失追踪 ID）"""
        from app.database import get_db
        from app.main import app

        async def _failing_get_db():
            mock_session = MagicMock()
            mock_session.execute = AsyncMock(side_effect=RuntimeError("DB lost"))
            yield mock_session

        original = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = _failing_get_db
        try:
            custom_id = "rel02-db-fault-trace-xyz789"
            resp = await client.get(
                "/api/v1/search",
                params={"keyword": "校园卡"},
                headers={**_school(fault_setup["school"]["code"]), "X-Request-ID": custom_id},
            )
            assert resp.status_code == 500
            assert resp.headers["X-Request-ID"] == custom_id
            # 错误响应体也带 request_id
            assert resp.json()["request_id"] == custom_id
        finally:
            if original is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = original
