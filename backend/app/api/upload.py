"""FND-03.4: 上传安全

安全策略：
1. 按文件内容 magic bytes 识别真实格式，不信任客户端声明的 content_type
2. 仅允许 JPEG / PNG / GIF 三类图片
3. 单文件大小 ≤ MAX_UPLOAD_SIZE（默认 5MB）
4. 像素尺寸 ≤ MAX_IMAGE_DIMENSION（默认 8000px），最小 1x1
5. 用 Pillow 重新编码图片（去除 EXIF/恶意 payload、规范化图片结构）
6. 文件名使用 uuid4 + 真实扩展名，杜绝路径穿越
7. 拒绝非图片或可疑文件
"""
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
    file_size: int = Field(..., description="文件大小（字节，重新编码后）")


# FND-03.4: 限制常量
MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE  # 默认 5MB
MAX_IMAGE_DIMENSION = 8000  # 单边最大像素
MIN_IMAGE_DIMENSION = 1     # 单边最小像素
THUMBNAIL_SIZE = (300, 300)


# magic bytes → (canonical_format, file_extension)
# 仅允许这三类图片格式；其他一律拒绝
_MAGIC_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "JPEG", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "PNG", "png"),
    (b"GIF87a", "GIF", "gif"),
    (b"GIF89a", "GIF", "gif"),
)


def _detect_format_by_magic(content: bytes) -> Optional[tuple[str, str]]:
    """通过 magic bytes 检测图片真实格式

    Returns:
        (PIL_format, extension) 或 None（非图片/不支持的格式）
    """
    for signature, fmt, ext in _MAGIC_SIGNATURES:
        if content.startswith(signature):
            return fmt, ext
    return None


def _validate_image_content(content: bytes) -> tuple[Image.Image, str, str]:
    """完整校验图片内容并返回 (PIL Image, format, extension)

    校验项：
        - magic bytes 必须匹配 JPEG/PNG/GIF 之一
        - Pillow verify() 必须通过
        - 像素尺寸限制
    """
    detected = _detect_format_by_magic(content)
    if detected is None:
        raise BadRequestException(
            detail="文件不是有效的图片或格式不受支持，仅允许 jpg/png/gif"
        )
    fmt, ext = detected

    try:
        # verify() 检查图片完整性（不实际解码像素）
        image = Image.open(BytesIO(content))
        image.verify()
    except Exception:
        raise BadRequestException(detail="文件不是有效的图片（解码失败）")

    # verify() 后图像对象已被消耗，重新打开用于实际处理
    try:
        image = Image.open(BytesIO(content))
        image.load()
    except Exception:
        raise BadRequestException(detail="文件不是有效的图片（解码失败）")

    # 像素尺寸校验
    width, height = image.size
    if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
        raise BadRequestException(
            detail=f"图片尺寸过小：{width}x{height}，最小要求 {MIN_IMAGE_DIMENSION}x{MIN_IMAGE_DIMENSION}"
        )
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise BadRequestException(
            detail=f"图片尺寸过大：{width}x{height}，最大允许 {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}"
        )

    # 校验 PIL 识别出的格式与 magic bytes 一致（双重校验，防伪造）
    if image.format != fmt:
        raise BadRequestException(
            detail="文件内容与声明的格式不一致，疑似伪造"
        )

    return image, fmt, ext


def _reencode_image(image: Image.Image, fmt: str, ext: str) -> bytes:
    """用 Pillow 重新编码图片，去除 EXIF/恶意 payload 并规范化结构

    - JPEG/PNG 转为 RGB（去除 alpha 通道）后保存
    - GIF 保持动画格式（save_all=True）
    """
    buffer = BytesIO()
    if fmt == "GIF":
        # GIF 保持原格式，保留动画
        image.save(buffer, format="GIF", save_all=True)
    elif fmt == "PNG":
        # PNG 支持 RGBA，保留透明通道
        save_image = image if image.mode in ("RGB", "RGBA") else image.convert("RGBA")
        save_image.save(buffer, format="PNG")
    else:
        # JPEG 不支持 alpha，转为 RGB
        save_image = image if image.mode == "RGB" else image.convert("RGB")
        save_image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


@router.post("/upload/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    上传图片（FND-03.4 安全加固）

    安全策略：
        - 按文件内容 magic bytes 识别真实格式，不信任 content_type
        - 仅允许 JPEG / PNG / GIF
        - 单文件 ≤ 5MB
        - 像素 ≤ 8000x8000
        - 用 Pillow 重新编码（去除 EXIF/恶意 payload）
        - 文件名 = uuid4 + 真实扩展名，杜绝路径穿越
        - 自动生成 300x300 缩略图
    """
    # COM-01.2: 权益校验——上传前必须确认学校有 active 订阅；
    # storage_mb 软限制的精确用量统计暂未接入（需汇总 uploads 目录大小），留扩展点由 COM-02 完善。
    from app.core.entitlement import EntitlementService
    ent_svc = await EntitlementService.create(db, current_user.school_id)
    if not ent_svc.has_active_subscription:
        raise BadRequestException(detail="当前学校未开通有效套餐，无法上传图片")

    # 1. 读取文件内容
    content = await file.read()
    file_size = len(content)

    # 2. 文件大小限制（先校验尺寸，避免对超大文件做后续处理）
    if file_size > MAX_FILE_SIZE:
        raise BadRequestException(
            detail=f"图片大小超过限制：{file_size / 1024 / 1024:.2f}MB，"
                   f"最大允许 {MAX_FILE_SIZE / 1024 / 1024:.2f}MB"
        )
    if file_size == 0:
        raise BadRequestException(detail="文件为空")

    # 3. FND-03.4: 按内容识别格式 + Pillow 完整校验 + 像素限制
    image, fmt, ext = _validate_image_content(content)

    # 4. FND-03.4: 重新编码图片（去除 EXIF/恶意 payload，规范化结构）
    try:
        reencoded_content = _reencode_image(image, fmt, ext)
    except Exception:
        raise BadRequestException(detail="图片重新编码失败，请检查文件是否损坏")
    finally:
        image.close()

    # 5. FND-03.4: 生成安全文件名（uuid + 真实扩展名），杜绝路径穿越
    safe_filename = f"{uuid.uuid4().hex}.{ext}"

    # 6. 确保上传目录存在
    upload_dir = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)

    # 7. 保存重新编码后的原图
    file_path = os.path.join(upload_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(reencoded_content)

    final_size = len(reencoded_content)

    # 8. 生成缩略图
    thumbnail_url = None
    try:
        thumb_filename = f"thumb_{safe_filename}"
        thumb_path = os.path.join(upload_dir, thumb_filename)

        # 重新打开原图用于缩略图（前面 image 已被 save 消耗）
        with Image.open(BytesIO(reencoded_content)) as thumb_image:
            thumb_image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            if fmt == "GIF":
                thumb_image.save(thumb_path, format="GIF", save_all=True)
            elif fmt == "PNG":
                save_thumb = thumb_image if thumb_image.mode in ("RGB", "RGBA") else thumb_image.convert("RGBA")
                try:
                    save_thumb.save(thumb_path, format="PNG")
                finally:
                    if save_thumb is not thumb_image:
                        save_thumb.close()
            else:
                save_thumb = thumb_image if thumb_image.mode == "RGB" else thumb_image.convert("RGB")
                try:
                    save_thumb.save(thumb_path, format="JPEG", quality=85)
                finally:
                    if save_thumb is not thumb_image:
                        save_thumb.close()

        thumbnail_url = f"/uploads/{thumb_filename}"
    except Exception:
        # 缩略图生成失败不影响原图上传
        pass

    # 9. 构建 URL
    url = f"/uploads/{safe_filename}"

    return UploadResponse(
        url=url,
        thumbnail_url=thumbnail_url,
        filename=safe_filename,
        file_size=final_size,
    )
