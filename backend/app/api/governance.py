"""GOV-01.2: 协同治理 API

调整后：仅保留 2 类互斥投票（证实/证伪）
原 3 类问题报告（update/expiration_report/conflict_report）已移除（与评论/举报冲突）。

端点：
- POST   /api/v1/posts/{post_id}/validations      提交有效性投票（作者禁投；每用户每帖一条，第二次替换）
- GET    /api/v1/posts/{post_id}/validations      聚合投票统计（confirmation_count/refutation_count + 最近记录）
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.validation_record import ValidationRecord
from app.schemas.governance import (
    ValidationVoteCreate,
    ValidationVoteResponse,
    ValidationAggregation,
)
from app.schemas.post import UserBrief
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.validation_type import normalize_validation_type, ValidationType

router = APIRouter(tags=["协同治理"])


# ============================================================
# 2 类互斥投票（validation_records: confirmation/refutation）
# ============================================================

@router.post(
    "/posts/{post_id}/validations",
    response_model=ValidationVoteResponse,
    summary="提交有效性投票（GOV-01.2）",
)
async def create_validation_vote(
    post_id: int,
    data: ValidationVoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """提交有效性投票（confirmation/refutation，2 类互斥）

    规则：
    - 禁止作者给自己的帖子投票（403）
    - 每用户每帖一条（唯一约束）；第二次提交"替换"原记录（更新类型/备注）
    - 向后兼容旧值：valid→confirmation / invalid→refutation

    TEN-02.3：跨校帖子统一返回 404。
    """
    # 查询帖子
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")
    check_resource_in_tenant(post.school_id, tenant)

    # GOV-01.2: 禁止作者给自己投票
    if post.user_id == current_user.id:
        raise ForbiddenException(detail="不能为自己的帖子投票")

    # 归一化类型（valid→confirmation / invalid→refutation）
    canonical_type = normalize_validation_type(data.validation_type)
    # 仅允许 2 类投票类型（schema 已限制，二次防御）
    if canonical_type not in ValidationType.ALL:
        raise BadRequestException(
            detail="投票类型仅支持 confirmation/refutation"
        )

    # 查询当前用户对此帖的已有投票
    result = await db.execute(
        select(ValidationRecord).where(
            ValidationRecord.post_id == post_id,
            ValidationRecord.user_id == current_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        # 替换语义：更新已有记录的类型/备注（保留 id）
        old_type = existing.validation_type
        if old_type in ValidationType.LEGACY_POSITIVE_COUNT_TYPES:
            post.valid_count = max(0, post.valid_count - 1)
        elif old_type in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES:
            post.invalid_count = max(0, post.invalid_count - 1)

        existing.validation_type = canonical_type
        existing.comment = data.comment

        if canonical_type in ValidationType.LEGACY_POSITIVE_COUNT_TYPES:
            post.valid_count += 1
        elif canonical_type in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES:
            post.invalid_count += 1

        record = existing
    else:
        # 新建投票
        record = ValidationRecord(
            post_id=post_id,
            user_id=current_user.id,
            validation_type=canonical_type,
            comment=data.comment,
        )
        db.add(record)
        if canonical_type in ValidationType.LEGACY_POSITIVE_COUNT_TYPES:
            post.valid_count += 1
        elif canonical_type in ValidationType.LEGACY_NEGATIVE_COUNT_TYPES:
            post.invalid_count += 1

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestException(detail="投票失败，请重试")

    await db.refresh(record)
    return ValidationVoteResponse(
        id=record.id,
        post_id=record.post_id,
        user_id=record.user_id,
        validation_type=record.validation_type,
        comment=record.comment,
        created_at=record.created_at,
        user=UserBrief(id=current_user.id, nickname=current_user.nickname, avatar_url=current_user.avatar_url),
    )


@router.get(
    "/posts/{post_id}/validations",
    response_model=ValidationAggregation,
    summary="聚合投票统计（GOV-01.2）",
)
async def get_validation_aggregation(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """聚合投票统计：confirmation_count/refutation_count + 最近记录 + 当前用户投票类型

    TEN-02.3：跨校帖子统一返回 404。
    """
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")
    check_resource_in_tenant(post.school_id, tenant)

    # 按类型分组计数
    result = await db.execute(
        select(
            ValidationRecord.validation_type,
            func.count(ValidationRecord.id).label("cnt"),
        )
        .where(ValidationRecord.post_id == post_id)
        .group_by(ValidationRecord.validation_type)
    )
    counts_by_type = {row[0]: row[1] for row in result.all()}

    confirmation_count = counts_by_type.get("confirmation", 0) + counts_by_type.get("valid", 0)
    refutation_count = counts_by_type.get("refutation", 0) + counts_by_type.get("invalid", 0)
    total = confirmation_count + refutation_count

    if confirmation_count > refutation_count:
        validity_status = "valid"
    elif refutation_count > confirmation_count:
        validity_status = "invalid"
    elif total > 0:
        validity_status = "uncertain"
    else:
        validity_status = "valid"

    # 当前用户投票类型
    user_validation_type = None
    result = await db.execute(
        select(ValidationRecord.validation_type).where(
            ValidationRecord.post_id == post_id,
            ValidationRecord.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        user_validation_type = normalize_validation_type(row)

    # 最近 10 条记录（含用户信息）
    result = await db.execute(
        select(ValidationRecord)
        .where(ValidationRecord.post_id == post_id)
        .order_by(ValidationRecord.created_at.desc())
        .limit(10)
        .options(selectinload(ValidationRecord.user))
    )
    records = result.scalars().all()
    recent = [
        ValidationVoteResponse(
            id=r.id,
            post_id=r.post_id,
            user_id=r.user_id,
            validation_type=r.validation_type,
            comment=r.comment,
            created_at=r.created_at,
            user=UserBrief(id=r.user.id, nickname=r.user.nickname, avatar_url=r.user.avatar_url)
            if r.user else None,
        )
        for r in records
    ]

    return ValidationAggregation(
        post_id=post_id,
        confirmation_count=confirmation_count,
        refutation_count=refutation_count,
        total_count=total,
        validity_status=validity_status,
        user_validation_type=user_validation_type,
        recent_records=recent,
    )
