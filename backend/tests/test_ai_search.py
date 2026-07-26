"""AI-02: AI 结构化搜索测试

覆盖：
- AI-02.1: POST /api/v1/search/ai 接口
    - 成功：返回意图 + 结果 + 分数 + 匹配理由
    - 降级：Provider 异常 / JSON 解析失败 / 敏感词 → fallback=true
    - overrides：用户提供覆盖项时跳过模型调用
- 租户隔离：只返回当前学校数据
- 数据过滤：只检索 published 且未过期未删除
- 白名单：分类/排序/时间/地图范围非法值丢弃
- 确定性排序：相同输入相同顺序
- 日志：ai_invocation_logs 成功/失败均记录
"""
import json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import AINetworkError, AITimeoutError
from app.ai.provider import CircuitBreaker, MockAIProvider
from app.core.post_status import PostStatus
from app.core.security import create_access_token, get_password_hash
from app.models.ai_invocation_log import AIInvocationLog
from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.post_image import PostImage
from app.models.post_type import PostType
from app.models.product_plan import ProductPlan
from app.models.school import School
from app.models.school_membership import SchoolMembership
from app.models.school_subscription import SchoolSubscription
from app.models.user import User


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


async def _create_post_type(db: AsyncSession, name: str, code: str) -> PostType:
    pt = PostType(name=name, code=code, is_active=True)
    db.add(pt)
    await db.flush()
    return pt


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
    post_type_id: int,
    title: str,
    content: str = "默认内容至少十个字符",
    status: str = PostStatus.PUBLISHED,
    location_id: int | None = None,
    like_count: int = 0,
    valid_count: int = 0,
    created_at: datetime | None = None,
    expire_at: datetime | None = None,
    is_deleted: bool = False,
) -> Post:
    p = Post(
        user_id=user_id, school_id=school_id,
        category_id=category_id, post_type_id=post_type_id,
        location_id=location_id, title=title, content=content,
        status=status, like_count=like_count, valid_count=valid_count,
        created_at=created_at or datetime.now(),
        expire_at=expire_at,
        is_deleted=is_deleted,
    )
    db.add(p)
    await db.flush()
    return p


def _school(code: str) -> dict:
    return {"X-School-Code": code}


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


def _intent_json(
    *,
    keyword: str | None = "校园卡",
    category: str | None = "失物招领",
    sort: str = "relevance",
    reasons: list[str] | None = None,
    map_bounds: dict | None = None,
) -> str:
    """构造合法的 SEARCH_INTENT_SCHEMA JSON 串。"""
    filters = {
        "keyword": keyword,
        "category": category,
        "sort": sort,
        "date_from": None,
        "date_to": None,
        "map_bounds": map_bounds,
    }
    return json.dumps(
        {
            "intent": f"查找{keyword or '信息'}",
            "filters": filters,
            "reasons": reasons or ["按相关度排序"],
        },
        ensure_ascii=False,
    )


# ============================================================
# 测试夹具：AI 搜索场景
# ============================================================
@pytest_asyncio.fixture
async def ai_search_setup(db_session: AsyncSession) -> dict:
    """AI 搜索测试夹具：单校多帖子覆盖各场景

    帖子矩阵（共 5 条已发布 + 1 条已过期 + 1 条待审核 + 1 条已删除）：
        - p1: published / "校园卡丢失" / 5 赞 / 2 证实 / loc_a / 今日创建
        - p2: published / "校园卡捡到" / 3 赞 / 1 证实 / loc_b / 一周前创建
        - p3: published / "图书馆读书会" / 10 赞 / 5 证实 / loc_a / 一月前创建（不同主题）
        - p4: published / "食堂美食节" / 0 赞 / 0 证实 / loc_b / 三天前创建
        - p5: published / "校园卡补办" / 1 赞 / 0 证实 / loc_a / 已删除（不应返回）
        - p6: published / "校园卡过期" / 0 赞 / 0 证实 / loc_a / 已过期（不应返回）
        - p7: pending / "校园卡待审" / 0 赞 / 0 证实 / loc_a / 待审核（不应返回）
    """
    school = await _create_school(db_session, "AI搜索测试大学", "ai-uni")
    await _assign_operations_subscription(db_session, school.id)

    user = await _create_user(db_session, "aisearchuser@example.com", "AI搜索用户", school.id)
    await _create_membership(db_session, user.id, school.id)

    cat_lost = await _create_category(db_session, school.id, "失物招领", "lost-found")
    cat_event = await _create_category(db_session, school.id, "活动", "event")
    pt_normal = await _create_post_type(db_session, "普通信息", "normal")
    loc_a = await _create_location(db_session, school.id, "图书馆", 31.0, 120.0)
    loc_b = await _create_location(db_session, school.id, "食堂", 31.001, 120.001)

    now = datetime.now()
    p1 = await _create_post(
        db_session, user.id, school.id, cat_lost.id, pt_normal.id,
        "校园卡丢失求助", "在图书馆丢失校园卡一张", PostStatus.PUBLISHED,
        location_id=loc_a.id, like_count=5, valid_count=2,
        created_at=now - timedelta(hours=1),
    )
    p2 = await _create_post(
        db_session, user.id, school.id, cat_lost.id, pt_normal.id,
        "校园卡捡到招领", "在食堂捡到校园卡一张", PostStatus.PUBLISHED,
        location_id=loc_b.id, like_count=3, valid_count=1,
        created_at=now - timedelta(days=7),
    )
    p3 = await _create_post(
        db_session, user.id, school.id, cat_event.id, pt_normal.id,
        "图书馆读书会活动", "本周三图书馆读书会", PostStatus.PUBLISHED,
        location_id=loc_a.id, like_count=10, valid_count=5,
        created_at=now - timedelta(days=30),
    )
    p4 = await _create_post(
        db_session, user.id, school.id, cat_event.id, pt_normal.id,
        "食堂美食节活动", "食堂二楼美食节", PostStatus.PUBLISHED,
        location_id=loc_b.id, like_count=0, valid_count=0,
        created_at=now - timedelta(days=3),
    )
    # 已删除的帖子（不应返回）
    p5 = await _create_post(
        db_session, user.id, school.id, cat_lost.id, pt_normal.id,
        "校园卡补办", "校园卡补办流程", PostStatus.PUBLISHED,
        location_id=loc_a.id, like_count=1, valid_count=0,
        created_at=now - timedelta(hours=2),
        is_deleted=True,
    )
    # 已过期的帖子（不应返回）
    p6 = await _create_post(
        db_session, user.id, school.id, cat_lost.id, pt_normal.id,
        "校园卡过期帖", "校园卡过期内容", PostStatus.PUBLISHED,
        location_id=loc_a.id, like_count=0, valid_count=0,
        created_at=now - timedelta(days=10),
        expire_at=now - timedelta(days=1),  # 已过期
    )
    # 待审核的帖子（不应返回）
    p7 = await _create_post(
        db_session, user.id, school.id, cat_lost.id, pt_normal.id,
        "校园卡待审", "待审内容", PostStatus.PENDING,
        location_id=loc_a.id, like_count=0, valid_count=0,
        created_at=now - timedelta(hours=1),
    )

    await db_session.commit()

    return {
        "school": {"id": school.id, "code": school.code, "name": school.name},
        "user": {"id": user.id, "token": create_access_token(data={"sub": str(user.id)})},
        "categories": {"lost": cat_lost, "event": cat_event},
        "post_types": {"normal": pt_normal},
        "locations": {"a": loc_a, "b": loc_b},
        "posts": {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5, "p6": p6, "p7": p7},
    }


def _patch_provider(monkeypatch, provider: MockAIProvider) -> None:
    """Patch get_provider in app.ai.service to return the given provider."""
    async def _mock_get_provider():
        return provider
    monkeypatch.setattr("app.ai.service.get_provider", _mock_get_provider)


# ============================================================
# 1. AI 搜索成功场景
# ============================================================
class TestAISearchSuccess:
    """AI 搜索成功：返回意图 + 结果 + 分数 + 匹配理由"""

    @pytest.mark.asyncio
    async def test_ai_search_returns_intent_and_results(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """成功调用：返回 intent / items / scores / match_reasons"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡", category="失物招领", sort="relevance"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is False
        assert data["fallback_reason"] is None
        assert data["intent"] is not None
        assert data["intent"]["filters"]["keyword"] == "校园卡"
        # 解析后 category_id 必须命中白名单
        assert data["intent"]["filters"]["category_id"] == ai_search_setup["categories"]["lost"].id
        assert data["intent"]["filters"]["category_name"] == "失物招领"
        # 结果只含 published 未过期未删除且匹配"校园卡"的帖子
        post_ids = {item["id"] for item in data["items"]}
        setup = ai_search_setup["posts"]
        assert setup["p1"].id in post_ids  # 校园卡丢失
        assert setup["p2"].id in post_ids  # 校园卡捡到
        assert setup["p3"].id not in post_ids  # 图书馆读书会（不匹配"校园卡"）
        assert setup["p5"].id not in post_ids  # 已删除
        assert setup["p6"].id not in post_ids  # 已过期
        assert setup["p7"].id not in post_ids  # pending
        # 每条结果都有匹配理由与分数
        # 注：JSON 序列化后 dict 的 int key 会变 string，故用 str(id) 校验
        for item in data["items"]:
            pid_key = str(item["id"])
            assert pid_key in data["match_reasons"]
            assert len(data["match_reasons"][pid_key]) > 0
            assert pid_key in data["scores"]
            assert 0.0 <= data["scores"][pid_key] <= 1.0
        # ai_log_id 不为空
        assert data["ai_log_id"] is not None

    @pytest.mark.asyncio
    async def test_ai_search_relevance_sort_puts_title_match_first(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """relevance 排序：标题匹配 > 内容匹配（确定性）"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡", sort="relevance"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # p1 标题"校园卡丢失求助"与 p2 标题"校园卡捡到招领"都含"校园卡"在标题中
        # p1 created_at 比 p2 新（p1 是 1 小时前，p2 是 7 天前），同分时按 created_at 降序
        # p1 与 p2 标题都包含关键词，相关度都是 1.0
        # p1 freshness 更高（1 小时内 = 接近 1.0），p2 freshness 较低（7 天 = ~0.77）
        # 所以 p1 应该排第一
        assert items[0]["id"] == ai_search_setup["posts"]["p1"].id

    @pytest.mark.asyncio
    async def test_ai_search_match_reasons_contain_keyword_hint(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """匹配理由包含关键词命中信息"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        p1_id = ai_search_setup["posts"]["p1"].id
        reasons = data["match_reasons"][str(p1_id)] if str(p1_id) in data["match_reasons"] else data["match_reasons"][p1_id]
        # p1 标题包含"校园卡"
        assert any("校园卡" in r for r in reasons)

    @pytest.mark.asyncio
    async def test_ai_search_logs_invocation(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch, db_session: AsyncSession,
    ):
        """成功调用记录 ai_invocation_logs（output_status=success）"""
        provider = _make_provider()
        provider.set_response(_intent_json())
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        log_id = resp.json()["ai_log_id"]
        assert log_id is not None

        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.school_id == ai_search_setup["school"]["id"]
        assert log.scene == "search_intent"
        assert log.output_status == "success"
        # 隐私约束：不保存完整 prompt
        assert not hasattr(log, "prompt")
        # candidate_count / result_count 应被更新
        assert log.candidate_count is not None
        assert log.result_count is not None


# ============================================================
# 2. AI 搜索降级场景
# ============================================================
class TestAISearchFallback:
    """AI 搜索降级：任一步失败 → fallback=true + 普通搜索结果"""

    @pytest.mark.asyncio
    async def test_fallback_on_provider_network_error(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """Provider 网络错误 → fallback=true + 用 query 作为关键词检索"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("network down"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert data["fallback_reason"] is not None
        assert "降级" in data["fallback_reason"]
        # 仍返回结果（用 query 作为关键词）
        assert len(data["items"]) > 0
        post_ids = {item["id"] for item in data["items"]}
        setup = ai_search_setup["posts"]
        assert setup["p1"].id in post_ids  # 标题含"校园卡"
        assert setup["p2"].id in post_ids
        # 降级时 intent 为 None
        assert data["intent"] is None

    @pytest.mark.asyncio
    async def test_fallback_on_provider_timeout(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """Provider 超时 → fallback=true"""
        provider = _make_provider(timeout=0.05, max_retries=0)
        provider.set_delay(0.3)
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert "超时" in data["fallback_reason"] or "降级" in data["fallback_reason"]

    @pytest.mark.asyncio
    async def test_fallback_on_json_parse_error(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """模型返回非 JSON → fallback=true"""
        provider = _make_provider()
        provider.set_response("这不是合法 JSON")
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert "解析失败" in data["fallback_reason"] or "降级" in data["fallback_reason"]

    @pytest.mark.asyncio
    async def test_fallback_on_sensitive_query(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """敏感词命中 → fallback=true（不调用模型）"""
        provider = _make_provider()
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "炸弹威胁校园"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert "敏感" in data["fallback_reason"]
        # 不应调用模型
        assert provider.call_count == 0
        # 仍返回结果（用敏感词本身作为关键词，本场景下无匹配，返回空）
        # 注：降级用原始 query 作为关键词检索，若无匹配则 total=0
        assert "items" in data

    @pytest.mark.asyncio
    async def test_fallback_logs_failure_status(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch, db_session: AsyncSession,
    ):
        """降级时仍记录 ai_invocation_logs（output_status != success）"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("err"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        log_id = resp.json()["ai_log_id"]
        assert log_id is not None

        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.output_status == "network_error"
        assert log.fallback_reason is not None


# ============================================================
# 3. overrides 覆盖（用户编辑 Chip）
# ============================================================
class TestAISearchOverrides:
    """用户提供 overrides 时不调用模型，直接用 overrides 检索"""

    @pytest.mark.asyncio
    async def test_overrides_skip_model_call(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """overrides 提供 keyword 时跳过模型调用"""
        provider = _make_provider()
        _patch_provider(monkeypatch, provider)

        cat_lost_id = ai_search_setup["categories"]["lost"].id
        resp = await client.post(
            "/api/v1/search/ai",
            json={
                "query": "找校园卡",
                "overrides": {
                    "keyword": "校园卡",
                    "category_id": cat_lost_id,
                    "sort": "latest",
                },
            },
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        # overrides 提供 keyword → 不调用模型
        assert provider.call_count == 0
        # 仍返回结果（按 overrides 检索）
        assert len(data["items"]) > 0
        # intent 应被构造（用 query 作为 intent 文本）
        assert data["intent"] is not None
        assert data["intent"]["filters"]["keyword"] == "校园卡"
        assert data["intent"]["filters"]["category_id"] == cat_lost_id
        # 不降级
        assert data["fallback"] is False

    @pytest.mark.asyncio
    async def test_overrides_invalid_category_id_ignored(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """overrides.category_id 不属于当前学校 → 置空（不报错）"""
        provider = _make_provider()
        _patch_provider(monkeypatch, provider)

        # 用一个不存在的 category_id（其他学校的 ID 也不应被接受）
        fake_cat_id = 999999
        resp = await client.post(
            "/api/v1/search/ai",
            json={
                "query": "找校园卡",
                "overrides": {
                    "keyword": "校园卡",
                    "category_id": fake_cat_id,
                },
            },
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        # category_id 被置空
        assert data["intent"]["filters"]["category_id"] is None


# ============================================================
# 4. 白名单校验
# ============================================================
class TestAISearchWhitelist:
    """AI 解析出的分类/排序/时间/地图范围做白名单校验"""

    @pytest.mark.asyncio
    async def test_invalid_category_dropped(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """AI 返回不存在的分类名 → category_id 置空（不报错，仍返回结果）"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡", category="不存在的分类"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is False
        assert data["intent"]["filters"]["category_id"] is None
        # 仍返回匹配"校园卡"的帖子（不按分类筛选）
        post_ids = {item["id"] for item in data["items"]}
        assert ai_search_setup["posts"]["p1"].id in post_ids

    @pytest.mark.asyncio
    async def test_invalid_sort_falls_back_to_latest(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """AI 返回非法 sort → 回退 latest

        注：SEARCH_INTENT_SCHEMA 的 sort 枚举已限制为合法值，但 service 层仍做防御性校验。
        这里通过 mock 一个绕过 schema 的场景测试 service 层防御。
        """
        # 构造一个 sort 字段为非法值的响应（绕过 schema 用 dict 直接注入）
        # 实际上 schema 会拦截，所以这里测试 service 层的 _validate_intent
        from app.services.ai_search import _validate_intent
        categories = list([ai_search_setup["categories"]["lost"]])
        locations = []

        # 模拟模型返回非法 sort
        parsed = {
            "intent": "测试",
            "filters": {"keyword": "校园卡", "category": None, "sort": "invalid_sort"},
            "reasons": [],
        }
        intent = _validate_intent(parsed, categories, locations, overrides=None)
        assert intent.filters.sort == "latest"  # 回退 latest

    @pytest.mark.asyncio
    async def test_map_bounds_filter_location(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """AI 返回 map_bounds → 按坐标范围过滤地点"""
        provider = _make_provider()
        # map_bounds 覆盖 loc_a（图书馆 31.0, 120.0），不含 loc_b（食堂 31.001, 120.001）
        bounds = {"north": 31.0005, "south": 30.9995, "east": 120.0005, "west": 119.9995}
        provider.set_response(_intent_json(keyword=None, category=None, sort="latest", map_bounds=bounds))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "图书馆附近的信息"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 200
        data = resp.json()
        # 应只返回 loc_a（图书馆）的帖子
        post_ids = {item["id"] for item in data["items"]}
        setup = ai_search_setup["posts"]
        # loc_a 的帖子：p1（图书馆校园卡）、p3（图书馆读书会）、p5(已删除排除)、p6(已过期排除)、p7(pending排除)
        assert setup["p1"].id in post_ids
        assert setup["p3"].id in post_ids
        # loc_b（食堂）的帖子应被排除
        assert setup["p2"].id not in post_ids  # 食堂校园卡
        assert setup["p4"].id not in post_ids  # 食堂美食节


# ============================================================
# 5. 租户隔离
# ============================================================
class TestAISearchTenantIsolation:
    """AI 搜索三校隔离：只返回当前学校数据，不泄露其他学校"""

    @pytest_asyncio.fixture
    async def two_schools_setup(self, db_session: AsyncSession) -> dict:
        """两校夹具：每校各有自己的分类/帖子"""
        schools = {}
        for code, name in [("sch-ai-a", "A校"), ("sch-ai-b", "B校")]:
            s = await _create_school(db_session, name, code)
            await _assign_operations_subscription(db_session, s.id)
            u = await _create_user(db_session, f"{code}@example.com", name, s.id)
            await _create_membership(db_session, u.id, s.id)
            cat = await _create_category(db_session, s.id, f"{code}-cat", f"{code}-code")
            pt = await _create_post_type(db_session, f"{code}-type", f"{code}-tcode")
            loc = await _create_location(db_session, s.id, f"{code}-loc", 31.0, 120.0)
            p1 = await _create_post(
                db_session, u.id, s.id, cat.id, pt.id,
                f"{name}-校园卡帖", f"{name}校园卡内容", PostStatus.PUBLISHED,
                location_id=loc.id,
            )
            p2 = await _create_post(
                db_session, u.id, s.id, cat.id, pt.id,
                f"{name}-普通帖", f"{name}普通内容", PostStatus.PUBLISHED,
                location_id=loc.id,
            )
            schools[code] = {
                "id": s.id, "code": s.code, "name": name,
                "user_token": create_access_token(data={"sub": str(u.id)}),
                "category_id": cat.id, "post_ids": {p1.id, p2.id},
                "校园卡_post_id": p1.id,
            }
        await db_session.commit()
        return schools

    @pytest.mark.asyncio
    async def test_a_school_only_returns_a_posts(
        self, client: AsyncClient, two_schools_setup: dict, monkeypatch,
    ):
        """A 校 AI 搜索只返回 A 校帖子"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡", category=None))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school("sch-ai-a"),
        )
        assert resp.status_code == 200
        post_ids = {item["id"] for item in resp.json()["items"]}
        a_setup = two_schools_setup["sch-ai-a"]
        b_setup = two_schools_setup["sch-ai-b"]
        # 只含 A 校匹配"校园卡"的帖子
        assert a_setup["校园卡_post_id"] in post_ids
        # 不含 B 校任何帖子
        assert post_ids.isdisjoint(b_setup["post_ids"])

    @pytest.mark.asyncio
    async def test_prompt_does_not_leak_other_school_categories(
        self, client: AsyncClient, two_schools_setup: dict, monkeypatch,
    ):
        """A 校调用时提示词不含 B 校分类名"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡", category=None))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school("sch-ai-a"),
        )
        assert resp.status_code == 200
        # 检查 prompt 不含 B 校分类名
        prompt = provider.last_prompt or ""
        assert "sch-ai-b-cat" not in prompt
        assert "sch-ai-a-cat" in prompt


# ============================================================
# 6. 确定性打分
# ============================================================
class TestAISearchDeterministicScoring:
    """相同输入产生相同分数与顺序"""

    @pytest.mark.asyncio
    async def test_same_input_same_order(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """两次相同调用 → 相同的分数与顺序"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡", sort="relevance"))
        _patch_provider(monkeypatch, provider)

        resp1 = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        # 重置 provider 以便第二次调用
        provider2 = _make_provider()
        provider2.set_response(_intent_json(keyword="校园卡", sort="relevance"))
        _patch_provider(monkeypatch, provider2)

        resp2 = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        items1 = resp1.json()["items"]
        items2 = resp2.json()["items"]
        scores1 = resp1.json()["scores"]
        scores2 = resp2.json()["scores"]

        # 相同顺序
        assert [i["id"] for i in items1] == [i["id"] for i in items2]
        # 相同分数
        for pid in scores1:
            assert scores1[pid] == scores2[pid]

    @pytest.mark.asyncio
    async def test_score_in_unit_range(
        self, client: AsyncClient, ai_search_setup: dict, monkeypatch,
    ):
        """分数在 [0, 1] 区间"""
        provider = _make_provider()
        provider.set_response(_intent_json(keyword="校园卡"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "找校园卡"},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        scores = resp.json()["scores"]
        for pid_str, score in scores.items():
            assert 0.0 <= score <= 1.0, f"score {score} 不在 [0,1]"


# ============================================================
# 7. 输入校验
# ============================================================
class TestAISearchInputValidation:
    """请求体校验"""

    @pytest.mark.asyncio
    async def test_empty_query_rejected(
        self, client: AsyncClient, ai_search_setup: dict,
    ):
        """空 query 返回 422"""
        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": ""},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_query_too_long_rejected(
        self, client: AsyncClient, ai_search_setup: dict,
    ):
        """超长 query（>200）返回 422"""
        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "x" * 201},
            headers=_school(ai_search_setup["school"]["code"]),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_school_code_rejected(
        self, client: AsyncClient, ai_search_setup: dict,
    ):
        """游客未提供 X-School-Code → 404（不泄露学校列表）"""
        resp = await client.post(
            "/api/v1/search/ai",
            json={"query": "校园卡"},
        )
        assert resp.status_code == 404
