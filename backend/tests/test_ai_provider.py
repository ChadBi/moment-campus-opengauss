"""AI-01.2 + AI-01.3: AI 调用服务集成测试（依赖数据库）。

覆盖：
- invoke_ai 成功/失败均记录 ai_invocation_logs
- 隐私约束：日志不保存完整 prompt，仅保存长度与哈希
- 超时 / 429 / 余额不足 / JSON 解析失败 / 熔断 降级并落库
- 三校隔离：school_id 强制来自 TenantContext，不接受外部传入
- update_invocation_result 补充结果数

注：Provider 单元测试见 test_ai_provider_unit.py。
"""
import inspect
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import (
    AIInsufficientQuotaError,
    AINetworkError,
    AIRateLimitError,
)
from app.ai.provider import CircuitBreaker, MockAIProvider
from app.ai.schemas import SEARCH_INTENT_SCHEMA
from app.ai.service import invoke_ai, update_invocation_result
from app.core.security import get_password_hash
from app.core.tenant import TenantContext
from app.models.ai_invocation_log import AIInvocationLog
from app.models.school import School
from app.models.user import User


# ============================================================
# 辅助
# ============================================================
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


def _valid_intent_json() -> str:
    return json.dumps(
        {
            "intent": "查找校园卡",
            "filters": {
                "keyword": "校园卡",
                "category": "失物招领",
                "sort": "latest",
                "date_from": None,
                "date_to": None,
            },
            "reasons": ["按最新排序"],
        },
        ensure_ascii=False,
    )


def _guest_tenant(school_id: int, school_code: str) -> TenantContext:
    return TenantContext(
        school_id=school_id,
        school_code=school_code,
        user=None,
        effective_role="guest",
        is_guest=True,
    )


# ============================================================
# 1. 成功调用 + 日志记录
# ============================================================
class TestInvokeAILogging:
    async def test_invoke_success_logs_record(
        self, db_session: AsyncSession, test_school: dict,
    ):
        provider = _make_provider()
        provider.set_response(_valid_intent_json())
        tenant = _guest_tenant(test_school["id"], test_school["code"])
        outcome = await invoke_ai(
            prompt="找校园卡",
            schema=SEARCH_INTENT_SCHEMA,
            scene="search_intent",
            tenant=tenant,
            db=db_session,
            trace_id="trace-1",
            provider=provider,
        )
        assert outcome.fallback is False
        assert outcome.response is not None
        assert outcome.response.parsed["intent"] == "查找校园卡"
        assert outcome.log_id is not None

        log = await db_session.get(AIInvocationLog, outcome.log_id)
        assert log is not None
        assert log.school_id == test_school["id"]
        assert log.user_id is None  # 游客
        assert log.scene == "search_intent"
        assert log.output_status == "success"
        assert log.model == "mock-model"
        assert log.provider == "mock"
        assert log.trace_id == "trace-1"
        assert log.fallback_reason is None

    async def test_invoke_logs_no_full_prompt_only_length_and_hash(
        self, db_session: AsyncSession, test_school: dict,
    ):
        """隐私约束：日志不保存完整 prompt，仅保存长度与哈希。"""
        provider = _make_provider()
        provider.set_response(_valid_intent_json())
        tenant = _guest_tenant(test_school["id"], test_school["code"])
        prompt = "这是一段包含敏感信息的搜索词：校园卡丢失"
        outcome = await invoke_ai(
            prompt=prompt,
            schema=SEARCH_INTENT_SCHEMA,
            scene="search_intent",
            tenant=tenant,
            db=db_session,
            provider=provider,
        )
        log = await db_session.get(AIInvocationLog, outcome.log_id)
        assert log.input_length == len(prompt)
        # input_hash 是 64 位 SHA-256
        assert log.input_hash is not None
        assert len(log.input_hash) == 64
        # 确保日志对象没有保存完整 prompt 字段（模型无此字段）
        assert not hasattr(log, "prompt")
        assert not hasattr(log, "input_text")


# ============================================================
# 2. 各类故障降级并落库
# ============================================================
class TestInvokeFallbackLogging:
    async def test_invoke_timeout_fallback_logs(
        self, db_session: AsyncSession, test_school: dict,
    ):
        provider = _make_provider(timeout=0.05, max_retries=0)
        provider.set_delay(0.3)
        tenant = _guest_tenant(test_school["id"], test_school["code"])
        outcome = await invoke_ai(
            prompt="x", schema=None, scene="search_intent",
            tenant=tenant, db=db_session, provider=provider,
        )
        assert outcome.fallback is True
        assert outcome.response is None
        assert outcome.output_status == "timeout"
        assert "降级" in outcome.fallback_reason

        log = await db_session.get(AIInvocationLog, outcome.log_id)
        assert log.output_status == "timeout"
        assert log.fallback_reason is not None

    async def test_invoke_rate_limit_fallback_logs(
        self, db_session: AsyncSession, test_school: dict,
    ):
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AIRateLimitError("429"))
        tenant = _guest_tenant(test_school["id"], test_school["code"])
        outcome = await invoke_ai(
            prompt="x", schema=None, scene="search_intent",
            tenant=tenant, db=db_session, provider=provider,
        )
        assert outcome.fallback is True
        assert outcome.output_status == "rate_limit"

    async def test_invoke_insufficient_quota_fallback_logs(
        self, db_session: AsyncSession, test_school: dict,
    ):
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AIInsufficientQuotaError("no quota"))
        tenant = _guest_tenant(test_school["id"], test_school["code"])
        outcome = await invoke_ai(
            prompt="x", schema=None, scene="search_intent",
            tenant=tenant, db=db_session, provider=provider,
        )
        assert outcome.fallback is True
        assert outcome.output_status == "insufficient_quota"

    async def test_invoke_json_parse_fail_fallback_logs(
        self, db_session: AsyncSession, test_school: dict,
    ):
        provider = _make_provider()
        provider.set_response("not json")
        tenant = _guest_tenant(test_school["id"], test_school["code"])
        outcome = await invoke_ai(
            prompt="x", schema=SEARCH_INTENT_SCHEMA, scene="search_intent",
            tenant=tenant, db=db_session, provider=provider,
        )
        assert outcome.fallback is True
        assert outcome.output_status == "json_parse_error"

    async def test_invoke_circuit_breaker_fallback_logs(
        self, db_session: AsyncSession, test_school: dict,
    ):
        provider = _make_provider(failure_threshold=2, max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("err"))
        tenant = _guest_tenant(test_school["id"], test_school["code"])
        # 前 2 次失败触发熔断
        for _ in range(2):
            await invoke_ai(
                prompt="x", schema=None, scene="search_intent",
                tenant=tenant, db=db_session, provider=provider,
            )
        # 第 3 次被熔断
        outcome = await invoke_ai(
            prompt="x", schema=None, scene="search_intent",
            tenant=tenant, db=db_session, provider=provider,
        )
        assert outcome.fallback is True
        assert outcome.output_status == "circuit_breaker"


# ============================================================
# 3. 三校隔离
# ============================================================
class TestTenantIsolation:
    async def test_school_id_not_in_signature(self):
        """invoke_ai 签名不接受 school_id 参数；school_id 强制取自 tenant。"""
        sig = inspect.signature(invoke_ai)
        assert "school_id" not in sig.parameters

    async def test_two_schools_logs_isolated(
        self, db_session: AsyncSession,
    ):
        """A 校调用只记 A 校日志，B 校调用只记 B 校日志。"""
        school_a = School(name="甲校", code="school-a", is_active=True)
        school_b = School(name="乙校", code="school-b", is_active=True)
        db_session.add_all([school_a, school_b])
        await db_session.commit()
        await db_session.refresh(school_a)
        await db_session.refresh(school_b)

        provider = _make_provider()
        provider.set_response(_valid_intent_json())

        outcome_a = await invoke_ai(
            prompt="甲校搜索", schema=SEARCH_INTENT_SCHEMA, scene="search_intent",
            tenant=_guest_tenant(school_a.id, school_a.code),
            db=db_session, trace_id="ta", provider=provider,
        )
        outcome_b = await invoke_ai(
            prompt="乙校搜索", schema=SEARCH_INTENT_SCHEMA, scene="search_intent",
            tenant=_guest_tenant(school_b.id, school_b.code),
            db=db_session, trace_id="tb", provider=provider,
        )

        log_a = await db_session.get(AIInvocationLog, outcome_a.log_id)
        log_b = await db_session.get(AIInvocationLog, outcome_b.log_id)
        assert log_a.school_id == school_a.id
        assert log_b.school_id == school_b.id
        assert log_a.school_id != log_b.school_id
        assert log_a.trace_id == "ta"
        assert log_b.trace_id == "tb"

        # 查询 A 校日志，不应包含 B 校记录
        result = await db_session.execute(
            select(AIInvocationLog).where(AIInvocationLog.school_id == school_a.id)
        )
        a_logs = result.scalars().all()
        assert len(a_logs) == 1
        assert a_logs[0].trace_id == "ta"

    async def test_user_id_recorded_for_logged_in_user(
        self, db_session: AsyncSession, test_school: dict,
    ):
        """登录用户调用 AI 时 user_id 正确记录（直接构造 User，避免 client fixture 链）。"""
        user = User(
            email="ai_test_user@example.com",
            nickname="AI测试用户",
            password_hash=get_password_hash("pass123"),
            school_id=test_school["id"],
            role="user",
            is_active=True,
            is_deleted=False,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        provider = _make_provider()
        provider.set_response(_valid_intent_json())
        tenant = TenantContext(
            school_id=test_school["id"],
            school_code=test_school["code"],
            user=user,
            effective_role="user",
            is_guest=False,
        )
        outcome = await invoke_ai(
            prompt="x", schema=SEARCH_INTENT_SCHEMA, scene="search_intent",
            tenant=tenant, db=db_session, provider=provider,
        )
        log = await db_session.get(AIInvocationLog, outcome.log_id)
        assert log.user_id == user.id


# ============================================================
# 4. update_invocation_result 补充结果数
# ============================================================
class TestUpdateInvocationResult:
    async def test_update_result_counts(
        self, db_session: AsyncSession, test_school: dict,
    ):
        provider = _make_provider()
        provider.set_response(_valid_intent_json())
        tenant = _guest_tenant(test_school["id"], test_school["code"])
        outcome = await invoke_ai(
            prompt="x", schema=SEARCH_INTENT_SCHEMA, scene="search_intent",
            tenant=tenant, db=db_session, provider=provider,
        )
        await update_invocation_result(
            db_session, outcome.log_id,
            candidate_count=42, result_count=10,
        )
        log = await db_session.get(AIInvocationLog, outcome.log_id)
        assert log.candidate_count == 42
        assert log.result_count == 10
