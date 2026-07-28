"""ORG-01.1: 官方发布主体用户端 API

公开/登录用户端点：
    GET  /api/v1/publishers                 发布主体列表（仅本校，verified 优先）
    GET  /api/v1/publishers/{id}            发布主体详情（主页：基本信息+成员+最近内容）
    GET  /api/v1/publishers/{id}/aggregation  聚合效果（浏览/订阅/分享/反馈/零结果）
    POST /api/v1/publishers/{id}/feedback   有效性反馈/零结果聚合
    POST /api/v1/publishers/{id}/share      分享计数上报
    GET  /api/v1/publishers/{id}/templates  主体专属模板列表

登录用户端点：
    POST /api/v1/publishers                 申请创建发布主体（强制 verified_status=pending）
    PUT  /api/v1/publishers/{id}            更新主体信息（仅 owner/admin 成员，verified_status 不可改）
    GET  /api/v1/me/publishers              当前用户加入的发布主体列表
    GET  /api/v1/templates                  学校级公共模板列表（用于 PostForm 选择）

设计要点：
    - verified_status 不可由用户设置/修改，强制 pending（认证标识需 admin 审核）
    - 认证不代表内容免审：发布主体关联的帖子仍走原 post_status 状态机审核流程
    - 三校隔离：所有查询按 tenant.school_id 过滤，跨校访问统一 404
    - 主页详情对游客也可见（公开主页），但创建/更新/反馈需登录
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.exceptions import (
    BadRequestException, NotFoundException, ForbiddenException, ConflictException,
)
from app.core.permissions import Role
from app.core.tenant import (
    TenantContext, get_tenant_context, check_resource_in_tenant, assert_writable_in_tenant,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.post_template import PostTemplate
from app.models.publisher_membership import PublisherMembership
from app.models.publisher_profile import PublisherProfile
from app.models.user import User
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.publisher import (
    PublisherBrief,
    PublisherProfileCreate,
    PublisherProfileUpdate,
    PublisherProfileResponse,
    PublisherDetailResponse,
    PublisherMembershipBrief,
    PublisherPostBrief,
    PublisherAggregationResponse,
    PublisherFeedbackRequest,
    PublisherShareRequest,
    PostTemplateCreate,
    PostTemplateUpdate,
    PostTemplateResponse,
    MEMBER_ROLES,
)
from app.core.post_status import PostStatus


router = APIRouter(tags=["官方发布主体"])


# ============================================================
# 辅助函数
# ============================================================
async def _load_publisher(
    db: AsyncSession, publisher_id: int, tenant: TenantContext
) -> PublisherProfile:
    """加载发布主体并校验租户隔离（跨校统一 404）"""
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


async def _load_membership(
    db: AsyncSession, publisher_id: int, user_id: int
) -> Optional[PublisherMembership]:
    return await db.scalar(
        select(PublisherMembership).where(
            PublisherMembership.publisher_id == publisher_id,
            PublisherMembership.user_id == user_id,
        )
    )


def _can_manage(membership: Optional[PublisherMembership]) -> bool:
    """是否可管理（owner/admin）"""
    return membership is not None and membership.role in ("owner", "admin")


async def _enrich_publisher_response(
    db: AsyncSession,
    p: PublisherProfile,
    tenant: TenantContext,
    include_members: bool = False,
    include_recent: bool = False,
) -> PublisherDetailResponse:
    """构建发布主体详情响应（含 location_name / 当前用户成员关系 / 最近内容）"""
    # location_name
    location_name: Optional[str] = None
    if p.location_id is not None:
        loc = await db.scalar(select(Location).where(Location.id == p.location_id))
        if loc is not None:
            location_name = loc.name

    # 当前用户成员关系
    is_member = False
    my_role: Optional[str] = None
    if tenant.user is not None:
        m = await _load_membership(db, p.id, tenant.user.id)
        if m is not None:
            is_member = True
            my_role = m.role

    # 成员列表（仅管理成员或公开主页可看，此处公开主页返回）
    memberships: List[PublisherMembershipBrief] = []
    if include_members:
        rows = await db.execute(
            select(PublisherMembership, User)
            .join(User, PublisherMembership.user_id == User.id)
            .where(PublisherMembership.publisher_id == p.id)
            .order_by(PublisherMembership.joined_at.asc())
        )
        for m, u in rows.all():
            memberships.append(PublisherMembershipBrief(
                id=m.id,
                user_id=m.user_id,
                role=m.role,
                joined_at=m.joined_at,
                user_nickname=u.nickname,
                user_email=u.email,
            ))

    # 最近内容（已发布）
    recent_posts: List[PublisherPostBrief] = []
    if include_recent:
        rows = await db.execute(
            select(Post, Category)
            .outerjoin(Category, Post.category_id == Category.id)
            .where(
                Post.publisher_id == p.id,
                Post.is_deleted == False,  # noqa: E712
                Post.status == PostStatus.PUBLISHED,
            )
            .order_by(Post.created_at.desc())
            .limit(10)
        )
        for post, cat in rows.all():
            recent_posts.append(PublisherPostBrief(
                id=post.id,
                title=post.title,
                status=post.status,
                category_id=post.category_id,
                category_name=cat.name if cat else None,
                created_at=post.created_at,
                view_count=post.view_count,
                like_count=post.like_count,
            ))

    return PublisherDetailResponse(
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
        view_count=p.view_count,
        subscribe_count=p.subscribe_count,
        share_count=p.share_count,
        valid_feedback_count=p.valid_feedback_count,
        invalid_feedback_count=p.invalid_feedback_count,
        zero_result_count=p.zero_result_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
        is_member=is_member,
        my_role=my_role,
        memberships=memberships,
        recent_posts=recent_posts,
    )


# ============================================================
# 公开/登录用户端点
# ============================================================
@router.get(
    "/publishers",
    response_model=PaginatedResponse[PublisherBrief],
    summary="发布主体列表（本校，认证主体优先）",
)
async def list_publishers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type_filter: Optional[str] = Query(None, alias="type", description="按类型筛选：department/club/service_org"),
    verified_status: Optional[str] = Query(None, description="按认证状态筛选"),
    keyword: Optional[str] = Query(None, description="按名称模糊搜索"),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """列出本校发布主体（公开接口，游客可访问）。

    TEN-02.3: 强制按当前学校过滤，跨校主体不会出现。
    默认 verified 主体在前，按 subscribe_count 倒序。
    """
    base_filter = [
        PublisherProfile.school_id == tenant.school_id,
        PublisherProfile.is_deleted == False,  # noqa: E712
    ]
    if type_filter:
        base_filter.append(PublisherProfile.type == type_filter)
    if verified_status:
        base_filter.append(PublisherProfile.verified_status == verified_status)
    if keyword:
        base_filter.append(PublisherProfile.name.ilike(f"%{keyword}%"))

    query = (
        select(PublisherProfile)
        .where(*base_filter)
        .order_by(
            # verified 优先（用 case 表达式），再按订阅数倒序
            (PublisherProfile.verified_status != "verified").asc(),
            PublisherProfile.subscribe_count.desc(),
            PublisherProfile.created_at.desc(),
        )
    )

    total = await db.scalar(
        select(func.count()).select_from(
            select(PublisherProfile).where(*base_filter).subquery()
        )
    )

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    publishers = result.scalars().all()

    items = [
        PublisherBrief(
            id=p.id,
            name=p.name,
            type=p.type,
            logo_url=p.logo_url,
            verified_status=p.verified_status,
            intro=p.intro,
            subscribe_count=p.subscribe_count,
            view_count=p.view_count,
        )
        for p in publishers
    ]
    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.get(
    "/publishers/{publisher_id}",
    response_model=PublisherDetailResponse,
    summary="发布主体详情（主页：基本信息+成员+最近内容）",
)
async def get_publisher_detail(
    publisher_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """发布主体主页（公开接口，游客可访问）。

    ORG-01.1: 名称/类型/简介/Logo/服务地点/时间/联系方式/认证状态/最近内容
    TEN-02.3: 跨校主体统一 404。
    浏览时 view_count +1（游客也计入）。
    """
    p = await _load_publisher(db, publisher_id, tenant)

    # 浏览计数 +1（同一事务提交，避免并发竞争用 SQL 自增）
    p.view_count = p.view_count + 1
    p.updated_at = datetime.now()
    await db.commit()
    await db.refresh(p)

    return await _enrich_publisher_response(
        db, p, tenant, include_members=True, include_recent=True,
    )


@router.get(
    "/publishers/{publisher_id}/aggregation",
    response_model=PublisherAggregationResponse,
    summary="组织后台聚合效果（浏览/订阅/分享/反馈/零结果）",
)
async def get_publisher_aggregation(
    publisher_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """ORG-01.4: 聚合效果。公开接口（游客也可查看主体公开效果数据）。

    TEN-02.3: 跨校主体统一 404。
    """
    p = await _load_publisher(db, publisher_id, tenant)

    # 统计该主体关联的内容数（按状态分组）
    status_rows = await db.execute(
        select(Post.status, func.count(Post.id)).where(
            Post.publisher_id == p.id,
            Post.is_deleted == False,  # noqa: E712
        ).group_by(Post.status)
    )
    status_map = {row[0]: row[1] for row in status_rows.all()}
    total_posts = sum(status_map.values())
    published_posts = status_map.get(PostStatus.PUBLISHED, 0)
    pending_posts = status_map.get(PostStatus.PENDING, 0)

    valid = p.valid_feedback_count
    invalid = p.invalid_feedback_count
    valid_rate: Optional[float] = None
    if valid + invalid > 0:
        valid_rate = round(valid / (valid + invalid), 4)

    return PublisherAggregationResponse(
        publisher_id=p.id,
        publisher_name=p.name,
        view_count=p.view_count,
        subscribe_count=p.subscribe_count,
        share_count=p.share_count,
        valid_feedback_count=valid,
        invalid_feedback_count=invalid,
        zero_result_count=p.zero_result_count,
        total_posts=total_posts,
        published_posts=published_posts,
        pending_posts=pending_posts,
        valid_rate=valid_rate,
    )


@router.post(
    "/publishers/{publisher_id}/feedback",
    response_model=MessageResponse,
    summary="有效性反馈/零结果关联需求聚合",
)
async def submit_publisher_feedback(
    publisher_id: int,
    data: PublisherFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """ORG-01.4: 用户对发布主体提交反馈（登录用户）。

    - valid：内容有效
    - invalid：内容无效
    - zero_result：未找到所需（零结果关联需求聚合）

    简单累计，不防重复（与产品事件统计口径一致，后续可在 ProductEvent 中去重）。
    TEN-02.3: 跨校主体统一 404。
    """
    assert_writable_in_tenant(tenant)
    p = await _load_publisher(db, publisher_id, tenant)

    if data.feedback_type == "valid":
        p.valid_feedback_count = p.valid_feedback_count + 1
    elif data.feedback_type == "invalid":
        p.invalid_feedback_count = p.invalid_feedback_count + 1
    else:
        p.zero_result_count = p.zero_result_count + 1
    p.updated_at = datetime.now()
    await db.commit()

    return MessageResponse(message="反馈已提交")


@router.post(
    "/publishers/{publisher_id}/share",
    response_model=MessageResponse,
    summary="分享计数上报",
)
async def share_publisher(
    publisher_id: int,
    data: PublisherShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """分享计数 +1（登录用户）。TEN-02.3: 跨校主体统一 404。"""
    assert_writable_in_tenant(tenant)
    p = await _load_publisher(db, publisher_id, tenant)
    p.share_count = p.share_count + 1
    p.updated_at = datetime.now()
    await db.commit()
    return MessageResponse(message="分享已记录")


# ============================================================
# 登录用户端点：申请创建 / 更新 / 我的主体
# ============================================================
@router.post(
    "/publishers",
    response_model=PublisherDetailResponse,
    summary="申请创建发布主体（强制 verified_status=pending）",
)
async def create_publisher(
    data: PublisherProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """ORG-01.1: 用户提交发布主体申请。

    关键约束：
    - verified_status 强制为 pending（用户不可自行设置认证标识）
    - 创建者自动成为 owner 成员
    - school_id 由 TenantContext 决定，忽略 body 中的 school_id
    - TEN-02.3: 写请求需在当前租户内（游客 404）
    """
    assert_writable_in_tenant(tenant)

    # 校验 location_id 属于当前学校（若提供）
    if data.location_id is not None:
        loc = await db.scalar(select(Location).where(Location.id == data.location_id))
        if loc is None:
            raise BadRequestException(detail="服务地点不存在")
        check_resource_in_tenant(loc.school_id, tenant)

    now = datetime.now()
    publisher = PublisherProfile(
        school_id=tenant.school_id,
        name=data.name,
        type=data.type,
        intro=data.intro,
        logo_url=data.logo_url,
        location_id=data.location_id,
        service_hours=data.service_hours,
        contact=data.contact,
        verified_status="pending",  # 强制 pending，不可由用户设置
        created_at=now,
        updated_at=now,
    )
    db.add(publisher)
    await db.flush()  # 获取 id

    # 创建者自动成为 owner
    membership = PublisherMembership(
        publisher_id=publisher.id,
        user_id=current_user.id,
        role="owner",
        joined_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(publisher)

    return await _enrich_publisher_response(
        db, publisher, tenant, include_members=True, include_recent=True,
    )


@router.put(
    "/publishers/{publisher_id}",
    response_model=PublisherDetailResponse,
    summary="更新发布主体信息（仅 owner/admin 成员，verified_status 不可改）",
)
async def update_publisher(
    publisher_id: int,
    data: PublisherProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新发布主体基本信息。

    权限：
    - 必须登录且为当前租户成员
    - 必须是该主体的 owner 或 admin 成员
    - verified_status 不可通过本接口修改（仅 admin 审核接口可流转）

    TEN-02.3: 跨校主体统一 404。
    """
    assert_writable_in_tenant(tenant)
    p = await _load_publisher(db, publisher_id, tenant)

    membership = await _load_membership(db, p.id, current_user.id)
    if not _can_manage(membership):
        raise ForbiddenException(detail="仅主体 owner/admin 成员可修改")

    # 校验 location_id
    if data.location_id is not None:
        loc = await db.scalar(select(Location).where(Location.id == data.location_id))
        if loc is None:
            raise BadRequestException(detail="服务地点不存在")
        check_resource_in_tenant(loc.school_id, tenant)

    if data.name is not None:
        p.name = data.name
    if data.intro is not None:
        p.intro = data.intro
    if data.logo_url is not None:
        p.logo_url = data.logo_url
    if data.location_id is not None:
        p.location_id = data.location_id
    if data.service_hours is not None:
        p.service_hours = data.service_hours
    if data.contact is not None:
        p.contact = data.contact
    p.updated_at = datetime.now()

    await db.commit()
    await db.refresh(p)

    return await _enrich_publisher_response(
        db, p, tenant, include_members=True, include_recent=True,
    )


@router.get(
    "/me/publishers",
    response_model=List[PublisherBrief],
    summary="当前用户加入的发布主体列表",
)
async def list_my_publishers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """列出当前用户在本校加入的发布主体。TEN-02.3: 按当前学校过滤。"""
    rows = await db.execute(
        select(PublisherProfile)
        .join(PublisherMembership, PublisherMembership.publisher_id == PublisherProfile.id)
        .where(
            PublisherMembership.user_id == current_user.id,
            PublisherProfile.school_id == tenant.school_id,
            PublisherProfile.is_deleted == False,  # noqa: E712
        )
        .order_by(PublisherMembership.joined_at.desc())
    )
    publishers = rows.scalars().all()
    return [
        PublisherBrief(
            id=p.id,
            name=p.name,
            type=p.type,
            logo_url=p.logo_url,
            verified_status=p.verified_status,
            intro=p.intro,
            subscribe_count=p.subscribe_count,
            view_count=p.view_count,
        )
        for p in publishers
    ]


# ============================================================
# 模板接口（用户端）
# ============================================================
@router.get(
    "/templates",
    response_model=List[PostTemplateResponse],
    summary="学校级公共模板列表（用于 PostForm 选择）",
)
async def list_public_templates(
    scene: Optional[str] = Query(None, description="按场景筛选"),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """ORG-01.3: 列出本校公共模板（publisher_id IS NULL）。

    公开接口（游客也可看模板列表，便于浏览；但应用模板发布需登录）。
    TEN-02.3: 按当前学校过滤。
    """
    base_filter = [
        PostTemplate.school_id == tenant.school_id,
        PostTemplate.is_active == True,  # noqa: E712
        PostTemplate.publisher_id.is_(None),
    ]
    if scene:
        base_filter.append(PostTemplate.scene == scene)

    rows = await db.execute(
        select(PostTemplate)
        .where(*base_filter)
        .order_by(PostTemplate.sort_order.asc(), PostTemplate.id.asc())
    )
    templates = rows.scalars().all()
    return [PostTemplateResponse(**_template_to_dict(t)) for t in templates]


@router.get(
    "/publishers/{publisher_id}/templates",
    response_model=List[PostTemplateResponse],
    summary="主体专属模板列表",
)
async def list_publisher_templates(
    publisher_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """列出指定主体的专属模板（公开，主页展示）。

    TEN-02.3: 跨校主体统一 404。
    """
    p = await _load_publisher(db, publisher_id, tenant)

    rows = await db.execute(
        select(PostTemplate)
        .where(
            PostTemplate.publisher_id == p.id,
            PostTemplate.is_active == True,  # noqa: E712
        )
        .order_by(PostTemplate.sort_order.asc(), PostTemplate.id.asc())
    )
    templates = rows.scalars().all()
    return [PostTemplateResponse(**_template_to_dict(t)) for t in templates]


@router.post(
    "/publishers/{publisher_id}/templates",
    response_model=PostTemplateResponse,
    summary="创建主体专属模板（仅 owner/admin 成员）",
)
async def create_publisher_template(
    publisher_id: int,
    data: PostTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """ORG-01.3: 主体 owner/admin 成员创建专属模板。

    AI 只补全建议，发布者确认——本接口仅创建模板结构，不调用 AI。
    TEN-02.3: 跨校主体统一 404。
    """
    assert_writable_in_tenant(tenant)
    p = await _load_publisher(db, publisher_id, tenant)

    membership = await _load_membership(db, p.id, current_user.id)
    if not _can_manage(membership):
        raise ForbiddenException(detail="仅主体 owner/admin 成员可创建模板")

    # 强制 publisher_id 为路径参数的值，忽略 body 中的 publisher_id
    now = datetime.now()
    template = PostTemplate(
        school_id=tenant.school_id,
        publisher_id=p.id,
        name=data.name,
        title_template=data.title_template,
        content_template=data.content_template,
        category_id=data.category_id,
        scene=data.scene,
        sort_order=data.sort_order,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return PostTemplateResponse(**_template_to_dict(template))


@router.put(
    "/templates/{template_id}",
    response_model=PostTemplateResponse,
    summary="更新模板",
)
async def update_template(
    template_id: int,
    data: PostTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新模板。

    权限：
    - 学校级公共模板（publisher_id IS NULL）：仅 admin 可改
    - 主体专属模板：主体 owner/admin 成员可改

    TEN-02.3: 跨校模板统一 404。
    """
    assert_writable_in_tenant(tenant)
    t = await db.scalar(select(PostTemplate).where(PostTemplate.id == template_id))
    if t is None:
        raise NotFoundException(detail="模板不存在")
    check_resource_in_tenant(t.school_id, tenant)

    if t.publisher_id is None:
        # 学校级公共模板：仅 admin 可改
        if not tenant.is_admin_in_tenant:
            raise ForbiddenException(detail="学校级公共模板仅管理员可修改")
    else:
        # 主体专属模板：owner/admin 成员可改
        p = await _load_publisher(db, t.publisher_id, tenant)
        membership = await _load_membership(db, p.id, current_user.id)
        if not _can_manage(membership):
            raise ForbiddenException(detail="仅主体 owner/admin 成员可修改模板")

    if data.name is not None:
        t.name = data.name
    if data.title_template is not None:
        t.title_template = data.title_template
    if data.content_template is not None:
        t.content_template = data.content_template
    if data.category_id is not None:
        t.category_id = data.category_id
    if data.scene is not None:
        t.scene = data.scene
    if data.sort_order is not None:
        t.sort_order = data.sort_order
    if data.is_active is not None:
        t.is_active = data.is_active
    t.updated_at = datetime.now()

    await db.commit()
    await db.refresh(t)
    return PostTemplateResponse(**_template_to_dict(t))


def _template_to_dict(t: PostTemplate) -> dict:
    """将 PostTemplate ORM 转为响应字典（含 publisher_name）"""
    return {
        "id": t.id,
        "school_id": t.school_id,
        "publisher_id": t.publisher_id,
        "publisher_name": None,  # 暂不预加载，列表场景前端可用 publisher_id 二次查询
        "name": t.name,
        "title_template": t.title_template,
        "content_template": t.content_template,
        "category_id": t.category_id,
        "scene": t.scene,
        "sort_order": t.sort_order,
        "is_active": t.is_active,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }
