"""AI-01.1: AI 异常分类。

所有 AI 调用失败都映射到下列异常类型之一，便于上层做差异化降级：
- AITimeoutError              超时
- AIRateLimitError            429 限流
- AIInsufficientQuotaError    余额不足 / 配额耗尽
- AINetworkError              网络错误（连接失败 / DNS / 中断）
- AIJSONParseError            模型返回无法解析为 JSON 或不符合 Schema
- AICircuitBreakerOpenError   熔断中（连续失败达阈值）

设计原则：
1. 不把原始异常消息直接透传给用户；日志中保留类型 + 截断消息。
2. 每个异常携带 output_status 字段，与 ai_invocation_logs.output_status 对齐，
   方便 service 层落库时统一映射。
"""
from __future__ import annotations


# output_status 枚举（与 ai_invocation_logs.output_status 字段对齐）
OUTPUT_STATUS_SUCCESS = "success"
OUTPUT_STATUS_TIMEOUT = "timeout"
OUTPUT_STATUS_RATE_LIMIT = "rate_limit"
OUTPUT_STATUS_INSUFFICIENT_QUOTA = "insufficient_quota"
OUTPUT_STATUS_NETWORK_ERROR = "network_error"
OUTPUT_STATUS_JSON_PARSE_ERROR = "json_parse_error"
OUTPUT_STATUS_CIRCUIT_BREAKER = "circuit_breaker"
OUTPUT_STATUS_ERROR = "error"  # 其他未分类错误


class AIError(Exception):
    """AI 调用异常基类。

    Attributes:
        output_status: 落库到 ai_invocation_logs.output_status 的状态码
        provider_message: 原始错误信息（仅日志用，不直接展示给前端）
    """

    output_status: str = OUTPUT_STATUS_ERROR

    def __init__(self, message: str = "", *, provider_message: str = "") -> None:
        super().__init__(message)
        self.provider_message = provider_message or message


class AITimeoutError(AIError):
    """请求超时（asyncio.wait_for 触发）。"""

    output_status = OUTPUT_STATUS_TIMEOUT


class AIRateLimitError(AIError):
    """Provider 返回 429 限流。"""

    output_status = OUTPUT_STATUS_RATE_LIMIT


class AIInsufficientQuotaError(AIError):
    """余额不足 / 配额耗尽。"""

    output_status = OUTPUT_STATUS_INSUFFICIENT_QUOTA


class AINetworkError(AIError):
    """网络错误（连接失败 / DNS / 中断）。"""

    output_status = OUTPUT_STATUS_NETWORK_ERROR


class AIJSONParseError(AIError):
    """模型返回无法解析为 JSON 或不符合传入的 JSON Schema。"""

    output_status = OUTPUT_STATUS_JSON_PARSE_ERROR


class AICircuitBreakerOpenError(AIError):
    """熔断中：连续失败次数达阈值，拒绝请求。

    由 provider 层在调用前检查触发，不再实际请求模型。
    """

    output_status = OUTPUT_STATUS_CIRCUIT_BREAKER
