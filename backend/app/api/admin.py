from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.post import Post
from app.models.report import Report
from app.models.admin_operation_log import AdminOperationLog
from app.models.category import Category
from app.models.tag import Tag
from app.models.post_tag import PostTag
from app.models.comment import Comment
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
    BatchOperationResponse,
)
from app.core.exceptions import NotFoundException, BadRequestException, ConflictException

router = APIRouter(tags=["管理"])


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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    获取待审核信息列表
    """
    # 查询待审核帖子
    query = select(Post).where(
        Post.status == "pending",
        Post.is_deleted == False
    ).order_by(Post.created_at.desc())

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询
    result = await db.execute(query)
    posts = result.scalars().all()

    # 构建响应
    items = []
    for post in posts:
        # 获取作者信息
        author_query = select(User).where(User.id == post.user_id)
        author_result = await db.execute(author_query)
        author = author_result.scalar_one_or_none()

        # 获取分类信息
        from app.models.category import Category
        category_query = select(Category).where(Category.id == post.category_id)
        category_result = await db.execute(category_query)
        category = category_result.scalar_one_or_none()

        items.append(PostBrief(
            id=post.id,
            title=post.title,
            content=post.content[:200] if len(post.content) > 200 else post.content,
            status=post.status,
            created_at=post.created_at,
            author_id=post.user_id,
            author_name=author.nickname if author else None,
            category_id=post.category_id,
            category_name=category.name if category else None,
        ))

    return PaginatedResponse.create(items, page, page_size, total)


@router.put("/admin/posts/{post_id}/approve", response_model=MessageResponse)
async def approve_post(
    post_id: int,
    data: ApproveRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    审核通过帖子
    """
    # 查询帖子
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise NotFoundException(detail="帖子不存在")

    if post.status != "pending":
        raise BadRequestException(detail="帖子状态不正确，无法审核")

    # 更新状态
    post.status = "approved"
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

    await db.commit()

    return MessageResponse(message="帖子已审核通过")


@router.put("/admin/posts/{post_id}/reject", response_model=MessageResponse)
async def reject_post(
    post_id: int,
    data: RejectRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    审核拒绝帖子
    """
    # 查询帖子
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise NotFoundException(detail="帖子不存在")

    if post.status != "pending":
        raise BadRequestException(detail="帖子状态不正确，无法审核")

    # 更新状态
    post.status = "rejected"
    post.updated_at = datetime.now()

    # 记录操作日志
    log = AdminOperationLog(
        admin_id=admin.id,
        action="reject_post",
        target_type="post",
        target_id=post_id,
        detail=f"拒绝原因：{data.reason}",
    )
    db.add(log)

    await db.commit()

    return MessageResponse(message="帖子已拒绝")


@router.get("/admin/users", response_model=PaginatedResponse[UserBrief])
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    获取用户列表
    """
    # 构建查询
    query = select(User).where(User.is_deleted == False)

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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    禁用/启用用户
    """
    # 查询用户
    query = select(User).where(User.id == user_id, User.is_deleted == False)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundException(detail="用户不存在")

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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    获取举报列表
    """
    # 构建查询
    query = select(Report)

    if status:
        query = query.where(Report.status == status)

    query = query.order_by(Report.created_at.desc())

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 执行查询
    result = await db.execute(query)
    reports = result.scalars().all()

    # 构建响应
    items = []
    for report in reports:
        # 获取帖子信息
        post_title = None
        if report.post_id:
            post_query = select(Post).where(Post.id == report.post_id)
            post_result = await db.execute(post_query)
            post = post_result.scalar_one_or_none()
            if post:
                post_title = post.title

        # 获取举报者信息
        reporter_query = select(User).where(User.id == report.reporter_id)
        reporter_result = await db.execute(reporter_query)
        reporter = reporter_result.scalar_one_or_none()

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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    处理举报
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
        # 删除帖子
        post_query = select(Post).where(Post.id == report.post_id)
        post_result = await db.execute(post_query)
        post = post_result.scalar_one_or_none()
        if post:
            post.is_deleted = True
            post.deleted_at = datetime.now()
            post.status = "deleted"

    elif data.action == "ban_user":
        # 禁用被举报者（帖子作者）
        if report.post_id:
            post_query = select(Post).where(Post.id == report.post_id)
            post_result = await db.execute(post_query)
            post = post_result.scalar_one_or_none()
            if post:
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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """返回管理员仪表盘的各项统计数据"""
    # 信息总数（未删除）
    total_posts = await db.scalar(
        select(func.count(Post.id)).where(Post.is_deleted == False)
    )
    # 待审核信息数
    pending_posts = await db.scalar(
        select(func.count(Post.id)).where(
            Post.status == "pending",
            Post.is_deleted == False,
        )
    )
    # 用户总数（未删除）
    total_users = await db.scalar(
        select(func.count(User.id)).where(User.is_deleted == False)
    )
    # 活跃用户数
    active_users = await db.scalar(
        select(func.count(User.id)).where(
            User.is_active == True,
            User.is_deleted == False,
        )
    )
    # 举报总数
    total_reports = await db.scalar(select(func.count(Report.id)))
    # 待处理举报数
    pending_reports = await db.scalar(
        select(func.count(Report.id)).where(Report.status == "pending")
    )
    # 评论总数（未删除）
    total_comments = await db.scalar(
        select(func.count(Comment.id)).where(Comment.is_deleted == False)
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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """分页查询管理员操作日志，支持多维度筛选"""
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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取分类列表（含禁用项），附带各分类下的信息数"""
    # 查询分类
    query = select(Category)
    if is_active is not None:
        query = query.where(Category.is_active == is_active)
    query = query.order_by(Category.sort_order.asc(), Category.id.asc())

    # 计算总数
    count_query = select(func.count()).select_from(Category)
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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """新建分类，code 必须唯一"""
    # 校验 code 唯一
    existing = await db.scalar(select(Category).where(Category.code == data.code))
    if existing:
        raise ConflictException(detail=f"分类编码 {data.code} 已存在")

    category = Category(
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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新分类（code 不可修改）"""
    category = await db.scalar(select(Category).where(Category.id == category_id))
    if not category:
        raise NotFoundException(detail="分类不存在")

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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """禁用分类（is_active=False），不真正删除以保留历史帖子的分类关联"""
    category = await db.scalar(select(Category).where(Category.id == category_id))
    if not category:
        raise NotFoundException(detail="分类不存在")

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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取标签列表（含已删项），支持名称搜索与多维度筛选"""
    query = select(Tag)
    if name:
        query = query.where(Tag.name.ilike(f"%{name}%"))
    if is_official is not None:
        query = query.where(Tag.is_official == is_official)
    if is_deleted is not None:
        query = query.where(Tag.is_deleted == is_deleted)

    query = query.order_by(Tag.usage_count.desc(), Tag.id.asc())

    # 计算总数
    count_query = select(func.count()).select_from(Tag)
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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新标签（名称 / 是否官方）"""
    tag = await db.scalar(select(Tag).where(Tag.id == tag_id))
    if not tag:
        raise NotFoundException(detail="标签不存在")

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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """软删除标签（is_deleted=True）"""
    tag = await db.scalar(select(Tag).where(Tag.id == tag_id))
    if not tag:
        raise NotFoundException(detail="标签不存在")

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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """合并标签：将 source_tag_ids 的帖子关联迁移到 target_tag_id，并软删除源标签"""
    # 校验 target
    if data.target_tag_id in data.source_tag_ids:
        raise BadRequestException(detail="目标标签不能与源标签相同")

    target_tag = await db.scalar(
        select(Tag).where(Tag.id == data.target_tag_id, Tag.is_deleted == False)
    )
    if not target_tag:
        raise NotFoundException(detail="目标标签不存在或已删除")

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
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """批量审核通过帖子，对不存在或非 pending 状态的帖子计入 failed_ids"""
    success_count = 0
    failed_ids = []

    for post_id in data.post_ids:
        post = await db.scalar(
            select(Post).where(Post.id == post_id, Post.is_deleted == False)
        )
        if not post:
            failed_ids.append(post_id)
            continue
        if post.status != "pending":
            failed_ids.append(post_id)
            continue

        post.status = "approved"
        post.updated_at = datetime.now()

        log = AdminOperationLog(
            admin_id=admin.id,
            action="approve_post",
            target_type="post",
            target_id=post_id,
            detail=data.reason,
        )
        db.add(log)
        success_count += 1

    await db.commit()

    return BatchOperationResponse(
        total=len(data.post_ids),
        success=success_count,
        failed=len(failed_ids),
        failed_ids=failed_ids,
        message=f"批量通过完成：成功 {success_count} 个，失败 {len(failed_ids)} 个",
    )


@router.post("/admin/posts/batch-reject", response_model=BatchOperationResponse, summary="批量审核拒绝")
async def batch_reject_posts(
    data: BatchRejectRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """批量审核拒绝帖子，对不存在或非 pending 状态的帖子计入 failed_ids"""
    success_count = 0
    failed_ids = []

    for post_id in data.post_ids:
        post = await db.scalar(
            select(Post).where(Post.id == post_id, Post.is_deleted == False)
        )
        if not post:
            failed_ids.append(post_id)
            continue
        if post.status != "pending":
            failed_ids.append(post_id)
            continue

        post.status = "rejected"
        post.updated_at = datetime.now()

        log = AdminOperationLog(
            admin_id=admin.id,
            action="reject_post",
            target_type="post",
            target_id=post_id,
            detail=f"拒绝原因：{data.reason}",
        )
        db.add(log)
        success_count += 1

    await db.commit()

    return BatchOperationResponse(
        total=len(data.post_ids),
        success=success_count,
        failed=len(failed_ids),
        failed_ids=failed_ids,
        message=f"批量拒绝完成：成功 {success_count} 个，失败 {len(failed_ids)} 个",
    )


@router.post("/admin/users/batch-toggle-active", response_model=BatchOperationResponse, summary="批量启用/禁用用户")
async def batch_toggle_users_active(
    data: BatchToggleActiveRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """批量启用/禁用用户，对自己、不存在或已删除的用户计入 failed_ids"""
    success_count = 0
    failed_ids = []
    action = "enable_user" if data.is_active else "disable_user"

    for user_id in data.user_ids:
        # 不能操作自己
        if user_id == admin.id:
            failed_ids.append(user_id)
            continue

        user = await db.scalar(
            select(User).where(User.id == user_id, User.is_deleted == False)
        )
        if not user:
            failed_ids.append(user_id)
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
        failed=len(failed_ids),
        failed_ids=failed_ids,
        message=f"批量{status_text}完成：成功 {success_count} 个，失败 {len(failed_ids)} 个",
    )
