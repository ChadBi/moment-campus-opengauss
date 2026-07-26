"""SUB-01.1: 用户级内容订阅 API（分类/地点/专题）

端点：
- GET    /api/v1/subscriptions                 当前用户在当前学校的订阅列表
- POST   /api/v1/subscriptions                 创建订阅（订阅某分类/地点/专题）
- DELETE /api/v1/subscriptions/{subscription_id}  取消订阅
- GET    /api/v1/subscriptions/check            检查当前用户是否已订阅某目标（前端按钮状态用）
- GET    /api/v1/subscriptions/targets          按目标聚合：返回当前用户已订阅的
                                                   category/location/topic ID 列表（前端批量渲染用）

设计要点：
1. 订阅与通知严格按学校隔离：school_id 强制使用 TenantContext 解析的学校，
   跨校订阅不可见，跨校通知不触发。
2. 唯一约束：(user_id, school_id, target_type, target_id) —— 同一用户在同一学校
   对同一目标只能订阅一次；重复订阅返回 409 Conflict。
3. target_type 必须为 category/location/topic 之一；target_id 必须属于当前学校，
   否则 404（不泄露存在性）。
4. 创建/删除/查看均需登录；游客 → 401（由 get_current_user 拦截）。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.subscription import UserSubscription
from app.models.category import Category
from app.models.location import Location
from app.models.topic_collection import TopicCollection
from app.schemas.common import MessageResponse, PaginatedResponse
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ConflictException,
)
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant

router = APIRouter(prefix="/subscriptions", tags=["订阅"])


# ============================================================
# Schemas
# ============================================================

class SubscriptionTargetType(str):
    """target_type 合法值常量"""
    CATEGORY = "category"
    LOCATION = "location"
    TOPIC = "topic"
    ALL = ("category", "location", "topic")


class SubscriptionCreate(BaseModel):
    """创建订阅请求

    school_id 字段不接受，强制由 TenantContext 决定（TEN-02.1）。
    """
    target_type: str = Field(
        ...,
        description="订阅目标类型：category / location / topic",
    )
    target_id: int = Field(..., ge=1, description="目标 ID")

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v: str) -> str:
        if v not in SubscriptionTargetType.ALL:
            raise ValueError(
                "target_type 必须为 category / location / topic 之一"
            )
        return v


class SubscriptionResponse(BaseModel):
    """订阅响应"""
    id: int
    user_id: int
    school_id: int
    target_type: str
    target_id: int
    target_name: Optional[str] = Field(
        None, description="目标名称（便于前端展示，由后端 join 查询填入）"
    )
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionCheckResponse(BaseModel):
    """订阅状态检查响应（前端按钮状态用）"""
    subscribed: bool
    subscription_id: Optional[int] = None


class SubscriptionTargetsResponse(BaseModel):
    """当前用户已订阅的目标 ID 列表（按 target_type 分组）"""
    category: List[int] = Field(default_factory=list)
    location: List[int] = Field(default_factory=list)
    topic: List[int] = Field(default_factory=list)


# ============================================================
# 辅助函数
# ============================================================

async def _validate_target_in_tenant(
    db: AsyncSession,
    target_type: str,
    target_id: int,
    tenant: TenantContext,
) -> str:
    """校验订阅目标属于当前学校，返回目标名称（用于响应展示）

    Raises:
        NotFoundException: 目标不存在或跨校 → 404（不泄露存在性）
    """
    if target_type == SubscriptionTargetType.CATEGORY:
        result = await db.execute(
            select(Category).where(Category.id == target_id)
        )
        target = result.scalar_one_or_none()
        if target is None:
            raise NotFoundException(detail="分类不存在")
        check_resource_in_tenant(target.school_id, tenant)
        return target.name
    elif target_type == SubscriptionTargetType.LOCATION:
        result = await db.execute(
            select(Location).where(
                Location.id == target_id,
                Location.is_deleted == False,  # noqa: E712
            )
        )
        target = result.scalar_one_or_none()
        if target is None:
            raise NotFoundException(detail="地点不存在")
        check_resource_in_tenant(target.school_id, tenant)
        return target.name
    elif target_type == SubscriptionTargetType.TOPIC:
        result = await db.execute(
            select(TopicCollection).where(
                TopicCollection.id == target_id,
                TopicCollection.is_deleted == False,  # noqa: E712
            )
        )
        target = result.scalar_one_or_none()
        if target is None:
            raise NotFoundException(detail="专题不存在")
        check_resource_in_tenant(target.school_id, tenant)
        return target.title
    else:
        raise BadRequestException(
            detail="target_type 必须为 category / location / topic 之一"
        )


async def _enrich_with_target_name(
    db: AsyncSession, items: List[UserSubscription]
) -> List[SubscriptionResponse]:
    """批量补全订阅项的目标名称（避免 N+1：按 target_type 分组一次性查询）"""
    if not items:
        return []

    # 按 target_type 分组收集 id
    by_type: dict[str, list[int]] = {"category": [], "location": [], "topic": []}
    for it in items:
        if it.target_type in by_type:
            by_type[it.target_type].append(it.target_id)

    name_map: dict[tuple[str, int], str] = {}

    # 一次性查询各类型目标名称
    if by_type["category"]:
        rows = await db.execute(
            select(Category.id, Category.name).where(Category.id.in_(by_type["category"]))
        )
        for tid, name in rows.all():
            name_map[("category", tid)] = name

    if by_type["location"]:
        rows = await db.execute(
            select(Location.id, Location.name).where(Location.id.in_(by_type["location"]))
        )
        for tid, name in rows.all():
            name_map[("location", tid)] = name

    if by_type["topic"]:
        rows = await db.execute(
            select(TopicCollection.id, TopicCollection.title).where(
                TopicCollection.id.in_(by_type["topic"])
            )
        )
        for tid, name in rows.all():
            name_map[("topic", tid)] = name

    return [
        SubscriptionResponse(
            id=it.id,
            user_id=it.user_id,
            school_id=it.school_id,
            target_type=it.target_type,
            target_id=it.target_id,
            target_name=name_map.get((it.target_type, it.target_id)),
            created_at=it.created_at,
        )
        for it in items
    ]


# ============================================================
# API 端点
# ============================================================

@router.get(
    "",
    response_model=PaginatedResponse[SubscriptionResponse],
    summary="获取我的订阅列表",
)
async def list_my_subscriptions(
    target_type: Optional[str] = Query(
        default=None,
        description="按目标类型筛选：category / location / topic",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取当前用户在当前学校的订阅列表

    TEN-02.3: 按当前学校过滤，跨校订阅不出现。
    支持 target_type 筛选与分页。
    """
    base_filter = (
        UserSubscription.user_id == current_user.id,
        UserSubscription.school_id == tenant.school_id,
    )

    query = select(UserSubscription).where(*base_filter)
    if target_type:
        if target_type not in SubscriptionTargetType.ALL:
            raise BadRequestException(
                detail="target_type 必须为 category / location / topic 之一"
            )
        query = query.where(UserSubscription.target_type == target_type)

    # 总数
    count_query = select(func.count()).select_from(UserSubscription).where(*base_filter)
    if target_type:
        count_query = count_query.where(UserSubscription.target_type == target_type)
    total = await db.scalar(count_query) or 0

    # 分页 + 排序（最新订阅在前）
    offset = (page - 1) * page_size
    query = (
        query.order_by(UserSubscription.created_at.desc(), UserSubscription.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    items = list(result.scalars().all())

    enriched = await _enrich_with_target_name(db, items)
    return PaginatedResponse.create(enriched, page, page_size, total)


@router.get(
    "/targets",
    response_model=SubscriptionTargetsResponse,
    summary="获取当前用户已订阅的目标 ID 列表（按类型分组）",
)
async def list_my_subscription_targets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """一次性返回当前用户在当前学校已订阅的全部目标 ID（按 target_type 分组）

    前端用于在分类/地点/专题列表/详情页批量渲染订阅按钮状态。
    """
    result = await db.execute(
        select(UserSubscription.target_type, UserSubscription.target_id).where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.school_id == tenant.school_id,
        )
    )
    resp = SubscriptionTargetsResponse()
    for ttype, tid in result.all():
        if ttype == SubscriptionTargetType.CATEGORY:
            resp.category.append(tid)
        elif ttype == SubscriptionTargetType.LOCATION:
            resp.location.append(tid)
        elif ttype == SubscriptionTargetType.TOPIC:
            resp.topic.append(tid)
    return resp


@router.get(
    "/check",
    response_model=SubscriptionCheckResponse,
    summary="检查是否已订阅某目标",
)
async def check_subscription(
    target_type: str = Query(..., description="目标类型：category / location / topic"),
    target_id: int = Query(..., ge=1, description="目标 ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """检查当前用户是否已订阅某目标（前端按钮状态用）

    跨校查询恒返回 subscribed=false（不泄露存在性）。
    """
    if target_type not in SubscriptionTargetType.ALL:
        raise BadRequestException(
            detail="target_type 必须为 category / location / topic 之一"
        )

    result = await db.execute(
        select(UserSubscription.id).where(
            UserSubscription.user_id == current_user.id,
            UserSubscription.school_id == tenant.school_id,
            UserSubscription.target_type == target_type,
            UserSubscription.target_id == target_id,
        ).limit(1)
    )
    sid = result.scalar_one_or_none()
    return SubscriptionCheckResponse(
        subscribed=sid is not None,
        subscription_id=sid,
    )


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=201,
    summary="订阅目标",
)
async def create_subscription(
    payload: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """订阅某分类/地点/专题

    - school_id 强制由 TenantContext 决定（忽略 body 中任何 school_id 字段）
    - target 必须属于当前学校，跨校 → 404（不泄露存在性）
    - 同用户同校同目标只能订阅一次，唯一约束冲突 → 409 Conflict
    """
    # 1. 校验目标属于当前学校（同时获取目标名称用于响应）
    target_name = await _validate_target_in_tenant(
        db, payload.target_type, payload.target_id, tenant
    )

    # 2. 创建订阅
    sub = UserSubscription(
        user_id=current_user.id,
        school_id=tenant.school_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
    )
    db.add(sub)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictException(detail="已订阅该目标，请勿重复订阅")
    await db.refresh(sub)

    return SubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        school_id=sub.school_id,
        target_type=sub.target_type,
        target_id=sub.target_id,
        target_name=target_name,
        created_at=sub.created_at,
    )


@router.delete(
    "/{subscription_id}",
    response_model=MessageResponse,
    summary="取消订阅",
)
async def delete_subscription(
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """取消订阅（按订阅记录 ID）

    - 仅可删除本人的订阅，他人订阅 → 404（不泄露存在性）
    - 跨校订阅 → 404（不泄露存在性）
    """
    result = await db.execute(
        select(UserSubscription).where(UserSubscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise NotFoundException(detail="订阅不存在")
    # 资源级租户 + 所有权双重校验
    if sub.user_id != current_user.id:
        raise NotFoundException(detail="订阅不存在")
    check_resource_in_tenant(sub.school_id, tenant)

    await db.delete(sub)
    await db.commit()
    return MessageResponse(message="已取消订阅")
