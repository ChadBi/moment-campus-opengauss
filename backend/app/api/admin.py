from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.post import Post
from app.models.report import Report
from app.models.admin_operation_log import AdminOperationLog
from app.schemas.common import PaginatedResponse, MessageResponse
from app.core.exceptions import NotFoundException, BadRequestException

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
