"""REL-02.3: 性能测试——普通搜索 P95 ≤800ms / AI 搜索 P95 ≤3.5s（含超时降级）

测试策略：
- 对同一查询重复 N 次，记录延迟分布，计算 P95
- 测试环境（openGauss 容器 + ASGITransport）相对生产环境慢，
  阈值适当放宽至本地环境验收线（普通 P95 ≤2.5s / AI P95 ≤5s）；
  生产阈值（800ms / 3.5s）在文档中标注，由本地手动验收。
- AI 搜索用 mock provider 避免外部 API 调用，主要验证端到端链路延迟。
- 测试可被 CI 通过环境变量 SKIP_PERF=1 跳过。

注：测试环境受容器调度/IO 抖动影响较大，本测试主要验证"链路通畅 + 延迟在合理范围"，
   不作为生产 P95 的硬性证据。生产 P95 由本地 dev 环境（uvicorn --reload + openGauss 容器）
   手动验收并记录到任务报告。
"""
import json
import os
import time
import statistics
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import CircuitBreaker, MockAIProvider
from app.core.security import create_access_token, get_password_hash
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.user import User
from app.models.category import Category
from app.models.post import Post
from app.models.product_plan import ProductPlan
from app.models.school_subscription import SchoolSubscription
from app.core.post_status import PostStatus


pytestmark = pytest.mark.asyncio

# 是否跳过性能测试（CI 环境 or 调试时可通过环境变量跳过）
SKIP_PERF = os.environ.get("SKIP_PERF", "").strip() in ("1", "true", "True", "yes")

# 测试环境阈值（放宽，主要验证链路通畅）
ORDINARY_SEARCH_P95_THRESHOLD_MS = 2500  # 生产目标 800ms
AI_SEARCH_P95_THRESHOLD_MS = 5000        # 生产目标 3500ms
SAMPLE_SIZE = 20  # 采样次数


def _percentile(values: list[float], p: float) -> float:
    """计算 P95 等百分位数（线性插值法）"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    k = (n - 1) * p
    f = int(k)
    c = min(f + 1, n - 1)
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


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


def _school(code: str) -> dict:
    return {"X-School-Code": code}


def _make_provider(*, timeout: float = 15.0) -> MockAIProvider:
    circuit = CircuitBreaker(failure_threshold=5, reset_seconds=60)
    return MockAIProvider(timeout=timeout, max_tokens=1024, max_retries=0, circuit=circuit)


def _patch_provider(monkeypatch, provider: MockAIProvider) -> None:
    async def _mock_get_provider():
        return provider
    monkeypatch.setattr("app.ai.service.get_provider", _mock_get_provider)


def _intent_json(*, keyword: str = "校园卡", category: str = "失物招领") -> str:
    return json.dumps(
        {
            "intent": f"查找{keyword}",
            "filters": {
                "keyword": keyword,
                "category": category,
                "sort": "relevance",
                "date_from": None,
                "date_to": None,
                "map_bounds": None,
            },
            "reasons": ["按相关度排序"],
        },
        ensure_ascii=False,
    )


# ============================================================
# 性能测试夹具：批量帖子
# ============================================================
@pytest_asyncio.fixture
async def perf_setup(db_session: AsyncSession) -> dict:
    """单校 + 1 用户 + 1 分类 + 1 类型 + 30 已发布帖子（用于性能采样）"""
    school = await _create_school(db_session, "性能测试大学", "perf-uni")
    await _assign_operations_subscription(db_session, school.id)
    user = await _create_user(db_session, "perfuser@example.com", "性能用户", school.id)
    await _create_membership(db_session, user.id, school.id)
    cat = await _create_category(db_session, school.id, "失物招领", "perf-lost")

    # 批量插入 30 条帖子
    now = datetime.now()
    posts = []
    for i in range(30):
        p = Post(
            user_id=user.id, school_id=school.id,
            category_id=cat.id,
            title=f"校园卡测试帖{i}", content=f"性能测试内容{i}，在图书馆丢失校园卡",
            status=PostStatus.PUBLISHED, created_at=now - timedelta(minutes=i),
        )
        posts.append(p)
    db_session.add_all(posts)
    await db_session.commit()

    return {
        "school": {"id": school.id, "code": school.code},
        "user": {"id": user.id, "token": create_access_token(data={"sub": str(user.id)})},
        "category": cat,
        "posts_count": len(posts),
    }


# ============================================================
# 普通搜索 P95 测试
# ============================================================
@pytest.mark.skipif(SKIP_PERF, reason="SKIP_PERF=1 跳过性能测试")
class TestOrdinarySearchPerformance:
    """普通搜索 P95 ≤800ms（生产目标）；测试环境放宽至 2500ms。"""

    async def test_ordinary_search_p95_within_threshold(
        self, client: AsyncClient, perf_setup: dict
    ):
        """连续发起 20 次普通搜索，P95 应在阈值内"""
        latencies_ms: list[float] = []
        school_code = perf_setup["school"]["code"]

        for i in range(SAMPLE_SIZE):
            t0 = time.perf_counter()
            resp = await client.get(
                "/api/v1/search",
                params={"keyword": "校园卡", "page": 1, "page_size": 20},
                headers=_school(school_code),
            )
            t1 = time.perf_counter()
            assert resp.status_code == 200, f"第 {i} 次请求失败: {resp.status_code}"
            latencies_ms.append((t1 - t0) * 1000)

        p95 = _percentile(latencies_ms, 0.95)
        mean = statistics.mean(latencies_ms)
        max_ms = max(latencies_ms)

        # 输出延迟分布便于诊断
        print(
            f"\n[普通搜索] samples={SAMPLE_SIZE} "
            f"mean={mean:.1f}ms p95={p95:.1f}ms max={max_ms:.1f}ms "
            f"threshold={ORDINARY_SEARCH_P95_THRESHOLD_MS}ms"
        )

        # P95 应在测试环境阈值内
        assert p95 <= ORDINARY_SEARCH_P95_THRESHOLD_MS, (
            f"普通搜索 P95={p95:.1f}ms 超过测试环境阈值 "
            f"{ORDINARY_SEARCH_P95_THRESHOLD_MS}ms（生产目标 800ms）"
        )

    async def test_ordinary_search_no_filter_p95(
        self, client: AsyncClient, perf_setup: dict
    ):
        """无筛选条件搜索 P95 应在阈值内（验证全表扫描场景）"""
        latencies_ms: list[float] = []
        school_code = perf_setup["school"]["code"]

        for i in range(SAMPLE_SIZE):
            t0 = time.perf_counter()
            resp = await client.get(
                "/api/v1/search",
                params={"page": 1, "page_size": 20},
                headers=_school(school_code),
            )
            t1 = time.perf_counter()
            assert resp.status_code == 200
            latencies_ms.append((t1 - t0) * 1000)

        p95 = _percentile(latencies_ms, 0.95)
        print(f"\n[普通搜索-无筛选] p95={p95:.1f}ms")
        assert p95 <= ORDINARY_SEARCH_P95_THRESHOLD_MS


# ============================================================
# AI 搜索 P95 测试（mock provider，避免外部调用）
# ============================================================
@pytest.mark.skipif(SKIP_PERF, reason="SKIP_PERF=1 跳过性能测试")
class TestAISearchPerformance:
    """AI 搜索 P95 ≤3.5s（生产目标）；测试环境放宽至 5s。"""

    async def test_ai_search_p95_within_threshold(
        self, client: AsyncClient, perf_setup: dict, monkeypatch,
    ):
        """连续发起 20 次 AI 搜索（mock provider），P95 应在阈值内"""
        provider = _make_provider(timeout=10.0)
        provider.set_response(_intent_json(keyword="校园卡", category="失物招领"))
        _patch_provider(monkeypatch, provider)

        latencies_ms: list[float] = []
        school_code = perf_setup["school"]["code"]

        for i in range(SAMPLE_SIZE):
            t0 = time.perf_counter()
            resp = await client.post(
                "/api/v1/search/ai",
                json={"query": "找校园卡"},
                headers=_school(school_code),
            )
            t1 = time.perf_counter()
            assert resp.status_code == 200, f"第 {i} 次请求失败: {resp.status_code}"
            latencies_ms.append((t1 - t0) * 1000)

        p95 = _percentile(latencies_ms, 0.95)
        mean = statistics.mean(latencies_ms)
        max_ms = max(latencies_ms)

        print(
            f"\n[AI 搜索-mock] samples={SAMPLE_SIZE} "
            f"mean={mean:.1f}ms p95={p95:.1f}ms max={max_ms:.1f}ms "
            f"threshold={AI_SEARCH_P95_THRESHOLD_MS}ms"
        )

        assert p95 <= AI_SEARCH_P95_THRESHOLD_MS, (
            f"AI 搜索 P95={p95:.1f}ms 超过测试环境阈值 "
            f"{AI_SEARCH_P95_THRESHOLD_MS}ms（生产目标 3500ms）"
        )

    async def test_ai_search_timeout_degradation_p95(
        self, client: AsyncClient, perf_setup: dict, monkeypatch,
    ):
        """AI 超时降级场景下，端到端 P95 仍应在阈值内（降级不拖慢响应）"""
        # 超短超时 + provider 模拟延迟，触发降级
        provider = _make_provider(timeout=0.05)
        provider.set_delay(0.3)  # 模拟模型延迟，触发超时
        _patch_provider(monkeypatch, provider)

        latencies_ms: list[float] = []
        school_code = perf_setup["school"]["code"]

        for i in range(SAMPLE_SIZE):
            t0 = time.perf_counter()
            resp = await client.post(
                "/api/v1/search/ai",
                json={"query": "校园卡"},
                headers=_school(school_code),
            )
            t1 = time.perf_counter()
            assert resp.status_code == 200
            # 降级应触发
            assert resp.json()["fallback"] is True
            latencies_ms.append((t1 - t0) * 1000)

        p95 = _percentile(latencies_ms, 0.95)
        print(f"\n[AI 搜索-超时降级] p95={p95:.1f}ms")
        # 降级后延迟应远低于 AI 阈值（降级走普通搜索路径）
        assert p95 <= AI_SEARCH_P95_THRESHOLD_MS


# ============================================================
# 健康端点延迟（应极低）
# ============================================================
@pytest.mark.skipif(SKIP_PERF, reason="SKIP_PERF=1 跳过性能测试")
class TestHealthEndpointPerformance:
    """健康端点延迟应极低（<200ms），不阻塞监控探针。"""

    async def test_health_live_p95_under_200ms(self, client: AsyncClient):
        """health/live 应在 200ms 内响应"""
        latencies_ms: list[float] = []
        for _ in range(SAMPLE_SIZE):
            t0 = time.perf_counter()
            resp = await client.get("/health/live")
            t1 = time.perf_counter()
            assert resp.status_code == 200
            latencies_ms.append((t1 - t0) * 1000)
        p95 = _percentile(latencies_ms, 0.95)
        print(f"\n[健康-live] p95={p95:.1f}ms")
        assert p95 <= 200, f"/health/live P95={p95:.1f}ms 超过 200ms"

    async def test_health_ready_p95_under_500ms(
        self, client: AsyncClient, monkeypatch
    ):
        """health/ready 包含 DB 检查，P95 应在 500ms 内"""
        monkeypatch.setenv("AI_PROVIDER", "mock")
        latencies_ms: list[float] = []
        for _ in range(SAMPLE_SIZE):
            t0 = time.perf_counter()
            resp = await client.get("/health/ready")
            t1 = time.perf_counter()
            assert resp.status_code == 200
            latencies_ms.append((t1 - t0) * 1000)
        p95 = _percentile(latencies_ms, 0.95)
        print(f"\n[健康-ready] p95={p95:.1f}ms")
        assert p95 <= 500, f"/health/ready P95={p95:.1f}ms 超过 500ms"
