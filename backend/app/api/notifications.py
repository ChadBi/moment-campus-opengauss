from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.models.notification_preference import (
    NotificationPreference,
    NOTIFICATION_CATEGORIES,
    SECURITY_CATEGORIES,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.core.tenant import TenantContext, get_tenant_context

router = APIRouter(tags=["通知"])


class NotificationResponse(BaseModel):
    """通知响应"""
    id: int = Field(..., description="通知ID")
    type: str = Field(..., description="通知类型")
    title: str = Field(..., description="标题")
    content: Optional[str] = Field(None, description="内容")
    target_type: Optional[str] = Field(None, description="目标类型")
    target_id: Optional[int] = Field(None, description="目标ID")
    actor_id: Optional[int] = Field(None, description="操作者ID")
    actor_name: Optional[str] = Field(None, description="操作者名称")
    actor_avatar: Optional[str] = Field(None, description="操作者头像")
    is_read: bool = Field(..., description="是否已读")
    read_at: Optional[datetime] = Field(None, description="已读时间")
    created_at: datetime = Field(..., description="创建时间")


class UnreadCountResponse(BaseModel):
    """PRF-01.2: 未读通知数量响应"""
    unread_count: int = Field(..., ge=0, description="未读通知数量")
    has_unread: bool = Field(..., description="是否存在未读通知")


@router.get("/notifications", response_model=PaginatedResponse[NotificationResponse])
async def get_notifications(
    type: Optional[str] = Query(None, description="通知类型"),
    is_read: Optional[bool] = Query(None, description="是否已读"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    获取通知列表
    支持按类型和已读状态筛选，分页返回

    DSC-01.2: 使用 selectinload 批量预加载 actor，消除每通知单独查询的 N+1。
    TEN-02.3：通知按用户隔离（Notification.user_id == current_user.id），
    TenantContext 确保用户在当前学校有访问权限。
    """
    # 构建基础查询
    # DSC-01.2: 在查询阶段就预加载 actor 关系，避免每行单独查 User
    query = (
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_deleted == False
        )
        .options(selectinload(Notification.actor))
    )

    # 筛选条件
    if type:
        query = query.where(Notification.type == type)
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)

    # 排序（最新的在前）
    query = query.order_by(Notification.created_at.desc())

    # 计算总数（基于无 selectinload 的子查询，把筛选条件放在子查询内）
    count_inner = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_deleted == False
    )
    if type:
        count_inner = count_inner.where(Notification.type == type)
    if is_read is not None:
        count_inner = count_inner.where(Notification.is_read == is_read)
    count_query = select(func.count()).select_from(count_inner.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询（已预加载关联）
    result = await db.execute(query)
    notifications = result.scalars().all()

    # 构建响应（actor 已预加载，无额外查询）
    items = []
    for notification in notifications:
        actor = notification.actor
        actor_name = actor.nickname if actor else None
        actor_avatar = actor.avatar_url if actor else None

        items.append(NotificationResponse(
            id=notification.id,
            type=notification.type,
            title=notification.title,
            content=notification.content,
            target_type=notification.target_type,
            target_id=notification.target_id,
            actor_id=notification.actor_id,
            actor_name=actor_name,
            actor_avatar=actor_avatar,
            is_read=notification.is_read,
            read_at=notification.read_at,
            created_at=notification.created_at,
        ))

    return PaginatedResponse.create(items, page, page_size, total)


@router.put("/notifications/{notification_id}/read", response_model=MessageResponse)
async def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    标记单个通知已读

    TEN-02.3：TenantContext 校验用户在当前学校的访问权限。
    """
    # 查询通知
    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
        Notification.is_deleted == False
    )
    result = await db.execute(query)
    notification = result.scalar_one_or_none()

    if not notification:
        raise NotFoundException(detail="通知不存在")

    # 标记已读
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now()
        await db.commit()

    return MessageResponse(message="已标记为已读")


@router.put("/notifications/read-all", response_model=MessageResponse)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    标记所有通知已读

    TEN-02.3：TenantContext 校验用户在当前学校的访问权限。
    """
    # 查询所有未读通知
    query = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,
        Notification.is_deleted == False
    )
    result = await db.execute(query)
    notifications = result.scalars().all()

    # 标记已读
    now = datetime.now()
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now

    await db.commit()

    return MessageResponse(message=f"已标记 {len(notifications)} 条通知为已读")


# ============================================================
# PRF-01.2: /notifications/unread-count 未读通知数量
# ============================================================
@router.get(
    "/notifications/unread-count",
    response_model=UnreadCountResponse,
    summary="未读通知数量（页头角标）",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取当前用户的未读通知数量

    PRF-01.2：用于页头未读角标实时显示。
    通知按 user_id 隔离（Notification.user_id == current_user.id），
    不区分学校（用户在不同学校产生的通知都聚合到该用户的通知中心）。
    返回 unread_count 与 has_unread（便于前端布尔判断）。
    """
    count = (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == current_user.id,
                Notification.is_read == False,
                Notification.is_deleted == False,
            )
        )
    ).scalar() or 0
    return UnreadCountResponse(
        unread_count=count,
        has_unread=count > 0,
    )


# ============================================================
# UX-01.5: /notifications/preferences 通知偏好
# ============================================================
class NotificationPreferenceResponse(BaseModel):
    """通知偏好响应"""
    instant_enabled: bool = Field(..., description="站内即时通知")
    site_digest_enabled: bool = Field(..., description="每日摘要")
    subscription_enabled: bool = Field(..., description="订阅类")
    interaction_enabled: bool = Field(..., description="互动类")
    audit_enabled: bool = Field(..., description="审核类（安全账号通知不可全关）")
    governance_enabled: bool = Field(..., description="治理类")
    system_enabled: bool = Field(..., description="系统类（安全账号通知不可全关）")
    digest_time: str = Field(..., description="每日摘要投递时间 HH:MM")
    email_enabled: bool = Field(..., description="是否同步邮件通知")


class NotificationPreferenceUpdate(BaseModel):
    """通知偏好更新请求

    安全账号通知（system/audit）不可全关：
    - 若尝试将 system_enabled 与 audit_enabled 同时设为 false，且 instant_enabled 也为 false，
      后端将拒绝（422），保证至少 instant=true。
    """
    instant_enabled: Optional[bool] = Field(None, description="站内即时通知")
    site_digest_enabled: Optional[bool] = Field(None, description="每日摘要")
    subscription_enabled: Optional[bool] = Field(None, description="订阅类")
    interaction_enabled: Optional[bool] = Field(None, description="互动类")
    audit_enabled: Optional[bool] = Field(None, description="审核类")
    governance_enabled: Optional[bool] = Field(None, description="治理类")
    system_enabled: Optional[bool] = Field(None, description="系统类")
    digest_time: Optional[str] = Field(None, description="每日摘要投递时间 HH:MM（05:00-23:00）")
    email_enabled: Optional[bool] = Field(None, description="是否同步邮件通知")


def _to_response(pref: NotificationPreference) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse(
        instant_enabled=pref.instant_enabled,
        site_digest_enabled=pref.site_digest_enabled,
        subscription_enabled=pref.subscription_enabled,
        interaction_enabled=pref.interaction_enabled,
        audit_enabled=pref.audit_enabled,
        governance_enabled=pref.governance_enabled,
        system_enabled=pref.system_enabled,
        digest_time=pref.digest_time,
        email_enabled=pref.email_enabled,
    )


def _validate_digest_time(value: str) -> str:
    """校验 HH:MM 格式，小时 05-23，分钟 00/30（保持简单，仅校验格式与范围）"""
    if not value or len(value) != 5 or value[2] != ':':
        raise BadRequestException(detail="digest_time 必须为 HH:MM 格式")
    try:
        h, m = int(value[:2]), int(value[3:])
    except ValueError:
        raise BadRequestException(detail="digest_time 必须为 HH:MM 格式")
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise BadRequestException(detail="digest_time 时间范围错误")
    return f"{h:02d}:{m:02d}"


@router.get(
    "/notifications/preferences",
    response_model=NotificationPreferenceResponse,
    summary="UX-01.5: 获取当前用户通知偏好",
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户通知偏好

    首次访问时自动 upsert 默认偏好（全部开启，digest_time=09:00）。
    通知偏好按 user_id 隔离，不区分学校。
    """
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        # 首次访问：写入默认偏好
        pref = NotificationPreference(user_id=current_user.id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return _to_response(pref)


@router.put(
    "/notifications/preferences",
    response_model=NotificationPreferenceResponse,
    summary="UX-01.5: 更新当前用户通知偏好",
)
async def update_notification_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户通知偏好

    安全账号通知不可全关：若 system/audit 全部关闭且 instant 也关闭，后端拒绝（422）。
    """
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == current_user.id
        )
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=current_user.id)
        db.add(pref)

    # 逐字段更新（仅更新请求中提供的字段）
    if payload.instant_enabled is not None:
        pref.instant_enabled = payload.instant_enabled
    if payload.site_digest_enabled is not None:
        pref.site_digest_enabled = payload.site_digest_enabled
    if payload.subscription_enabled is not None:
        pref.subscription_enabled = payload.subscription_enabled
    if payload.interaction_enabled is not None:
        pref.interaction_enabled = payload.interaction_enabled
    if payload.audit_enabled is not None:
        pref.audit_enabled = payload.audit_enabled
    if payload.governance_enabled is not None:
        pref.governance_enabled = payload.governance_enabled
    if payload.system_enabled is not None:
        pref.system_enabled = payload.system_enabled
    if payload.digest_time is not None:
        pref.digest_time = _validate_digest_time(payload.digest_time)
    if payload.email_enabled is not None:
        pref.email_enabled = payload.email_enabled

    # 安全账号通知不可全关：system/audit 全关 + instant 也关时拒绝
    # 即：保证至少有一个安全通道（instant 站内通知）
    if (
        not pref.system_enabled
        and not pref.audit_enabled
        and not pref.instant_enabled
    ):
        raise BadRequestException(
            detail="安全账号通知（system/audit）不可全部关闭，至少保留站内即时通知"
        )

    await db.commit()
    await db.refresh(pref)
    return _to_response(pref)
