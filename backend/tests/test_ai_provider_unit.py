"""AI-01: Provider 适配层单元测试（不依赖数据库）。

覆盖 Provider 自身逻辑：
- Mock Provider 正常调用 + 结构化输出
- JSON 解析失败 / Schema 校验失败
- 超时 / 429 / 余额不足 / 网络错误 降级
- 重试（指数退避，可重试错误重试后成功 / 余额不足不重试）
- 熔断机制（达阈值熔断 / 超时后半开恢复）

本文件覆盖 conftest 的 setup_database fixture 为 no-op，
因为这些测试不操作数据库，避免触发 openGauss TRUNCATE 偶发可见性问题。
"""
import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.ai.exceptions import (
    AICircuitBreakerOpenError,
    AIInsufficientQuotaError,
    AIJSONParseError,
    AINetworkError,
    AIRateLimitError,
    AITimeoutError,
)
from app.ai.provider import (
    AIInvokeOptions,
    CircuitBreaker,
    MockAIProvider,
    OpenAIProvider,
)
from app.ai.schemas import SEARCH_INTENT_SCHEMA, validate_structured_output


# ============================================================
# 覆盖 conftest.setup_database：单元测试不操作 DB，跳过 TRUNCATE
# ============================================================
@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """no-op：本文件全部为 Provider 单元测试，不接触数据库。"""
    yield


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


class _FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self.response


class _FakeOpenAIClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_FakeCompletions(response))


def _openai_response(
    content: str = '{"ok": true}',
    *,
    reasoning_content: str = "",
    finish_reason: str = "stop",
    reasoning_tokens: int = 0,
):
    return SimpleNamespace(
        id="resp-test-1",
        choices=[SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(
                content=content,
                reasoning_content=reasoning_content,
            ),
        )],
        usage=SimpleNamespace(
            prompt_tokens=12,
            completion_tokens=max(reasoning_tokens, 4),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens),
        ),
    )


def _make_openai_provider(model: str, api_base: str, response) -> tuple[OpenAIProvider, _FakeOpenAIClient]:
    provider = OpenAIProvider(
        api_key="test-key",
        model=model,
        timeout=15.0,
        max_tokens=1024,
        max_retries=0,
        circuit=CircuitBreaker(failure_threshold=5, reset_seconds=60),
        api_base=api_base,
    )
    client = _FakeOpenAIClient(response)
    provider._client = client
    return provider, client


# ============================================================
# 1. Mock Provider 正常调用 + 结构化输出
# ============================================================
class TestMockProviderNormal:
    async def test_mock_normal_call_returns_parsed(self):
        provider = _make_provider()
        provider.set_response(_valid_intent_json())
        resp = await provider.complete("找校园卡", schema=SEARCH_INTENT_SCHEMA)
        assert resp.provider == "mock"
        assert resp.parsed is not None
        assert resp.parsed["intent"] == "查找校园卡"
        assert resp.parsed["filters"]["keyword"] == "校园卡"
        assert resp.output_status == "success"
        assert resp.latency_ms >= 0
        assert provider.call_count == 1

    async def test_mock_call_without_schema_returns_no_parsed(self):
        provider = _make_provider()
        provider.set_response("普通文本回复")
        resp = await provider.complete("hello", schema=None)
        assert resp.parsed is None
        assert resp.content == "普通文本回复"

    async def test_structured_output_validation_success(self):
        data = {"intent": "x", "filters": {"keyword": None, "category": None,
                "sort": None, "date_from": None, "date_to": None}, "reasons": None}
        out = validate_structured_output(data, SEARCH_INTENT_SCHEMA)
        assert out == data

    async def test_structured_output_strips_unknown_fields_recursively(self):
        data = {
            "intent": "x",
            "filters": {
                "keyword": None,
                "category": None,
                "sort": None,
                "date_from": None,
                "date_to": None,
                "unexpected_nested": "drop-me",
            },
            "reasons": None,
            "unexpected_top": {"echo": "drop-me"},
        }
        out = validate_structured_output(data, SEARCH_INTENT_SCHEMA)
        assert "unexpected_top" not in out
        assert "unexpected_nested" not in out["filters"]

    async def test_structured_output_schema_fail(self):
        # 缺少 required 字段 filters → Schema 校验失败
        bad_data = {"intent": "x"}
        with pytest.raises(AIJSONParseError):
            validate_structured_output(bad_data, SEARCH_INTENT_SCHEMA)

    async def test_structured_output_wrong_enum_fail(self):
        bad_data = {
            "intent": "x",
            "filters": {"keyword": None, "category": None,
                        "sort": "invalid_sort", "date_from": None, "date_to": None},
            "reasons": None,
        }
        with pytest.raises(AIJSONParseError):
            validate_structured_output(bad_data, SEARCH_INTENT_SCHEMA)


# ============================================================
# 2. JSON 解析失败降级
# ============================================================
class TestJSONParseFailure:
    async def test_json_parse_fail_raises(self):
        provider = _make_provider()
        provider.set_response("这不是 JSON")
        with pytest.raises(AIJSONParseError):
            await provider.complete("x", schema=SEARCH_INTENT_SCHEMA)

    async def test_json_block_extract_success(self):
        # 模型把 JSON 包在 ```json 代码块里也能解析
        provider = _make_provider()
        provider.set_response(f"解释文字\n```json\n{_valid_intent_json()}\n```\n结尾")
        resp = await provider.complete("x", schema=SEARCH_INTENT_SCHEMA)
        assert resp.parsed is not None
        assert resp.parsed["intent"] == "查找校园卡"


# ============================================================
# 3. 超时降级
# ============================================================
class TestTimeoutFallback:
    async def test_timeout_raises_timeout_error(self):
        provider = _make_provider(timeout=0.05, max_retries=0)
        provider.set_delay(0.3)  # 慢响应，超过 0.05s timeout
        with pytest.raises(AITimeoutError):
            await provider.complete("x", schema=SEARCH_INTENT_SCHEMA)

    async def test_timeout_records_circuit_failure(self):
        # 超时是可重试错误，max_retries=0 时直接 record_failure
        provider = _make_provider(timeout=0.05, max_retries=0)
        provider.set_delay(0.3)
        with pytest.raises(AITimeoutError):
            await provider.complete("x", schema=None)
        assert provider.circuit.failures == 1


# ============================================================
# 4. 429 / 余额不足 / 网络错误 降级
# ============================================================
class TestErrorClassification:
    async def test_rate_limit_429_fallback(self):
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AIRateLimitError("429"))
        with pytest.raises(AIRateLimitError):
            await provider.complete("x", schema=None)
        assert provider.circuit.failures == 1

    async def test_insufficient_quota_fallback(self):
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AIInsufficientQuotaError("no quota"))
        with pytest.raises(AIInsufficientQuotaError):
            await provider.complete("x", schema=None)

    async def test_network_error_fallback(self):
        provider = _make_provider(max_retries=0)
        provider.set_exception_factory(lambda: AINetworkError("conn refused"))
        with pytest.raises(AINetworkError):
            await provider.complete("x", schema=None)

    async def test_insufficient_quota_not_retried(self):
        # 余额不足不可重试：max_retries=3 时仍只调用一次
        provider = _make_provider(max_retries=3)
        provider.set_exception_factory(lambda: AIInsufficientQuotaError("no quota"))
        with pytest.raises(AIInsufficientQuotaError):
            await provider.complete("x", schema=None)
        assert provider.call_count == 1  # 未重试


# ============================================================
# 5. 重试（指数退避）
# ============================================================
class TestRetry:
    async def test_retry_then_success(self, monkeypatch):
        # 加速：patch provider 模块的 asyncio.sleep 为 noop
        async def _noop_sleep(_):
            return None
        monkeypatch.setattr("app.ai.provider.asyncio.sleep", _noop_sleep)

        provider = _make_provider(max_retries=3)
        state = {"n": 0}

        def factory():
            state["n"] += 1
            if state["n"] < 3:
                return AINetworkError("transient")
            return None  # 第 3 次成功

        provider.set_exception_factory(factory)
        resp = await provider.complete("x", schema=None)
        assert resp.output_status == "success"
        assert provider.call_count == 3
        # 成功后熔断计数清零
        assert provider.circuit.failures == 0

    async def test_retry_exhausted_then_raise(self, monkeypatch):
        async def _noop_sleep(_):
            return None
        monkeypatch.setattr("app.ai.provider.asyncio.sleep", _noop_sleep)

        provider = _make_provider(max_retries=2)
        provider.set_exception_factory(lambda: AINetworkError("always fail"))
        with pytest.raises(AINetworkError):
            await provider.complete("x", schema=None)
        # 1 次首次 + 2 次重试 = 3 次
        assert provider.call_count == 3
        assert provider.circuit.failures == 1


# ============================================================
# 6. 熔断机制
# ============================================================
class TestCircuitBreaker:
    async def test_circuit_opens_after_threshold(self):
        provider = _make_provider(failure_threshold=3, reset_seconds=60, max_retries=0)
        provider.set_exception_factory(lambda: AIRateLimitError("429"))

        # 前 3 次失败（failures 1→2→3，第 3 次后 open）
        for _ in range(3):
            with pytest.raises(AIRateLimitError):
                await provider.complete("x", schema=None)
        assert provider.circuit.failures == 3

        # 第 4 次应被熔断拒绝
        with pytest.raises(AICircuitBreakerOpenError):
            await provider.complete("x", schema=None)

    async def test_circuit_resets_after_timeout(self):
        provider = _make_provider(
            failure_threshold=2, reset_seconds=0.2, max_retries=0,
        )
        provider.set_exception_factory(lambda: AINetworkError("err"))

        # 失败 2 次触发熔断
        for _ in range(2):
            with pytest.raises(AINetworkError):
                await provider.complete("x", schema=None)

        # 立即调用应被熔断
        with pytest.raises(AICircuitBreakerOpenError):
            await provider.complete("x", schema=None)

        # 等待熔断恢复时间后，半开放行一次；恢复正常响应 → 闭合
        await asyncio.sleep(0.25)
        provider.set_response(_valid_intent_json())
        resp = await provider.complete("x", schema=SEARCH_INTENT_SCHEMA)
        assert resp.output_status == "success"
        # 成功后计数清零
        assert provider.circuit.failures == 0


# ============================================================
# 7. DeepSeek V4 思考模式控制与空响应诊断
# ============================================================
class TestDeepSeekThinkingMode:
    async def test_deepseek_thinking_disabled_uses_extra_body(self):
        provider, client = _make_openai_provider(
            "deepseek-v4-flash",
            "https://api.deepseek.com",
            _openai_response(),
        )

        await provider._invoke(
            "地点摘要",
            AIInvokeOptions(thinking=False, max_tokens=1500, timeout=60.0),
        )

        kwargs = client.chat.completions.last_kwargs
        assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
        assert kwargs["max_tokens"] == 1500
        assert kwargs["timeout"] == 60.0

    async def test_default_options_do_not_change_other_deepseek_scenes(self):
        provider, client = _make_openai_provider(
            "deepseek-v4-flash",
            "https://api.deepseek.com",
            _openai_response(),
        )

        await provider._invoke("AI 搜索", AIInvokeOptions())

        assert "extra_body" not in client.chat.completions.last_kwargs

    async def test_non_deepseek_provider_ignores_thinking_option(self):
        provider, client = _make_openai_provider(
            "gpt-4o-mini",
            "https://api.openai.com/v1",
            _openai_response(),
        )

        await provider._invoke("普通请求", AIInvokeOptions(thinking=False))

        assert "extra_body" not in client.chat.completions.last_kwargs

    async def test_empty_content_logs_safe_reasoning_metadata(self, caplog):
        provider, _ = _make_openai_provider(
            "deepseek-v4-flash",
            "https://api.deepseek.com",
            _openai_response(
                content="",
                reasoning_content="内部推理内容",
                finish_reason="length",
                reasoning_tokens=1500,
            ),
        )

        with caplog.at_level(logging.WARNING, logger="app.ai.provider"):
            result = await provider._invoke("敏感 prompt 不应进入日志", AIInvokeOptions())

        assert result.content == ""
        assert "ai_provider_empty_content" in caplog.text
        assert "response_id=resp-test-1" in caplog.text
        assert "finish_reason=length" in caplog.text
        assert "reasoning_tokens=1500" in caplog.text
        assert "reasoning_length=6" in caplog.text
        assert "内部推理内容" not in caplog.text
        assert "敏感 prompt" not in caplog.text
