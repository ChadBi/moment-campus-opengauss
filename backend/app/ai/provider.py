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
import re
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
    thinking: Optional[bool] = None  # DeepSeek V4 思考模式；None → 使用服务端默认值


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
    async def _invoke(self, prompt: str, options: AIInvokeOptions, schema: Optional[dict[str, Any]] = None) -> AIInvokeResult:
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
                    self._invoke(prompt, opts, schema),
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
                    try:
                        parsed = self._parse_and_validate(raw.content, schema)
                    except AIJSONParseError:
                        logger.warning(
                            "ai_provider_json_parse_failed provider=%s model=%s content_length=%s",
                            self.name,
                            raw.model,
                            len(raw.content),
                        )
                        raise
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
    """从模型输出中提取 JSON，支持多种包裹方式。

    策略：
    1. 尝试提取 ```json ... ``` 或 ``` ... ``` 代码块
    2. 尝试找到第一个 { 或 [ 到最后一个匹配的 } 或 ]
    """
    # 策略1：markdown 代码块
    pattern = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
    match = pattern.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略2：找到第一个 { 到最后一个 }（处理嵌套对象）
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 策略3：找到第一个 [ 到最后一个 ]（处理数组）
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate = text[first_bracket:last_bracket + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

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

    def _is_deepseek(self) -> bool:
        """判断当前 OpenAI 兼容端点是否为 DeepSeek。"""
        return (
            self.model.lower().startswith("deepseek-")
            or "deepseek.com" in self.api_base.lower()
        )

    async def _invoke(
        self,
        prompt: str,
        options: AIInvokeOptions,
        schema: Optional[dict[str, Any]] = None,
    ) -> AIInvokeResult:
        client = self._get_client()
        messages: list[dict[str, str]] = []
        if options.system_prompt:
            messages.append({"role": "system", "content": options.system_prompt})
        messages.append({"role": "user", "content": prompt})

        max_tokens = options.max_tokens or self.max_tokens
        effective_timeout = options.timeout or self.timeout
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": options.temperature,
                "max_tokens": max_tokens,
                "timeout": effective_timeout,
            }
            if options.thinking is not None and self._is_deepseek():
                kwargs["extra_body"] = {
                    "thinking": {"type": "enabled" if options.thinking else "disabled"},
                }
            resp = await client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001  统一分类
            raise self._classify_openai_error(exc) from exc

        choice = resp.choices[0]
        message = choice.message
        content = message.content or ""
        usage = getattr(resp, "usage", None)
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        completion_details = getattr(usage, "completion_tokens_details", None)
        reasoning_tokens = getattr(completion_details, "reasoning_tokens", 0) or 0
        reasoning_content = getattr(message, "reasoning_content", None) or ""
        if not content:
            logger.warning(
                "ai_provider_empty_content provider=%s model=%s response_id=%s "
                "finish_reason=%s output_tokens=%s reasoning_tokens=%s reasoning_length=%s",
                self.name,
                self.model,
                getattr(resp, "id", None),
                getattr(choice, "finish_reason", None),
                output_tokens,
                reasoning_tokens,
                len(reasoning_content),
            )
        return AIInvokeResult(
            content=content,
            model=self.model,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=output_tokens,
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

    默认行为（未调用 set_response 时）：
    - 识别 prompt 类型（搜索意图 / 发布建议），基于用户实际输入动态生成响应，
      使本地开发环境（AI_PROVIDER=mock）的 AI 搜索/发布建议功能可用。
    - 调用 set_response 后切换为"固定响应"模式，便于测试断言。
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
        # 固定响应回退（仅当 _generate_dynamic_response 无法识别 prompt 时使用）
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
        # 是否被 set_response 覆盖（True 时关闭动态生成，便于测试断言）
        self._response_overridden: bool = False
        self._exception: Optional[Exception] = None
        self._exception_factory: Optional[Any] = None
        self._delay: Optional[float] = None
        self.call_count: int = 0
        self.last_prompt: Optional[str] = None

    # ----- 配置 -----
    def set_response(self, content: str) -> None:
        """预设模型返回的原始文本（关闭动态生成，便于测试断言）。"""
        self._response = content
        self._response_overridden = True
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

    # ----- 动态响应生成（本地开发 mock 模式可用） -----
    @staticmethod
    def _extract_user_query(prompt: str) -> Optional[str]:
        """从搜索意图 prompt 中提取用户原始查询。

        prompt 末尾为：
            # 用户查询
            {query}
        """
        marker = "# 用户查询"
        idx = prompt.rfind(marker)
        if idx < 0:
            return None
        query = prompt[idx + len(marker):].strip()
        return query or None

    @staticmethod
    def _extract_publish_draft(prompt: str) -> Optional[dict[str, Any]]:
        """从发布建议 prompt 中提取草稿原文（标题/正文）。

        prompt 中包含：
            # 用户草稿
            标题：xxx
            正文：xxx
        """
        marker = "# 用户草稿"
        idx = prompt.rfind(marker)
        if idx < 0:
            return None
        block = prompt[idx + len(marker):].strip()
        title: Optional[str] = None
        content: Optional[str] = None
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("标题：") or line.startswith("标题:"):
                title = line.split("：", 1)[-1].split(":", 1)[-1].strip() or None
            elif line.startswith("正文：") or line.startswith("正文:"):
                content = line.split("：", 1)[-1].split(":", 1)[-1].strip() or None
        if title is None and content is None:
            return None
        return {"title": title, "content": content}

    @staticmethod
    def _extract_first_noun(query: str, max_len: int = 12) -> str:
        """从用户查询中提取核心关键词（用于 mock 模式检索）。

        策略：
        1. 去除常见疑问/停用词与时间词
        2. 优先取连续中文字符片段
        3. 截断到 max_len
        """
        if not query:
            return ""
        # 去除常见疑问词、停用词与时间词（避免把"今天""什么时候"当作关键词）
        stop_words = [
            "什么", "怎么", "怎样", "如何", "哪里", "哪儿", "哪个",
            "为什么", "是不是", "有没有", "请问", "麻烦", "一下",
            "的", "了", "吗", "呢", "啊", "吧", "是", "在", "有",
            "今天", "明天", "昨天", "后天", "前天",
            "这周", "下周", "上周", "本周",
            "这个月", "下个月", "上个月",
            "时候", "时间", "时候的",
            "现在", "目前", "当前",
            "几", "多少",
        ]
        cleaned = query
        for w in stop_words:
            cleaned = cleaned.replace(w, " ")
        # 取最长的连续中文/字母数字片段
        segments = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", cleaned)
        if not segments:
            # 回退：原 query 的中文片段
            segments = re.findall(r"[\u4e00-\u9fa5]+", query) or [query[:max_len]]
        # 选最长的片段
        segments.sort(key=len, reverse=True)
        keyword = segments[0][:max_len]
        return keyword

    def _generate_dynamic_response(self, prompt: str) -> str:
        """根据 prompt 类型动态生成响应（本地开发 mock 模式可用）。

        - 搜索意图 prompt（"你是校园信息搜索助手"）：提取用户查询，返回 keyword=核心词
        - 发布建议 prompt（"你是校园信息发布助手"）：返回 null 建议不动原文
        - 其他：回退到固定响应 self._response
        """
        # 1. 搜索意图
        if "你是校园信息搜索助手" in prompt:
            user_query = self._extract_user_query(prompt) or ""
            keyword = self._extract_first_noun(user_query) or user_query[:12]
            return json.dumps(
                {
                    "intent": f"查找与「{keyword}」相关的校园信息" if keyword else "校园信息搜索",
                    "filters": {
                        "keyword": keyword or None,
                        "category": None,
                        "sort": "relevance",
                        "date_from": None,
                        "date_to": None,
                        "map_bounds": None,
                    },
                    "reasons": [
                        f"按相关度排序匹配「{keyword}」的校园信息" if keyword else "按相关度排序校园信息"
                    ],
                },
                ensure_ascii=False,
            )

        # 2. 发布建议
        if "你是校园信息发布助手" in prompt:
            # 不修改原文，给出最小可用建议
            return json.dumps(
                {
                    "suggestions": {
                        "title": None,
                        "optimized_title": None,
                        "optimized_content": None,
                        "summary": None,
                        "category": None,
                        "tags": [],
                        "default_validity_days": 30,
                    },
                    "missing_info": [],
                    "sensitive_warnings": [],
                },
                ensure_ascii=False,
            )

        # 3. 回退：固定响应
        return self._response

    # ----- 实现 -----
    async def _invoke(self, prompt: str, options: AIInvokeOptions, schema: Optional[dict[str, Any]] = None) -> AIInvokeResult:
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
        # 响应选择：set_response 覆盖 > 动态生成 > 固定默认
        if self._response_overridden:
            content = self._response
        else:
            content = self._generate_dynamic_response(prompt)
        return AIInvokeResult(
            content=content,
            model="mock-model",
            input_tokens=len(prompt) // 4,
            output_tokens=len(content) // 4,
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
