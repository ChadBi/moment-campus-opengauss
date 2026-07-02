from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.like import Like
from app.models.favorite import Favorite
from app.models.validation_record import ValidationRecord
from app.models.report import Report
from app.models.notification import Notification
from app.schemas.interaction import (
    LikeResponse,
    FavoriteResponse,
    ValidationCreate,
    ValidationResponse,
    ValidationStatsResponse,
)
from app.schemas.common import MessageResponse
from app.core.exceptions import NotFoundException, BadRequestException
from app.core.validation_type import (
    normalize_validation_type,
    ValidationType,
)

router = APIRouter(tags=["互动"])


class ReportCreateSchema(BaseModel):
    report_type: str = Field(
        ...,
        pattern="^(spam|abuse|harassment|false_info|other)$",
        description="举报类型：spam（垃圾信息）/ abuse（滥用）/ harassment（骚扰）/ false_info（虚假信息）/ other（其他）"
    )
    description: Optional[str] = Field(None, max_length=1000, description="举报描述，最多1000字符")


@router.post("/posts/{post_id}/like", response_model=LikeResponse)
async def toggle_like(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    点赞/取消点赞（切换）
    如果已点赞则取消点赞，如果未点赞则点赞
    """
    # 查询帖子
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # 查询是否已点赞
    result = await db.execute(
        select(Like).where(Like.post_id == post_id, Like.user_id == current_user.id)
    )
    existing_like = result.scalar_one_or_none()

    if existing_like:
        # 取消点赞
        await db.delete(existing_like)
        post.like_count = max(0, post.like_count - 1)
        is_liked = False
    else:
        # 点赞
        new_like = Like(post_id=post_id, user_id=current_user.id)
        db.add(new_like)
        post.like_count += 1
        is_liked = True

        # 创建通知（不给自己的帖子点赞发通知）
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                type="like",
                title="有人赞了你的帖子",
                content=f"{current_user.nickname}赞了你的帖子「{post.title}」",
                target_type="post",
                target_id=post_id,
                actor_id=current_user.id,
            )
            db.add(notification)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestException(detail="操作失败，请重试")

    await db.refresh(post)

    return LikeResponse(
        post_id=post_id,
        like_count=post.like_count,
        is_liked=is_liked,
    )


@router.post("/posts/{post_id}/favorite", response_model=FavoriteResponse)
async def toggle_favorite(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    收藏/取消收藏（切换）
    如果已收藏则取消收藏，如果未收藏则收藏
    """
    # 查询帖子
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # 查询是否已收藏
    result = await db.execute(
        select(Favorite).where(Favorite.post_id == post_id, Favorite.user_id == current_user.id)
    )
    existing_favorite = result.scalar_one_or_none()

    if existing_favorite:
        # 取消收藏
        await db.delete(existing_favorite)
        post.favorite_count = max(0, post.favorite_count - 1)
        is_favorited = False
    else:
        # 收藏
        new_favorite = Favorite(post_id=post_id, user_id=current_user.id)
        db.add(new_favorite)
        post.favorite_count += 1
        is_favorited = True

        # 创建通知（不给自己的帖子收藏发通知）
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                type="favorite",
                title="有人收藏了你的帖子",
                content=f"{current_user.nickname}收藏了你的帖子「{post.title}」",
                target_type="post",
                target_id=post_id,
                actor_id=current_user.id,
            )
            db.add(notification)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestException(detail="操作失败，请重试")

    await db.refresh(post)

    return FavoriteResponse(
        post_id=post_id,
        favorite_count=post.favorite_count,
        is_favorited=is_favorited,
    )


@router.post("/posts/{post_id}/validate", response_model=ValidationResponse)
async def create_validation(
    post_id: int,
    data: ValidationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    协同验证（T-B-02 扩展为 5 类）

    用户可对帖子提交 5 类协同验证：
    - confirmation: 证实（信息真实有效）
    - refutation: 证伪（信息有误）
    - update: 补充更新
    - expiration_report: 过期上报
    - conflict_report: 冲突上报

    向后兼容旧值：valid→confirmation / invalid→refutation / uncertain→update
    """
    # 查询帖子
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # 归一化验证类型（别名 → 正式名）
    canonical_type = normalize_validation_type(data.validation_type)

    # 创建协同验证记录（统一存储正式名）
    validation = ValidationRecord(
        post_id=post_id,
        user_id=current_user.id,
        validation_type=canonical_type,
        comment=data.comment,
    )
    db.add(validation)

    # 兼容旧 Post.valid_count / invalid_count 统计字段
    # - confirmation → valid_count +1
    # - refutation   → invalid_count +1
    # - 其他 3 类不计入旧字段（待 T-C-01 可信度计算统一处理）
    if canonical_type in ValidationType.LEGACY_POSITIVE_COUNT_TYPES:
        post.valid_count += 1
    elif canonical_type in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES:
        post.invalid_count += 1

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestException(detail="操作失败，请重试")

    await db.refresh(validation)

    return ValidationResponse(
        id=validation.id,
        post_id=validation.post_id,
        user_id=validation.user_id,
        validation_type=validation.validation_type,
        comment=validation.comment,
        created_at=validation.created_at,
    )


@router.post("/posts/{post_id}/report", response_model=MessageResponse)
async def create_report(
    post_id: int,
    data: ReportCreateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    创建举报
    用户可以举报帖子
    """
    # 查询帖子
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # 检查是否已举报
    result = await db.execute(
        select(Report).where(
            Report.post_id == post_id,
            Report.reporter_id == current_user.id,
            Report.status == "pending"
        )
    )
    existing_report = result.scalar_one_or_none()
    if existing_report:
        raise BadRequestException(detail="您已举报过该帖子，请等待处理")

    # 创建举报
    report = Report(
        post_id=post_id,
        reporter_id=current_user.id,
        report_type=data.report_type,
        description=data.description,
        status="pending",
    )
    db.add(report)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestException(detail="操作失败，请重试")

    return MessageResponse(message="举报已提交，我们会尽快处理")


# ============================================================
# T-B-04: 协同验证统计接口
# ============================================================

@router.get(
    "/posts/{post_id}/validation-stats",
    response_model=ValidationStatsResponse,
    summary="获取协同验证统计（T-B-04）",
)
async def get_validation_stats(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取帖子的协同验证统计（5 类细分计数 + 旧 3 类兼容字段）

    返回字段：
    - 旧 3 类（兼容）：valid_count / invalid_count / uncertain_count
    - 新 5 类细分：confirmation_count / refutation_count / update_count /
                  expiration_report_count / conflict_report_count
    - total_count: 总验证数
    - validity_status: 综合有效性状态（valid/invalid/uncertain）
    """
    # 查询帖子
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.is_deleted == False)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # 按 validation_type 分组计数
    result = await db.execute(
        select(
            ValidationRecord.validation_type,
            func.count(ValidationRecord.id).label("cnt"),
        )
        .where(ValidationRecord.post_id == post_id)
        .group_by(ValidationRecord.validation_type)
    )
    counts_by_type = {row[0]: row[1] for row in result.all()}

    # 5 类正式计数
    confirmation_count = counts_by_type.get("confirmation", 0)
    refutation_count = counts_by_type.get("refutation", 0)
    update_count = counts_by_type.get("update", 0)
    expiration_report_count = counts_by_type.get("expiration_report", 0)
    conflict_report_count = counts_by_type.get("conflict_report", 0)

    # 旧 3 类兼容字段（数据库可能存有旧值 valid/invalid/uncertain，累加到对应新类）
    legacy_valid = counts_by_type.get("valid", 0)
    legacy_invalid = counts_by_type.get("invalid", 0)
    legacy_uncertain = counts_by_type.get("uncertain", 0)

    valid_count = confirmation_count + legacy_valid
    invalid_count = refutation_count + legacy_invalid
    uncertain_count = update_count + legacy_uncertain

    total = sum(counts_by_type.values())

    # 综合有效性状态：以 confirmation vs refutation 比例判定
    if valid_count > invalid_count:
        validity_status = "valid"
    elif invalid_count > valid_count:
        validity_status = "invalid"
    elif total > 0:
        validity_status = "uncertain"
    else:
        validity_status = "valid"

    return ValidationStatsResponse(
        post_id=post_id,
        valid_count=valid_count,
        invalid_count=invalid_count,
        uncertain_count=uncertain_count,
        confirmation_count=confirmation_count,
        refutation_count=refutation_count,
        update_count=update_count,
        expiration_report_count=expiration_report_count,
        conflict_report_count=conflict_report_count,
        total_count=total,
        validity_status=validity_status,
    )
