"""TOPIC-01.1: 用户端专题 API

仅展示已发布（published）专题；专题只能引用同校已发布/已过期帖子。
切换学校（X-School-Code / ?school=）只展示当前学校专题。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional

from app.database import get_db
from app.models.topic_collection import TopicCollection
from app.models.topic_collection_post import TopicCollectionPost
from app.models.post import Post
from app.schemas.topic import (
    TopicListItem, TopicDetail, TopicPostItem, TopicStatus,
)
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundException
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.post_status import PostStatus

router = APIRouter(prefix="/topics", tags=["专题"])


# 用户端可见的帖子状态：published / expired（与 posts API 一致）
_USER_VISIBLE_POST_STATUSES = {PostStatus.PUBLISHED, PostStatus.EXPIRED}


@router.get("", response_model=PaginatedResponse[TopicListItem], summary="获取专题列表（用户端）")
async def get_topics(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取已发布专题列表（按 sort_order 升序，published_at 降序）

    TOPIC-01.1: 用户端仅展示 status=published 的专题。
    TEN-02.3: 按当前学校过滤，跨校专题不出现。
    """
    base_filter = (
        TopicCollection.school_id == tenant.school_id,
        TopicCollection.status == TopicStatus.PUBLISHED,
        TopicCollection.is_deleted == False,  # noqa: E712
    )

    query = (
        select(TopicCollection)
        .where(*base_filter)
        .order_by(
            TopicCollection.sort_order.asc(),
            TopicCollection.published_at.desc().nullslast(),
            TopicCollection.id.asc(),
        )
    )

    count_query = select(func.count()).select_from(TopicCollection).where(*base_filter)
    total = await db.scalar(count_query)

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    topics = result.scalars().all()

    items = [
        TopicListItem(
            id=t.id,
            title=t.title,
            description=t.description,
            cover_url=t.cover_url,
            post_count=t.post_count,
            view_count=t.view_count,
            sort_order=t.sort_order,
            published_at=t.published_at,
            created_at=t.created_at,
        )
        for t in topics
    ]
    return PaginatedResponse.create(items, page, page_size, total or 0)


@router.get("/{topic_id}", response_model=TopicDetail, summary="获取专题详情（用户端）")
async def get_topic_detail(
    topic_id: int,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取专题详情，含关联帖子列表（按 sort_order 升序）

    TOPIC-01.1:
    - 仅返回 status=published 的专题，否则 404
    - 专题内的帖子仅展示 published/expired 状态，draft/pending/archived 不出现
    TEN-02.3: 跨校专题统一 404。
    """
    topic = await db.scalar(
        select(TopicCollection).where(
            TopicCollection.id == topic_id,
            TopicCollection.is_deleted == False,  # noqa: E712
        )
    )
    if not topic:
        raise NotFoundException(detail="专题不存在")

    # 资源级租户校验：跨校专题统一 404
    check_resource_in_tenant(topic.school_id, tenant)

    # 用户端仅可见 published 专题
    if topic.status != TopicStatus.PUBLISHED:
        raise NotFoundException(detail="专题不存在")

    # 查询专题内的帖子（仅展示 published/expired）
    rows = await db.execute(
        select(TopicCollectionPost, Post)
        .join(Post, TopicCollectionPost.post_id == Post.id)
        .where(
            TopicCollectionPost.topic_collection_id == topic.id,
            Post.is_deleted == False,  # noqa: E712
            Post.status.in_(_USER_VISIBLE_POST_STATUSES),
        )
        .options(
            joinedload(Post.user),
            joinedload(Post.category),
            joinedload(Post.post_type),
        )
        .order_by(TopicCollectionPost.sort_order.asc(), TopicCollectionPost.id.asc())
    )
    posts_list: list[TopicPostItem] = []
    for tcp, post in rows.unique().all():
        # 取帖子第一张图作为封面
        cover_image_url: Optional[str] = None
        # 延迟查询首图，避免 N+1：使用单独 select
        posts_list.append(TopicPostItem(
            id=post.id,
            title=post.title,
            content=post.content[:200] if len(post.content) > 200 else post.content,
            status=post.status,
            view_count=post.view_count,
            like_count=post.like_count,
            comment_count=post.comment_count,
            category_id=post.category_id,
            category_name=post.category.name if post.category else None,
            post_type_id=post.post_type_id,
            post_type_name=post.post_type.name if post.post_type else None,
            author_id=post.user_id if not post.is_anonymous else None,
            author_name=post.user.nickname if (post.user and not post.is_anonymous) else None,
            cover_image_url=cover_image_url,
            sort_order=tcp.sort_order,
            created_at=post.created_at,
        ))

    # 批量补齐首图（避免 N+1）
    if posts_list:
        post_ids = [p.id for p in posts_list]
        from app.models.post_image import PostImage
        image_rows = await db.execute(
            select(PostImage.post_id, PostImage.image_url)
            .where(
                PostImage.post_id.in_(post_ids),
                PostImage.is_deleted == False,  # noqa: E712
            )
            .order_by(PostImage.post_id.asc(), PostImage.sort_order.asc())
        )
        first_image_map: dict[int, str] = {}
        for pid, url in image_rows.all():
            if pid not in first_image_map:
                first_image_map[pid] = url
        for p in posts_list:
            p.cover_image_url = first_image_map.get(p.id)

    # 浏览数 +1（同事务提交）
    topic.view_count = (topic.view_count or 0) + 1
    await db.commit()

    return TopicDetail(
        id=topic.id,
        title=topic.title,
        description=topic.description,
        cover_url=topic.cover_url,
        post_count=topic.post_count,
        view_count=topic.view_count,
        sort_order=topic.sort_order,
        published_at=topic.published_at,
        created_at=topic.created_at,
        posts=posts_list,
    )
