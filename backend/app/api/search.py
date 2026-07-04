from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user_optional
from app.models.user import User
from app.models.post import Post
from app.models.category import Category
from app.models.location import Location
from app.models.post_tag import PostTag
from app.models.tag import Tag
from app.models.search_history import SearchHistory
from app.schemas.post import PostListResponse
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundException

router = APIRouter(tags=["搜索"])


@router.get("/search", response_model=PaginatedResponse[PostListResponse])
async def search_posts(
    keyword: Optional[str] = Query(None, max_length=100, description="搜索关键词"),
    category_id: Optional[int] = Query(None, description="分类ID"),
    location_id: Optional[int] = Query(None, description="地点ID"),
    post_type_id: Optional[int] = Query(None, description="信息类型ID"),
    school_id: Optional[int] = Query(None, description="学校ID"),
    tag: Optional[str] = Query(None, max_length=50, description="标签"),
    sort_by: str = Query("created_at", pattern="^(created_at|like_count|comment_count|view_count)$", description="排序字段"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="排序方式"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    搜索信息
    支持关键词搜索、多字段筛选、排序和分页
    """
    # 构建基础查询
    query = select(Post).where(Post.is_deleted == False, Post.status == "published")

    # 关键词搜索（多字段模糊匹配）
    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.where(
            or_(
                Post.title.ilike(keyword_pattern),
                Post.content.ilike(keyword_pattern),
                Post.contact_info.ilike(keyword_pattern),
            )
        )

    # 筛选条件
    if category_id:
        query = query.where(Post.category_id == category_id)
    if location_id:
        query = query.where(Post.location_id == location_id)
    if post_type_id:
        query = query.where(Post.post_type_id == post_type_id)
    if school_id:
        query = query.where(Post.school_id == school_id)

    # 标签筛选
    if tag:
        tag_query = select(Tag.id).where(Tag.name == tag, Tag.is_deleted == False)
        tag_result = await db.execute(tag_query)
        tag_id = tag_result.scalar_one_or_none()
        if tag_id:
            post_tag_query = select(PostTag.post_id).where(PostTag.tag_id == tag_id)
            post_tag_result = await db.execute(post_tag_query)
            post_ids = [row[0] for row in post_tag_result.fetchall()]
            if post_ids:
                query = query.where(Post.id.in_(post_ids))
            else:
                # 没有匹配的帖子，返回空结果
                return PaginatedResponse.create([], page, page_size, 0)

    # 排序
    sort_column = getattr(Post, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

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

    # 转换为响应格式
    items = []
    for post in posts:
        # 获取分类信息
        category_result = await db.execute(
            select(Category).where(Category.id == post.category_id)
        )
        category = category_result.scalar_one_or_none()

        # 获取地点信息
        location = None
        if post.location_id:
            location_result = await db.execute(
                select(Location).where(Location.id == post.location_id)
            )
            location = location_result.scalar_one_or_none()

        # 获取作者信息
        author_result = await db.execute(
            select(User).where(User.id == post.user_id)
        )
        author = author_result.scalar_one_or_none()

        # 获取标签
        tag_query = (
            select(Tag)
            .join(PostTag, PostTag.tag_id == Tag.id)
            .where(PostTag.post_id == post.id, Tag.is_deleted == False)
        )
        tag_result = await db.execute(tag_query)
        tags = tag_result.scalars().all()

        # 获取封面图
        from app.models.post_image import PostImage
        image_query = (
            select(PostImage)
            .where(PostImage.post_id == post.id, PostImage.is_deleted == False)
            .order_by(PostImage.sort_order)
            .limit(1)
        )
        image_result = await db.execute(image_query)
        cover_image = None
        first_image = image_result.scalar_one_or_none()
        if first_image:
            cover_image = first_image.image_url

        # 构建响应
        post_dict = {
            "id": post.id,
            "user_id": post.user_id,
            "title": post.title,
            "content": post.content,
            "is_anonymous": post.is_anonymous,
            "category": category,
            "location": location,
            "author": {"id": author.id, "nickname": author.nickname, "avatar_url": author.avatar_url} if (author and not post.is_anonymous) else None,
            "cover_image": cover_image,
            "tags": tags,
            "like_count": post.like_count,
            "comment_count": post.comment_count,
            "view_count": post.view_count,
            "valid_count": post.valid_count,
            "invalid_count": post.invalid_count,
            "is_recommend": post.is_recommend,
            "created_at": post.created_at,
            "expire_at": post.expire_at,
        }
        items.append(PostListResponse(**post_dict))

    # 记录搜索历史（如果有用户登录且有关键词）
    if current_user and keyword:
        search_history = SearchHistory(
            user_id=current_user.id,
            keyword=keyword,
            result_count=total,
        )
        db.add(search_history)
        await db.commit()

    return PaginatedResponse.create(items, page, page_size, total)
