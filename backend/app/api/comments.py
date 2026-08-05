from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user
from app.models.comment import Comment
from app.models.post import Post
from app.models.user import User
from app.models.notification import Notification
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.permissions import require_campus_verified

router = APIRouter(tags=["评论"])


def _build_comment_response(comment: Comment, include_replies: bool = False) -> CommentResponse:
    """DSC-02.1: 手动构造 CommentResponse，避免 model_validate 递归触发未加载关系的 lazy load

    - include_replies=True 时，递归构造 replies（仅一层，避免无限递归）
    - include_replies=False 时，replies 恒为 None（用于回复本身，不再嵌套）
    """
    author = None
    if comment.user:
        if comment.is_anonymous:
            # UC-01: 用户离校后评论匿名化——作者显示「已离校用户」，移除认证徽标
            author = {
                "id": comment.user.id,
                "nickname": "已离校用户",
                "avatar_url": None,
                "is_verified": False,
            }
        else:
            author = {"id": comment.user.id, "nickname": comment.user.nickname, "avatar_url": comment.user.avatar_url, "is_verified": comment.user.campus_verified}

    reply_to_user = None
    if comment.reply_to_user:
        reply_to_user = {"id": comment.reply_to_user.id, "nickname": comment.reply_to_user.nickname, "avatar_url": comment.reply_to_user.avatar_url}

    replies: list = []
    reply_count = 0
    if include_replies and comment.replies:
        for reply in comment.replies:
            if reply.is_deleted:
                continue
            replies.append(_build_comment_response(reply, include_replies=False))
            reply_count += 1

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        reply_to_user_id=comment.reply_to_user_id,
        content=comment.content,
        like_count=comment.like_count,
        status=comment.status,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        author=author,
        reply_to_user=reply_to_user,
        replies=replies if include_replies else None,
        reply_count=reply_count,
    )


@router.get("/posts/{post_id}/comments", response_model=PaginatedResponse[CommentResponse], summary="获取评论列表")
async def get_post_comments(
    post_id: int,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取评论列表，支持分页，包含子评论

    TEN-02.3：跨校帖子统一返回 404。
    """
    # 验证信息存在
    post_result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = post_result.scalar_one_or_none()
    if post is None:
        raise NotFoundException(detail="信息不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

    # 查询顶级评论（parent_id 为空的评论）
    query = select(Comment).where(
        Comment.post_id == post_id,
        Comment.parent_id.is_(None),
        Comment.is_deleted == False,
    )
    query = query.order_by(Comment.created_at.asc())

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 预加载关联数据：评论者、被回复者、子评论（包含子评论的评论者）
    # DSC-02.1: 加载二级回复避免 MissingGreenlet（model_validate 会递归访问 replies.replies）
    query = query.options(
        joinedload(Comment.user),
        joinedload(Comment.reply_to_user),
        selectinload(Comment.replies).options(
            joinedload(Comment.user),
            joinedload(Comment.reply_to_user),
            selectinload(Comment.replies).options(
                joinedload(Comment.user),
                joinedload(Comment.reply_to_user),
            ),
        ),
    )

    result = await db.execute(query)
    comments = result.unique().scalars().all()

    # 转换为响应格式
    # DSC-02.1: 手动构造 CommentResponse，避免 model_validate 递归触发未加载关系的 lazy load
    items = []
    for comment in comments:
        comment_data = _build_comment_response(comment, include_replies=True)
        items.append(comment_data)

    return PaginatedResponse.create(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=201, summary="创建评论",
             dependencies=[Depends(require_campus_verified())])
async def create_comment(
    post_id: int,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """创建评论，需要认证，支持回复

    TEN-02.3：跨校帖子统一返回 404。
    """
    # 验证信息存在
    post_result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = post_result.scalar_one_or_none()
    if post is None:
        raise NotFoundException(detail="信息不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

    # 如果是回复，验证父评论存在
    parent_comment = None
    if comment_data.parent_id is not None:
        parent_result = await db.execute(
            select(Comment).where(
                Comment.id == comment_data.parent_id,
                Comment.post_id == post_id,
                Comment.is_deleted == False,
            )
        )
        parent_comment = parent_result.scalar_one_or_none()
        if parent_comment is None:
            raise NotFoundException(detail="父评论不存在")

    # 创建评论
    comment = Comment(
        post_id=post_id,
        user_id=current_user.id,
        parent_id=comment_data.parent_id,
        reply_to_user_id=comment_data.reply_to_user_id,
        content=comment_data.content,
        status="approved",  # 评论直接通过审核
    )
    db.add(comment)
    await db.flush()

    # 更新信息的评论计数
    post.comment_count += 1

    # 创建通知
    # 1. 评论帖子：通知帖子作者（不给自己发通知）
    # 2. 回复评论：通知被回复者（如果有 reply_to_user_id 且不是自己）
    if comment_data.reply_to_user_id is not None:
        # 回复评论：通知被回复者
        if comment_data.reply_to_user_id != current_user.id:
            db.add(Notification(
                user_id=comment_data.reply_to_user_id,
                type="comment",
                title="有人回复了你的评论",
                content=f"{current_user.nickname} 回复了你的评论：{comment_data.content[:30]}",
                target_type="post",
                target_id=post_id,
                actor_id=current_user.id,
                is_read=False,
            ))
    elif post.user_id != current_user.id:
        # 评论帖子（非回复）：通知帖子作者
        db.add(Notification(
            user_id=post.user_id,
            type="comment",
            title="您的帖子有新评论",
            content=f"{current_user.nickname} 评论了你的《{post.title}》",
            target_type="post",
            target_id=post_id,
            actor_id=current_user.id,
            is_read=False,
        ))

    await db.commit()

    # 重新查询以获取关联数据（预加载 replies 防止 MissingGreenlet）
    query = select(Comment).where(Comment.id == comment.id)
    query = query.options(
        joinedload(Comment.user),
        joinedload(Comment.reply_to_user),
        selectinload(Comment.replies),
    )
    result = await db.execute(query)
    comment = result.unique().scalar_one()

    # DSC-02.1: 手动构造响应，避免 model_validate 递归触发 lazy load
    return _build_comment_response(comment, include_replies=False)


@router.delete("/comments/{comment_id}", summary="删除评论",
               dependencies=[Depends(require_campus_verified())])
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """删除评论（软删除），需要认证，验证所有权

    TEN-02.3：跨校评论统一返回 404。
    """
    # 查询评论
    query = select(Comment).where(Comment.id == comment_id, Comment.is_deleted == False)
    result = await db.execute(query)
    comment = result.scalar_one_or_none()

    if comment is None:
        raise NotFoundException(detail="评论不存在")

    # TEN-02.3: 资源级租户校验——通过帖子确认评论属于当前学校
    post_result = await db.execute(select(Post).where(Post.id == comment.post_id))
    post = post_result.scalar_one_or_none()
    if post is not None:
        check_resource_in_tenant(post.school_id, tenant)

    # 验证所有权
    if comment.user_id != current_user.id:
        raise ForbiddenException(detail="没有权限删除此评论")

    # 软删除
    comment.is_deleted = True
    comment.deleted_at = datetime.now()

    # 更新信息的评论计数
    if post:
        post.comment_count = max(0, post.comment_count - 1)

    await db.commit()

    return {"message": "删除成功"}
