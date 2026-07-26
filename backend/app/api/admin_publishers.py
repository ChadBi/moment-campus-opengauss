"""ORG-01.2: 校级 admin 发布主体管理 API

管理端点（需 admin 及以上角色）：
    GET    /api/v1/admin/publishers                发布主体管理列表（含 pending/verified/revoked/rejected）
    GET    /api/v1/admin/publishers/{id}           管理详情（含审核字段/成员数）
    PUT    /api/v1/admin/publishers/{id}/verify    审核/认证/撤销/恢复
    DELETE /api/v1/admin/publishers/{id}           软删除发布主体
    GET    /api/v1/admin/publishers/{id}/members   成员列表
    POST   /api/v1/admin/publishers/{id}/members   添加成员
    PUT    /api/v1/admin/publishers/{id}/members/{user_id}  更新成员角色
    DELETE /api/v1/admin/publishers/{id}/members/{user_id}  移除成员
    POST   /api/v1/admin/templates                 创建学校级公共模板
    GET    /api/v1/admin/templates                 管理模板列表（含禁用项）
    DELETE /api/v1/admin/templates/{id}            软删除模板（is_active=False）

设计要点：
    - verified_status 仅由本组接口流转（用户端不可改）
    - 认证不代表内容免审：发布主体关联帖子仍走原 post_status 审核流程
    - TEN-02.3: 所有查询按 tenant.school_id 过滤，跨校访问统一 404
    - 所有写操作记录 AdminOperationLog
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException, NotFoundException, ConflictException, ForbiddenException,
)
from app.core.permissions import require_role, Role
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.database import get_db
from app.models.admin_operation_log import AdminOperationLog
from app.models.location import Location
from app.models.post_template import PostTemplate
from app.models.publisher_membership import PublisherMembership
from app.models.publisher_profile import PublisherProfile
from app.models.user import User
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.publisher import (
    PublisherAdminResponse,
    PublisherVerifyRequest,
    PublisherMemberAddRequest,
    PublisherMemberUpdateRequest,
    PublisherMembershipBrief,
    PostTemplateCreate,
    PostTemplateUpdate,
    PostTemplateResponse,
)


router = APIRouter(prefix="/admin", tags=["管理-官方发布主体"])

# 复用 admin 依赖：admin 及以上可访问
AdminDep = Depends(require_role(Role.ADMIN))

# 状态流转规则
_VERIFY_TRANSITIONS: dict[str, dict[str, str]] = {
    "approve": {"from": "pending", "to": "verified"},
    "reject": {"from": "pending", "to": "rejected"},
    "revoke": {"from": "verified", "to": "revoked"},
    "restore": {"from": "revoked", "to": "pending"},  # 也允许 rejected → pending
}

_ACTION_LABELS: dict[str, str] = {
    "approve": "认证通过",
    "reject": "驳回申请",
    "revoke": "撤销认证",
    "restore": "恢复待审核",
}


# ============================================================
# 辅助函数
# ============================================================
async def _load_publisher_admin(
    db: AsyncSession, publisher_id: int, tenant: TenantContext
) -> PublisherProfile:
    p = await db.scalar(
        select(PublisherProfile).where(
            PublisherProfile.id == publisher_id,
            PublisherProfile.is_deleted == False,  # noqa: E712
        )
    )
    if p is None:
        raise NotFoundException(detail="发布主体不存在")
    check_resource_in_tenant(p.school_id, tenant)
    return p


async def _publisher_to_admin_response(
    db: AsyncSession, p: PublisherProfile
) -> PublisherAdminResponse:
    """构建管理端响应（含 location_name / verified_by_name / member_count）"""
    location_name: Optional[str] = None
    if p.location_id is not None:
        loc = await db.scalar(select(Location).where(Location.id == p.location_id))
        if loc is not None:
            location_name = loc.name

    verified_by_name: Optional[str] = None
    if p.verified_by is not None:
        u = await db.scalar(select(User).where(User.id == p.verified_by))
        if u is not None:
            verified_by_name = u.nickname

    member_count = await db.scalar(
        select(func.count(PublisherMembership.id)).where(
            PublisherMembership.publisher_id == p.id
        )
    ) or 0

    return PublisherAdminResponse(
        id=p.id,
        school_id=p.school_id,
        name=p.name,
        type=p.type,
        intro=p.intro,
        logo_url=p.logo_url,
        location_id=p.location_id,
        location_name=location_name,
        service_hours=p.service_hours,
        contact=p.contact,
        verified_status=p.verified_status,
        verified_at=p.verified_at,
        verified_by=p.verified_by,
        verified_by_name=verified_by_name,
        verify_note=p.verify_note,
        view_count=p.view_count,
        subscribe_count=p.subscribe_count,
        share_count=p.share_count,
        valid_feedback_count=p.valid_feedback_count,
        invalid_feedback_count=p.invalid_feedback_count,
        zero_result_count=p.zero_result_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
        member_count=member_count,
    )


# ============================================================
# 管理列表 / 详情
# ============================================================
@router.get(
    "/publishers",
    response_model=PaginatedResponse[PublisherAdminResponse],
    summary="发布主体管理列表（ADM-01 + ORG-01.2）",
)
async def admin_list_publishers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verified_status: Optional[str] = Query(None, description="按认证状态筛选"),
    type_filter: Optional[str] = Query(None, alias="type", description="按类型筛选"),
    keyword: Optional[str] = Query(None, description="按名称模糊搜索"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """发布主体管理列表（含全部认证状态）。

    TEN-02.3: 按当前学校过滤，跨校主体不会出现。
    """
    base_filter = [
        PublisherProfile.school_id == tenant.school_id,
        PublisherProfile.is_deleted == False,  # noqa: E712
    ]
    if verified_status:
        base_filter.append(PublisherProfile.verified_status == verified_status)
    if type_filter:
        base_filter.append(PublisherProfile.type == type_filter)
    if keyword:
        base_filter.append(PublisherProfile.name.ilike(f"%{keyword}%"))

    query = (
        select(PublisherProfile)
        .where(*base_filter)
        .order_by(PublisherProfile.created_at.desc())
    )
    total = await db.scalar(
        select(func.count()).select_from(
            select(PublisherProfile).where(*base_filter).subquery()
        )
    )

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    publishers = result.scalars().all()

    items = [await _publisher_to_admin_response(db, p) for p in publishers]
    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.get(
    "/publishers/{publisher_id}",
    response_model=PublisherAdminResponse,
    summary="发布主体管理详情",
)
async def admin_get_publisher(
    publisher_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """管理详情。TEN-02.3: 跨校主体统一 404。"""
    p = await _load_publisher_admin(db, publisher_id, tenant)
    return await _publisher_to_admin_response(db, p)


# ============================================================
# 审核 / 认证 / 撤销 / 恢复
# ============================================================
@router.put(
    "/publishers/{publisher_id}/verify",
    response_model=PublisherAdminResponse,
    summary="审核/认证/撤销/恢复发布主体（ORG-01.2）",
)
async def admin_verify_publisher(
    publisher_id: int,
    data: PublisherVerifyRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """ORG-01.2: 认证状态流转。

    流转规则：
    - approve: pending → verified（认证通过）
    - reject:  pending → rejected（驳回申请）
    - revoke:  verified → revoked（撤销认证）
    - restore: revoked/rejected → pending（恢复待审核）

    认证标识不可由用户自行设置，仅本接口可流转 verified_status。
    认证不代表内容免审：发布主体关联帖子仍走原 post_status 审核流程。

    TEN-02.3: 跨校主体统一 404。同事务提交状态变更 + 操作日志 + 通知。
    """
    p = await _load_publisher_admin(db, publisher_id, tenant)

    rule = _VERIFY_TRANSITIONS[data.action]
    # restore 允许从 revoked 或 rejected 流转
    allowed_from = ("revoked", "rejected") if data.action == "restore" else (rule["from"],)
    if p.verified_status not in allowed_from:
        raise BadRequestException(
            detail=f"当前状态 {p.verified_status} 不允许执行 {data.action} 操作"
            f"（需为 {'/'.join(allowed_from)}）"
        )

    now = datetime.now()
    p.verified_status = rule["to"]
    p.verified_at = now
    p.verified_by = admin.id
    p.verify_note = data.note
    p.updated_at = now

    # 操作日志
    db.add(AdminOperationLog(
        admin_id=admin.id,
        action=f"publisher_{data.action}",
        target_type="publisher_profile",
        target_id=p.id,
        detail=f"{_ACTION_LABELS[data.action]}：{p.name}（{p.type}）"
               + (f"；备注：{data.note}" if data.note else ""),
    ))

    await db.commit()
    await db.refresh(p)
    return await _publisher_to_admin_response(db, p)


# ============================================================
# 软删除发布主体
# ============================================================
@router.delete(
    "/publishers/{publisher_id}",
    response_model=MessageResponse,
    summary="软删除发布主体",
)
async def admin_delete_publisher(
    publisher_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """软删除发布主体（is_deleted=True）。

    注意：关联帖子的 publisher_id 由外键 ON DELETE SET NULL 处理，
    但软删除不触发外键级联，关联帖子保持 publisher_id（仍可在主页显示）。
    若需解除关联，应由 admin 单独操作。

    TEN-02.3: 跨校主体统一 404。
    """
    p = await _load_publisher_admin(db, publisher_id, tenant)
    if p.is_deleted:
        raise BadRequestException(detail="发布主体已删除")

    p.is_deleted = True
    p.deleted_at = datetime.now()
    p.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="delete_publisher",
        target_type="publisher_profile",
        target_id=p.id,
        detail=f"删除发布主体：{p.name}",
    ))
    await db.commit()
    return MessageResponse(message=f"发布主体 {p.name} 已删除")


# ============================================================
# 成员管理
# ============================================================
@router.get(
    "/publishers/{publisher_id}/members",
    response_model=List[PublisherMembershipBrief],
    summary="发布主体成员列表",
)
async def admin_list_members(
    publisher_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """成员列表。TEN-02.3: 跨校主体统一 404。"""
    p = await _load_publisher_admin(db, publisher_id, tenant)
    rows = await db.execute(
        select(PublisherMembership, User)
        .join(User, PublisherMembership.user_id == User.id)
        .where(PublisherMembership.publisher_id == p.id)
        .order_by(PublisherMembership.joined_at.asc())
    )
    return [
        PublisherMembershipBrief(
            id=m.id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
            user_nickname=u.nickname,
            user_email=u.email,
        )
        for m, u in rows.all()
    ]


@router.post(
    "/publishers/{publisher_id}/members",
    response_model=PublisherMembershipBrief,
    summary="添加成员（admin 直接指定）",
)
async def admin_add_member(
    publisher_id: int,
    data: PublisherMemberAddRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """admin 直接添加成员（不要求被添加用户为该校 active 成员，但建议是）。

    TEN-02.3: 跨校主体统一 404。同事务提交 + 操作日志。
    """
    p = await _load_publisher_admin(db, publisher_id, tenant)

    # 校验被添加用户存在
    target_user = await db.scalar(select(User).where(User.id == data.user_id))
    if target_user is None:
        raise NotFoundException(detail="被添加用户不存在")

    # 校验未已加入
    existing = await db.scalar(
        select(PublisherMembership).where(
            PublisherMembership.publisher_id == p.id,
            PublisherMembership.user_id == data.user_id,
        )
    )
    if existing is not None:
        raise ConflictException(detail="该用户已是本主体成员")

    now = datetime.now()
    membership = PublisherMembership(
        publisher_id=p.id,
        user_id=data.user_id,
        role=data.role,
        joined_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(membership)

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="publisher_add_member",
        target_type="publisher_profile",
        target_id=p.id,
        detail=f"添加成员 user_id={data.user_id}（{target_user.nickname}）角色={data.role}",
    ))

    await db.commit()
    await db.refresh(membership)
    return PublisherMembershipBrief(
        id=membership.id,
        user_id=membership.user_id,
        role=membership.role,
        joined_at=membership.joined_at,
        user_nickname=target_user.nickname,
        user_email=target_user.email,
    )


@router.put(
    "/publishers/{publisher_id}/members/{user_id}",
    response_model=PublisherMembershipBrief,
    summary="更新成员角色",
)
async def admin_update_member(
    publisher_id: int,
    user_id: int,
    data: PublisherMemberUpdateRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新成员角色。TEN-02.3: 跨校主体统一 404。"""
    p = await _load_publisher_admin(db, publisher_id, tenant)
    m = await db.scalar(
        select(PublisherMembership).where(
            PublisherMembership.publisher_id == p.id,
            PublisherMembership.user_id == user_id,
        )
    )
    if m is None:
        raise NotFoundException(detail="成员不存在")

    old_role = m.role
    m.role = data.role
    m.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="publisher_update_member",
        target_type="publisher_profile",
        target_id=p.id,
        detail=f"成员 user_id={user_id} 角色 {old_role} → {data.role}",
    ))
    await db.commit()
    await db.refresh(m)

    u = await db.scalar(select(User).where(User.id == m.user_id))
    return PublisherMembershipBrief(
        id=m.id,
        user_id=m.user_id,
        role=m.role,
        joined_at=m.joined_at,
        user_nickname=u.nickname if u else None,
        user_email=u.email if u else None,
    )


@router.delete(
    "/publishers/{publisher_id}/members/{user_id}",
    response_model=MessageResponse,
    summary="移除成员",
)
async def admin_remove_member(
    publisher_id: int,
    user_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """移除成员。TEN-02.3: 跨校主体统一 404。"""
    p = await _load_publisher_admin(db, publisher_id, tenant)
    m = await db.scalar(
        select(PublisherMembership).where(
            PublisherMembership.publisher_id == p.id,
            PublisherMembership.user_id == user_id,
        )
    )
    if m is None:
        raise NotFoundException(detail="成员不存在")

    await db.delete(m)

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="publisher_remove_member",
        target_type="publisher_profile",
        target_id=p.id,
        detail=f"移除成员 user_id={user_id}",
    ))
    await db.commit()
    return MessageResponse(message="成员已移除")


# ============================================================
# 学校级公共模板管理
# ============================================================
@router.get(
    "/templates",
    response_model=PaginatedResponse[PostTemplateResponse],
    summary="模板管理列表（含禁用项，含主体专属）",
)
async def admin_list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    scene: Optional[str] = Query(None, description="按场景筛选"),
    publisher_id: Optional[int] = Query(None, description="按发布主体筛选（含 NULL 公共模板）"),
    is_active: Optional[bool] = Query(None, description="按启用状态筛选"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """模板管理列表（含禁用项与主体专属模板）。

    TEN-02.3: 按当前学校过滤。
    """
    base_filter = [PostTemplate.school_id == tenant.school_id]
    if scene:
        base_filter.append(PostTemplate.scene == scene)
    if publisher_id is not None:
        base_filter.append(PostTemplate.publisher_id == publisher_id)
    if is_active is not None:
        base_filter.append(PostTemplate.is_active == is_active)

    query = (
        select(PostTemplate)
        .where(*base_filter)
        .order_by(PostTemplate.sort_order.asc(), PostTemplate.id.asc())
    )
    total = await db.scalar(
        select(func.count()).select_from(
            select(PostTemplate).where(*base_filter).subquery()
        )
    )

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    templates = result.scalars().all()

    items = []
    for t in templates:
        items.append(PostTemplateResponse(
            id=t.id,
            school_id=t.school_id,
            publisher_id=t.publisher_id,
            publisher_name=None,
            name=t.name,
            title_template=t.title_template,
            content_template=t.content_template,
            category_id=t.category_id,
            post_type_id=t.post_type_id,
            scene=t.scene,
            sort_order=t.sort_order,
            is_active=t.is_active,
            created_at=t.created_at,
            updated_at=t.updated_at,
        ))
    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.post(
    "/templates",
    response_model=PostTemplateResponse,
    summary="创建学校级公共模板（admin）",
)
async def admin_create_template(
    data: PostTemplateCreate,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """创建模板。

    - publisher_id 为空：学校级公共模板（admin 创建）
    - publisher_id 非空：主体专属模板（admin 也可代创建，校验主体属本校）
    - school_id 由 TenantContext 决定
    - TEN-02.3: 若指定 publisher_id，跨校主体统一 404
    """
    if data.publisher_id is not None:
        await _load_publisher_admin(db, data.publisher_id, tenant)

    now = datetime.now()
    template = PostTemplate(
        school_id=tenant.school_id,
        publisher_id=data.publisher_id,
        name=data.name,
        title_template=data.title_template,
        content_template=data.content_template,
        category_id=data.category_id,
        post_type_id=data.post_type_id,
        scene=data.scene,
        sort_order=data.sort_order,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(template)

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="create_post_template",
        target_type="post_template",
        target_id=0,
        detail=f"创建模板：{data.name}（scene={data.scene}）",
    ))
    await db.commit()
    await db.refresh(template)

    return PostTemplateResponse(
        id=template.id,
        school_id=template.school_id,
        publisher_id=template.publisher_id,
        publisher_name=None,
        name=template.name,
        title_template=template.title_template,
        content_template=template.content_template,
        category_id=template.category_id,
        post_type_id=template.post_type_id,
        scene=template.scene,
        sort_order=template.sort_order,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.delete(
    "/templates/{template_id}",
    response_model=MessageResponse,
    summary="禁用模板（软删除 is_active=False）",
)
async def admin_delete_template(
    template_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """禁用模板（is_active=False），不真正删除以保留历史关联。

    TEN-02.3: 跨校模板统一 404。
    """
    t = await db.scalar(select(PostTemplate).where(PostTemplate.id == template_id))
    if t is None:
        raise NotFoundException(detail="模板不存在")
    check_resource_in_tenant(t.school_id, tenant)

    if not t.is_active:
        raise BadRequestException(detail="模板已是禁用状态")

    t.is_active = False
    t.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="delete_post_template",
        target_type="post_template",
        target_id=t.id,
        detail=f"禁用模板：{t.name}",
    ))
    await db.commit()
    return MessageResponse(message=f"模板 {t.name} 已禁用")
