"""ANA-01.3 + ANA-02: 事件上报 + 数据分析 API

提供两类端点：

ANA-01.3 事件上报：
- POST /api/v1/analytics/events 批量上报（登录/游客均可）
- 严格依赖白名单 + 最小字段 + 幂等键

ANA-02 校级分析（admin 及以上）：
- GET /api/v1/admin/analytics 校级指标复算（漏斗/留存/搜索/内容/治理/AI）
- GET /api/v1/admin/analytics/zero-results 零结果主题洞察（隐私阈值保护）
- 平台层只看学校级聚合；校级 admin 看本校聚合，不提供跨校用户轨迹
"""
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request, Header
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analytics import track_events_batch, EVENT_WHITELIST
from app.core.permissions import require_role, Role
from app.core.tenant import get_tenant_context, TenantContext
from app.database import get_db
from app.models.user import User
from app.services.analytics_service import (
    SchoolAnalyticsService,
    DEFAULT_WINDOW_DAYS,
)

router = APIRouter(prefix="/analytics", tags=["产品分析"])
admin_analytics_router = APIRouter(prefix="/admin/analytics", tags=["管理-数据分析"])


# ============================================================
# Schemas
# ============================================================
class EventInput(BaseModel):
    """单个事件上报体。

    - event_id：客户端生成的 UUID（幂等键，必填）
    - event_name：事件名（必须在白名单内）
    - occurred_at：事件发生时间（ISO 字符串或 datetime；缺省由服务端填 now）
    - session_id：前端会话 ID（可空）
    - fields：最小字段集（白名单 schema 校验；多余字段被剔除，敏感字段拒绝）
    - user_id：仅 super_admin 跨校上报时可显式指定；普通用户/游客上报会被忽略，
      以 TenantContext 解析得到的 user_id 为准
    """
    event_id: str = Field(..., min_length=1, max_length=64, description="客户端生成的 UUID（幂等键）")
    event_name: str = Field(..., min_length=1, max_length=50, description="事件名（白名单内）")
    occurred_at: Optional[datetime] = Field(None, description="事件发生时间；缺省由服务端填 now")
    session_id: Optional[str] = Field(None, max_length=64, description="前端会话 ID")
    fields: Optional[dict[str, Any]] = Field(None, description="最小字段集（白名单校验）")
    user_id: Optional[int] = Field(
        None, description="仅 super_admin 可显式指定；其余用户上报会被忽略",
    )

    @field_validator("event_name")
    @classmethod
    def _validate_event_name(cls, v: str) -> str:
        if v not in EVENT_WHITELIST:
            raise ValueError(
                f"非白名单事件：{v!r}，允许值：{sorted(EVENT_WHITELIST.keys())}"
            )
        return v


class EventsBatchRequest(BaseModel):
    """批量上报请求体。"""
    events: list[EventInput] = Field(..., min_length=1, max_length=50,
                                      description="事件列表（1-50 条/批）")


class EventResult(BaseModel):
    event_id: str
    inserted: bool
    error: Optional[str] = None


class EventsBatchResponse(BaseModel):
    """批量上报响应。

    - total：本次上报事件总数
    - inserted：新插入数
    - idempotent：幂等命中数（重复 event_id）
    - rejected：被拒数（非白名单 / 敏感字段 / 校验失败）
    - results：每个事件的明细
    """
    total: int
    inserted: int
    idempotent: int
    rejected: int
    results: list[EventResult]


# ============================================================
# Routes
# ============================================================
@router.post(
    "/events",
    response_model=EventsBatchResponse,
    summary="批量上报产品事件",
)
async def batch_report_events(
    body: EventsBatchRequest,
    request: Request,
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """批量上报产品事件（登录/游客均可）。

    流程：
        1. TenantContext 解析当前学校（游客必须传 X-School-Code / ?school=）
        2. 每个事件：白名单 + 最小字段 + 敏感字段校验 → 幂等入库
        3. 非白名单 / 敏感字段事件被拒，不影响其他事件入库
        4. 重复 event_id 不重复入库（幂等）

    返回每个事件的入库结果（inserted / idempotent / rejected）。
    """
    # trace_id 优先 X-Request-ID 头，其次 request.state.request_id（中间件注入）
    trace_id = x_request_id or getattr(request.state, "request_id", None)

    # 上报 user_id：游客为 None；登录用户取 tenant.user.id；
    # 仅 super_admin 跨校上报场景下，前端可显式传 user_id（仍受白名单约束）
    if tenant.is_guest or tenant.user is None:
        reporter_user_id: Optional[int] = None
    else:
        reporter_user_id = tenant.user.id

    events_payload: list[dict[str, Any]] = []
    for ev in body.events:
        # 普通用户/游客上报的 user_id 字段被忽略（防伪造）；super_admin 可显式指定
        override_user_id: Optional[int] = None
        if tenant.is_super_admin and ev.user_id is not None:
            override_user_id = ev.user_id

        events_payload.append({
            "event_id": ev.event_id,
            "event_name": ev.event_name,
            "occurred_at": ev.occurred_at,
            "session_id": ev.session_id,
            "fields": ev.fields,
            "user_id": override_user_id or reporter_user_id,
        })

    results = await track_events_batch(
        db,
        events_payload,
        school_id=tenant.school_id,
        user_id=reporter_user_id,
        trace_id=trace_id,
    )

    inserted_count = sum(1 for r in results if r["inserted"])
    idempotent_count = sum(
        1 for r in results
        if not r["inserted"] and (r["error"] == "idempotent_conflict" or r["error"] is None)
    )
    rejected_count = sum(
        1 for r in results
        if not r["inserted"] and r["error"] not in (None, "idempotent_conflict")
    )

    return EventsBatchResponse(
        total=len(results),
        inserted=inserted_count,
        idempotent=idempotent_count,
        rejected=rejected_count,
        results=[EventResult(**r) for r in results],
    )


# ============================================================
# ANA-02.1 / ANA-02.2: 校级分析接口（admin 及以上）
# ============================================================
@admin_analytics_router.get(
    "",
    summary="校级分析指标（ANA-02.2，admin 及以上）",
)
async def get_school_analytics(
    window_days: int = Query(
        default=DEFAULT_WINDOW_DAYS,
        ge=1,
        le=180,
        description="指标复算时间窗口（天），默认 30",
    ),
    tenant: TenantContext = Depends(get_tenant_context),
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """ANA-02.2 校级分析指标：从 product_events / posts / ai_invocation_logs /
    reports / post_change_reports 等业务表实时复算。

    覆盖指标：
    - 漏斗（学校查看 → 搜索 → 发布 → 审核 → 公开）
    - 7 日回访率
    - 搜索成功率 / 零结果率
    - 分享订阅转化
    - 内容有效率（published 且未过期 / 总内容）
    - 审核治理 SLA（平均审核/举报/问题报告处理时长）
    - AI 每次成功检索用量 + 降级率

    每个指标附带元数据：time_window / sample_size / last_updated_at / empty_state。

    ANA-02.1：平台层只看学校级聚合；本接口返回当前 admin 所属学校的聚合数据，
    不暴露跨校用户轨迹。super_admin 可通过 X-School-Code 切换查看任意学校。
    """
    svc = SchoolAnalyticsService(db, tenant.school_id)
    metrics = await svc.compute_all(window_days=window_days)
    return metrics.to_dict()


@admin_analytics_router.get(
    "/zero-results",
    summary="零结果主题洞察（ANA-02.1，隐私阈值保护）",
)
async def get_zero_results_insight(
    window_days: int = Query(
        default=DEFAULT_WINDOW_DAYS,
        ge=1,
        le=180,
        description="回溯窗口（天），默认 30",
    ),
    tenant: TenantContext = Depends(get_tenant_context),
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """ANA-02.1 零结果主题洞察。

    - 从 search_zero 事件的 fields_json 聚合 keyword_length + category_code
    - 单个主题样本量 < PRIVACY_THRESHOLD 时标记 hidden_for_privacy=true，
      仍计入总数但不返回具体聚合字段（隐私硬约束）
    - super_admin 可通过 X-School-Code 查看任意学校
    """
    svc = SchoolAnalyticsService(db, tenant.school_id)
    insight = await svc.compute_zero_results_insight(window_days=window_days)
    return insight.to_dict()
