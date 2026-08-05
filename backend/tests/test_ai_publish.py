"""AI-03: AI 辅助发布建议测试

覆盖：
- AI-03.1: POST /api/v1/posts/ai-suggest 接口
    - 成功：返回结构化建议（标题/摘要/分类/默认信息截止天数）+ 遗漏信息 + 敏感提醒
    - 不修改原文：响应只返回建议，不修改 Post 任何字段
    - 失败不阻塞：Provider 异常 / JSON 解析失败 / 输入过短 → fallback=true，仍返回敏感检测
    - 白名单：分类必须来自当前学校，非法值丢弃
- AI-03.2: 三校隔离：分类/信息截止天数来自当前学校，不引用其他学校数据
- 敏感信息检测：手机/邮箱/身份证/银行卡/QQ 命中
- 日志：ai_invocation_logs 成功/失败均记录

Task 1.3 调整：Tag 模型已删除，标签相关测试已跳过或调整为期望空 tags 列表
"""
import json
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import AINetworkError
from app.ai.provider import CircuitBreaker, MockAIProvider
from app.core.security import create_access_token, get_password_hash
from app.models.ai_invocation_log import AIInvocationLog
from app.models.category import Category
from app.models.location import Location
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
        campus_verified=True,  # D4 门禁：默认已认证
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


async def _create_category(
    db: AsyncSession,
    school_id: int,
    name: str,
    code: str,
    default_validity_days: int = 30,
) -> Category:
    c = Category(
        school_id=school_id, name=name, code=code, icon="🔍",
        default_validity_days=default_validity_days, is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


async def _create_location(
    db: AsyncSession, school_id: int, name: str, lat: float, lng: float
) -> Location:
    loc = Location(school_id=school_id, name=name, latitude=lat, longitude=lng, is_verified=True)
    db.add(loc)
    await db.flush()
    return loc


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


def _suggestion_json(
    *,
    title: str | None = None,
    summary: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    default_validity_days: int | None = None,
    missing_info: list[str] | None = None,
    sensitive_warnings: list[str] | None = None,
) -> str:
    """构造合法的 PUBLISH_SUGGESTION_SCHEMA JSON 串。"""
    return json.dumps(
        {
            "suggestions": {
                "title": title,
                "summary": summary,
                "category": category,
                "tags": tags or [],
                "default_validity_days": default_validity_days,
            },
            "missing_info": missing_info or [],
            "sensitive_warnings": sensitive_warnings or [],
        },
        ensure_ascii=False,
    )


# ============================================================
# 测试夹具：AI 发布建议场景
# ============================================================
@pytest_asyncio.fixture
async def ai_publish_setup(db_session: AsyncSession) -> dict:
    """AI 发布建议测试夹具：单校多分类/地点

    提供：
    - 一个学校 + operations 订阅 + 用户 + membership
    - 2 个分类（失物招领 / 活动），各自有不同默认信息截止天数
    - 1 个地点
    - 用户 token

    Task 1.3 调整：Tag 模型已删除，不再创建标签
    """
    school = await _create_school(db_session, "AI发布建议测试大学", "ai-pub")
    await _assign_operations_subscription(db_session, school.id)

    user = await _create_user(db_session, "aipubuser@example.com", "AI发布用户", school.id)
    await _create_membership(db_session, user.id, school.id)

    cat_lost = await _create_category(
        db_session, school.id, "失物招领", "lost-found", default_validity_days=14,
    )
    cat_event = await _create_category(
        db_session, school.id, "活动", "event", default_validity_days=7,
    )
    loc_library = await _create_location(db_session, school.id, "图书馆", 31.0, 120.0)

    await db_session.commit()

    return {
        "school": {"id": school.id, "code": school.code, "name": school.name},
        "user": {"id": user.id, "token": create_access_token(data={"sub": str(user.id)})},
        "categories": {"lost": cat_lost, "event": cat_event},
        "location": loc_library,
    }


@pytest_asyncio.fixture
async def two_schools_publish_setup(db_session: AsyncSession) -> dict:
    """两校夹具：每校有自己的分类/地点

    用于测试三校隔离：A 校的 AI 建议不应引用 B 校的分类。

    Task 1.3 调整：Tag 模型已删除，不再创建标签
    """
    schools = {}
    for code, name in [("pub-a", "A校"), ("pub-b", "B校")]:
        s = await _create_school(db_session, name, code)
        await _assign_operations_subscription(db_session, s.id)
        u = await _create_user(db_session, f"{code}@example.com", name, s.id)
        await _create_membership(db_session, u.id, s.id)
        cat = await _create_category(
            db_session, s.id, f"{code}-分类", f"{code}-code", default_validity_days=10,
        )
        loc = await _create_location(db_session, s.id, f"{code}-loc", 31.0, 120.0)
        await db_session.flush()
        schools[code] = {
            "id": s.id, "code": s.code, "name": name,
            "user_token": create_access_token(data={"sub": str(u.id)}),
            "category_id": cat.id, "category_name": cat.name,
            "location_id": loc.id,
        }
    await db_session.commit()
    return schools


def _patch_provider(monkeypatch, provider: MockAIProvider) -> None:
    """Patch get_provider in app.ai.service to return the given provider."""
    async def _mock_get_provider():
        return provider
    monkeypatch.setattr("app.ai.service.get_provider", _mock_get_provider)


# ============================================================
# 1. 成功场景
# ============================================================
class TestAIPublishSuggestSuccess:
    """AI 发布建议成功：返回结构化建议 + 遗漏 + 敏感"""

    @pytest.mark.asyncio
    async def test_returns_structured_suggestions(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """成功调用：返回 suggestions / missing_info / sensitive_warnings"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(
            title="校园卡丢失求助",
            summary="在图书馆丢失校园卡，请拾到者联系",
            category="失物招领",
            tags=["校园卡", "招领"],
            default_validity_days=14,
            missing_info=["建议补充丢失时间"],
            sensitive_warnings=[],
        ))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "校园卡丢了",
                "content": "今天在图书馆丢失校园卡一张，请拾到者联系",
                "category_id": ai_publish_setup["categories"]["lost"].id,
                "location_id": ai_publish_setup["location"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is False
        assert data["fallback_reason"] is None
        # suggestions 结构完整
        sug = data["suggestions"]
        assert sug is not None
        assert sug["title"] == "校园卡丢失求助"
        assert sug["summary"] == "在图书馆丢失校园卡，请拾到者联系"
        # category 白名单校验后保留 category_id
        assert sug["category"] == "失物招领"
        assert sug["category_id"] == ai_publish_setup["categories"]["lost"].id
        # Task 1.3 调整：Tag 模型已删除，tags 始终为空列表
        assert sug["tags"] == []
        # default_validity_days 来自模型输出
        assert sug["default_validity_days"] == 14
        # missing_info 合并模型输出
        assert any("丢失时间" in m for m in data["missing_info"])
        # sensitive_warnings 为空（无敏感信息）
        assert data["sensitive_warnings"] == []
        # ai_log_id 不为空
        assert data["ai_log_id"] is not None

    @pytest.mark.asyncio
    async def test_validity_falls_back_to_category_default(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """模型未给 default_validity_days → 回退到当前已选分类的默认信息截止天数"""
        provider = _make_provider()
        # 模型不返回 default_validity_days（null）
        provider.set_response(_suggestion_json(
            title=None, summary="测试摘要", category=None, tags=[],
            default_validity_days=None,
        ))
        _patch_provider(monkeypatch, provider)

        cat_lost = ai_publish_setup["categories"]["lost"]
        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": cat_lost.id,
                "location_id": ai_publish_setup["location"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        # 默认信息截止天数应回退到 cat_lost.default_validity_days = 14
        assert resp.json()["suggestions"]["default_validity_days"] == cat_lost.default_validity_days

    @pytest.mark.asyncio
    async def test_logs_invocation_on_success(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch, db_session: AsyncSession,
    ):
        """成功调用记录 ai_invocation_logs（output_status=success）"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
                "location_id": ai_publish_setup["location"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        log_id = resp.json()["ai_log_id"]
        assert log_id is not None

        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.school_id == ai_publish_setup["school"]["id"]
        assert log.scene == "publish_suggestion"
        assert log.output_status == "success"
        # 隐私约束：不保存完整 prompt
        assert not hasattr(log, "prompt")
        assert log.result_count is not None
        assert log.result_count > 0


# ============================================================
# 2. 降级场景
# ============================================================
class TestAIPublishSuggestFallback:
    """AI 发布建议降级：任一步失败 → fallback=true，仍返回敏感检测"""

    @pytest.mark.asyncio
    async def test_fallback_on_provider_network_error(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """Provider 网络错误 → fallback=true，仍返回敏感检测/缺失提示"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("network down"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert data["fallback_reason"] is not None
        assert "降级" in data["fallback_reason"] or "不可用" in data["fallback_reason"]
        # 仍返回 missing_info（确定性，不依赖模型）
        assert isinstance(data["missing_info"], list)
        # suggestions 为空（降级）
        assert data["suggestions"] is None

    @pytest.mark.asyncio
    async def test_fallback_on_provider_timeout(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """Provider 超时 → fallback=true"""
        provider = _make_provider(timeout=0.05, max_retries=0)
        provider.set_delay(0.3)
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert "超时" in data["fallback_reason"] or "降级" in data["fallback_reason"]

    @pytest.mark.asyncio
    async def test_fallback_on_json_parse_error(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """模型返回非 JSON → fallback=true"""
        provider = _make_provider()
        provider.set_response("这不是合法 JSON")
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert "解析失败" in data["fallback_reason"] or "降级" in data["fallback_reason"]

    @pytest.mark.asyncio
    async def test_fallback_on_input_too_short(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """标题 + 正文都过短 → fallback=true，不调用模型"""
        provider = _make_provider()
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "ab",  # <3
                "content": "cd",  # <5
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True
        assert "过短" in data["fallback_reason"]
        # 不应调用模型
        assert provider.call_count == 0
        # 仍返回 missing_info（确定性）
        assert isinstance(data["missing_info"], list)
        assert len(data["missing_info"]) > 0

    @pytest.mark.asyncio
    async def test_fallback_logs_failure_status(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch, db_session: AsyncSession,
    ):
        """降级时仍记录 ai_invocation_logs（output_status != success）"""
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("err"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        log_id = resp.json()["ai_log_id"]
        assert log_id is not None

        log = await db_session.get(AIInvocationLog, log_id)
        assert log is not None
        assert log.output_status == "network_error"
        assert log.fallback_reason is not None


# ============================================================
# 3. 敏感信息检测（确定性，不依赖模型）
# ============================================================
class TestAIPublishSensitiveDetection:
    """敏感信息检测：手机/邮箱/身份证/银行卡/QQ"""

    @pytest.mark.asyncio
    async def test_detect_phone_number(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """正文含手机号 → sensitive_warnings 含手机类型"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "我的手机号是 13800138000，请联系我",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # sensitive_warnings 含手机相关
        assert any("手机" in w or "电话" in w for w in data["sensitive_warnings"])
        # sensitive_findings 含 phone 类型
        assert "phone" in data["sensitive_findings"]
        assert "13800138000" in data["sensitive_findings"]["phone"]

    @pytest.mark.asyncio
    async def test_detect_email(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """正文含邮箱 → sensitive_warnings 含邮箱类型"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "联系邮箱 test@example.com 请发邮件",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any("邮箱" in w for w in data["sensitive_warnings"])
        assert "email" in data["sensitive_findings"]
        assert "test@example.com" in data["sensitive_findings"]["email"]

    @pytest.mark.asyncio
    async def test_detect_id_card(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """正文含身份证号 → sensitive_warnings 含身份证类型"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "身份证号 110101199001011234 请核对",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any("身份证" in w for w in data["sensitive_warnings"])
        assert "id_card" in data["sensitive_findings"]

    @pytest.mark.asyncio
    async def test_sensitive_detection_works_without_model(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """输入过短降级时，敏感检测仍生效（不依赖模型）"""
        provider = _make_provider()
        _patch_provider(monkeypatch, provider)

        # 即使标题正文短，但联系方式中含手机号也应被检测
        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "ab",
                "content": "cd",
                "contact_info": "13800138000",
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # 降级（输入过短）
        assert data["fallback"] is True
        # 仍检测到手机号
        assert any("手机" in w or "电话" in w for w in data["sensitive_warnings"])
        assert "phone" in data["sensitive_findings"]


# ============================================================
# 4. 白名单校验（AI-03.2）
# ============================================================
class TestAIPublishWhitelist:
    """AI 解析出的分类/标签做白名单校验：非法值丢弃，不报错"""

    @pytest.mark.asyncio
    async def test_invalid_category_dropped(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """AI 返回不存在的分类名 → category_id 置空（不报错，仍返回结果）"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(
            summary="ok", category="不存在的分类", tags=["校园卡"],
        ))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # 分类被丢弃
        assert data["suggestions"]["category"] is None
        assert data["suggestions"]["category_id"] is None
        # Task 1.3 调整：Tag 模型已删除，tags 始终为空列表
        assert data["suggestions"]["tags"] == []

    @pytest.mark.asyncio
    async def test_validity_days_out_of_range_falls_back(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """default_validity_days 超出 1-365 → 回退到当前分类默认值"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(
            summary="ok", default_validity_days=99999,  # 超出范围
        ))
        _patch_provider(monkeypatch, provider)

        cat_lost = ai_publish_setup["categories"]["lost"]
        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": cat_lost.id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        # 超出范围 → 回退到 cat_lost.default_validity_days = 14
        assert resp.json()["suggestions"]["default_validity_days"] == cat_lost.default_validity_days


# ============================================================
# 5. 租户隔离（AI-03.2）
# ============================================================
class TestAIPublishTenantIsolation:
    """AI-03.2: 三校隔离：分类/标签/信息截止天数来自当前学校"""

    @pytest.mark.asyncio
    async def test_prompt_does_not_leak_other_school_categories(
        self, client: AsyncClient, two_schools_publish_setup: dict, monkeypatch,
    ):
        """A 校调用时提示词不含 B 校分类名"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        a_setup = two_schools_publish_setup["pub-a"]
        b_setup = two_schools_publish_setup["pub-b"]
        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": a_setup["category_id"],
            },
            headers={
                **_school(a_setup["code"]),
                **_auth(a_setup["user_token"]),
            },
        )
        assert resp.status_code == 200
        prompt = provider.last_prompt or ""
        # 提示词含 A 校分类
        assert a_setup["category_name"] in prompt
        # 提示词不含 B 校分类
        assert b_setup["category_name"] not in prompt
        # Task 1.3 调整：Tag 模型已删除，不再校验提示词是否含 B 校标签

    @pytest.mark.asyncio
    async def test_b_school_category_dropped_in_a_school(
        self, client: AsyncClient, two_schools_publish_setup: dict, monkeypatch,
    ):
        """A 校调用，模型返回 B 校分类名 → category_id 置空"""
        provider = _make_provider()
        a_setup = two_schools_publish_setup["pub-a"]
        b_setup = two_schools_publish_setup["pub-b"]
        # 让模型"误报" B 校分类
        provider.set_response(_suggestion_json(summary="ok", category=b_setup["category_name"]))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": a_setup["category_id"],
            },
            headers={
                **_school(a_setup["code"]),
                **_auth(a_setup["user_token"]),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # B 校分类不在 A 校白名单 → 丢弃
        assert data["suggestions"]["category"] is None
        assert data["suggestions"]["category_id"] is None

# ============================================================
# 6. 鉴权与输入校验
# ============================================================
class TestAIPublishAuthAndValidation:
    """鉴权与请求体校验"""

    @pytest.mark.asyncio
    async def test_unauthenticated_rejected(
        self, client: AsyncClient, ai_publish_setup: dict,
    ):
        """未登录访问 → 401"""
        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={"title": "测试", "content": "测试内容"},
            headers=_school(ai_publish_setup["school"]["code"]),
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_school_code_uses_user_default_school(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """登录用户未提供 X-School-Code → 使用用户默认学校（仍可调用）

        注：与 AI 搜索不同（搜索允许游客，缺 X-School-Code 必 404），
        AI 发布建议要求登录，登录用户已有默认学校，缺 X-School-Code 时使用默认学校。
        """
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers=_auth(ai_publish_setup["user"]["token"]),
        )
        # 用户已登录，使用其默认学校
        assert resp.status_code == 200
        assert resp.json()["fallback"] is False

    @pytest.mark.asyncio
    async def test_title_too_long_rejected(
        self, client: AsyncClient, ai_publish_setup: dict,
    ):
        """超长 title（>200）→ 422"""
        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={"title": "x" * 201, "content": "测试内容"},
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_content_too_long_rejected(
        self, client: AsyncClient, ai_publish_setup: dict,
    ):
        """超长 content（>5000）→ 422"""
        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={"title": "测试", "content": "x" * 5001},
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 422


# ============================================================
# 7. 缺失字段检测（确定性，不依赖模型）
# ============================================================
class TestAIPublishMissingInfo:
    """缺失字段检测：根据草稿字段空缺情况生成提示"""

    @pytest.mark.asyncio
    async def test_missing_title_hint(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """标题为空 → missing_info 含标题提示"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        missing = resp.json()["missing_info"]
        assert any("标题" in m for m in missing)

    @pytest.mark.asyncio
    async def test_missing_category_hint(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """未选分类 → missing_info 含分类提示"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                # 不传 category_id
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        missing = resp.json()["missing_info"]
        assert any("分类" in m for m in missing)

    @pytest.mark.asyncio
    async def test_missing_expire_hint(
        self, client: AsyncClient, ai_publish_setup: dict, monkeypatch,
    ):
        """未设置信息截止时间 → missing_info 含信息截止时间提示"""
        provider = _make_provider()
        provider.set_response(_suggestion_json(summary="ok"))
        _patch_provider(monkeypatch, provider)

        resp = await client.post(
            "/api/v1/posts/ai-suggest",
            json={
                "title": "测试标题足够长",
                "content": "测试正文内容足够长，方便 AI 给出建议",
                "category_id": ai_publish_setup["categories"]["lost"].id,
                # 不传 expire_at
            },
            headers={
                **_school(ai_publish_setup["school"]["code"]),
                **_auth(ai_publish_setup["user"]["token"]),
            },
        )
        assert resp.status_code == 200
        missing = resp.json()["missing_info"]
        assert any("信息截止时间" in m for m in missing)
