import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional
from PIL import Image
from io import BytesIO

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings
from app.schemas.common import MessageResponse
from app.core.exceptions import BadRequestException

router = APIRouter(tags=["上传"])


class UploadResponse(BaseModel):
    """上传响应"""
    url: str = Field(..., description="图片URL")
    thumbnail_url: Optional[str] = Field(None, description="缩略图URL")
    filename: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小（字节）")


# 允许的图片格式
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
}

# 最大文件大小：5MB
MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE


@router.post("/upload/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    上传图片
    验证格式和大小，保存到 uploads，返回 URL
    支持 jpg, png, gif 格式，最大 5MB
    自动生成缩略图
    """
    # 验证文件类型
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestException(
            detail=f"不支持的图片格式：{file.content_type}，仅支持 jpg, png, gif"
        )

    # 读取文件内容
    content = await file.read()
    file_size = len(content)

    # 验证文件大小
    if file_size > MAX_FILE_SIZE:
        raise BadRequestException(
            detail=f"图片大小超过限制：{file_size / 1024 / 1024:.2f}MB，最大允许 5MB"
        )

    # 验证文件内容是否为有效图片
    try:
        image = Image.open(BytesIO(content))
        image.verify()
        # 重新打开，因为 verify() 会消耗图片
        image = Image.open(BytesIO(content))
    except Exception:
        raise BadRequestException(detail="文件不是有效的图片")

    # 生成唯一文件名
    ext = ALLOWED_CONTENT_TYPES[file.content_type]
    unique_filename = f"{uuid.uuid4().hex}.{ext}"

    # 确保上传目录存在
    upload_dir = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)

    # 保存原图
    file_path = os.path.join(upload_dir, unique_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # 生成缩略图
    thumbnail_url = None
    try:
        # 缩略图尺寸
        thumb_size = (300, 300)
        thumb_filename = f"thumb_{unique_filename}"
        thumb_path = os.path.join(upload_dir, thumb_filename)

        # 创建缩略图
        thumb = image.copy()
        thumb.thumbnail(thumb_size, Image.Resampling.LANCZOS)

        # 保存缩略图（如果是 GIF，保持原格式；否则转为 JPEG）
        if ext == "gif":
            thumb.save(thumb_path, format="GIF", save_all=True)
        else:
            # 转换为 RGB（如果是 RGBA）
            if thumb.mode in ("RGBA", "P"):
                thumb = thumb.convert("RGB")
            thumb.save(thumb_path, format="JPEG", quality=85)

        thumbnail_url = f"/uploads/{thumb_filename}"
    except Exception:
        # 缩略图生成失败不影响原图上传
        pass

    # 构建 URL
    url = f"/uploads/{unique_filename}"

    return UploadResponse(
        url=url,
        thumbnail_url=thumbnail_url,
        filename=unique_filename,
        file_size=file_size,
    )
