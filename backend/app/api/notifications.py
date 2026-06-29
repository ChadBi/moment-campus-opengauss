from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.common import PaginatedResponse, MessageResponse
from app.core.exceptions import NotFoundException, ForbiddenException

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


@router.get("/notifications", response_model=PaginatedResponse[NotificationResponse])
async def get_notifications(
    type: Optional[str] = Query(None, description="通知类型"),
    is_read: Optional[bool] = Query(None, description="是否已读"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取通知列表
    支持按类型和已读状态筛选，分页返回
    """
    # 构建基础查询
    query = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_deleted == False
    )

    # 筛选条件
    if type:
        query = query.where(Notification.type == type)
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)

    # 排序（最新的在前）
    query = query.order_by(Notification.created_at.desc())

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询
    result = await db.execute(query)
    notifications = result.scalars().all()

    # 获取操作者信息
    items = []
    for notification in notifications:
        actor_name = None
        actor_avatar = None
        if notification.actor_id:
            actor_query = select(User).where(User.id == notification.actor_id)
            actor_result = await db.execute(actor_query)
            actor = actor_result.scalar_one_or_none()
            if actor:
                actor_name = actor.nickname
                actor_avatar = actor.avatar_url

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
):
    """
    标记单个通知已读
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
):
    """
    标记所有通知已读
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
