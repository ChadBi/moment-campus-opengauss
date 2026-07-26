"""AI-01.1 + AI-01.3: AI 调用服务。

职责：
1. 封装 Provider 调用 + 自动记录 ai_invocation_logs（成功/失败均记录）。
2. 三校隔离：school_id 强制取自 TenantContext，不接受外部传入。
3. 自动降级：失败时不抛异常给业务层，而是返回带 fallback 标记的 AIInvokeOutcome，
   上层（AI-02/AI-03）据此切换普通搜索 / 手动发布。
4. 隐私：只记录 input_length + input_hash，不记录完整 prompt。

用法（AI-02 示例）：
    outcome = await invoke_ai(prompt, schema, scene="search_intent",
                              tenant=tenant, user=user, trace_id=request_id)
    if outcome.fallback:
        # 降级普通搜索
    else:
        intent = outcome.response.parsed
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.models.ai_invocation_log import AIInvocationLog
from app.models.user import User

from app.ai.exceptions import (
    AIError,
    OUTPUT_STATUS_SUCCESS,
)
from app.ai.provider import (
    AIInvokeOptions,
    AIProvider,
    AIResponse,
    get_provider,
)

logger = logging.getLogger(__name__)


@dataclass
class AIInvokeOutcome:
    """invoke_ai 的统一返回（永不抛 AIError 给业务层）。

    Attributes:
        response: 成功时为 AIResponse；失败时为 None
        output_status: 落库状态码（success/timeout/...）
        fallback: 是否已降级（True 表示 AI 调用失败，业务应走降级路径）
        fallback_reason: 降级原因（失败时填，可直接展示/记录）
        latency_ms: 调用耗时（毫秒）
        log_id: 对应 ai_invocation_logs 记录 ID（便于上层补充 result_count）
    """

    response: Optional[AIResponse]
    output_status: str
    fallback: bool
    fallback_reason: Optional[str]
    latency_ms: int
    log_id: Optional[int]


# 各类异常对应的中文降级原因（不向用户暴露原始错误）
_FALLBACK_REASONS = {
    "timeout": "AI 响应超时，已降级普通搜索",
    "rate_limit": "AI 服务限流，已降级普通搜索",
    "insufficient_quota": "AI 配额不足，已降级普通搜索",
    "network_error": "AI 网络异常，已降级普通搜索",
    "json_parse_error": "AI 输出解析失败，已降级普通搜索",
    "circuit_breaker": "AI 服务熔断中，已降级普通搜索",
    "error": "AI 调用失败，已降级普通搜索",
}


async def invoke_ai(
    prompt: str,
    schema: Optional[dict[str, Any]],
    scene: str,
    tenant: TenantContext,
    db: AsyncSession,
    user: Optional[User] = None,
    options: Optional[AIInvokeOptions] = None,
    trace_id: Optional[str] = None,
    provider: Optional[AIProvider] = None,
) -> AIInvokeOutcome:
    """调用 AI 并自动记录日志；失败时返回降级标记（不抛异常）。

    Args:
        prompt: 输入文本
        schema: 结构化输出 JSON Schema（可空）
        scene: 调用场景（search_intent / publish_suggestion 等）
        tenant: 租户上下文（school_id 强制取自此，三校隔离）
        db: 数据库会话
        user: 当前用户（可空，游客为 None；默认取 tenant.user）
        options: 调用选项
        trace_id: 链路追踪 ID
        provider: 可选 Provider（测试注入；默认 get_provider()）

    Returns:
        AIInvokeOutcome：成功 response 有值；失败 fallback=True。
    """
    # 三校隔离：school_id 只来自 TenantContext，绝不接受外部传入
    school_id = tenant.school_id
    current_user = user if user is not None else tenant.user
    user_id = current_user.id if current_user is not None else None

    input_length = len(prompt)
    input_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    prov = provider if provider is not None else await get_provider()

    response: Optional[AIResponse] = None
    output_status = OUTPUT_STATUS_SUCCESS
    fallback_reason: Optional[str] = None
    latency_ms = 0
    error_msg = ""

    try:
        response = await prov.complete(prompt, schema, options)
        latency_ms = response.latency_ms
        output_status = response.output_status
    except AIError as exc:
        output_status = exc.output_status
        latency_ms = 0  # 失败时延迟由 provider 内部计时，此处记 0（状态已是失败）
        fallback_reason = _FALLBACK_REASONS.get(exc.output_status, _FALLBACK_REASONS["error"])
        error_msg = str(exc)[:200]
        logger.warning(
            "ai_invoke_failed school_id=%s scene=%s status=%s msg=%.200s trace=%s",
            school_id, scene, output_status, error_msg, trace_id,
        )
    except Exception as exc:  # noqa: BLE001  兜底：任何未预期异常都降级
        output_status = "error"
        fallback_reason = _FALLBACK_REASONS["error"]
        error_msg = f"{type(exc).__name__}: {str(exc)[:200]}"
        logger.exception(
            "ai_invoke_unexpected school_id=%s scene=%s trace=%s",
            school_id, scene, trace_id,
        )

    fallback = output_status != OUTPUT_STATUS_SUCCESS

    # 落库（成功/失败均记录；不保存完整 prompt）
    log = AIInvocationLog(
        school_id=school_id,
        user_id=user_id,
        scene=scene,
        model=response.model if response else getattr(prov, "name", "unknown"),
        provider=getattr(prov, "name", "unknown"),
        latency_ms=latency_ms,
        input_length=input_length,
        input_hash=input_hash,
        output_status=output_status,
        fallback_reason=fallback_reason,
        trace_id=trace_id,
        created_at=datetime.now(),
    )
    db.add(log)
    await db.commit()
    # commit 后 log.id 已通过 INSERT ... RETURNING 填充（expire_on_commit=False），
    # 无需 refresh，避免 openGauss commit 后立即 refresh 的可见性偶发问题

    return AIInvokeOutcome(
        response=response,
        output_status=output_status,
        fallback=fallback,
        fallback_reason=fallback_reason,
        latency_ms=latency_ms,
        log_id=log.id,
    )


async def update_invocation_result(
    db: AsyncSession,
    log_id: int,
    candidate_count: Optional[int] = None,
    result_count: Optional[int] = None,
    fallback_reason: Optional[str] = None,
) -> None:
    """上层检索完成后补充候选数/结果数/降级原因（AI-02 使用）。

    Args:
        db: 数据库会话
        log_id: invoke_ai 返回的 log_id
        candidate_count: 检索候选数
        result_count: 最终返回结果数
        fallback_reason: 若上层进一步降级，可覆盖原因
    """
    log = await db.get(AIInvocationLog, log_id)
    if log is None:
        return
    if candidate_count is not None:
        log.candidate_count = candidate_count
    if result_count is not None:
        log.result_count = result_count
    if fallback_reason is not None:
        log.fallback_reason = fallback_reason
    await db.commit()
