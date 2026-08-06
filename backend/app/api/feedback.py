"""用户反馈 API（建议/问题/投诉/其他）

端点：
- POST   /feedback                 提交反馈（需登录，记录 user_id / school_id）
- GET    /feedback                 查看"我的"反馈（分页）
- GET    /feedback/all             管理端全部反馈（admin 及以上，按状态/类型过滤，按学校隔离）
- PATCH  /feedback/{id}            处理反馈：更新 status / remark（admin 及以上）

设计要点：
1. 反馈严格按学校隔离：school_id 强制由 TenantContext 决定，跨校反馈不可见。
2. 用户端仅能查看/提交自己的反馈；管理端按当前学校过滤。
3. 处理反馈时记录 AdminOperationLog（与举报/分类等管理操作一致）。
4. 状态进入 resolved 时写入 resolved_at，离开时清空。
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.feedback import Feedback
from app.models.admin_operation_log import AdminOperationLog
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackAdminUpdate
from app.core.exceptions import NotFoundException
from app.core.permissions import require_role, Role
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant

router = APIRouter(prefix="/feedback", tags=["反馈"])


def _to_response(f: Feedback) -> FeedbackResponse:
    return FeedbackResponse.model_validate(f)


@router.post("", response_model=FeedbackResponse, status_code=201, summary="提交反馈")
async def create_feedback(
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """提交反馈（需登录）

    - user_id / school_id 由后端写入，school_id 强制使用 TenantContext 决定。
    """
    feedback = Feedback(
        user_id=current_user.id,
        school_id=tenant.school_id,
        feedback_type=payload.feedback_type,
        content=payload.content,
        contact=payload.contact,
        status="open",
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return _to_response(feedback)


@router.get("", response_model=PaginatedResponse[FeedbackResponse], summary="我的反馈")
async def list_my_feedbacks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """查看当前用户在当前学校的反馈（分页，最新在前）"""
    base_filter = (
        Feedback.user_id == current_user.id,
        Feedback.school_id == tenant.school_id,
    )
    total = await db.scalar(
        select(func.count()).select_from(Feedback).where(*base_filter)
    ) or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Feedback)
        .where(*base_filter)
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = [_to_response(f) for f in result.scalars().all()]
    return PaginatedResponse.create(items, page, page_size, total)


@router.get("/all", response_model=PaginatedResponse[FeedbackResponse], summary="全部反馈（管理端）")
async def list_all_feedbacks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态过滤：open / in_review / resolved"),
    type: Optional[str] = Query(None, description="按类型过滤：suggestion / bug / complaint / other"),
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """管理端全部反馈（admin 及以上）

    TEN-02.3：按当前学校过滤，跨校反馈不会出现在列表中。
    """
    base_filter = (Feedback.school_id == tenant.school_id,)
    if status:
        base_filter += (Feedback.status == status,)
    if type:
        base_filter += (Feedback.feedback_type == type,)

    total = await db.scalar(
        select(func.count()).select_from(Feedback).where(*base_filter)
    ) or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Feedback)
        .where(*base_filter)
        .options(selectinload(Feedback.user))
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = []
    for f in result.unique().scalars().all():
        resp = _to_response(f)
        resp.user_name = f.user.nickname if f.user else None
        items.append(resp)
    return PaginatedResponse.create(items, page, page_size, total)


@router.patch("/{feedback_id}", response_model=FeedbackResponse, summary="处理反馈（管理端）")
async def update_feedback(
    feedback_id: int,
    payload: FeedbackAdminUpdate,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """处理反馈：更新 status / remark（admin 及以上）

    TEN-02.3：跨校反馈统一返回 404。
    """
    feedback = await db.scalar(
        select(Feedback).where(Feedback.id == feedback_id).options(selectinload(Feedback.user))
    )
    if not feedback:
        raise NotFoundException(detail="反馈不存在")
    check_resource_in_tenant(feedback.school_id, tenant)

    changes = []
    if payload.status is not None and payload.status != feedback.status:
        changes.append(f"status: {feedback.status} → {payload.status}")
        feedback.status = payload.status
        # 进入 resolved 写入 resolved_at，离开时清空
        if payload.status == "resolved":
            feedback.resolved_at = datetime.now()
        else:
            feedback.resolved_at = None
    if payload.remark is not None:
        changes.append(f"remark: {feedback.remark or ''} → {payload.remark}")
        feedback.remark = payload.remark

    feedback.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="update_feedback",
        target_type="feedback",
        target_id=feedback_id,
        detail="；".join(changes) if changes else "反馈处理（无字段变更）",
    ))
    await db.commit()
    await db.refresh(feedback)

    resp = _to_response(feedback)
    resp.user_name = feedback.user.nickname if feedback.user else None
    return resp