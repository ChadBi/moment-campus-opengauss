"""AI-01.1: Provider 适配层。

职责：
1. 抽象基类 AIProvider：complete(prompt, schema, options) → AIResponse
   统一封装：超时（asyncio.wait_for）+ 指数退避重试 + 熔断 + JSON 解析 + Schema 校验 + 错误分类。
   子类只需实现 _invoke(prompt, options) → AIInvokeResult（原始文本 + token 用量）。
2. OpenAIProvider：使用 openai SDK（延迟导入，mock 模式无需安装）。
3. MockAIProvider：测试用，可注入预设响应 / 异常 / 延迟。
4. get_provider()：按 settings.AI_PROVIDER 工厂返回单例。

安全约束：
- 密钥仅从服务端环境变量读取，不进日志、不进响应、不进前端。
- 失败日志只记录异常类型与截断消息（<=200 字符），不记录完整 prompt。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import settings

from app.ai.exceptions import (
    AICircuitBreakerOpenError,
    AIError,
    AIInsufficientQuotaError,
    AIJSONParseError,
    AINetworkError,
    AIRateLimitError,
    AITimeoutError,
    OUTPUT_STATUS_SUCCESS,
)
from app.ai.schemas import validate_structured_output

logger = logging.getLogger(__name__)


# ============================================================
# 调用选项与响应数据结构
# ============================================================
@dataclass
class AIInvokeOptions:
    """单次 AI 调用选项（可覆盖 settings 默认值）。"""

    timeout: Optional[float] = None  # None → 用 settings.AI_TIMEOUT
    max_tokens: Optional[int] = None  # None → 用 settings.AI_MAX_TOKENS
    max_retries: Optional[int] = None  # None → 用 settings.AI_MAX_RETRIES
    temperature: float = 0.2
    system_prompt: Optional[str] = None  # 可选系统提示


@dataclass
class AIInvokeResult:
    """Provider 原始调用结果（未做 Schema 校验）。"""

    content: str  # 模型返回的原始文本
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AIResponse:
    """AI 调用对外的统一响应。"""

    content: str
    parsed: Any  # Schema 校验后的结构化对象；schema=None 时为 None
    model: str
    provider: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    output_status: str = OUTPUT_STATUS_SUCCESS


# ============================================================
# 熔断器（Circuit Breaker）
# ============================================================
class CircuitBreaker:
    """简单的异步熔断器（per-provider 单例）。

    状态机：
        closed  --连续失败达阈值--> open
        open    --经过 reset_seconds--> half_open（放行一次）
        half_open --成功--> closed / --失败--> open
    """

    def __init__(
        self,
        failure_threshold: int,
        reset_seconds: int,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float = 0.0  # 进入 open 的 monotonic 时间
        self._lock = asyncio.Lock()

    def _is_open_timed_out(self) -> bool:
        return (time.monotonic() - self._opened_at) >= self.reset_seconds

    async def allow_request(self) -> bool:
        """是否允许放行请求（open 超时后自动进入 half_open 放行一次）。"""
        async with self._lock:
            if self._failures < self.failure_threshold:
                return True
            # 已达阈值 → open 状态
            if self._is_open_timed_out():
                # 进入 half_open，放行一次（不立即重置计数，等结果决定）
                return True
            return False

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()

    async def reset(self) -> None:
        """测试用：强制重置熔断器状态。"""
        async with self._lock:
            self._failures = 0
            self._opened_at = 0.0

    @property
    def failures(self) -> int:
        return self._failures


# 可重试的异常类型（指数退避）：超时 / 限流 / 网络
_RETRYABLE = (AITimeoutError, AIRateLimitError, AINetworkError)


# ============================================================
# 抽象基类
# ============================================================
class AIProvider:
    """Provider 抽象基类。

    子类实现 _invoke(prompt, options) → AIInvokeResult。
    基类负责：熔断检查 → 超时包裹 → 重试退避 → JSON 解析 → Schema 校验 → 错误分类。
    """

    name: str = "base"

    def __init__(
        self,
        timeout: float,
        max_tokens: int,
        max_retries: int,
        circuit: CircuitBreaker,
    ) -> None:
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.circuit = circuit

    # ------------------------------------------------------------
    # 子类实现
    # ------------------------------------------------------------
    async def _invoke(self, prompt: str, options: AIInvokeOptions) -> AIInvokeResult:
        raise NotImplementedError

    # ------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------
    async def complete(
        self,
        prompt: str,
        schema: Optional[dict[str, Any]] = None,
        options: Optional[AIInvokeOptions] = None,
    ) -> AIResponse:
        """调用模型并返回结构化响应。

        Args:
            prompt: 用户提示文本
            schema: 可选 JSON Schema；提供时模型输出必须为可校验的 JSON
            options: 单次调用选项（覆盖默认）

        Raises:
            AICircuitBreakerOpenError: 熔断中
            AITimeoutError / AIRateLimitError / AIInsufficientQuotaError /
            AINetworkError / AIJSONParseError / AIError: 各类失败
        """
        opts = options or AIInvokeOptions()
        timeout = opts.timeout or self.timeout
        max_retries = opts.max_retries if opts.max_retries is not None else self.max_retries

        # 1. 熔断检查
        if not await self.circuit.allow_request():
            raise AICircuitBreakerOpenError(
                "AI 服务熔断中，已降级",
                provider_message="circuit breaker open",
            )

        start = time.monotonic()
        last_exc: Optional[AIError] = None
        attempt = 0
        # 总尝试次数 = 1 + max_retries
        while attempt <= max_retries:
            attempt += 1
            try:
                raw = await asyncio.wait_for(
                    self._invoke(prompt, opts),
                    timeout=timeout,
                )
            except asyncio.TimeoutError as exc:
                last_exc = AITimeoutError(
                    f"AI 请求超时（{timeout}s）",
                    provider_message="asyncio.wait_for timeout",
                )
            except AIError as exc:
                # 余额不足 / JSON 解析失败 / 熔断不重试
                if not isinstance(exc, _RETRYABLE):
                    await self.circuit.record_failure()
                    raise
                last_exc = exc
            except Exception as exc:  # noqa: BLE001  兜底未分类异常
                last_exc = AINetworkError(
                    "AI 网络错误",
                    provider_message=f"{type(exc).__name__}: {str(exc)[:200]}",
                )
            else:
                # 调用成功 → 解析 JSON + Schema 校验
                latency_ms = int((time.monotonic() - start) * 1000)
                parsed = None
                if schema is not None:
                    parsed = self._parse_and_validate(raw.content, schema)
                await self.circuit.record_success()
                return AIResponse(
                    content=raw.content,
                    parsed=parsed,
                    model=raw.model,
                    provider=self.name,
                    latency_ms=latency_ms,
                    input_tokens=raw.input_tokens,
                    output_tokens=raw.output_tokens,
                )

            # 可重试错误 → 指数退避（1s, 2s, 4s ...）
            if attempt <= max_retries and isinstance(last_exc, _RETRYABLE):
                backoff = 2 ** (attempt - 1)  # 1, 2, 4 ...
                logger.warning(
                    "ai_provider_retry provider=%s attempt=%d backoff=%ss "
                    "error=%s msg=%.200s",
                    self.name, attempt, backoff,
                    type(last_exc).__name__, str(last_exc),
                )
                await asyncio.sleep(backoff)
                continue
            # 不可重试或重试用尽
            break

        # 重试用尽
        await self.circuit.record_failure()
        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------
    # JSON 解析 + Schema 校验
    # ------------------------------------------------------------
    @staticmethod
    def _parse_and_validate(content: str, schema: dict[str, Any]) -> Any:
        """解析模型输出为 JSON 并校验 Schema。

        解析策略：
        1. 先尝试整段 json.loads
        2. 失败则尝试提取首个 ```json ... ``` 代码块再解析
        3. 仍失败 → AIJSONParseError
        """
        text = content.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = _extract_json_block(text)
            if data is None:
                raise AIJSONParseError(
                    "模型输出无法解析为 JSON",
                    provider_message=f"json decode failed: {text[:200]}",
                ) from None
        return validate_structured_output(data, schema)


def _extract_json_block(text: str) -> Any:
    """从 markdown ```json 代码块中提取 JSON。"""
    import re

    pattern = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


# ============================================================
# OpenAI Provider（延迟导入 openai，mock 模式无需安装）
# ============================================================
class OpenAIProvider(AIProvider):
    """基于 openai SDK 的 Provider。"""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        max_tokens: int,
        max_retries: int,
        circuit: CircuitBreaker,
        api_base: str = "",
    ) -> None:
        super().__init__(timeout, max_tokens, max_retries, circuit)
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self._client = None  # 延迟构造

    def _get_client(self):
        if self._client is None:
            # 延迟导入：mock 模式 / 未安装 openai 时不会触发
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover - 依赖缺失路径
                raise AIError(
                    "未安装 openai SDK，请运行 pip install openai",
                    provider_message=str(exc),
                ) from exc
            kwargs: dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout}
            if self.api_base:
                kwargs["base_url"] = self.api_base
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def _invoke(self, prompt: str, options: AIInvokeOptions) -> AIInvokeResult:
        client = self._get_client()
        messages: list[dict[str, str]] = []
        if options.system_prompt:
            messages.append({"role": "system", "content": options.system_prompt})
        messages.append({"role": "user", "content": prompt})

        max_tokens = options.max_tokens or self.max_tokens
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=options.temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001  统一分类
            raise self._classify_openai_error(exc) from exc

        content = resp.choices[0].message.content or ""
        usage = resp.usage
        return AIInvokeResult(
            content=content,
            model=self.model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    @staticmethod
    def _classify_openai_error(exc: Exception) -> AIError:
        """将 openai SDK 异常映射到 AI 异常分类。"""
        # 延迟导入异常类
        try:
            from openai import (
                APIConnectionError,
                APITimeoutError,
                RateLimitError,
                APIStatusError,
            )
        except ImportError:  # pragma: no cover
            return AIError(
                "AI 调用失败",
                provider_message=f"{type(exc).__name__}: {str(exc)[:200]}",
            )

        if isinstance(exc, APITimeoutError):
            return AITimeoutError("AI 请求超时", provider_message=str(exc)[:200])
        if isinstance(exc, APIConnectionError):
            return AINetworkError("AI 网络连接失败", provider_message=str(exc)[:200])
        if isinstance(exc, RateLimitError):
            # 余额不足 / 配额耗尽在 openai 里通常也走 429，body.code=insufficient_quota
            msg = str(exc).lower()
            body = getattr(exc, "body", None) or {}
            code = ""
            if isinstance(body, dict):
                code = str(body.get("code", "")).lower()
            if "insufficient_quota" in msg or "insufficient_quota" in code or "billing" in msg:
                return AIInsufficientQuotaError(
                    "AI 配额不足", provider_message=str(exc)[:200],
                )
            return AIRateLimitError("AI 限流（429）", provider_message=str(exc)[:200])
        if isinstance(exc, APIStatusError):
            status = getattr(exc, "status_code", None) or 0
            msg = str(exc).lower()
            if status == 402 or "insufficient" in msg or "billing" in msg:
                return AIInsufficientQuotaError(
                    "AI 余额不足", provider_message=str(exc)[:200],
                )
            if status >= 500:
                return AINetworkError(
                    "AI 服务端错误", provider_message=str(exc)[:200],
                )
            return AIError(
                "AI 调用失败",
                provider_message=f"status={status} {str(exc)[:200]}",
            )
        return AIError(
            "AI 调用失败",
            provider_message=f"{type(exc).__name__}: {str(exc)[:200]}",
        )


# ============================================================
# Mock Provider（测试用）
# ============================================================
class MockAIProvider(AIProvider):
    """测试用假 Provider。

    通过 set_response 预设返回内容；通过 set_exception 注入异常类型；
    通过 set_delay 注入延迟（用于测试超时）。

    默认返回一个符合 SEARCH_INTENT_SCHEMA 的 JSON 串。
    """

    name = "mock"

    def __init__(
        self,
        timeout: float = 15.0,
        max_tokens: int = 1024,
        max_retries: int = 3,
        circuit: Optional[CircuitBreaker] = None,
    ) -> None:
        super().__init__(
            timeout=timeout,
            max_tokens=max_tokens,
            max_retries=max_retries,
            circuit=circuit or CircuitBreaker(failure_threshold=5, reset_seconds=60),
        )
        self._response: str = json.dumps(
            {
                "intent": "查找失物招领信息",
                "filters": {
                    "keyword": "校园卡",
                    "category": "失物招领",
                    "sort": "latest",
                    "date_from": None,
                    "date_to": None,
                },
                "reasons": ["按最新排序便于查找近期丢失物品"],
            },
            ensure_ascii=False,
        )
        self._exception: Optional[Exception] = None
        self._exception_factory: Optional[Any] = None
        self._delay: Optional[float] = None
        self.call_count: int = 0
        self.last_prompt: Optional[str] = None

    # ----- 配置 -----
    def set_response(self, content: str) -> None:
        """预设模型返回的原始文本。"""
        self._response = content
        self._exception = None
        self._exception_factory = None

    def set_exception(self, exc: Exception) -> None:
        """注入固定异常（每次调用都抛同一个实例）。"""
        self._exception = exc
        self._exception_factory = None

    def set_exception_factory(self, factory) -> None:
        """注入异常工厂（每次调用调用 factory() 产生新异常）。

        用途：测试重试时，每次抛新异常实例（避免一个实例被 raise 多次的语义混淆）。
        """
        self._exception_factory = factory
        self._exception = None

    def set_delay(self, seconds: float) -> None:
        """注入延迟（模拟慢响应，配合小 timeout 测试超时）。"""
        self._delay = seconds

    # ----- 实现 -----
    async def _invoke(self, prompt: str, options: AIInvokeOptions) -> AIInvokeResult:
        self.call_count += 1
        self.last_prompt = prompt
        if self._delay is not None:
            await asyncio.sleep(self._delay)
        if self._exception_factory is not None:
            exc = self._exception_factory()
            if exc is not None:
                raise exc
        if self._exception is not None:
            raise self._exception
        return AIInvokeResult(
            content=self._response,
            model="mock-model",
            input_tokens=len(prompt) // 4,
            output_tokens=len(self._response) // 4,
        )


# ============================================================
# 工厂（单例）
# ============================================================
_provider_instance: Optional[AIProvider] = None
_provider_lock = asyncio.Lock()


async def get_provider() -> AIProvider:
    """按 settings.AI_PROVIDER 返回单例 Provider。

    mock → MockAIProvider（默认，无需 API Key）
    openai → OpenAIProvider
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance
    async with _provider_lock:
        if _provider_instance is not None:
            return _provider_instance
        _provider_instance = _build_provider()
        return _provider_instance


def _build_provider() -> AIProvider:
    provider_type = (settings.AI_PROVIDER or "mock").lower()
    circuit = CircuitBreaker(
        failure_threshold=settings.AI_CIRCUIT_FAILURE_THRESHOLD,
        reset_seconds=settings.AI_CIRCUIT_RESET_SECONDS,
    )
    if provider_type == "openai":
        if not settings.AI_API_KEY:
            raise AIError(
                "AI_PROVIDER=openai 但未配置 AI_API_KEY",
                provider_message="missing AI_API_KEY",
            )
        return OpenAIProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            timeout=settings.AI_TIMEOUT,
            max_tokens=settings.AI_MAX_TOKENS,
            max_retries=settings.AI_MAX_RETRIES,
            circuit=circuit,
            api_base=settings.AI_API_BASE,
        )
    # 默认 mock
    return MockAIProvider(
        timeout=settings.AI_TIMEOUT,
        max_tokens=settings.AI_MAX_TOKENS,
        max_retries=settings.AI_MAX_RETRIES,
        circuit=circuit,
    )


async def reset_provider() -> None:
    """测试用：重置单例 Provider（下次 get_provider 重建）。"""
    global _provider_instance
    async with _provider_lock:
        _provider_instance = None
