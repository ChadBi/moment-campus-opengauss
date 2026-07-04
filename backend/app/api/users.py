from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import os
import uuid
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.category import Category
from app.models.location import Location
from app.models.post_tag import PostTag
from app.models.tag import Tag
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.post import PostListResponse
from app.schemas.common import MessageResponse, PaginatedResponse
from app.core.exceptions import BadRequestException
from app.config import settings

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.put("/me", response_model=UserResponse, summary="更新用户信息")
async def update_user_info(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 更新用户信息
    if data.nickname is not None:
        current_user.nickname = data.nickname
    if data.bio is not None:
        current_user.bio = data.bio
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url

    current_user.updated_at = datetime.now()
    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.post("/me/avatar", response_model=MessageResponse, summary="上传头像")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 验证文件格式
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise BadRequestException(detail="不支持的图片格式，仅支持 JPG、PNG、GIF、WEBP")

    # 验证文件大小
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise BadRequestException(detail=f"图片大小不能超过 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    # 生成唯一文件名
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{file_extension}"

    # 确保上传目录存在
    upload_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(upload_dir, exist_ok=True)

    # 保存文件
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # 生成访问 URL
    avatar_url = f"/uploads/avatars/{filename}"

    # 更新用户头像
    current_user.avatar_url = avatar_url
    current_user.updated_at = datetime.now()
    await db.commit()

    return MessageResponse(
        message="头像上传成功",
        data={"avatar_url": avatar_url}
    )


@router.get("/me/posts", response_model=PaginatedResponse[PostListResponse], summary="获取我的信息列表")
async def get_my_posts(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 查询我的帖子（未删除），预加载关联数据
    query = select(Post).options(
        selectinload(Post.user),
        selectinload(Post.category),
        selectinload(Post.location),
        selectinload(Post.post_tags).selectinload(PostTag.tag),
    ).where(
        Post.user_id == current_user.id,
        Post.is_deleted == False
    ).order_by(Post.created_at.desc())

    # 获取总数
    count_query = select(func.count()).select_from(Post).where(
        Post.user_id == current_user.id,
        Post.is_deleted == False
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    posts_result = await db.execute(query.offset(offset).limit(page_size))
    posts = posts_result.scalars().all()

    return PaginatedResponse.create(
        items=posts,
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/me/favorites", response_model=PaginatedResponse[PostListResponse], summary="获取我的收藏列表", deprecated=True, include_in_schema=False)
async def get_my_favorites(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[已废弃] 收藏功能已下线，返回空列表"""
    return PaginatedResponse.create(
        items=[],
        page=page,
        page_size=page_size,
        total=0
    )
