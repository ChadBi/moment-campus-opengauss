"""COM-01.4 + TEN-04 平台级路由（super_admin 专用）。

仅 super_admin 可访问，用于：
- 给学校分配/续期套餐
- 查看全平台订阅列表
- 修改订阅状态（续期/暂停）
- 查看套餐及权益项字典
- TEN-04.1：平台学校管理（创建/列表/详情/启停 + 完整初始化）
- TEN-04.2：开通清单 + 暂停恢复
- TEN-04.3：平台审计日志

所有写操作记录旧值/新值/原因/操作者到 note 字段，并写入 platform_audit_logs。
"""
from datetime import datetime
from typing import Optional, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import require_role, Role
from app.core.exceptions import (
    BadRequestException, NotFoundException, ConflictException,
)
from app.core.entitlement import EntitlementService, EntitlementKey
from app.database import get_db
from app.models.product_plan import ProductPlan
from app.models.plan_entitlement import PlanEntitlement
from app.models.school_subscription import SchoolSubscription
from app.models.school import School
from app.models.school_settings import SchoolSettings
from app.models.school_invitation import SchoolInvitation
from app.models.school_membership import SchoolMembership
from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.tenant_usage_daily import TenantUsageDaily
from app.models.user import User
from app.models.platform_audit import PlatformAuditLog
from app.models.ai_invocation_log import AIInvocationLog
from app.models.report import Report
from app.models.job_run_record import JobRunRecord
from app.services.school_provisioning import (
    SchoolProvisioningService,
    SchoolProvisionRequest,
    SchoolBatchImportService,
    build_activation_funnel,
    write_platform_audit,
)


router = APIRouter(prefix="/platform", tags=["平台管理"])


# ============================================================
# Schemas
# ============================================================
class PlanBrief(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    status: str
    sort_order: int


class PlanEntitlementBrief(BaseModel):
    id: int
    plan_id: int
    key: str
    limit_value: Optional[int] = None
    is_hard: bool
    description: Optional[str] = None


class PlanDetail(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    status: str
    sort_order: int
    entitlements: list[PlanEntitlementBrief] = Field(default_factory=list)


class SubscriptionBrief(BaseModel):
    id: int
    school_id: int
    plan_id: int
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    status: str
    started_at: datetime
    expires_at: Optional[datetime] = None
    assigned_by: Optional[int] = None
    assigned_at: datetime
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SubscriptionAssignRequest(BaseModel):
    """分配/续期套餐请求。"""
    plan_code: str = Field(..., description="套餐代码（trial/standard/operations）")
    expires_at: Optional[datetime] = Field(None, description="到期时间；NULL 表示不限")
    note: Optional[str] = Field(None, description="操作备注（原因/旧值/新值）")


class SubscriptionUpdateRequest(BaseModel):
    """续期/暂停/恢复请求。"""
    status: Optional[str] = Field(
        None, description="目标状态：active/expired/suspended；不传则只更新 expires_at/note"
    )
    expires_at: Optional[datetime] = Field(None, description="新到期时间；不传保留原值")
    note: Optional[str] = Field(None, description="操作备注")


# ============================================================
# Routes
# ============================================================
@router.get("/plans", response_model=list[PlanDetail], summary="套餐及权益字典")
async def list_plans(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """列出全部套餐及其权益项（super_admin）。"""
    stmt = (
        select(ProductPlan)
        .options(selectinload(ProductPlan.entitlements))
        .order_by(ProductPlan.sort_order)
    )
    result = await db.execute(stmt)
    plans = result.scalars().all()
    return [
        PlanDetail(
            id=p.id,
            code=p.code,
            name=p.name,
            description=p.description,
            status=p.status,
            sort_order=p.sort_order,
            entitlements=[
                PlanEntitlementBrief(
                    id=e.id, plan_id=e.plan_id, key=e.key,
                    limit_value=e.limit_value, is_hard=e.is_hard,
                    description=e.description,
                )
                for e in p.entitlements
            ],
        )
        for p in plans
    ]


@router.get("/subscriptions", summary="订阅列表（分页）")
async def list_subscriptions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    school_id: Optional[int] = Query(None, description="按学校筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """列出全平台学校订阅（super_admin，分页）。"""
    stmt = select(SchoolSubscription).options(
        selectinload(SchoolSubscription.plan),
    )
    if school_id is not None:
        stmt = stmt.where(SchoolSubscription.school_id == school_id)
    if status is not None:
        stmt = stmt.where(SchoolSubscription.status == status)

    # 总数
    count_stmt = select(func.count()).select_from(
        select(SchoolSubscription).subquery()
    )
    if school_id is not None:
        count_stmt = select(func.count()).select_from(
            select(SchoolSubscription).where(SchoolSubscription.school_id == school_id).subquery()
        )
        if status is not None:
            count_stmt = select(func.count()).select_from(
                select(SchoolSubscription).where(
                    SchoolSubscription.school_id == school_id,
                    SchoolSubscription.status == status,
                ).subquery()
            )
    elif status is not None:
        count_stmt = select(func.count()).select_from(
            select(SchoolSubscription).where(
                SchoolSubscription.status == status
            ).subquery()
        )

    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(SchoolSubscription.assigned_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    subs = result.scalars().all()

    items = [
        SubscriptionBrief(
            id=s.id, school_id=s.school_id, plan_id=s.plan_id,
            plan_code=s.plan.code if s.plan else None,
            plan_name=s.plan.name if s.plan else None,
            status=s.status, started_at=s.started_at,
            expires_at=s.expires_at, assigned_by=s.assigned_by,
            assigned_at=s.assigned_at, note=s.note,
            created_at=s.created_at, updated_at=s.updated_at,
        ).model_dump()
        for s in subs
    ]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        "has_more": page * page_size < total,
    }


@router.post(
    "/schools/{school_id}/subscription",
    response_model=SubscriptionBrief,
    summary="分配/续期套餐",
)
async def assign_subscription(
    school_id: int,
    body: SubscriptionAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """给学校分配新订阅或续期当前订阅（super_admin）。

    业务规则：
    1. 学校必须存在
    2. 套餐 code 必须存在且为 active
    3. 若学校已有 active 订阅：
       - 旧订阅置 expired（记入 note）
       - 创建新 active 订阅
       note 记录：旧套餐/旧到期/新套餐/新到期/操作者/原因
    4. 若无 active 订阅：直接创建新订阅
    """
    # 1. 校验学校存在
    school = (await db.execute(select(School).where(School.id == school_id))).scalar_one_or_none()
    if school is None:
        raise NotFoundException(detail="学校不存在")

    # 2. 校验套餐存在且 active
    plan = (await db.execute(
        select(ProductPlan).where(ProductPlan.code == body.plan_code)
    )).scalar_one_or_none()
    if plan is None:
        raise BadRequestException(detail=f"套餐 code='{body.plan_code}' 不存在")
    if plan.status != "active":
        raise BadRequestException(detail=f"套餐 '{body.plan_code}' 当前状态为 {plan.status}，不可分配")

    # 3. 查找已有 active 订阅
    existing = (await db.execute(
        select(SchoolSubscription).options(selectinload(SchoolSubscription.plan))
        .where(
            SchoolSubscription.school_id == school_id,
            SchoolSubscription.status == "active",
        ).order_by(SchoolSubscription.assigned_at.desc()).limit(1)
    )).scalar_one_or_none()

    now = datetime.now()
    note_parts: list[str] = []
    if existing is not None:
        # 旧订阅标记 expired
        old_plan_code = existing.plan.code if existing.plan else f"plan#{existing.plan_id}"
        note_parts.append(
            f"旧订阅 id={existing.id} (plan={old_plan_code}, "
            f"expires_at={existing.expires_at.isoformat() if existing.expires_at else 'NULL'}) "
            f"由 super_admin(id={current_user.id}) 续期至新套餐 {body.plan_code}"
        )
        existing.status = "expired"
        existing.updated_at = now
        if existing.note:
            existing.note = f"{existing.note}\n[续期] {note_parts[-1]}"
        else:
            existing.note = note_parts[-1]
        await db.flush()

    # 4. 创建新订阅
    new_note = body.note or ""
    if note_parts:
        new_note = (new_note + ("\n" if new_note else "")) + "\n".join(note_parts)

    new_sub = SchoolSubscription(
        school_id=school_id,
        plan_id=plan.id,
        status="active",
        started_at=now,
        expires_at=body.expires_at,
        assigned_by=current_user.id,
        assigned_at=now,
        note=new_note or None,
    )
    db.add(new_sub)
    # TEN-04.3：写入平台审计日志（分配/续期套餐）
    await write_platform_audit(
        db,
        operator_id=current_user.id,
        target_school_id=school_id,
        action="subscription.assign",
        old_value=(
            {"subscription_id": existing.id, "plan_code": old_plan_code,
             "expires_at": existing.expires_at.isoformat() if existing.expires_at else None}
            if existing is not None else None
        ),
        new_value={
            "subscription_id": None, "plan_code": body.plan_code,
            "expires_at": body.expires_at.isoformat() if body.expires_at else None,
        },
        reason=body.note,
    )
    await db.commit()
    await db.refresh(new_sub, attribute_names=["plan"])

    return SubscriptionBrief(
        id=new_sub.id, school_id=new_sub.school_id, plan_id=new_sub.plan_id,
        plan_code=new_sub.plan.code if new_sub.plan else None,
        plan_name=new_sub.plan.name if new_sub.plan else None,
        status=new_sub.status, started_at=new_sub.started_at,
        expires_at=new_sub.expires_at, assigned_by=new_sub.assigned_by,
        assigned_at=new_sub.assigned_at, note=new_sub.note,
        created_at=new_sub.created_at, updated_at=new_sub.updated_at,
    )


@router.put(
    "/subscriptions/{subscription_id}",
    response_model=SubscriptionBrief,
    summary="续期/暂停/恢复订阅",
)
async def update_subscription(
    subscription_id: int,
    body: SubscriptionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """更新订阅（续期 / 暂停 / 恢复）（super_admin）。

    - 续期：仅更新 expires_at
    - 暂停：status='suspended'
    - 恢复：status='active'（若已 expired，需走分配接口而非本接口）
    """
    sub = (await db.execute(
        select(SchoolSubscription).options(selectinload(SchoolSubscription.plan))
        .where(SchoolSubscription.id == subscription_id)
    )).scalar_one_or_none()
    if sub is None:
        raise NotFoundException(detail="订阅不存在")

    # 校验目标状态合法
    valid_statuses = {"active", "expired", "suspended"}
    if body.status is not None and body.status not in valid_statuses:
        raise BadRequestException(
            detail=f"非法 status='{body.status}'，允许值：{sorted(valid_statuses)}"
        )

    # 不允许直接通过本接口把 expired 改回 active（应走分配接口）
    if sub.status == "expired" and body.status == "active":
        raise BadRequestException(
            detail="已过期订阅不可直接恢复为 active，请走 POST /platform/schools/{school_id}/subscription 重新分配"
        )

    now = datetime.now()
    old_status = sub.status
    old_expires = sub.expires_at

    if body.status is not None:
        sub.status = body.status
    if body.expires_at is not None:
        sub.expires_at = body.expires_at
    sub.assigned_by = current_user.id
    sub.assigned_at = now

    note_append = (
        f"[update] 操作者 super_admin(id={current_user.id}) "
        f"旧状态={old_status} 新状态={sub.status} "
        f"旧到期={old_expires.isoformat() if old_expires else 'NULL'} "
        f"新到期={sub.expires_at.isoformat() if sub.expires_at else 'NULL'}"
    )
    if body.note:
        note_append += f" 备注={body.note}"
    if sub.note:
        sub.note = f"{sub.note}\n{note_append}"
    else:
        sub.note = note_append
    sub.updated_at = now

    # TEN-04.3：写入平台审计日志（续期/暂停/恢复订阅）
    await write_platform_audit(
        db,
        operator_id=current_user.id,
        target_school_id=sub.school_id,
        action="subscription.update",
        old_value={
            "subscription_id": sub.id, "status": old_status,
            "expires_at": old_expires.isoformat() if old_expires else None,
        },
        new_value={
            "subscription_id": sub.id, "status": sub.status,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        },
        reason=body.note,
    )
    await db.commit()
    await db.refresh(sub, attribute_names=["plan"])

    return SubscriptionBrief(
        id=sub.id, school_id=sub.school_id, plan_id=sub.plan_id,
        plan_code=sub.plan.code if sub.plan else None,
        plan_name=sub.plan.name if sub.plan else None,
        status=sub.status, started_at=sub.started_at,
        expires_at=sub.expires_at, assigned_by=sub.assigned_by,
        assigned_at=sub.assigned_at, note=sub.note,
        created_at=sub.created_at, updated_at=sub.updated_at,
    )


# ============================================================
# TEN-04.1 + TEN-04.2 + TEN-04.3：平台学校管理 + 开通清单 + 审计
# ============================================================
class SchoolCreateRequest(BaseModel):
    """创建学校请求。"""
    code: str = Field(..., min_length=2, max_length=20, description="学校 code（唯一）")
    name: str = Field(..., min_length=2, max_length=100, description="学校名称")
    center_lat: Optional[float] = Field(None, description="地图中心纬度")
    center_lng: Optional[float] = Field(None, description="地图中心经度")
    map_zoom: Optional[int] = Field(None, ge=1, le=20, description="地图缩放级别，默认 16")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    brand_color: Optional[str] = Field(None, description="主题色（如 #1890ff）")
    description: Optional[str] = Field(None, description="学校简介")
    admin_email: Optional[str] = Field(None, description="首位管理员邀请邮箱")
    plan_code: Optional[str] = Field(None, description="默认套餐 code，默认 trial")
    province: Optional[str] = Field(None)
    city: Optional[str] = Field(None)
    address: Optional[str] = Field(None)


class SchoolStatusUpdateRequest(BaseModel):
    """启用/暂停学校请求。"""
    is_active: bool = Field(..., description="目标状态：true=启用 / false=暂停")
    reason: Optional[str] = Field(None, description="操作原因")


class SchoolBrief(BaseModel):
    """学校列表项（含订阅/激活状态/成员数/内容数）。"""
    id: int
    code: str
    name: str
    logo_url: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    map_zoom: Optional[int] = None
    province: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # 聚合字段
    member_count: int = 0
    post_count: int = 0
    category_count: int = 0
    # 订阅摘要
    subscription_status: Optional[str] = None
    subscription_plan_code: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None


class SchoolDetail(SchoolBrief):
    """学校详情（含开通清单状态）。"""
    description: Optional[str] = None
    brand_color: Optional[str] = None
    # 开通清单（TEN-04.2）
    checklist: dict = Field(default_factory=dict, description="开通清单各项 bool")


class SchoolCreateResponse(BaseModel):
    """创建学校响应。"""
    school: dict
    settings: dict
    invitation: Optional[dict] = None
    subscription: Optional[dict] = None
    categories_copied: int = 0
    audit_id: Optional[int] = None


class PlatformAuditBrief(BaseModel):
    """平台审计日志项。"""
    id: int
    operator_id: Optional[int] = None
    target_school_id: Optional[int] = None
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


def _client_meta(request: Request) -> tuple[Optional[str], Optional[str]]:
    """从 Request 提取 IP 与 UA（用于审计）。"""
    ip = None
    if request:
        ip = request.client.host if request.client else None
        # 兼容反向代理
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            ip = fwd.split(",")[0].strip()
    ua = request.headers.get("user-agent") if request else None
    return ip, ua


@router.post(
    "/schools",
    response_model=SchoolCreateResponse,
    summary="创建学校（super_admin，完整初始化）",
)
async def create_school(
    body: SchoolCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """创建学校并完成完整初始化（super_admin）。

    自动完成：
    1. 创建 School 行
    2. 从江南大学复制默认分类
    3. 创建 SchoolSettings 默认行
    4. 创建首位管理员邀请（若提供 admin_email）
    5. 分配默认套餐（trial 或指定 plan_code）
    6. 写入平台审计日志（action=school.create）
    """
    svc = SchoolProvisioningService(db)
    req = SchoolProvisionRequest(
        code=body.code,
        name=body.name,
        center_lat=body.center_lat,
        center_lng=body.center_lng,
        map_zoom=body.map_zoom,
        logo_url=body.logo_url,
        brand_color=body.brand_color,
        description=body.description,
        admin_email=body.admin_email,
        plan_code=body.plan_code,
        province=body.province,
        city=body.city,
        address=body.address,
    )
    result = await svc.create_school(req, operator_id=current_user.id)

    school = result["school"]
    settings = result["settings"]
    invitation = result["invitation"]
    subscription = result["subscription"]
    categories_copied = result["categories_copied"]

    # TEN-04.3：写入平台审计日志
    ip, ua = _client_meta(request)
    new_value = {
        "school_id": school.id, "code": school.code, "name": school.name,
        "plan_code": body.plan_code or "trial",
        "categories_copied": categories_copied,
        "invitation_created": invitation is not None,
    }
    await write_platform_audit(
        db,
        operator_id=current_user.id,
        target_school_id=school.id,
        action="school.create",
        old_value=None,
        new_value=new_value,
        reason=f"super_admin 创建学校 {school.code}",
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()

    # 重新刷新以拿到 created_at 等字段
    await db.refresh(school)
    await db.refresh(settings)
    if invitation is not None:
        await db.refresh(invitation)
    if subscription is not None:
        await db.refresh(subscription, attribute_names=["plan"])

    # 查询刚写的审计 id
    audit_row = (await db.execute(
        select(PlatformAuditLog).where(
            PlatformAuditLog.operator_id == current_user.id,
            PlatformAuditLog.action == "school.create",
            PlatformAuditLog.target_school_id == school.id,
        ).order_by(PlatformAuditLog.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    return SchoolCreateResponse(
        school={
            "id": school.id, "code": school.code, "name": school.name,
            "center_lat": school.center_lat, "center_lng": school.center_lng,
            "map_zoom": school.map_zoom, "logo_url": school.logo_url,
            "is_active": school.is_active,
            "created_at": school.created_at, "updated_at": school.updated_at,
        },
        settings={
            "school_id": settings.school_id, "site_name": settings.site_name,
            "description": settings.description, "brand_color": settings.brand_color,
            "logo_url": settings.logo_url,
        },
        invitation=(
            {
                "id": invitation.id, "school_id": invitation.school_id,
                "email": invitation.email, "role": invitation.role,
                "invitation_code": invitation.invitation_code,
                "status": invitation.status, "created_at": invitation.created_at,
            }
            if invitation is not None else None
        ),
        subscription=(
            {
                "id": subscription.id, "school_id": subscription.school_id,
                "plan_id": subscription.plan_id,
                "plan_code": subscription.plan.code if subscription.plan else None,
                "status": subscription.status, "started_at": subscription.started_at,
                "expires_at": subscription.expires_at,
            }
            if subscription is not None else None
        ),
        categories_copied=categories_copied,
        audit_id=audit_row.id if audit_row is not None else None,
    )


@router.get(
    "/schools",
    summary="平台学校列表（含订阅/激活状态/成员数/内容数）",
)
async def list_schools(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_active: Optional[bool] = Query(None, description="按激活状态筛选"),
    keyword: Optional[str] = Query(None, description="按名称/code 模糊搜索"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """列出全平台学校（super_admin，分页）。"""
    stmt = select(School)
    if is_active is not None:
        stmt = stmt.where(School.is_active == is_active)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((School.name.ilike(like)) | (School.code.ilike(like)))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(School.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    schools = (await db.execute(stmt)).scalars().all()

    if not schools:
        return {
            "items": [], "page": page, "page_size": page_size,
            "total": int(total),
            "total_pages": (int(total) + page_size - 1) // page_size if page_size > 0 else 0,
            "has_more": page * page_size < int(total),
        }

    school_ids = [s.id for s in schools]

    # 聚合成员数
    member_counts = dict((await db.execute(
        select(SchoolMembership.school_id, func.count())
        .where(SchoolMembership.school_id.in_(school_ids),
               SchoolMembership.status == "active")
        .group_by(SchoolMembership.school_id)
    )).all())
    # 聚合帖子数
    post_counts = dict((await db.execute(
        select(Post.school_id, func.count())
        .where(Post.school_id.in_(school_ids),
               Post.is_deleted == False)  # noqa: E712
        .group_by(Post.school_id)
    )).all())
    # 聚合分类数
    cat_counts = dict((await db.execute(
        select(Category.school_id, func.count())
        .where(Category.school_id.in_(school_ids))
        .group_by(Category.school_id)
    )).all())
    # 最新 active 订阅
    sub_rows = (await db.execute(
        select(SchoolSubscription)
        .options(selectinload(SchoolSubscription.plan))
        .where(SchoolSubscription.school_id.in_(school_ids),
               SchoolSubscription.status == "active")
    )).scalars().all()
    sub_map = {s.school_id: s for s in sub_rows}

    items = [
        SchoolBrief(
            id=s.id, code=s.code, name=s.name, logo_url=s.logo_url,
            center_lat=s.center_lat, center_lng=s.center_lng, map_zoom=s.map_zoom,
            province=s.province, city=s.city, address=s.address,
            is_active=s.is_active, created_at=s.created_at, updated_at=s.updated_at,
            member_count=int(member_counts.get(s.id, 0)),
            post_count=int(post_counts.get(s.id, 0)),
            category_count=int(cat_counts.get(s.id, 0)),
            subscription_status=(sub_map[s.id].status if s.id in sub_map else None),
            subscription_plan_code=(
                sub_map[s.id].plan.code if s.id in sub_map and sub_map[s.id].plan else None
            ),
            subscription_expires_at=(sub_map[s.id].expires_at if s.id in sub_map else None),
        ).model_dump()
        for s in schools
    ]
    return {
        "items": items, "page": page, "page_size": page_size,
        "total": int(total),
        "total_pages": (int(total) + page_size - 1) // page_size if page_size > 0 else 0,
        "has_more": page * page_size < int(total),
    }


@router.get(
    "/schools/{school_id}",
    response_model=SchoolDetail,
    summary="学校详情（含开通清单状态）",
)
async def get_school_detail(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """获取学校详情（含订阅/聚合/开通清单）（super_admin）。"""
    school = (await db.execute(
        select(School).where(School.id == school_id)
    )).scalar_one_or_none()
    if school is None:
        raise NotFoundException(detail="学校不存在")

    # 订阅
    sub = (await db.execute(
        select(SchoolSubscription).options(selectinload(SchoolSubscription.plan))
        .where(SchoolSubscription.school_id == school_id,
               SchoolSubscription.status == "active")
        .order_by(SchoolSubscription.assigned_at.desc()).limit(1)
    )).scalar_one_or_none()

    # 聚合
    member_count = (await db.execute(
        select(func.count()).select_from(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.status == "active",
        )
    )).scalar() or 0
    post_count = (await db.execute(
        select(func.count()).select_from(Post).where(
            Post.school_id == school_id,
            Post.is_deleted == False,  # noqa: E712
        )
    )).scalar() or 0
    cat_count = (await db.execute(
        select(func.count()).select_from(Category).where(Category.school_id == school_id)
    )).scalar() or 0

    # 开通清单
    svc = SchoolProvisioningService(db)
    checklist = await svc.get_provisioning_checklist(school_id)

    # settings（取 description / brand_color）
    settings = (await db.execute(
        select(SchoolSettings).where(SchoolSettings.school_id == school_id)
    )).scalar_one_or_none()

    return SchoolDetail(
        id=school.id, code=school.code, name=school.name, logo_url=school.logo_url,
        center_lat=school.center_lat, center_lng=school.center_lng, map_zoom=school.map_zoom,
        province=school.province, city=school.city, address=school.address,
        is_active=school.is_active, created_at=school.created_at, updated_at=school.updated_at,
        member_count=int(member_count), post_count=int(post_count),
        category_count=int(cat_count),
        subscription_status=(sub.status if sub else None),
        subscription_plan_code=(sub.plan.code if sub and sub.plan else None),
        subscription_expires_at=(sub.expires_at if sub else None),
        description=(settings.description if settings else None),
        brand_color=(settings.brand_color if settings else None),
        checklist=checklist.to_dict(),
    )


@router.put(
    "/schools/{school_id}/status",
    response_model=SchoolBrief,
    summary="启用/暂停学校",
)
async def update_school_status(
    school_id: int,
    body: SchoolStatusUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """启用/暂停学校（super_admin）。

    - 暂停后 is_active=false：所有写接口由 app/core/tenant.py 在解析阶段
      拒绝（inactive → 404 "学校不存在或已停用"），同时 platform 层
      SchoolProvisioningService.assert_school_writable 提供更明确的恢复路径提示。
    - 恢复后 is_active=true：写接口恢复正常。
    - 写入平台审计日志（action=school.suspend / school.reactivate）。
    """
    school = (await db.execute(
        select(School).where(School.id == school_id)
    )).scalar_one_or_none()
    if school is None:
        raise NotFoundException(detail="学校不存在")

    old_active = school.is_active
    if old_active == body.is_active:
        raise BadRequestException(
            detail=f"学校当前 is_active 已为 {old_active}，无需变更"
        )

    school.is_active = body.is_active
    school.updated_at = datetime.now()

    # 聚合（响应 SchoolBrief）
    member_count = (await db.execute(
        select(func.count()).select_from(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.status == "active",
        )
    )).scalar() or 0
    post_count = (await db.execute(
        select(func.count()).select_from(Post).where(
            Post.school_id == school_id,
            Post.is_deleted == False,  # noqa: E712
        )
    )).scalar() or 0
    cat_count = (await db.execute(
        select(func.count()).select_from(Category).where(Category.school_id == school_id)
    )).scalar() or 0
    sub = (await db.execute(
        select(SchoolSubscription).options(selectinload(SchoolSubscription.plan))
        .where(SchoolSubscription.school_id == school_id,
               SchoolSubscription.status == "active")
        .order_by(SchoolSubscription.assigned_at.desc()).limit(1)
    )).scalar_one_or_none()

    # TEN-04.3：审计
    ip, ua = _client_meta(request)
    action = "school.suspend" if not body.is_active else "school.reactivate"
    await write_platform_audit(
        db,
        operator_id=current_user.id,
        target_school_id=school_id,
        action=action,
        old_value={"is_active": old_active},
        new_value={"is_active": body.is_active},
        reason=body.reason,
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    await db.refresh(school)

    return SchoolBrief(
        id=school.id, code=school.code, name=school.name, logo_url=school.logo_url,
        center_lat=school.center_lat, center_lng=school.center_lng, map_zoom=school.map_zoom,
        province=school.province, city=school.city, address=school.address,
        is_active=school.is_active, created_at=school.created_at, updated_at=school.updated_at,
        member_count=int(member_count), post_count=int(post_count),
        category_count=int(cat_count),
        subscription_status=(sub.status if sub else None),
        subscription_plan_code=(sub.plan.code if sub and sub.plan else None),
        subscription_expires_at=(sub.expires_at if sub else None),
    )


@router.get(
    "/audit",
    summary="平台审计日志列表（super_admin）",
)
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: Optional[str] = Query(None, description="按动作类型筛选（如 school.create）"),
    target_school_id: Optional[int] = Query(None, description="按目标学校筛选"),
    operator_id: Optional[int] = Query(None, description="按操作者筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """列出平台审计日志（super_admin，分页）。"""
    stmt = select(PlatformAuditLog)
    if action is not None:
        stmt = stmt.where(PlatformAuditLog.action == action)
    if target_school_id is not None:
        stmt = stmt.where(PlatformAuditLog.target_school_id == target_school_id)
    if operator_id is not None:
        stmt = stmt.where(PlatformAuditLog.operator_id == operator_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(PlatformAuditLog.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    logs = (await db.execute(stmt)).scalars().all()

    items = [
        PlatformAuditBrief(
            id=l.id, operator_id=l.operator_id,
            target_school_id=l.target_school_id, action=l.action,
            old_value=l.old_value, new_value=l.new_value, reason=l.reason,
            ip_address=l.ip_address, user_agent=l.user_agent,
            created_at=l.created_at,
        ).model_dump()
        for l in logs
    ]
    return {
        "items": items, "page": page, "page_size": page_size,
        "total": int(total),
        "total_pages": (int(total) + page_size - 1) // page_size if page_size > 0 else 0,
        "has_more": page * page_size < int(total),
    }


# ============================================================
# COM-02.1：套餐历史变更查询
# ============================================================
@router.get(
    "/schools/{school_id}/subscription-history",
    summary="学校套餐历史变更（super_admin）",
)
async def list_subscription_history(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """列出某学校的全部订阅历史（按 assigned_at 倒序，含 active/expired/suspended）。

    COM-02.1：用于平台后台展示历史变更。
    """
    school = (await db.execute(
        select(School).where(School.id == school_id)
    )).scalar_one_or_none()
    if school is None:
        raise NotFoundException(detail="学校不存在")

    subs = (await db.execute(
        select(SchoolSubscription)
        .options(selectinload(SchoolSubscription.plan))
        .where(SchoolSubscription.school_id == school_id)
        .order_by(SchoolSubscription.assigned_at.desc())
    )).scalars().all()

    items = [
        SubscriptionBrief(
            id=s.id, school_id=s.school_id, plan_id=s.plan_id,
            plan_code=s.plan.code if s.plan else None,
            plan_name=s.plan.name if s.plan else None,
            status=s.status, started_at=s.started_at,
            expires_at=s.expires_at, assigned_by=s.assigned_by,
            assigned_at=s.assigned_at, note=s.note,
            created_at=s.created_at, updated_at=s.updated_at,
        ).model_dump()
        for s in subs
    ]
    return {"items": items, "total": len(items)}


# ============================================================
# COM-02.1 / COM-02.3：告警查询（基于 EntitlementService）
# ============================================================
async def _build_school_alerts(db: AsyncSession, school_id: int) -> dict:
    """为单所学校构建当前告警与额度余量摘要。"""
    school = (await db.execute(
        select(School).where(School.id == school_id)
    )).scalar_one_or_none()
    if school is None:
        raise NotFoundException(detail="学校不存在")

    # 显式 selectinload(plan)，避免 async 上下文中访问 subscription.plan 触发懒加载
    sub_row = (await db.execute(
        select(SchoolSubscription)
        .options(selectinload(SchoolSubscription.plan))
        .where(
            SchoolSubscription.school_id == school_id,
            SchoolSubscription.status == "active",
        )
        .order_by(SchoolSubscription.assigned_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    plan_code = sub_row.plan.code if (sub_row and sub_row.plan) else None

    # EntitlementService 只用于权益项 check（不访问 plan_code 属性避免懒加载）
    svc = await EntitlementService.create(db, school_id)

    # 当前用量（实时统计）
    member_count = (await db.execute(
        select(func.count()).select_from(SchoolMembership).where(
            SchoolMembership.school_id == school_id,
            SchoolMembership.status == "active",
        )
    )).scalar() or 0
    post_count = (await db.execute(
        select(func.count()).select_from(Post).where(
            Post.school_id == school_id,
            Post.is_deleted == False,  # noqa: E712
        )
    )).scalar() or 0

    # AI 调用次数（当日，从 tenant_usage_daily 取，缺失视为 0）
    from datetime import date as _date
    today = _date.today()
    ai_calls = (await db.execute(
        select(TenantUsageDaily.ai_calls_count).where(
            TenantUsageDaily.school_id == school_id,
            TenantUsageDaily.usage_date == today,
        )
    )).scalar() or 0

    # 存储用量（暂用 tenant_usage_daily 最新一条；缺失视为 0）
    storage_row = (await db.execute(
        select(TenantUsageDaily.storage_used_mb).where(
            TenantUsageDaily.school_id == school_id,
        ).order_by(TenantUsageDaily.usage_date.desc()).limit(1)
    )).scalar() or 0

    # 逐项 check
    checks = {
        "members_max": await svc.check(EntitlementKey.MEMBERS_MAX, int(member_count)),
        "posts_max": await svc.check(EntitlementKey.POSTS_MAX, int(post_count)),
        "storage_mb": await svc.check(EntitlementKey.STORAGE_MB, int(storage_row)),
        "ai_calls_daily": await svc.check(EntitlementKey.AI_CALLS_DAILY, int(ai_calls)),
    }

    alerts: list[dict] = []
    entitlements: list[dict] = []
    for key, reason in checks.items():
        ent = svc.entitlements.get(key)
        limit_value = ent.limit_value if ent is not None else None
        is_hard = ent.is_hard if ent is not None else False
        current_value = reason.current_value
        entitlements.append({
            "key": key,
            "limit_value": limit_value,
            "is_hard": is_hard,
            "current_value": current_value,
            "code": reason.code,
            "message": reason.message,
            "allowed": reason.allowed,
        })
        # 告警条件：warning 类或 hard 拒绝
        if reason.code in ("ENT_WARNING_80", "ENT_WARNING_100",
                           "ENT_WARNING_SOFT_EXCEEDED", "ENT_LIMIT_HARD_EXCEEDED",
                           "ENT_NO_SUBSCRIPTION"):
            alerts.append({
                "key": key,
                "code": reason.code,
                "message": reason.message,
                "limit_value": limit_value,
                "current_value": current_value,
                "is_hard": is_hard,
                "severity": "critical" if reason.code in (
                    "ENT_LIMIT_HARD_EXCEEDED", "ENT_NO_SUBSCRIPTION"
                ) else "warning",
            })

    # 订阅到期告警（30 天内到期）
    subscription_expires_at = None
    days_to_expire: Optional[int] = None
    expire_alert: Optional[dict] = None
    if svc.subscription is not None and svc.subscription.expires_at is not None:
        subscription_expires_at = svc.subscription.expires_at
        delta = (svc.subscription.expires_at - datetime.now()).total_seconds()
        days_to_expire = int(delta // 86400)
        if days_to_expire <= 30:
            expire_alert = {
                "key": "subscription_expiring",
                "code": "ENT_SUBSCRIPTION_EXPIRING",
                "message": (
                    f"学校订阅将在 {days_to_expire} 天后到期"
                    f"（{subscription_expires_at.isoformat()}），请联系平台续期"
                ),
                "expires_at": subscription_expires_at.isoformat(),
                "days_to_expire": days_to_expire,
                "severity": "critical" if days_to_expire <= 7 else "warning",
            }
            alerts.append(expire_alert)

    return {
        "school_id": school_id,
        "school_code": school.code,
        "school_name": school.name,
        "is_active": school.is_active,
        "plan_code": plan_code,
        "subscription_status": (svc.subscription.status
                                if svc.subscription is not None else None),
        "subscription_expires_at": (
            subscription_expires_at.isoformat() if subscription_expires_at else None
        ),
        "days_to_expire": days_to_expire,
        "entitlements": entitlements,
        "alerts": alerts,
        "alerts_count": len(alerts),
    }


@router.get(
    "/schools/{school_id}/alerts",
    summary="学校额度告警（super_admin）",
)
async def get_school_alerts(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """获取指定学校的当前告警与额度余量（COM-02.1 / COM-02.3）。"""
    return await _build_school_alerts(db, school_id)


@router.get(
    "/alerts",
    summary="全平台额度告警（super_admin）",
)
async def list_all_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """全平台告警汇总：每所学校一条，附带其当前告警列表。"""
    schools = (await db.execute(
        select(School).order_by(School.created_at.desc())
    )).scalars().all()
    items = []
    for s in schools:
        item = await _build_school_alerts(db, s.id)
        items.append(item)
    return {
        "items": items,
        "total": len(items),
        "alert_schools_count": sum(1 for i in items if i["alerts_count"] > 0),
    }


# ============================================================
# COM-02.2：开通向导批量导入
# ============================================================
IMPORT_TEMPLATE_CSV = (
    "type,name,description,latitude,longitude,floor,building,"
    "title,content,category_code,location_ref,expire_at,is_anonymous,contact_info\r\n"
    "location,图书馆北门,,31.491200,120.270500,1,图书馆,,,,,,\r\n"
    "location,第二食堂,,31.490100,120.271200,,,二食堂,,,,,,\r\n"
    "post,,,31.491200,120.270500,,,,"
    "失物招领示例,在图书馆北门丢失黑色钱包一个请联系失主,lost_found,1,2026-12-31T23:59:59,false,13800000000\r\n"
)


@router.get(
    "/import-template",
    summary="下载导入模板（CSV）",
    response_class=Response,
)
async def download_import_template(
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """下载开通向导批量导入 CSV 模板（super_admin）。

    模板包含 2 行 location 示例 + 1 行 post 示例。
    post 通过 location_ref 引用同批次 location 的 row_index 或 name。
    """
    return Response(
        content=IMPORT_TEMPLATE_CSV,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="school-import-template.csv"'
            ),
        },
    )


class ImportRequest(BaseModel):
    """批量导入请求体（JSON 数组）。

    每行必须含 type 字段（location/post）。
    school_id 由 URL 路径指定，请求体里的 school_id 会被忽略。
    """
    rows: list[dict[str, Any]] = Field(..., min_length=1, max_length=500,
                                       description="导入行数组（最多 500 行）")


@router.post(
    "/schools/{school_id}/import",
    summary="批量导入地点与首批内容（super_admin，事务保护）",
)
async def import_school_data(
    school_id: int,
    body: ImportRequest,
    dry_run: bool = Query(default=False, description="true=只预览不写库"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """开通向导批量导入（COM-02.2）。

    流程：
    1. 校验学校存在且可写
    2. 解析请求体 rows（JSON 数组，强制 school_id=路径参数）
    3. 预览（dry_run=true）：返回校验后的行 + 错误列表，不写库
    4. 提交（dry_run=false）：任一行失败整批回滚（savepoint），
       记录批次审计日志（action=school.import / school.import.failed）

    只接受当前目标学校的数据，请求体里的 school_id 字段会被忽略。
    """
    svc = SchoolBatchImportService(db)
    rows = SchoolBatchImportService.parse_json_rows(body.rows)

    preview = await svc.preview(rows, school_id=school_id)

    if dry_run or preview.errors:
        return {"mode": "preview", "result": preview.to_dict()}

    # 实际提交（commit 内部已通过 savepoint 保护并写入批次审计）
    result = await svc.commit(preview, school_id=school_id, operator_id=current_user.id)

    # 由 super_admin 路径统一 commit
    await db.commit()

    return {"mode": "commit", "result": result.to_dict()}


# ============================================================
# COM-02.4：激活漏斗
# ============================================================
@router.get(
    "/activation-funnel",
    summary="激活漏斗（super_admin，各校开通清单完成阶段）",
)
async def get_activation_funnel(
    keyword: Optional[str] = Query(None, description="按名称/code 模糊搜索"),
    is_active: Optional[bool] = Query(None, description="按激活状态筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """激活漏斗：每所学校一行，含 5 项开通清单 + 已完成阶段数 + 是否 activated。

    activated = checklist.all_done 且 is_active
    activated_stage = 已完成阶段数（0-5）
    """
    items = await build_activation_funnel(db, keyword=keyword, is_active=is_active)
    total = len(items)
    activated_count = sum(1 for i in items if i.activated)
    return {
        "items": [i.to_dict() for i in items],
        "total": total,
        "activated_count": activated_count,
        "avg_activated_stage": (
            sum(i.activated_stage for i in items) / total if total > 0 else 0.0
        ),
    }


# ============================================================
# ADM-01.2：平台首页跨校统计（super_admin）
# ============================================================
class SchoolAIStat(BaseModel):
    """单校 AI 调用统计（含降级率）。"""
    school_id: int
    school_code: Optional[str] = None
    school_name: Optional[str] = None
    ai_calls: int = 0
    fallback_calls: int = 0
    fallback_rate: float = 0.0


class AbnormalTenantItem(BaseModel):
    """异常租户项。"""
    school_id: int
    school_code: Optional[str] = None
    school_name: Optional[str] = None
    reasons: list[str] = Field(default_factory=list)


class ActivationRecordItem(BaseModel):
    """学校开通记录（来自平台审计 school.create）。"""
    school_id: Optional[int] = None
    school_code: Optional[str] = None
    school_name: Optional[str] = None
    operator_id: Optional[int] = None
    plan_code: Optional[str] = None
    created_at: datetime


class PlatformOverviewResponse(BaseModel):
    """ADM-01.2: 平台首页跨校统计。"""
    # 学校数
    school_total: int = 0
    school_active: int = 0
    school_inactive: int = 0
    # 活跃成员（active membership 总数）
    active_members: int = 0
    # 内容治理量（全平台待办）
    pending_posts: int = 0
    pending_reports: int = 0
    governance_total: int = 0
    # 各校 AI 调用降级率
    ai_stats: list[SchoolAIStat] = Field(default_factory=list)
    ai_calls_total: int = 0
    ai_fallback_total: int = 0
    ai_fallback_rate: float = 0.0
    # 异常租户
    abnormal_tenants: list[AbnormalTenantItem] = Field(default_factory=list)
    # 最近开通记录
    activation_records: list[ActivationRecordItem] = Field(default_factory=list)


@router.get(
    "/overview",
    response_model=PlatformOverviewResponse,
    summary="平台首页跨校统计（ADM-01.2，super_admin）",
)
async def get_platform_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """平台首页：学校数/活跃成员/内容治理量/各校 AI 调用降级率/异常租户/开通记录。

    仅 super_admin 可访问；普通 admin 访问返回 403（由 require_role 保证）。
    """
    import json as _json

    # ---------- 学校数 ----------
    school_rows = (await db.execute(
        select(School.id, School.code, School.name, School.is_active)
        .order_by(School.created_at.asc())
    )).all()
    school_total = len(school_rows)
    school_active = sum(1 for r in school_rows if r.is_active)
    school_inactive = school_total - school_active
    school_map = {r.id: r for r in school_rows}

    # ---------- 活跃成员 ----------
    active_members = (await db.execute(
        select(func.count()).select_from(SchoolMembership).where(
            SchoolMembership.status == "active"
        )
    )).scalar() or 0

    # ---------- 内容治理量 ----------
    pending_posts = (await db.execute(
        select(func.count(Post.id)).where(
            Post.status == "pending", Post.is_deleted == False,  # noqa: E712
        )
    )).scalar() or 0
    pending_reports = (await db.execute(
        select(func.count(Report.id)).where(Report.status == "pending")
    )).scalar() or 0
    governance_total = pending_posts + pending_reports

    # ---------- 各校 AI 调用降级率 ----------
    ai_rows = (await db.execute(
        select(
            AIInvocationLog.school_id,
            func.count(AIInvocationLog.id),
            func.count(AIInvocationLog.id).filter(
                AIInvocationLog.fallback_reason.isnot(None)
            ),
        ).group_by(AIInvocationLog.school_id)
    )).all()

    ai_stats: list[SchoolAIStat] = []
    ai_calls_total = 0
    ai_fallback_total = 0
    for sid, calls, fallbacks in ai_rows:
        calls = int(calls or 0)
        fallbacks = int(fallbacks or 0)
        ai_calls_total += calls
        ai_fallback_total += fallbacks
        school = school_map.get(sid)
        ai_stats.append(SchoolAIStat(
            school_id=sid,
            school_code=school.code if school else None,
            school_name=school.name if school else None,
            ai_calls=calls,
            fallback_calls=fallbacks,
            fallback_rate=round(fallbacks / calls, 4) if calls > 0 else 0.0,
        ))
    ai_fallback_rate = (
        round(ai_fallback_total / ai_calls_total, 4) if ai_calls_total > 0 else 0.0
    )

    # ---------- 异常租户 ----------
    # 口径：学校被暂停 / AI 降级率 ≥50%（且调用数 ≥5）/ 订阅缺失或 30 天内到期
    abnormal: dict[int, AbnormalTenantItem] = {}

    def _mark(school_id: int, reason: str) -> None:
        school = school_map.get(school_id)
        if school_id not in abnormal:
            abnormal[school_id] = AbnormalTenantItem(
                school_id=school_id,
                school_code=school.code if school else None,
                school_name=school.name if school else None,
                reasons=[],
            )
        abnormal[school_id].reasons.append(reason)

    # 暂停学校
    for r in school_rows:
        if not r.is_active:
            _mark(r.id, "学校已暂停")

    # AI 高降级率
    for stat in ai_stats:
        if stat.ai_calls >= 5 and stat.fallback_rate >= 0.5:
            _mark(stat.school_id, f"AI 降级率 {stat.fallback_rate * 100:.0f}%（{stat.fallback_calls}/{stat.ai_calls}）")

    # 订阅异常：无 active 订阅 / 30 天内到期
    active_subs = (await db.execute(
        select(SchoolSubscription)
        .options(selectinload(SchoolSubscription.plan))
        .where(SchoolSubscription.status == "active")
    )).scalars().all()
    sub_map = {s.school_id: s for s in active_subs}
    now = datetime.now()
    for r in school_rows:
        sub = sub_map.get(r.id)
        if sub is None:
            _mark(r.id, "无有效订阅")
        elif sub.expires_at is not None:
            days = int((sub.expires_at - now).total_seconds() // 86400)
            if days <= 30:
                _mark(r.id, f"订阅 {days} 天后到期")

    # ---------- 开通记录（最近 20 条 school.create 审计） ----------
    audit_rows = (await db.execute(
        select(PlatformAuditLog)
        .where(PlatformAuditLog.action == "school.create")
        .order_by(PlatformAuditLog.created_at.desc())
        .limit(20)
    )).scalars().all()

    activation_records: list[ActivationRecordItem] = []
    for log in audit_rows:
        school = school_map.get(log.target_school_id) if log.target_school_id else None
        plan_code: Optional[str] = None
        if log.new_value:
            try:
                plan_code = _json.loads(log.new_value).get("plan_code")
            except (ValueError, AttributeError):
                plan_code = None
        activation_records.append(ActivationRecordItem(
            school_id=log.target_school_id,
            school_code=school.code if school else None,
            school_name=school.name if school else None,
            operator_id=log.operator_id,
            plan_code=plan_code,
            created_at=log.created_at,
        ))

    return PlatformOverviewResponse(
        school_total=school_total,
        school_active=school_active,
        school_inactive=school_inactive,
        active_members=int(active_members),
        pending_posts=int(pending_posts),
        pending_reports=int(pending_reports),
        governance_total=int(governance_total),
        ai_stats=ai_stats,
        ai_calls_total=ai_calls_total,
        ai_fallback_total=ai_fallback_total,
        ai_fallback_rate=ai_fallback_rate,
        abnormal_tenants=list(abnormal.values()),
        activation_records=activation_records,
    )


# ============================================================
# ANA-02.1: 平台级分析指标（super_admin，跨校聚合）
# ============================================================
@router.get(
    "/analytics",
    summary="平台级分析指标（ANA-02.1，super_admin 专用）",
)
async def get_platform_analytics(
    window_days: int = Query(
        default=30, ge=1, le=180,
        description="指标复算时间窗口（天），默认 30",
    ),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """ANA-02.1 平台级分析指标（super_admin 专用，跨校聚合）。

    关键约束（spec ANA-02.1）：
    - **平台只看学校级聚合**：每所学校一行聚合指标，不暴露跨校用户轨迹
    - 平台层只统计事件/业务计数，不提供用户级跨校串联
    - 各校聚合后再次汇总成平台级指标（funnel / search / ai / governance）

    覆盖指标：
    - 各校聚合（funnel_summary / search_success_rate / search_zero_rate / ai_calls）
    - 平台级漏斗聚合（学校查看 → 搜索 → 提交 → 公开）
    - 平台级搜索成功率 + 零结果率
    - 平台级 AI 用量（调用数 / 成功率 / 降级率 / 平均延迟）
    - 平台级治理 SLA（平均审核时长 + 平均举报处理时长）

    平台层不返回零结果主题明细（隐私阈值由各校 admin 自行查看本校数据）。
    每个指标附带元数据：time_window / sample_size / last_updated_at / empty_state。
    """
    from app.services.analytics_service import PlatformAnalyticsService
    # window_days 已由 Query(ge=1, le=180) 强制校验，直接传入
    svc = PlatformAnalyticsService(db)
    metrics = await svc.compute_all(window_days=int(window_days))
    return metrics.to_dict()
