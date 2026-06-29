from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.models.post import Post
from app.models.tag import Tag
from app.models.post_tag import PostTag
from app.models.post_image import PostImage
from app.models.like import Like
from app.models.favorite import Favorite
from app.models.user import User
from app.models.category import Category
from app.schemas.post import PostCreate, PostUpdate, PostResponse, PostListResponse, TagBrief
from app.schemas.common import PaginatedResponse
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException

router = APIRouter(prefix="/posts", tags=["信息"])


def generate_slug(name: str) -> str:
    """生成标签的 slug"""
    return name.lower().replace(" ", "-").strip()


@router.get("", response_model=PaginatedResponse[PostListResponse], summary="获取信息列表")
async def get_posts(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    category_id: Optional[int] = Query(default=None, description="分类ID"),
    post_type_id: Optional[int] = Query(default=None, description="信息类型ID"),
    status: Optional[str] = Query(default=None, description="状态"),
    sort: str = Query(default="latest", description="排序方式: latest/hottest/nearest"),
    db: AsyncSession = Depends(get_db),
):
    """获取信息列表，支持分页、筛选和排序"""
    # 基础查询
    query = select(Post).where(Post.is_deleted == False, Post.status == "published")

    # 筛选
    if category_id is not None:
        query = query.where(Post.category_id == category_id)
    if post_type_id is not None:
        query = query.where(Post.post_type_id == post_type_id)
    if status is not None:
        query = query.where(Post.status == status)

    # 排序
    if sort == "latest":
        query = query.order_by(Post.is_top.desc(), Post.created_at.desc())
    elif sort == "hottest":
        query = query.order_by(Post.is_top.desc(), Post.like_count.desc(), Post.created_at.desc())
    elif sort == "nearest":
        # 按距离排序需要 location，这里简化为按更新时间排序
        query = query.order_by(Post.is_top.desc(), Post.updated_at.desc())
    else:
        query = query.order_by(Post.is_top.desc(), Post.created_at.desc())

    # 计算总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # 预加载关联数据
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        selectinload(Post.post_tags).selectinload(PostTag.tag),
        selectinload(Post.post_images),
    )

    result = await db.execute(query)
    posts = result.unique().scalars().all()

    # 转换为响应格式
    items = []
    for post in posts:
        post_data = PostListResponse.model_validate(post)
        # 设置封面图片
        if post.post_images:
            post_data.cover_image = post.post_images[0].image_url if post.post_images else None
        # 设置标签
        if post.post_tags:
            post_data.tags = [TagBrief.model_validate(pt.tag) for pt in post.post_tags if pt.tag]
        items.append(post_data)

    return PaginatedResponse.create(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{post_id}", response_model=PostResponse, summary="获取信息详情")
async def get_post(
    post_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """获取信息详情，增加浏览次数"""
    # 查询信息
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        joinedload(Post.post_type),
        selectinload(Post.post_tags).selectinload(PostTag.tag),
        selectinload(Post.post_images),
    )

    result = await db.execute(query)
    post = result.unique().scalar_one_or_none()

    if post is None:
        raise NotFoundException(detail="信息不存在")

    # 增加浏览次数
    post.view_count += 1
    await db.commit()
    await db.refresh(post, attribute_names=["view_count"])

    # 检查当前用户是否点赞/收藏
    is_liked = False
    is_favorited = False
    if current_user:
        like_result = await db.execute(
            select(Like).where(Like.post_id == post_id, Like.user_id == current_user.id)
        )
        is_liked = like_result.scalar_one_or_none() is not None

        fav_result = await db.execute(
            select(Favorite).where(Favorite.post_id == post_id, Favorite.user_id == current_user.id)
        )
        is_favorited = fav_result.scalar_one_or_none() is not None

    # 构建响应
    response = PostResponse.model_validate(post)
    response.is_liked = is_liked
    response.is_favorited = is_favorited

    # 设置标签
    if post.post_tags:
        response.tags = [TagBrief.model_validate(pt.tag) for pt in post.post_tags if pt.tag]

    return response


@router.post("", response_model=PostResponse, status_code=201, summary="创建信息")
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建信息，需要认证"""
    # 创建信息
    post = Post(
        user_id=current_user.id,
        school_id=current_user.school_id,
        category_id=post_data.category_id,
        post_type_id=post_data.post_type_id or 1,  # 默认类型
        location_id=post_data.location_id,
        title=post_data.title,
        content=post_data.content,
        is_anonymous=post_data.is_anonymous,
        status="pending",  # 需要审核
        expire_at=post_data.expire_at,
        activity_start_at=post_data.activity_start_at,
        activity_end_at=post_data.activity_end_at,
        lost_type=post_data.lost_type,
        contact_info=post_data.contact_info,
    )

    # 如果没有设置过期时间，使用分类的默认有效期
    if post.expire_at is None:
        cat_result = await db.execute(select(Category).where(Category.id == post.category_id))
        category = cat_result.scalar_one_or_none()
        if category:
            post.expire_at = datetime.now() + timedelta(days=category.default_validity_days)

    db.add(post)
    await db.flush()  # 获取 post.id

    # 处理标签
    if post_data.tags:
        for tag_name in post_data.tags:
            tag_name = tag_name.strip()
            if not tag_name:
                continue

            # 查找或创建标签
            slug = generate_slug(tag_name)
            tag_result = await db.execute(select(Tag).where(Tag.slug == slug, Tag.is_deleted == False))
            tag = tag_result.scalar_one_or_none()

            if tag is None:
                tag = Tag(name=tag_name, slug=slug)
                db.add(tag)
                await db.flush()

            # 创建关联
            post_tag = PostTag(post_id=post.id, tag_id=tag.id)
            db.add(post_tag)

            # 更新标签使用次数
            tag.usage_count += 1

    # 处理图片
    if post_data.image_urls:
        for idx, image_url in enumerate(post_data.image_urls):
            post_image = PostImage(
                post_id=post.id,
                image_url=image_url,
                sort_order=idx,
            )
            db.add(post_image)

    await db.commit()
    await db.refresh(post)

    # 重新查询以获取关联数据
    query = select(Post).where(Post.id == post.id)
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        joinedload(Post.post_type),
        selectinload(Post.post_tags).selectinload(PostTag.tag),
        selectinload(Post.post_images),
    )
    result = await db.execute(query)
    post = result.unique().scalar_one()

    response = PostResponse.model_validate(post)
    if post.post_tags:
        response.tags = [TagBrief.model_validate(pt.tag) for pt in post.post_tags if pt.tag]

    return response


@router.put("/{post_id}", response_model=PostResponse, summary="更新信息")
async def update_post(
    post_id: int,
    post_data: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新信息，需要认证，验证所有权"""
    # 查询信息
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        joinedload(Post.post_type),
        selectinload(Post.post_tags).selectinload(PostTag.tag),
        selectinload(Post.post_images),
    )

    result = await db.execute(query)
    post = result.unique().scalar_one_or_none()

    if post is None:
        raise NotFoundException(detail="信息不存在")

    # 验证所有权
    if post.user_id != current_user.id:
        raise ForbiddenException(detail="没有权限修改此信息")

    # 更新字段
    update_data = post_data.model_dump(exclude_unset=True)

    # 处理标签更新
    if "tags" in update_data:
        tags = update_data.pop("tags")
        # 删除旧的关联
        old_tags_result = await db.execute(
            select(PostTag).where(PostTag.post_id == post_id)
        )
        old_post_tags = old_tags_result.scalars().all()
        for pt in old_post_tags:
            # 减少标签使用次数
            tag_result = await db.execute(select(Tag).where(Tag.id == pt.tag_id))
            tag = tag_result.scalar_one_or_none()
            if tag:
                tag.usage_count = max(0, tag.usage_count - 1)
            await db.delete(pt)

        # 添加新的标签
        if tags:
            for tag_name in tags:
                tag_name = tag_name.strip()
                if not tag_name:
                    continue

                slug = generate_slug(tag_name)
                tag_result = await db.execute(select(Tag).where(Tag.slug == slug, Tag.is_deleted == False))
                tag = tag_result.scalar_one_or_none()

                if tag is None:
                    tag = Tag(name=tag_name, slug=slug)
                    db.add(tag)
                    await db.flush()

                post_tag = PostTag(post_id=post.id, tag_id=tag.id)
                db.add(post_tag)
                tag.usage_count += 1

    # 处理图片更新
    if "image_urls" in update_data:
        image_urls = update_data.pop("image_urls")
        # 删除旧的图片
        old_images_result = await db.execute(
            select(PostImage).where(PostImage.post_id == post_id)
        )
        old_images = old_images_result.scalars().all()
        for img in old_images:
            await db.delete(img)

        # 添加新的图片
        if image_urls:
            for idx, image_url in enumerate(image_urls):
                post_image = PostImage(
                    post_id=post.id,
                    image_url=image_url,
                    sort_order=idx,
                )
                db.add(post_image)

    # 更新其他字段
    for field, value in update_data.items():
        if hasattr(post, field):
            setattr(post, field, value)

    await db.commit()

    # 重新查询以获取更新后的关联数据
    query = select(Post).where(Post.id == post.id)
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        joinedload(Post.post_type),
        selectinload(Post.post_tags).selectinload(PostTag.tag),
        selectinload(Post.post_images),
    )
    result = await db.execute(query)
    post = result.unique().scalar_one()

    response = PostResponse.model_validate(post)
    if post.post_tags:
        response.tags = [TagBrief.model_validate(pt.tag) for pt in post.post_tags if pt.tag]

    return response


@router.delete("/{post_id}", summary="删除信息")
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除信息（软删除），需要认证，验证所有权"""
    # 查询信息
    query = select(Post).where(Post.id == post_id, Post.is_deleted == False)
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if post is None:
        raise NotFoundException(detail="信息不存在")

    # 验证所有权
    if post.user_id != current_user.id:
        raise ForbiddenException(detail="没有权限删除此信息")

    # 软删除
    post.is_deleted = True
    post.deleted_at = datetime.now()

    await db.commit()

    return {"message": "删除成功"}
