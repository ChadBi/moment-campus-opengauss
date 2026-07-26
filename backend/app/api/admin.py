from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json

from app.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.post_image import PostImage
from app.models.post_type import PostType
from app.models.location import Location
from app.models.report import Report
from app.models.post_change_report import PostChangeReport
from app.models.admin_operation_log import AdminOperationLog
from app.models.category import Category
from app.models.tag import Tag
from app.models.post_tag import PostTag
from app.models.comment import Comment
from app.models.notification import Notification
from app.models.school_membership import SchoolMembership
from app.models.school_settings import SchoolSettings
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.admin import (
    DashboardStats,
    AdminLogResponse,
    CategoryCreate,
    CategoryUpdate,
    CategoryAdminResponse,
    TagAdminResponse,
    TagUpdate,
    TagMergeRequest,
    BatchApproveRequest,
    BatchRejectRequest,
    BatchToggleActiveRequest,
    BatchFailedItem,
    BatchOperationResponse,
    TodoStats,
    TodoItem,
    AdminPostDetail,
    AuthorHistoryStats,
    ReasonTemplate,
    ReasonTemplateResponse,
    GovernanceReportBrief,
    GovernanceHandleRequest,
    LocationAdminResponse,
    ExpirePostsJobRequest,
    JobRunRecordResponse,
    SchoolSettingsResponse,
    SchoolSettingsUpdate,
)
from app.core.exceptions import (
    NotFoundException, BadRequestException, ConflictException, ForbiddenException,
)
from app.core.permissions import require_role, Role
from app.core.post_status import can_transition, PostStatus
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.entitlement import EntitlementService, EntitlementKey
from app.models.tenant_usage_daily import TenantUsageDaily

router = APIRouter(tags=["管理"])


# FND-03.3: 统一管理员依赖（替代旧 get_current_admin）
# 所有管理路由统一通过 require_role(Role.ADMIN) 校验，user < admin < super_admin
AdminDep = Depends(require_role(Role.ADMIN))


def _check_post_in_admin_school(post: Post, tenant: TenantContext) -> None:
    """FND-03.3 + TEN-02.3: 资源级校验——跨校访问统一返回 404。

    委托给 check_resource_in_tenant，避免泄露存在性。
    super_admin 跨校操作由 TenantContext 解析时已处理（指定 X-School-Code）。
    """
    check_resource_in_tenant(post.school_id, tenant)


def add_review_notification(
    db: AsyncSession,
    post: Post,
    admin: User,
    approved: bool,
    reason: Optional[str] = None,
) -> None:
    """给帖子作者写入审核结果通知。"""
    title = "帖子审核通过" if approved else "帖子审核未通过"
    # PUB-02: 驳回 = pending → draft，作者可修改后重新提交，通知中给出下一步动作
    action_text = "已审核通过并公开展示" if approved else "未通过审核，已退回草稿，可修改后重新提交"
    content = f"你的《{post.title}》{action_text}。"
    if reason:
        content = f"{content}备注：{reason}"

    db.add(Notification(
        user_id=post.user_id,
        type="audit",
        title=title,
        content=content[:500],
        target_type="post",
        target_id=post.id,
        actor_id=admin.id,
        is_read=False,
    ))


class PostBrief(BaseModel):
    """帖子简要信息（用于审核列表）"""
    id: int
    title: str
    content: str
    status: str
    created_at: datetime
    author_id: int
    author_name: Optional[str] = None
    category_id: int
    category_name: Optional[str] = None


class UserBrief(BaseModel):
    """用户简要信息（用于用户列表）"""
    id: int
    email: str
    nickname: str
    role: str
    is_active: bool
    created_at: datetime
    school_id: int


class ReportBrief(BaseModel):
    """举报简要信息（用于举报列表）"""
    id: int
    post_id: Optional[int] = None
    post_title: Optional[str] = None
    reporter_id: int
    reporter_name: Optional[str] = None
    report_type: str
    description: Optional[str] = None
    status: str
    created_at: datetime


class ApproveRequest(BaseModel):
    """审核通过请求"""
    reason: Optional[str] = Field(None, max_length=500, description="审核备注")


class RejectRequest(BaseModel):
    """审核拒绝请求"""
    reason: str = Field(..., min_length=1, max_length=500, description="拒绝原因")


class ToggleActiveRequest(BaseModel):
    """禁用/启用用户请求"""
    is_active: bool = Field(..., description="是否启用")
    reason: Optional[str] = Field(None, max_length=500, description="操作原因")


class HandleReportRequest(BaseModel):
    """处理举报请求"""
    action: str = Field(..., pattern="^(dismiss|warn|delete_post|ban_user)$", description="处理动作")
    reason: str = Field(..., min_length=1, max_length=500, description="处理说明")


@router.get("/admin/posts/pending", response_model=PaginatedResponse[PostBrief])
async def get_pending_posts(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    获取待审核信息列表

    DSC-01.2: 使用 joinedload 预加载 author 和 category，消除每帖单独查询的 N+1。
    TEN-02.3：按当前学校过滤，跨校帖子不会出现在待审核列表中。
    """
    # 查询待审核帖子（TEN-02.3: 强制按当前学校过滤）
    # DSC-01.2: 在基础查询阶段就加入 joinedload，避免每帖单独查 author 和 category
    query = (
        select(Post)
        .where(
            Post.status == "pending",
            Post.is_deleted == False,
            Post.school_id == tenant.school_id,
        )
        .options(
            joinedload(Post.user),
            joinedload(Post.category),
        )
        .order_by(Post.created_at.desc())
    )

    # 计算总数（基于无 offset/limit 的子查询）
    count_query = select(func.count()).select_from(
        select(Post).where(
            Post.status == "pending",
            Post.is_deleted == False,
            Post.school_id == tenant.school_id,
        ).subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询（已预加载关联）
    result = await db.execute(query)
    posts = result.unique().scalars().all()

    # 构建响应（关联数据已预加载，无额外查询）
    items = []
    for post in posts:
        items.append(PostBrief(
            id=post.id,
            title=post.title,
            content=post.content[:200] if len(post.content) > 200 else post.content,
            status=post.status,
            created_at=post.created_at,
            author_id=post.user_id,
            author_name=post.user.nickname if post.user else None,
            category_id=post.category_id,
            category_name=post.category.name if post.category else None,
        ))

    return PaginatedResponse.create(items, page, page_size, total)


@router.put("/admin/posts/{post_id}/approve", response_model=MessageResponse)
async def approve_post(
    post_id: int,
    data: ApproveRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    审核通过帖子

    FND-03.2/FND-03.3: 状态变化通过状态机校验，资源级校验帖子属于当前学校。
    TEN-02.3: 跨校对象统一返回 404。
    """
    # 查询帖子
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise NotFoundException(detail="帖子不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    _check_post_in_admin_school(post, tenant)

    if post.status != PostStatus.PENDING:
        raise BadRequestException(detail="帖子状态不正确，无法审核")

    # FND-03.2: 通过状态机校验 pending → published
    if not can_transition(PostStatus.PENDING, PostStatus.PUBLISHED):
        raise BadRequestException(detail="状态机不允许 pending → published 流转")

    # 更新状态（审核通过 = published，与状态机和列表查询条件一致）
    post.status = PostStatus.PUBLISHED
    post.updated_at = datetime.now()

    # 记录操作日志
    log = AdminOperationLog(
        admin_id=admin.id,
        action="approve_post",
        target_type="post",
        target_id=post_id,
        detail=data.reason,
    )
    db.add(log)
    add_review_notification(db, post, admin, approved=True, reason=data.reason)

    # SUB-01.2: 新帖发布订阅通知（pending → published 时触发；幂等，重复审核不重复通知）
    # 与审核结果通知（audit 类）互补：本通知面向订阅者，audit 通知面向作者
    from app.services.subscription_notifier import notify_new_post
    await notify_new_post(db, post, actor_id=admin.id)

    await db.commit()

    return MessageResponse(message="帖子已审核通过")


@router.put("/admin/posts/{post_id}/reject", response_model=MessageResponse)
async def reject_post(
    post_id: int,
    data: RejectRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    审核拒绝帖子

    FND-03.2/FND-03.3: 状态变化通过状态机校验，资源级校验帖子属于当前学校。
    TEN-02.3: 跨校对象统一返回 404。
    """
    # 查询帖子
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise NotFoundException(detail="帖子不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    _check_post_in_admin_school(post, tenant)

    if post.status != PostStatus.PENDING:
        raise BadRequestException(detail="帖子状态不正确，无法审核")

    # FND-03.2 + PUB-02: 驳回 = pending → draft（退回草稿，作者可修改后重新提交）
    if not can_transition(PostStatus.PENDING, PostStatus.DRAFT):
        raise BadRequestException(detail="状态机不允许 pending → draft 流转")

    # 更新状态（驳回 = draft，作者可在"我的发布-草稿"中继续编辑并重新提交）
    post.status = PostStatus.DRAFT
    post.updated_at = datetime.now()

    # 记录操作日志
    log = AdminOperationLog(
        admin_id=admin.id,
        action="reject_post",
        target_type="post",
        target_id=post_id,
        detail=f"驳回原因：{data.reason}",
    )
    db.add(log)
    add_review_notification(db, post, admin, approved=False, reason=data.reason)

    await db.commit()

    return MessageResponse(message="帖子已驳回，已退回作者草稿")


@router.get("/admin/users", response_model=PaginatedResponse[UserBrief])
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    获取用户列表

    TEN-02.3：按当前学校过滤，跨校用户不会出现在列表中。
    """
    # 构建查询（TEN-02.3: 强制按当前学校过滤）
    query = select(User).where(
        User.is_deleted == False,
        User.school_id == tenant.school_id,
    )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    query = query.order_by(User.created_at.desc())

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询
    result = await db.execute(query)
    users = result.scalars().all()

    # 构建响应
    items = [
        UserBrief(
            id=user.id,
            email=user.email,
            nickname=user.nickname,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            school_id=user.school_id,
        )
        for user in users
    ]

    return PaginatedResponse.create(items, page, page_size, total)


@router.put("/admin/users/{user_id}/toggle-active", response_model=MessageResponse)
async def toggle_user_active(
    user_id: int,
    data: ToggleActiveRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    禁用/启用用户

    TEN-02.3：跨校用户统一返回 404。
    """
    # 查询用户
    query = select(User).where(User.id == user_id, User.is_deleted == False)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundException(detail="用户不存在")

    # TEN-02.3: 资源级租户校验——跨校用户统一 404
    check_resource_in_tenant(user.school_id, tenant)

    if user.id == admin.id:
        raise BadRequestException(detail="不能修改自己的状态")

    # 更新状态
    user.is_active = data.is_active
    user.updated_at = datetime.now()

    # 记录操作日志
    action = "enable_user" if data.is_active else "disable_user"
    log = AdminOperationLog(
        admin_id=admin.id,
        action=action,
        target_type="user",
        target_id=user_id,
        detail=data.reason,
    )
    db.add(log)

    await db.commit()

    status_text = "启用" if data.is_active else "禁用"
    return MessageResponse(message=f"用户已{status_text}")


@router.get("/admin/reports", response_model=PaginatedResponse[ReportBrief])
async def get_reports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="举报状态"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    获取举报列表

    DSC-01.2: 使用 selectinload 预加载 reporter 与 post，消除每举报单独查询的 N+1。
    TEN-02.3：按当前学校过滤，跨校举报不会出现在列表中。
    """
    # 构建查询（TEN-02.3: 通过 join Post 强制按当前学校过滤）
    # DSC-01.2: 使用 selectinload 批量预加载 reporter 与 post，避免每行单独查询
    base_filter = or_(
        Post.school_id == tenant.school_id,
        Post.id.is_(None),  # 举报无关联帖子时仍可见（数据兼容）
    )

    query = (
        select(Report)
        .outerjoin(Post, Report.post_id == Post.id)
        .where(base_filter)
        .options(
            selectinload(Report.post),
            selectinload(Report.reporter),
        )
        .order_by(Report.created_at.desc())
    )

    if status:
        query = query.where(Report.status == status)

    # 计算总数（基于 base_filter，不含 selectinload）
    count_query = (
        select(func.count())
        .select_from(Report)
        .outerjoin(Post, Report.post_id == Post.id)
        .where(base_filter)
    )
    if status:
        count_query = count_query.where(Report.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询（已预加载关联）
    result = await db.execute(query)
    reports = result.unique().scalars().all()

    # 构建响应（关联数据已预加载，无额外查询）
    items = []
    for report in reports:
        post_title = report.post.title if report.post else None
        reporter = report.reporter
        items.append(ReportBrief(
            id=report.id,
            post_id=report.post_id,
            post_title=post_title,
            reporter_id=report.reporter_id,
            reporter_name=reporter.nickname if reporter else None,
            report_type=report.report_type,
            description=report.description,
            status=report.status,
            created_at=report.created_at,
        ))

    return PaginatedResponse.create(items, page, page_size, total)


@router.put("/admin/reports/{report_id}/handle", response_model=MessageResponse)
async def handle_report(
    report_id: int,
    data: HandleReportRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    处理举报

    TEN-02.3：跨校对象统一返回 404。
    """
    # 查询举报
    query = select(Report).where(Report.id == report_id)
    result = await db.execute(query)
    report = result.scalar_one_or_none()

    if not report:
        raise NotFoundException(detail="举报不存在")

    if report.status != "pending":
        raise BadRequestException(detail="举报已处理")

    # 更新举报状态
    report.status = "handled"
    report.handler_id = admin.id
    report.handle_result = f"处理动作：{data.action}，原因：{data.reason}"
    report.handled_at = datetime.now()
    report.updated_at = datetime.now()

    # 根据处理动作执行相应操作
    if data.action == "delete_post" and report.post_id:
        # FND-03.2/FND-03.3: 删除帖子走 is_deleted=True + 状态机 → archived，
        # 不写第 7 种 deleted 状态；同时校验管理员对本校帖子的资源权限
        post_query = select(Post).where(Post.id == report.post_id)
        post_result = await db.execute(post_query)
        post = post_result.scalar_one_or_none()
        if post:
            _check_post_in_admin_school(post, tenant)
            post.is_deleted = True
            post.deleted_at = datetime.now()
            if post.status != PostStatus.ARCHIVED:
                if not can_transition(post.status, PostStatus.ARCHIVED):
                    raise BadRequestException(
                        detail=f"当前状态 {post.status} 不允许归档"
                    )
                post.status = PostStatus.ARCHIVED
                post.updated_at = datetime.now()

    elif data.action == "ban_user":
        # 禁用被举报者（帖子作者）
        if report.post_id:
            post_query = select(Post).where(Post.id == report.post_id)
            post_result = await db.execute(post_query)
            post = post_result.scalar_one_or_none()
            if post:
                # FND-03.3: 资源级校验
                _check_post_in_admin_school(post, tenant)
                user_query = select(User).where(User.id == post.user_id)
                user_result = await db.execute(user_query)
                user = user_result.scalar_one_or_none()
                if user:
                    user.is_active = False

    # 记录操作日志
    log = AdminOperationLog(
        admin_id=admin.id,
        action="handle_report",
        target_type="report",
        target_id=report_id,
        detail=report.handle_result,
    )
    db.add(log)

    await db.commit()

    return MessageResponse(message="举报已处理")


# ============================================================
# 仪表盘统计
# ============================================================
@router.get("/admin/stats", response_model=DashboardStats, summary="仪表盘统计数据")
async def get_admin_stats(
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """返回管理员仪表盘的各项统计数据

    TEN-02.3：所有统计按当前学校过滤。
    """
    # 信息总数（未删除，TEN-02.3: 按当前学校过滤）
    total_posts = await db.scalar(
        select(func.count(Post.id)).where(
            Post.is_deleted == False,
            Post.school_id == tenant.school_id,
        )
    )
    # 待审核信息数
    pending_posts = await db.scalar(
        select(func.count(Post.id)).where(
            Post.status == "pending",
            Post.is_deleted == False,
            Post.school_id == tenant.school_id,
        )
    )
    # 用户总数（未删除）
    total_users = await db.scalar(
        select(func.count(User.id)).where(
            User.is_deleted == False,
            User.school_id == tenant.school_id,
        )
    )
    # 活跃用户数
    active_users = await db.scalar(
        select(func.count(User.id)).where(
            User.is_active == True,
            User.is_deleted == False,
            User.school_id == tenant.school_id,
        )
    )
    # 举报总数（TEN-02.3: 通过 Post join 按学校过滤）
    total_reports = await db.scalar(
        select(func.count(Report.id)).outerjoin(Post, Report.post_id == Post.id).where(
            or_(
                Post.school_id == tenant.school_id,
                Post.id.is_(None),
            )
        )
    )
    # 待处理举报数
    pending_reports = await db.scalar(
        select(func.count(Report.id)).outerjoin(Post, Report.post_id == Post.id).where(
            Report.status == "pending",
            or_(
                Post.school_id == tenant.school_id,
                Post.id.is_(None),
            ),
        )
    )
    # 评论总数（未删除，TEN-02.3: 通过 Post join 按学校过滤）
    total_comments = await db.scalar(
        select(func.count(Comment.id)).join(Post, Comment.post_id == Post.id).where(
            Comment.is_deleted == False,
            Post.school_id == tenant.school_id,
        )
    )

    return DashboardStats(
        total_posts=total_posts or 0,
        pending_posts=pending_posts or 0,
        total_users=total_users or 0,
        active_users=active_users or 0,
        total_reports=total_reports or 0,
        pending_reports=pending_reports or 0,
        total_comments=total_comments or 0,
    )


# ============================================================
# ADM-01.1: 校级待办统计（首页待办卡片）
# ============================================================
@router.get("/admin/todos", response_model=TodoStats, summary="校级待办统计（ADM-01.1）")
async def get_admin_todos(
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """返回校级后台首页 7 类待办统计，每项附带前端队列跳转路径（含筛选参数）。

    待办类别：待审核 / 待处理举报 / 待核验地点 / 过期报告 / 冲突报告 /
    更新建议 / 异常任务（24h 内失败的任务运行记录）。

    TEN-02.3：全部按当前学校过滤；任务运行记录为全局任务，不按学校过滤。
    """
    # 待审核内容
    pending_posts = await db.scalar(
        select(func.count(Post.id)).where(
            Post.status == PostStatus.PENDING,
            Post.is_deleted == False,
            Post.school_id == tenant.school_id,
        )
    )
    # 待处理举报
    pending_reports = await db.scalar(
        select(func.count(Report.id)).outerjoin(Post, Report.post_id == Post.id).where(
            Report.status == "pending",
            or_(Post.school_id == tenant.school_id, Post.id.is_(None)),
        )
    )
    # 待核验地点
    unverified_locations = await db.scalar(
        select(func.count(Location.id)).where(
            Location.is_verified == False,
            Location.is_deleted == False,
            Location.school_id == tenant.school_id,
        )
    )

    # 3 类未结案问题报告（open/in_review），join Post 按学校过滤
    async def _count_change_reports(report_type: str) -> int:
        return await db.scalar(
            select(func.count(PostChangeReport.id))
            .join(Post, PostChangeReport.post_id == Post.id)
            .where(
                PostChangeReport.report_type == report_type,
                PostChangeReport.status.in_(["open", "in_review"]),
                Post.school_id == tenant.school_id,
            )
        ) or 0

    expiration_reports = await _count_change_reports("expiration_report")
    conflict_reports = await _count_change_reports("conflict_report")
    update_suggestions = await _count_change_reports("update")

    # 异常任务：24h 内失败的任务运行记录（全局任务，跨校共享）
    from app.models.job_run_record import JobRunRecord
    from datetime import timedelta
    failed_jobs = await db.scalar(
        select(func.count(JobRunRecord.id)).where(
            JobRunRecord.status == "failed",
            JobRunRecord.started_at >= datetime.now() - timedelta(hours=24),
        )
    )

    # REL-02.3: 本校最近 24h AI 调用降级率（本地环境采样监控）
    from app.models.ai_invocation_log import AIInvocationLog
    ai_window_start = datetime.now() - timedelta(hours=24)
    ai_calls_24h = await db.scalar(
        select(func.count(AIInvocationLog.id)).where(
            AIInvocationLog.school_id == tenant.school_id,
            AIInvocationLog.created_at >= ai_window_start,
        )
    ) or 0
    ai_fallback_24h = await db.scalar(
        select(func.count(AIInvocationLog.id)).where(
            AIInvocationLog.school_id == tenant.school_id,
            AIInvocationLog.created_at >= ai_window_start,
            AIInvocationLog.fallback_reason.isnot(None),
        )
    ) or 0
    ai_fallback_rate = (
        round(ai_fallback_24h / ai_calls_24h, 4) if ai_calls_24h > 0 else 0.0
    )

    items = [
        TodoItem(key="pending_posts", label="待审核内容", count=pending_posts or 0,
                 queue_url="/admin/review"),
        TodoItem(key="pending_reports", label="待处理举报", count=pending_reports or 0,
                 queue_url="/admin/reports?status=pending"),
        TodoItem(key="unverified_locations", label="待核验地点", count=unverified_locations or 0,
                 queue_url="/admin/locations?verified=false"),
        TodoItem(key="expiration_reports", label="过期报告", count=expiration_reports,
                 queue_url="/admin/governance?type=expiration_report&status=open"),
        TodoItem(key="conflict_reports", label="冲突报告", count=conflict_reports,
                 queue_url="/admin/governance?type=conflict_report&status=open"),
        TodoItem(key="update_suggestions", label="更新建议", count=update_suggestions,
                 queue_url="/admin/governance?type=update&status=open"),
        TodoItem(key="failed_jobs", label="异常任务", count=failed_jobs or 0,
                 queue_url="/admin/jobs?status=failed"),
    ]
    total = sum(i.count for i in items)

    return TodoStats(
        pending_posts=pending_posts or 0,
        pending_reports=pending_reports or 0,
        unverified_locations=unverified_locations or 0,
        expiration_reports=expiration_reports,
        conflict_reports=conflict_reports,
        update_suggestions=update_suggestions,
        failed_jobs=failed_jobs or 0,
        total=total,
        items=items,
        ai_calls_24h=int(ai_calls_24h),
        ai_fallback_24h=int(ai_fallback_24h),
        ai_fallback_rate=ai_fallback_rate,
    )


# ============================================================
# ADM-01.3: 审核原因模板
# ============================================================
APPROVE_REASON_TEMPLATES: list[dict] = [
    {"code": "approve_ok", "label": "内容合规",
     "text": "内容真实有效，符合社区规范，审核通过。"},
    {"code": "approve_verified", "label": "已核实",
     "text": "经核实信息属实，审核通过并公开展示。"},
]

REJECT_REASON_TEMPLATES: list[dict] = [
    {"code": "reject_invalid", "label": "内容不实",
     "text": "信息内容不实或已失效，请核实后重新发布。"},
    {"code": "reject_ad", "label": "广告营销",
     "text": "内容包含广告营销信息，不符合校园信息发布规范。"},
    {"code": "reject_inappropriate", "label": "不当内容",
     "text": "内容包含不当言论或敏感信息，不予通过。"},
    {"code": "reject_incomplete", "label": "信息不完整",
     "text": "信息要素不完整（缺少时间/地点/联系方式等），请补充后重新提交。"},
    {"code": "reject_duplicate", "label": "重复发布",
     "text": "与已发布信息重复，请勿重复提交。"},
]


@router.get(
    "/admin/review/templates",
    response_model=ReasonTemplateResponse,
    summary="审核原因模板（ADM-01.3）",
)
async def get_review_templates(admin: User = AdminDep):
    """返回通过/驳回的预设原因模板，前端可在模板基础上自定义修改。"""
    return ReasonTemplateResponse(
        approve=[ReasonTemplate(**t) for t in APPROVE_REASON_TEMPLATES],
        reject=[ReasonTemplate(**t) for t in REJECT_REASON_TEMPLATES],
    )


# ============================================================
# ADM-01.2: 审核详情（管理专用接口）
# ============================================================
@router.get(
    "/admin/posts/{post_id}",
    response_model=AdminPostDetail,
    summary="审核详情（管理专用接口，ADM-01.2）",
)
async def get_admin_post_detail(
    post_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """审核详情：完整内容、分类、地点、有效期、图片、作者历史与治理概况。

    管理专用接口，不依赖公开帖子详情（公开详情对 pending 帖子不可见）。
    TEN-02.3：跨校帖子统一返回 404。
    """
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id, Post.is_deleted == False)
        .options(
            joinedload(Post.user),
            joinedload(Post.category),
            joinedload(Post.post_type),
            joinedload(Post.location),
        )
    )
    post = result.unique().scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")
    _check_post_in_admin_school(post, tenant)

    # 图片
    image_rows = await db.execute(
        select(PostImage.image_url).where(
            PostImage.post_id == post_id,
            PostImage.is_deleted == False,
        ).order_by(PostImage.sort_order.asc())
    )
    images = [row[0] for row in image_rows.all()]

    # 作者历史统计（同校范围）
    author_posts = await db.execute(
        select(Post.status, func.count(Post.id)).where(
            Post.user_id == post.user_id,
            Post.school_id == tenant.school_id,
            Post.is_deleted == False,
        ).group_by(Post.status)
    )
    status_counts = {row[0]: row[1] for row in author_posts.all()}
    author_total = sum(status_counts.values())
    # 作者收到的举报数（其帖子被举报次数）
    author_report_count = await db.scalar(
        select(func.count(Report.id))
        .join(Post, Report.post_id == Post.id)
        .where(Post.user_id == post.user_id, Post.school_id == tenant.school_id)
    )

    # 本帖治理概况
    open_change_reports = await db.scalar(
        select(func.count(PostChangeReport.id)).where(
            PostChangeReport.post_id == post_id,
            PostChangeReport.status.in_(["open", "in_review"]),
        )
    )
    pending_user_reports = await db.scalar(
        select(func.count(Report.id)).where(
            Report.post_id == post_id,
            Report.status == "pending",
        )
    )

    return AdminPostDetail(
        id=post.id,
        title=post.title,
        content=post.content,
        status=post.status,
        is_anonymous=post.is_anonymous,
        created_at=post.created_at,
        updated_at=post.updated_at,
        expire_at=post.expire_at,
        contact_info=post.contact_info,
        lost_type=post.lost_type,
        view_count=post.view_count,
        like_count=post.like_count,
        comment_count=post.comment_count,
        valid_count=post.valid_count,
        invalid_count=post.invalid_count,
        author_id=post.user_id,
        author_name=post.user.nickname if post.user else None,
        author_email=post.user.email if post.user else None,
        category_id=post.category_id,
        category_name=post.category.name if post.category else None,
        post_type_id=post.post_type_id,
        post_type_name=post.post_type.name if post.post_type else None,
        location_id=post.location_id,
        location_name=post.location.name if post.location else None,
        location_verified=post.location.is_verified if post.location else None,
        images=images,
        author_history=AuthorHistoryStats(
            total_posts=author_total,
            published_posts=status_counts.get(PostStatus.PUBLISHED, 0),
            rejected_posts=status_counts.get(PostStatus.ARCHIVED, 0),
            report_received_count=author_report_count or 0,
        ),
        open_change_reports=open_change_reports or 0,
        pending_user_reports=pending_user_reports or 0,
    )


# ============================================================
# ADM-01.5: 治理工作台（3 类问题报告队列 + 处理动作）
# ============================================================
@router.get(
    "/admin/governance/reports",
    response_model=PaginatedResponse[GovernanceReportBrief],
    summary="治理报告队列（ADM-01.5）",
)
async def list_governance_reports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    report_type: Optional[str] = Query(
        None, description="按类型筛选：update/expiration_report/conflict_report"
    ),
    status: Optional[str] = Query(
        None, description="按状态筛选：open/in_review/resolved/dismissed"
    ),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """跨帖子的问题报告队列（合并 3 类协同治理报告的管理入口）。

    TEN-02.3：join Post 强制按当前学校过滤，跨校报告不会出现。
    """
    base_filter = [Post.school_id == tenant.school_id]
    if report_type:
        base_filter.append(PostChangeReport.report_type == report_type)
    if status:
        base_filter.append(PostChangeReport.status == status)

    query = (
        select(PostChangeReport)
        .join(Post, PostChangeReport.post_id == Post.id)
        .where(*base_filter)
        .options(
            selectinload(PostChangeReport.post),
            selectinload(PostChangeReport.reporter),
            selectinload(PostChangeReport.handler),
        )
        .order_by(PostChangeReport.created_at.desc())
    )

    count_query = (
        select(func.count(PostChangeReport.id))
        .join(Post, PostChangeReport.post_id == Post.id)
        .where(*base_filter)
    )
    total = await db.scalar(count_query)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    reports = result.unique().scalars().all()

    items = [
        GovernanceReportBrief(
            id=r.id,
            post_id=r.post_id,
            post_title=r.post.title if r.post else None,
            post_status=r.post.status if r.post else None,
            reporter_id=r.reporter_id,
            reporter_name=r.reporter.nickname if r.reporter else None,
            report_type=r.report_type,
            description=r.description,
            evidence_url=r.evidence_url,
            status=r.status,
            handler_id=r.handler_id,
            handler_name=r.handler.nickname if r.handler else None,
            handler_note=r.handler_note,
            handled_at=r.handled_at,
            created_at=r.created_at,
        )
        for r in reports
    ]
    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.put(
    "/admin/governance/reports/{report_id}/handle",
    response_model=GovernanceReportBrief,
    summary="处理治理报告（ADM-01.5，同事务提交）",
)
async def handle_governance_report(
    report_id: int,
    data: GovernanceHandleRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """处理问题报告：报告状态流转 + 帖子状态变化 + 通知在同一事务中提交。

    - resolve：标记已解决（帖子状态不变）
    - dismiss：驳回报告（帖子状态不变）
    - mark_expired：确认过期 → 帖子转 expired（状态机校验）
    - mark_conflict：确认冲突 → 帖子转 conflict（状态机校验）

    处理动作、报告状态、帖子状态与通知作者/报告人在同一事务提交，
    任一失败整体回滚。TEN-02.3：跨校报告统一返回 404。
    """
    result = await db.execute(
        select(PostChangeReport)
        .where(PostChangeReport.id == report_id)
        .options(
            selectinload(PostChangeReport.reporter),
            selectinload(PostChangeReport.handler),
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise NotFoundException(detail="报告不存在")

    post = await db.scalar(select(Post).where(Post.id == report.post_id))
    if post is None:
        raise NotFoundException(detail="帖子不存在")
    _check_post_in_admin_school(post, tenant)

    if report.status in ("resolved", "dismissed"):
        raise BadRequestException(detail="报告已结案，不能重复处理")

    now = datetime.now()
    action_label = {
        "resolve": "标记已解决",
        "dismiss": "驳回",
        "mark_expired": "确认过期",
        "mark_conflict": "确认冲突",
    }[data.action]

    # 帖子状态变化（状态机校验）
    post_status_changed: Optional[str] = None
    if data.action == "mark_expired":
        if post.status != PostStatus.EXPIRED:
            if not can_transition(post.status, PostStatus.EXPIRED):
                raise BadRequestException(
                    detail=f"帖子当前状态 {post.status} 不允许转为 expired"
                )
            post.status = PostStatus.EXPIRED
            post_status_changed = PostStatus.EXPIRED
    elif data.action == "mark_conflict":
        if post.status != PostStatus.CONFLICT:
            if not can_transition(post.status, PostStatus.CONFLICT):
                raise BadRequestException(
                    detail=f"帖子当前状态 {post.status} 不允许转为 conflict"
                )
            post.status = PostStatus.CONFLICT
            post_status_changed = PostStatus.CONFLICT

    if post_status_changed:
        post.updated_at = now

    # 报告状态流转
    report.status = "resolved" if data.action != "dismiss" else "dismissed"
    report.handler_id = admin.id
    report.handler_note = f"{action_label}：{data.reason}"
    report.handled_at = now
    report.updated_at = now

    # 通知（同一事务）：通知报告人处理结果；帖子状态变化时同时通知作者
    type_label = {
        "update": "更新建议", "expiration_report": "过期报告", "conflict_report": "冲突报告",
    }.get(report.report_type, report.report_type)
    db.add(Notification(
        user_id=report.reporter_id,
        type="audit",
        title="问题报告已处理",
        content=f"你对《{post.title}》提交的{type_label}已处理：{action_label}。备注：{data.reason}"[:500],
        target_type="post",
        target_id=post.id,
        actor_id=admin.id,
        is_read=False,
    ))
    if post_status_changed and post.user_id != report.reporter_id:
        status_label = "已过期" if post_status_changed == PostStatus.EXPIRED else "冲突中"
        db.add(Notification(
            user_id=post.user_id,
            type="audit",
            title="帖子状态变更",
            content=f"你的《{post.title}》经管理员确认转为「{status_label}」。备注：{data.reason}"[:500],
            target_type="post",
            target_id=post.id,
            actor_id=admin.id,
            is_read=False,
        ))

    # 操作日志（同一事务）
    db.add(AdminOperationLog(
        admin_id=admin.id,
        action=f"governance_{data.action}",
        target_type="post_change_report",
        target_id=report_id,
        detail=f"{type_label} #{report_id} → {action_label}；原因：{data.reason}"
               + (f"；帖子 → {post_status_changed}" if post_status_changed else ""),
    ))

    # SUB-01.2: 订阅冲突通知（帖子转 conflict 时通知订阅者，与作者通知互补）
    if post_status_changed == PostStatus.CONFLICT:
        from app.services.subscription_notifier import notify_post_conflict
        await notify_post_conflict(db, post, actor_id=admin.id, reason=data.reason)

    # 同事务提交：报告状态 + 帖子状态 + 通知 + 日志
    await db.commit()

    handler_name = admin.nickname
    return GovernanceReportBrief(
        id=report.id,
        post_id=report.post_id,
        post_title=post.title,
        post_status=post.status,
        reporter_id=report.reporter_id,
        reporter_name=report.reporter.nickname if report.reporter else None,
        report_type=report.report_type,
        description=report.description,
        evidence_url=report.evidence_url,
        status=report.status,
        handler_id=report.handler_id,
        handler_name=handler_name,
        handler_note=report.handler_note,
        handled_at=report.handled_at,
        created_at=report.created_at,
    )


# ============================================================
# ADM-01.6: 地点核验
# ============================================================
@router.get(
    "/admin/locations",
    response_model=PaginatedResponse[LocationAdminResponse],
    summary="地点列表（管理视图，ADM-01.6）",
)
async def list_admin_locations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_verified: Optional[bool] = Query(None, description="按核验状态筛选"),
    keyword: Optional[str] = Query(None, description="按名称模糊搜索"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """地点管理列表：默认全部，支持按核验状态/名称筛选。

    TEN-02.3：按当前学校过滤。
    """
    query = select(Location).where(
        Location.school_id == tenant.school_id,
        Location.is_deleted == False,
    )
    if is_verified is not None:
        query = query.where(Location.is_verified == is_verified)
    if keyword:
        query = query.where(Location.name.ilike(f"%{keyword}%"))
    query = query.order_by(Location.is_verified.asc(), Location.created_at.desc())

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    locations = result.scalars().all()

    items = [
        LocationAdminResponse(
            id=loc.id,
            name=loc.name,
            description=loc.description,
            latitude=float(loc.latitude),
            longitude=float(loc.longitude),
            floor=loc.floor,
            building=loc.building,
            post_count=loc.post_count,
            is_verified=loc.is_verified,
            created_at=loc.created_at,
        )
        for loc in locations
    ]
    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.put(
    "/admin/locations/{location_id}/verify",
    response_model=LocationAdminResponse,
    summary="核验/取消核验地点（ADM-01.6）",
)
async def verify_location(
    location_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
    is_verified: bool = Query(True, description="true=核验通过 / false=取消核验"),
):
    """核验地点（或取消核验）。

    操作与日志在同一事务提交。TEN-02.3：跨校地点统一返回 404。
    """
    loc = await db.scalar(
        select(Location).where(Location.id == location_id, Location.is_deleted == False)
    )
    if not loc:
        raise NotFoundException(detail="地点不存在")
    check_resource_in_tenant(loc.school_id, tenant)

    if loc.is_verified == is_verified:
        raise BadRequestException(
            detail="地点已是核验状态" if is_verified else "地点已是未核验状态"
        )

    loc.is_verified = is_verified
    loc.updated_at = datetime.now()

    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="verify_location" if is_verified else "unverify_location",
        target_type="location",
        target_id=location_id,
        detail=f"{'核验通过' if is_verified else '取消核验'}地点：{loc.name}",
    ))
    await db.commit()

    return LocationAdminResponse(
        id=loc.id,
        name=loc.name,
        description=loc.description,
        latitude=float(loc.latitude),
        longitude=float(loc.longitude),
        floor=loc.floor,
        building=loc.building,
        post_count=loc.post_count,
        is_verified=loc.is_verified,
        created_at=loc.created_at,
    )


# ============================================================
# ADM-02.1: 学校设置 CRUD（仅本校 admin 可访问）
# ============================================================
# 学校设置在后端真实存储，跨浏览器生效。body 里的 school_id 不可改，
# 由 TenantContext 决定。PUT 时记录旧值/新值/操作者到 AdminOperationLog.detail
# （JSON 文本：{"old": {...}, "new": {...}, "changes": ["field: old -> new", ...]}）。
# 设置行可能在 super_admin 创建学校时由 SchoolProvisioningService 写入；
# 若 GET 时不存在，按默认值自动补建一份（防御性补全）。
_DEFAULT_SETTINGS_TEMPLATE: dict = {
    "site_name": None,
    "description": None,
    "require_review": True,
    "allow_anonymous": True,
    "allow_comments": True,
    "publish_frequency": 10,
    "image_limit": 9,
    "default_validity_days": 30,
    "brand_color": None,
    "logo_url": None,
}

# 允许通过 PUT 修改的字段及其取值（用于 diff 审计）
_SETTINGS_FIELDS: tuple[str, ...] = (
    "site_name", "description", "require_review", "allow_anonymous",
    "allow_comments", "publish_frequency", "image_limit",
    "default_validity_days", "brand_color", "logo_url",
)


def _settings_to_dict(s: SchoolSettings) -> dict:
    return {f: getattr(s, f) for f in _SETTINGS_FIELDS}


def _settings_to_response(s: SchoolSettings) -> SchoolSettingsResponse:
    return SchoolSettingsResponse(
        site_name=s.site_name,
        description=s.description,
        require_review=s.require_review,
        allow_anonymous=s.allow_anonymous,
        allow_comments=s.allow_comments,
        publish_frequency=s.publish_frequency,
        image_limit=s.image_limit,
        default_validity_days=s.default_validity_days,
        brand_color=s.brand_color,
        logo_url=s.logo_url,
        updated_at=s.updated_at,
    )


async def _get_or_create_settings(
    db: AsyncSession, school_id: int
) -> SchoolSettings:
    """获取或自动创建学校设置行（防御性补全，使用默认值）。"""
    s = await db.scalar(
        select(SchoolSettings).where(SchoolSettings.school_id == school_id)
    )
    if s is None:
        now = datetime.now()
        s = SchoolSettings(
            school_id=school_id,
            created_at=now,
            updated_at=now,
            **_DEFAULT_SETTINGS_TEMPLATE,
        )
        db.add(s)
        await db.flush()
    return s


@router.get(
    "/admin/settings",
    response_model=SchoolSettingsResponse,
    summary="获取学校设置（ADM-02.1）",
)
async def get_school_settings(
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取当前学校设置。

    - 仅 admin 及以上可访问（普通 user 403，由 require_role 保证）
    - 后端真实存储，跨浏览器生效
    - 设置不存在时按默认值自动补建（防御性补全）
    - TEN-02.3: school_id 由 TenantContext 决定，不信任 query/body
    """
    settings = await _get_or_create_settings(db, tenant.school_id)
    await db.commit()  # 提交可能的自动补建
    return _settings_to_response(settings)


@router.put(
    "/admin/settings",
    response_model=SchoolSettingsResponse,
    summary="更新学校设置（ADM-02.1）",
)
async def update_school_settings(
    data: SchoolSettingsUpdate,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新当前学校设置（部分更新）。

    - 仅 admin 及以上可访问
    - school_id 由 TenantContext 决定，不可改
    - 全部字段可选；未传字段保持原值
    - 在 AdminOperationLog.detail 中以 JSON 文本记录旧值/新值/字段级 diff + 操作者
      admin_id（操作者）由 AdminOperationLog.admin_id 列承载
    - 同事务提交：设置变更 + 审计日志
    """
    settings = await _get_or_create_settings(db, tenant.school_id)
    old_values = _settings_to_dict(settings)

    changes: list[str] = []
    new_values = dict(old_values)
    for field in _SETTINGS_FIELDS:
        value = getattr(data, field, None)
        if value is None:
            continue  # 部分更新：未传字段保持原值
        old_value = getattr(settings, field)
        if old_value == value:
            continue
        changes.append(f"{field}: {old_value!r} → {value!r}")
        setattr(settings, field, value)
        new_values[field] = value

    if not changes:
        # 无变更：仍返回当前值（不写日志，避免噪音）
        return _settings_to_response(settings)

    settings.updated_at = datetime.now()

    detail_payload = {
        "old": old_values,
        "new": new_values,
        "changes": changes,
        "operator": {"id": admin.id, "email": admin.email, "nickname": admin.nickname},
        "school_id": tenant.school_id,
    }
    db.add(AdminOperationLog(
        admin_id=admin.id,
        action="update_school_settings",
        target_type="school_settings",
        target_id=tenant.school_id,
        detail=json.dumps(detail_payload, ensure_ascii=False, default=str),
    ))

    await db.commit()
    await db.refresh(settings)
    return _settings_to_response(settings)


# ============================================================
# 操作日志
# ============================================================
@router.get("/admin/logs", response_model=PaginatedResponse[AdminLogResponse], summary="操作日志列表")
async def get_admin_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    admin_id: Optional[int] = Query(None, description="按管理员ID筛选"),
    action: Optional[str] = Query(None, description="按操作类型筛选"),
    target_type: Optional[str] = Query(None, description="按目标类型筛选"),
    date_from: Optional[datetime] = Query(None, description="起始时间"),
    date_to: Optional[datetime] = Query(None, description="截止时间"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """分页查询管理员操作日志，支持多维度筛选

    TEN-02.3：TenantContext 校验管理员在当前学校的权限。
    AdminOperationLog 暂无 school_id 字段，按当前管理员本人操作记录过滤。
    """
    # 构建查询（join User 获取 admin_name）
    query = select(AdminOperationLog, User.nickname).outerjoin(
        User, AdminOperationLog.admin_id == User.id
    )

    if admin_id is not None:
        query = query.where(AdminOperationLog.admin_id == admin_id)
    if action:
        query = query.where(AdminOperationLog.action == action)
    if target_type:
        query = query.where(AdminOperationLog.target_type == target_type)
    if date_from:
        query = query.where(AdminOperationLog.created_at >= date_from)
    if date_to:
        query = query.where(AdminOperationLog.created_at <= date_to)

    query = query.order_by(AdminOperationLog.created_at.desc())

    # 计算总数
    count_query = select(func.count()).select_from(AdminOperationLog)
    if admin_id is not None:
        count_query = count_query.where(AdminOperationLog.admin_id == admin_id)
    if action:
        count_query = count_query.where(AdminOperationLog.action == action)
    if target_type:
        count_query = count_query.where(AdminOperationLog.target_type == target_type)
    if date_from:
        count_query = count_query.where(AdminOperationLog.created_at >= date_from)
    if date_to:
        count_query = count_query.where(AdminOperationLog.created_at <= date_to)
    total = await db.scalar(count_query)

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    items = [
        AdminLogResponse(
            id=log.id,
            admin_id=log.admin_id,
            admin_name=nickname,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            detail=log.detail,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            created_at=log.created_at,
        )
        for log, nickname in rows
    ]

    return PaginatedResponse.create(items, page, page_size, total or 0)


# ============================================================
# 分类管理
# ============================================================
@router.get("/admin/categories", response_model=PaginatedResponse[CategoryAdminResponse], summary="分类列表（含禁用项）")
async def get_admin_categories(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量，默认50"),
    is_active: Optional[bool] = Query(None, description="按启用状态筛选"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取分类列表（含禁用项），附带各分类下的信息数

    TEN-02.3：按当前学校过滤，跨校分类不会出现在列表中。
    """
    # 查询分类（TEN-02.3: 强制按当前学校过滤）
    query = select(Category).where(Category.school_id == tenant.school_id)
    if is_active is not None:
        query = query.where(Category.is_active == is_active)
    query = query.order_by(Category.sort_order.asc(), Category.id.asc())

    # 计算总数
    count_query = select(func.count()).select_from(Category).where(
        Category.school_id == tenant.school_id
    )
    if is_active is not None:
        count_query = count_query.where(Category.is_active == is_active)
    total = await db.scalar(count_query)

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    categories = result.scalars().all()

    if not categories:
        return PaginatedResponse.create([], page, page_size, total or 0)

    # 批量查询各分类的帖子数
    category_ids = [c.id for c in categories]
    post_count_rows = await db.execute(
        select(Post.category_id, func.count(Post.id)).where(
            Post.category_id.in_(category_ids),
            Post.is_deleted == False,
        ).group_by(Post.category_id)
    )
    post_count_map = {cat_id: cnt for cat_id, cnt in post_count_rows.all()}

    items = [
        CategoryAdminResponse(
            id=cat.id,
            name=cat.name,
            code=cat.code,
            icon=cat.icon,
            description=cat.description,
            default_validity_days=cat.default_validity_days,
            sort_order=cat.sort_order,
            is_active=cat.is_active,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
            post_count=post_count_map.get(cat.id, 0),
        )
        for cat in categories
    ]

    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.post("/admin/categories", response_model=CategoryAdminResponse, summary="新建分类")
async def create_category(
    data: CategoryCreate,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """新建分类，code 必须唯一

    TEN-02.1: 强制使用 tenant.school_id，忽略 body 里的 school_id。
    """
    # 校验 code 唯一（TEN-02.3: 同校内唯一）
    existing = await db.scalar(
        select(Category).where(
            Category.code == data.code,
            Category.school_id == tenant.school_id,
        )
    )
    if existing:
        raise ConflictException(detail=f"分类编码 {data.code} 已存在")

    # TEN-02.1: 强制使用 tenant.school_id
    category = Category(
        school_id=tenant.school_id,
        name=data.name,
        code=data.code,
        icon=data.icon,
        description=data.description,
        default_validity_days=data.default_validity_days,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(category)

    # 记录操作日志
    log = AdminOperationLog(
        admin_id=admin.id,
        action="create_category",
        target_type="category",
        target_id=0,  # 创建时还没有 id，commit 后由前端刷新
        detail=f"新建分类：{data.name}（code={data.code}）",
    )
    db.add(log)

    await db.commit()
    await db.refresh(category)

    # 回填日志的 target_id
    log.target_id = category.id
    await db.commit()

    return CategoryAdminResponse(
        id=category.id,
        name=category.name,
        code=category.code,
        icon=category.icon,
        description=category.description,
        default_validity_days=category.default_validity_days,
        sort_order=category.sort_order,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
        post_count=0,
    )


@router.put("/admin/categories/{category_id}", response_model=CategoryAdminResponse, summary="更新分类")
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新分类（code 不可修改）

    TEN-02.3：跨校分类统一返回 404。
    """
    category = await db.scalar(select(Category).where(Category.id == category_id))
    if not category:
        raise NotFoundException(detail="分类不存在")

    # TEN-02.3: 资源级租户校验
    check_resource_in_tenant(category.school_id, tenant)

    changes = []
    if data.name is not None and data.name != category.name:
        changes.append(f"name: {category.name} → {data.name}")
        category.name = data.name
    if data.icon is not None and data.icon != category.icon:
        changes.append(f"icon: {category.icon} → {data.icon}")
        category.icon = data.icon
    if data.description is not None:
        category.description = data.description
    if data.default_validity_days is not None:
        category.default_validity_days = data.default_validity_days
    if data.sort_order is not None:
        category.sort_order = data.sort_order
    if data.is_active is not None:
        category.is_active = data.is_active
        changes.append(f"is_active: {not data.is_active} → {data.is_active}")

    category.updated_at = datetime.now()

    # 记录操作日志
    log = AdminOperationLog(
        admin_id=admin.id,
        action="update_category",
        target_type="category",
        target_id=category_id,
        detail="；".join(changes) if changes else "无变更",
    )
    db.add(log)

    await db.commit()
    await db.refresh(category)

    # 查询 post_count
    post_count = await db.scalar(
        select(func.count(Post.id)).where(
            Post.category_id == category_id,
            Post.is_deleted == False,
        )
    )

    return CategoryAdminResponse(
        id=category.id,
        name=category.name,
        code=category.code,
        icon=category.icon,
        description=category.description,
        default_validity_days=category.default_validity_days,
        sort_order=category.sort_order,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
        post_count=post_count or 0,
    )


@router.delete("/admin/categories/{category_id}", response_model=MessageResponse, summary="禁用分类（软删除）")
async def delete_category(
    category_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """禁用分类（is_active=False），不真正删除以保留历史帖子的分类关联

    TEN-02.3：跨校分类统一返回 404。
    """
    category = await db.scalar(select(Category).where(Category.id == category_id))
    if not category:
        raise NotFoundException(detail="分类不存在")

    # TEN-02.3: 资源级租户校验
    check_resource_in_tenant(category.school_id, tenant)

    if not category.is_active:
        raise BadRequestException(detail="分类已是禁用状态")

    category.is_active = False
    category.updated_at = datetime.now()

    log = AdminOperationLog(
        admin_id=admin.id,
        action="delete_category",
        target_type="category",
        target_id=category_id,
        detail=f"禁用分类：{category.name}（code={category.code}）",
    )
    db.add(log)

    await db.commit()
    return MessageResponse(message=f"分类 {category.name} 已禁用")


# ============================================================
# 标签管理
# ============================================================
@router.get("/admin/tags", response_model=PaginatedResponse[TagAdminResponse], summary="标签列表（含已删项）")
async def get_admin_tags(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    name: Optional[str] = Query(None, description="按名称模糊搜索"),
    is_official: Optional[bool] = Query(None, description="按是否官方筛选"),
    is_deleted: Optional[bool] = Query(None, description="按是否已删除筛选（默认全部）"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取标签列表（含已删项），支持名称搜索与多维度筛选

    TEN-02.3：按当前学校过滤，跨校标签不会出现在列表中。
    """
    # TEN-02.3: 强制按当前学校过滤
    query = select(Tag).where(Tag.school_id == tenant.school_id)
    if name:
        query = query.where(Tag.name.ilike(f"%{name}%"))
    if is_official is not None:
        query = query.where(Tag.is_official == is_official)
    if is_deleted is not None:
        query = query.where(Tag.is_deleted == is_deleted)

    query = query.order_by(Tag.usage_count.desc(), Tag.id.asc())

    # 计算总数
    count_query = select(func.count()).select_from(Tag).where(
        Tag.school_id == tenant.school_id
    )
    if name:
        count_query = count_query.where(Tag.name.ilike(f"%{name}%"))
    if is_official is not None:
        count_query = count_query.where(Tag.is_official == is_official)
    if is_deleted is not None:
        count_query = count_query.where(Tag.is_deleted == is_deleted)
    total = await db.scalar(count_query)

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    tags = result.scalars().all()

    items = [
        TagAdminResponse(
            id=t.id,
            name=t.name,
            slug=t.slug,
            usage_count=t.usage_count,
            is_official=t.is_official,
            is_deleted=t.is_deleted,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tags
    ]

    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.put("/admin/tags/{tag_id}", response_model=TagAdminResponse, summary="更新标签")
async def update_tag(
    tag_id: int,
    data: TagUpdate,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新标签（名称 / 是否官方）

    TEN-02.3：跨校标签统一返回 404。
    """
    tag = await db.scalar(select(Tag).where(Tag.id == tag_id))
    if not tag:
        raise NotFoundException(detail="标签不存在")

    # TEN-02.3: 资源级租户校验
    check_resource_in_tenant(tag.school_id, tenant)

    changes = []
    if data.name is not None and data.name != tag.name:
        # 校验名称唯一
        existing = await db.scalar(select(Tag).where(Tag.name == data.name, Tag.id != tag_id))
        if existing:
            raise ConflictException(detail="标签名称已存在")
        changes.append(f"name: {tag.name} → {data.name}")
        tag.name = data.name
    if data.is_official is not None and data.is_official != tag.is_official:
        changes.append(f"is_official: {tag.is_official} → {data.is_official}")
        tag.is_official = data.is_official

    tag.updated_at = datetime.now()

    log = AdminOperationLog(
        admin_id=admin.id,
        action="update_tag",
        target_type="tag",
        target_id=tag_id,
        detail="；".join(changes) if changes else "无变更",
    )
    db.add(log)

    await db.commit()
    await db.refresh(tag)

    return TagAdminResponse(
        id=tag.id,
        name=tag.name,
        slug=tag.slug,
        usage_count=tag.usage_count,
        is_official=tag.is_official,
        is_deleted=tag.is_deleted,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
    )


@router.delete("/admin/tags/{tag_id}", response_model=MessageResponse, summary="删除标签（软删除）")
async def delete_tag(
    tag_id: int,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """软删除标签（is_deleted=True）

    TEN-02.3：跨校标签统一返回 404。
    """
    tag = await db.scalar(select(Tag).where(Tag.id == tag_id))
    if not tag:
        raise NotFoundException(detail="标签不存在")

    # TEN-02.3: 资源级租户校验
    check_resource_in_tenant(tag.school_id, tenant)

    if tag.is_deleted:
        raise BadRequestException(detail="标签已删除")

    tag.is_deleted = True
    tag.deleted_at = datetime.now()
    tag.updated_at = datetime.now()

    log = AdminOperationLog(
        admin_id=admin.id,
        action="delete_tag",
        target_type="tag",
        target_id=tag_id,
        detail=f"删除标签：{tag.name}",
    )
    db.add(log)

    await db.commit()
    return MessageResponse(message=f"标签 {tag.name} 已删除")


@router.post("/admin/tags/merge", response_model=BatchOperationResponse, summary="合并标签")
async def merge_tags(
    data: TagMergeRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """合并标签：将 source_tag_ids 的帖子关联迁移到 target_tag_id，并软删除源标签

    TEN-02.3：跨校标签统一返回 404。
    """
    # 校验 target
    if data.target_tag_id in data.source_tag_ids:
        raise BadRequestException(detail="目标标签不能与源标签相同")

    target_tag = await db.scalar(
        select(Tag).where(Tag.id == data.target_tag_id, Tag.is_deleted == False)
    )
    if not target_tag:
        raise NotFoundException(detail="目标标签不存在或已删除")

    # TEN-02.3: 资源级租户校验
    check_resource_in_tenant(target_tag.school_id, tenant)

    # 查询源标签
    source_tags = await db.execute(
        select(Tag).where(
            Tag.id.in_(data.source_tag_ids),
            Tag.is_deleted == False,
        )
    )
    source_tags_list = source_tags.scalars().all()
    if not source_tags_list:
        raise NotFoundException(detail="源标签不存在或已全部删除")

    success_count = 0
    failed_ids = []
    migrated_count = 0

    for source_tag in source_tags_list:
        # 查询源标签的所有 PostTag
        pt_rows = await db.execute(
            select(PostTag).where(PostTag.tag_id == source_tag.id)
        )
        source_post_tags = pt_rows.scalars().all()

        for spt in source_post_tags:
            # 检查该 post 是否已关联 target_tag
            existing = await db.scalar(
                select(PostTag).where(
                    PostTag.post_id == spt.post_id,
                    PostTag.tag_id == data.target_tag_id,
                )
            )
            if existing:
                # 已存在关联，删除源关联
                await db.delete(spt)
            else:
                # 迁移：修改 tag_id
                spt.tag_id = data.target_tag_id
                migrated_count += 1

        # 软删除源标签
        source_tag.is_deleted = True
        source_tag.deleted_at = datetime.now()
        source_tag.updated_at = datetime.now()
        success_count += 1

    # 重新统计 target_tag 的 usage_count
    target_post_count = await db.scalar(
        select(func.count(PostTag.id)).where(PostTag.tag_id == data.target_tag_id)
    )
    target_tag.usage_count = target_post_count or 0
    target_tag.updated_at = datetime.now()

    failed_ids = [tid for tid in data.source_tag_ids if tid not in [t.id for t in source_tags_list]]

    log = AdminOperationLog(
        admin_id=admin.id,
        action="merge_tag",
        target_type="tag",
        target_id=data.target_tag_id,
        detail=f"合并 {success_count} 个标签到 {target_tag.name}，迁移 {migrated_count} 条关联",
    )
    db.add(log)

    await db.commit()

    return BatchOperationResponse(
        total=len(data.source_tag_ids),
        success=success_count,
        failed=len(failed_ids),
        failed_ids=failed_ids,
        message=f"已合并 {success_count} 个标签到「{target_tag.name}」，迁移 {migrated_count} 条关联",
    )


# ============================================================
# 批量操作
# ============================================================
@router.post("/admin/posts/batch-approve", response_model=BatchOperationResponse, summary="批量审核通过")
async def batch_approve_posts(
    data: BatchApproveRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """批量审核通过帖子，逐项返回成功/失败/原因（ADM-01.4 不静默跳过）

    FND-03.2/FND-03.3: 状态变化通过状态机校验，资源级校验帖子属于当前学校。
    TEN-02.3: 跨校帖子计入失败并注明原因。
    """
    success_count = 0
    failed_items: list[BatchFailedItem] = []

    for post_id in data.post_ids:
        post = await db.scalar(
            select(Post).where(Post.id == post_id, Post.is_deleted == False)
        )
        if not post:
            failed_items.append(BatchFailedItem(id=post_id, reason="帖子不存在或已删除"))
            continue
        # TEN-02.3: 资源级校验，跨校帖子计入失败
        try:
            _check_post_in_admin_school(post, tenant)
        except NotFoundException:
            failed_items.append(BatchFailedItem(id=post_id, reason="帖子不属于当前学校"))
            continue
        if post.status != PostStatus.PENDING:
            failed_items.append(BatchFailedItem(
                id=post_id, reason=f"当前状态为 {post.status}，非待审核状态"
            ))
            continue
        # FND-03.2: 状态机校验
        if not can_transition(PostStatus.PENDING, PostStatus.PUBLISHED):
            failed_items.append(BatchFailedItem(id=post_id, reason="状态机不允许该流转"))
            continue

        post.status = PostStatus.PUBLISHED
        post.updated_at = datetime.now()

        log = AdminOperationLog(
            admin_id=admin.id,
            action="approve_post",
            target_type="post",
            target_id=post_id,
            detail=data.reason,
        )
        db.add(log)
        add_review_notification(db, post, admin, approved=True, reason=data.reason)
        # SUB-01.2: 新帖发布订阅通知（批量审核通过时一并触发，幂等）
        from app.services.subscription_notifier import notify_new_post
        await notify_new_post(db, post, actor_id=admin.id)
        success_count += 1

    await db.commit()

    return BatchOperationResponse(
        total=len(data.post_ids),
        success=success_count,
        failed=len(failed_items),
        failed_ids=[item.id for item in failed_items],
        failed_items=failed_items,
        message=f"批量通过完成：成功 {success_count} 个，失败 {len(failed_items)} 个",
    )


@router.post("/admin/posts/batch-reject", response_model=BatchOperationResponse, summary="批量审核拒绝")
async def batch_reject_posts(
    data: BatchRejectRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """批量审核拒绝帖子，逐项返回成功/失败/原因（ADM-01.4 不静默跳过）

    FND-03.2/FND-03.3: 状态变化通过状态机校验，资源级校验帖子属于当前学校。
    TEN-02.3: 跨校帖子计入失败并注明原因。
    PUB-02: 驳回 = pending → draft（退回草稿，作者可修改后重新提交）。
    """
    success_count = 0
    failed_items: list[BatchFailedItem] = []

    for post_id in data.post_ids:
        post = await db.scalar(
            select(Post).where(Post.id == post_id, Post.is_deleted == False)
        )
        if not post:
            failed_items.append(BatchFailedItem(id=post_id, reason="帖子不存在或已删除"))
            continue
        try:
            _check_post_in_admin_school(post, tenant)
        except NotFoundException:
            failed_items.append(BatchFailedItem(id=post_id, reason="帖子不属于当前学校"))
            continue
        if post.status != PostStatus.PENDING:
            failed_items.append(BatchFailedItem(
                id=post_id, reason=f"当前状态为 {post.status}，非待审核状态"
            ))
            continue
        # PUB-02: 驳回 = pending → draft（退回草稿，作者可修改后重新提交）
        if not can_transition(PostStatus.PENDING, PostStatus.DRAFT):
            failed_items.append(BatchFailedItem(id=post_id, reason="状态机不允许该流转"))
            continue

        post.status = PostStatus.DRAFT
        post.updated_at = datetime.now()

        log = AdminOperationLog(
            admin_id=admin.id,
            action="reject_post",
            target_type="post",
            target_id=post_id,
            detail=f"驳回原因：{data.reason}",
        )
        db.add(log)
        add_review_notification(db, post, admin, approved=False, reason=data.reason)
        success_count += 1

    await db.commit()

    return BatchOperationResponse(
        total=len(data.post_ids),
        success=success_count,
        failed=len(failed_items),
        failed_ids=[item.id for item in failed_items],
        failed_items=failed_items,
        message=f"批量拒绝完成：成功 {success_count} 个，失败 {len(failed_items)} 个",
    )


@router.post("/admin/users/batch-toggle-active", response_model=BatchOperationResponse, summary="批量启用/禁用用户")
async def batch_toggle_users_active(
    data: BatchToggleActiveRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """批量启用/禁用用户，逐项返回成功/失败/原因（ADM-01.4 不静默跳过）

    TEN-02.3: 跨校用户计入失败并注明原因。
    """
    success_count = 0
    failed_items: list[BatchFailedItem] = []
    action = "enable_user" if data.is_active else "disable_user"

    for user_id in data.user_ids:
        # 不能操作自己
        if user_id == admin.id:
            failed_items.append(BatchFailedItem(id=user_id, reason="不能操作自己"))
            continue

        user = await db.scalar(
            select(User).where(User.id == user_id, User.is_deleted == False)
        )
        if not user:
            failed_items.append(BatchFailedItem(id=user_id, reason="用户不存在或已删除"))
            continue

        # TEN-02.3: 资源级租户校验——跨校用户计入失败
        try:
            check_resource_in_tenant(user.school_id, tenant)
        except NotFoundException:
            failed_items.append(BatchFailedItem(id=user_id, reason="用户不属于当前学校"))
            continue

        user.is_active = data.is_active
        user.updated_at = datetime.now()

        log = AdminOperationLog(
            admin_id=admin.id,
            action=action,
            target_type="user",
            target_id=user_id,
            detail=data.reason,
        )
        db.add(log)
        success_count += 1

    await db.commit()

    status_text = "启用" if data.is_active else "禁用"
    return BatchOperationResponse(
        total=len(data.user_ids),
        success=success_count,
        failed=len(failed_items),
        failed_ids=[item.id for item in failed_items],
        failed_items=failed_items,
        message=f"批量{status_text}完成：成功 {success_count} 个，失败 {len(failed_items)} 个",
    )


# ============================================================
# COM-02.3：校级用量页
# ============================================================
@router.get(
    "/admin/usage",
    summary="校级用量页：当前套餐/额度余量/统计口径/最后更新（admin/super_admin）",
)
async def get_school_usage(
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """COM-02.3：校级后台用量页。

    返回：
    - 当前套餐（plan_code/plan_name/subscription_status/subscription_expires_at）
    - 各额度余量（key/limit_value/current_value/remaining/code/message）
    - 统计口径（members_count 实时 / posts_count 实时 / ai_calls 当日 / storage 最近一条）
    - 最后更新时间（last_updated_at）
    - 联系平台入口提示（contact_platform_hint）

    额度阈值与到期统一错误码/中文说明由 EntitlementService 提供。
    """
    # 显式 selectinload(plan)，避免 async 上下文中访问 subscription.plan 触发懒加载
    from sqlalchemy.orm import selectinload as _selectinload
    from app.models.school_subscription import SchoolSubscription
    sub_row = (await db.execute(
        select(SchoolSubscription)
        .options(_selectinload(SchoolSubscription.plan))
        .where(
            SchoolSubscription.school_id == tenant.school_id,
            SchoolSubscription.status == "active",
        )
        .order_by(SchoolSubscription.assigned_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    if sub_row is not None and sub_row.plan is not None:
        plan_code = sub_row.plan.code
        plan_name = sub_row.plan.name

    # EntitlementService 只用于权益项 check（不访问 plan_code 属性避免懒加载）
    svc = await EntitlementService.create(db, tenant.school_id)

    # 实时统计
    member_count = (await db.execute(
        select(func.count()).select_from(SchoolMembership).where(
            SchoolMembership.school_id == tenant.school_id,
            SchoolMembership.status == "active",
        )
    )).scalar() or 0
    post_count = (await db.execute(
        select(func.count()).select_from(Post).where(
            Post.school_id == tenant.school_id,
            Post.is_deleted == False,  # noqa: E712
        )
    )).scalar() or 0

    # AI 调用（当日，tenant_usage_daily）
    from datetime import date as _date
    today = _date.today()
    ai_calls_today = (await db.execute(
        select(TenantUsageDaily.ai_calls_count).where(
            TenantUsageDaily.school_id == tenant.school_id,
            TenantUsageDaily.usage_date == today,
        )
    )).scalar() or 0

    # 存储（tenant_usage_daily 最新一条）
    storage_row = (await db.execute(
        select(TenantUsageDaily).where(
            TenantUsageDaily.school_id == tenant.school_id,
        ).order_by(TenantUsageDaily.usage_date.desc()).limit(1)
    )).scalar_one_or_none()
    storage_used_mb = int(storage_row.storage_used_mb) if storage_row is not None else 0
    last_updated_at = (
        storage_row.updated_at.isoformat() if storage_row is not None else None
    )

    checks = {
        "members_max": await svc.check(EntitlementKey.MEMBERS_MAX, int(member_count)),
        "posts_max": await svc.check(EntitlementKey.POSTS_MAX, int(post_count)),
        "storage_mb": await svc.check(EntitlementKey.STORAGE_MB, storage_used_mb),
        "ai_calls_daily": await svc.check(EntitlementKey.AI_CALLS_DAILY, int(ai_calls_today)),
    }

    entitlements: list[dict] = []
    alerts: list[dict] = []
    for key, reason in checks.items():
        ent = svc.entitlements.get(key)
        limit_value = ent.limit_value if ent is not None else None
        is_hard = ent.is_hard if ent is not None else False
        remaining: Optional[int] = None
        if limit_value is not None and limit_value > 0 and reason.current_value is not None:
            remaining = max(0, limit_value - int(reason.current_value))
        entitlements.append({
            "key": key,
            "limit_value": limit_value,
            "current_value": reason.current_value,
            "remaining": remaining,
            "is_hard": is_hard,
            "code": reason.code,
            "message": reason.message,
            "allowed": reason.allowed,
        })
        if reason.code in ("ENT_WARNING_80", "ENT_WARNING_100",
                           "ENT_WARNING_SOFT_EXCEEDED", "ENT_LIMIT_HARD_EXCEEDED",
                           "ENT_NO_SUBSCRIPTION"):
            alerts.append({
                "key": key,
                "code": reason.code,
                "message": reason.message,
                "severity": "critical" if reason.code in (
                    "ENT_LIMIT_HARD_EXCEEDED", "ENT_NO_SUBSCRIPTION"
                ) else "warning",
            })

    # 订阅到期告警（30 天内）
    days_to_expire: Optional[int] = None
    subscription_expires_at = None
    if svc.subscription is not None and svc.subscription.expires_at is not None:
        subscription_expires_at = svc.subscription.expires_at
        delta = (svc.subscription.expires_at - datetime.now()).total_seconds()
        days_to_expire = int(delta // 86400)
        if days_to_expire <= 30:
            alerts.append({
                "key": "subscription_expiring",
                "code": "ENT_SUBSCRIPTION_EXPIRING",
                "message": (
                    f"订阅将在 {days_to_expire} 天后到期"
                    f"（{subscription_expires_at.isoformat()}），请联系平台续期"
                ),
                "days_to_expire": days_to_expire,
                "severity": "critical" if days_to_expire <= 7 else "warning",
            })

    return {
        "school_id": tenant.school_id,
        "school_code": tenant.school_code,
        "plan_code": plan_code,
        "plan_name": plan_name,
        "subscription_status": (
            svc.subscription.status if svc.subscription is not None else None
        ),
        "subscription_expires_at": (
            subscription_expires_at.isoformat() if subscription_expires_at else None
        ),
        "days_to_expire": days_to_expire,
        "entitlements": entitlements,
        "alerts": alerts,
        "alerts_count": len(alerts),
        "stats": {
            "members_count": int(member_count),
            "posts_count": int(post_count),
            "ai_calls_today": int(ai_calls_today),
            "storage_used_mb": storage_used_mb,
            "last_updated_at": last_updated_at,
            "stat_basis": "realtime",
        },
        "contact_platform_hint": (
            "如需扩容或续期，请联系平台管理员（admin@momentcampus.com）"
        ),
    }


# ============================================================
# GOV-02: 自动过期任务手动触发与运行记录
# ============================================================
@router.post(
    "/admin/jobs/expire-posts",
    response_model=JobRunRecordResponse,
    summary="手动触发帖子过期任务（GOV-02.2）",
)
async def trigger_expire_posts_job(
    data: ExpirePostsJobRequest,
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
):
    """手动触发自动过期任务（支持 dry-run）

    GOV-02.2: 支持 dry-run 与手动重跑
    - 支持 dry_run 参数（只报告不执行，不写库、不发通知）
    - 返回任务执行记录（处理数量、耗时、失败列表）
    - 仅 admin 及以上可调用
    - 重复执行不重复通知、不产生非法状态（由 job 内部幂等保证）

    注意：
    - worker 跨校扫描所有学校的帖子，但通知按帖子作者 user_id 隔离
    - 若已有同名任务正在运行（status='running'），返回该记录而非重复执行
    """
    from app.jobs.expire_posts import expire_posts_job

    record = await expire_posts_job(
        db=db,
        dry_run=data.dry_run,
        triggered_by="manual",
        triggered_user_id=admin.id,
    )

    # 计算耗时
    duration_seconds = None
    if record.finished_at and record.started_at:
        duration_seconds = (
            record.finished_at - record.started_at
        ).total_seconds()

    return JobRunRecordResponse(
        id=record.id,
        job_name=record.job_name,
        status=record.status,
        started_at=record.started_at,
        finished_at=record.finished_at,
        processed_count=record.processed_count,
        failed_count=record.failed_count,
        error_message=record.error_message,
        triggered_by=record.triggered_by,
        triggered_user_id=record.triggered_user_id,
        dry_run=record.dry_run,
        metadata=record.metadata_,
        duration_seconds=duration_seconds,
    )


@router.get(
    "/admin/jobs/expire-posts/records",
    response_model=PaginatedResponse[JobRunRecordResponse],
    summary="查询过期任务运行记录（GOV-02.2）",
)
async def list_expire_posts_job_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态筛选：running/success/failed"),
    admin: User = AdminDep,
    db: AsyncSession = Depends(get_db),
):
    """查询过期任务的运行记录列表

    GOV-02.2: 记录开始/成功/失败/处理数量/耗时
    - 支持按状态筛选
    - 分页返回，按 started_at 倒序
    - 仅 admin 及以上可查询
    """
    from app.models.job_run_record import JobRunRecord

    query = select(JobRunRecord).where(JobRunRecord.job_name == "expire_posts")
    if status:
        query = query.where(JobRunRecord.status == status)
    query = query.order_by(JobRunRecord.started_at.desc())

    # 计算总数
    count_query = select(func.count()).select_from(JobRunRecord).where(
        JobRunRecord.job_name == "expire_posts"
    )
    if status:
        count_query = count_query.where(JobRunRecord.status == status)
    total = await db.scalar(count_query)

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    records = result.scalars().all()

    items = []
    for record in records:
        duration_seconds = None
        if record.finished_at and record.started_at:
            duration_seconds = (
                record.finished_at - record.started_at
            ).total_seconds()
        items.append(JobRunRecordResponse(
            id=record.id,
            job_name=record.job_name,
            status=record.status,
            started_at=record.started_at,
            finished_at=record.finished_at,
            processed_count=record.processed_count,
            failed_count=record.failed_count,
            error_message=record.error_message,
            triggered_by=record.triggered_by,
            triggered_user_id=record.triggered_user_id,
            dry_run=record.dry_run,
            metadata=record.metadata_,
            duration_seconds=duration_seconds,
        ))

    return PaginatedResponse.create(items, page, page_size, total or 0)
