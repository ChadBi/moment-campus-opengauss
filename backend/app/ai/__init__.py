"""AI-01: AI 调用基础模块。

对外导出：
- Provider 适配层：AIProvider / OpenAIProvider / MockAIProvider / get_provider
- 调用选项与响应：AIInvokeOptions / AIResponse
- 异常分类：AIError 及子类
- 结构化输出：SEARCH_INTENT_SCHEMA / PUBLISH_SUGGESTION_SCHEMA / validate_structured_output
- 调用服务：invoke_ai / AIInvokeOutcome / update_invocation_result
"""
from app.ai.exceptions import (
    AIError,
    AITimeoutError,
    AIRateLimitError,
    AIInsufficientQuotaError,
    AINetworkError,
    AIJSONParseError,
    AICircuitBreakerOpenError,
)
from app.ai.schemas import (
    SEARCH_INTENT_SCHEMA,
    PUBLISH_SUGGESTION_SCHEMA,
    validate_structured_output,
)
from app.ai.provider import (
    AIInvokeOptions,
    AIInvokeResult,
    AIResponse,
    AIProvider,
    OpenAIProvider,
    MockAIProvider,
    CircuitBreaker,
    get_provider,
    reset_provider,
)
from app.ai.service import (
    AIInvokeOutcome,
    invoke_ai,
    update_invocation_result,
)

__all__ = [
    # exceptions
    "AIError",
    "AITimeoutError",
    "AIRateLimitError",
    "AIInsufficientQuotaError",
    "AINetworkError",
    "AIJSONParseError",
    "AICircuitBreakerOpenError",
    # schemas
    "SEARCH_INTENT_SCHEMA",
    "PUBLISH_SUGGESTION_SCHEMA",
    "validate_structured_output",
    # provider
    "AIInvokeOptions",
    "AIInvokeResult",
    "AIResponse",
    "AIProvider",
    "OpenAIProvider",
    "MockAIProvider",
    "CircuitBreaker",
    "get_provider",
    "reset_provider",
    # service
    "AIInvokeOutcome",
    "invoke_ai",
    "update_invocation_result",
]
