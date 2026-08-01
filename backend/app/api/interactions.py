from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.like import Like
from app.models.validation_record import ValidationRecord
from app.models.report import Report
from app.models.notification import Notification
from app.schemas.interaction import (
    LikeResponse,
    ValidationCreate,
    ValidationResponse,
    ValidationStatsResponse,
    ReportCreate,
)
from app.schemas.common import MessageResponse
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.validation_type import (
    normalize_validation_type,
    ValidationType,
)

router = APIRouter(tags=["互动"])


@router.post("/posts/{post_id}/like", response_model=LikeResponse)
async def toggle_like(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    点赞/取消点赞（切换）
    如果已点赞则取消点赞，如果未点赞则点赞

    TEN-02.3：跨校帖子统一返回 404。
    """
    # 查询帖子
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

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


@router.post("/posts/{post_id}/validate", response_model=ValidationResponse)
async def create_validation(
    post_id: int,
    data: ValidationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    协同验证（2 类互斥可切换）

    每用户对每帖只能有一条验证记录，规则：
    - 无记录 → 新建（confirmation 或 refutation）
    - 已有同类型记录 → 删除（取消）
    - 已有不同类型记录 → 删除原记录，新建新类型（切换）

    TEN-02.3：跨校帖子统一返回 404。
    """
    # 查询帖子
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

    if post.user_id == current_user.id:
        raise ForbiddenException(detail="不能为自己的帖子投票")

    canonical_type = normalize_validation_type(data.validation_type.value)

    # 查询当前用户对此帖的已有验证记录（任意类型）
    result = await db.execute(
        select(ValidationRecord).where(
            ValidationRecord.post_id == post_id,
            ValidationRecord.user_id == current_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.validation_type == canonical_type:
            # 同类型 → 取消（删除记录）
            await db.delete(existing)
            if canonical_type == ValidationType.CONFIRMATION:
                post.valid_count = max(0, post.valid_count - 1)
            else:
                post.invalid_count = max(0, post.invalid_count - 1)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise BadRequestException(detail="操作失败，请重试")
            return ValidationResponse(
                post_id=post_id,
                user_id=current_user.id,
                action="removed",
                current_validation_type=None,
                confirmation_count=post.valid_count,
                refutation_count=post.invalid_count,
            )
        else:
            if existing.validation_type == ValidationType.CONFIRMATION:
                post.valid_count = max(0, post.valid_count - 1)
            else:
                post.invalid_count = max(0, post.invalid_count - 1)
            existing.validation_type = canonical_type
            existing.comment = data.comment
            if canonical_type == ValidationType.CONFIRMATION:
                post.valid_count += 1
            else:
                post.invalid_count += 1
            await db.commit()
            await db.refresh(existing)
            return ValidationResponse(
                id=existing.id,
                post_id=existing.post_id,
                user_id=existing.user_id,
                validation_type=existing.validation_type,
                comment=existing.comment,
                created_at=existing.created_at,
                action="switched",
                current_validation_type=existing.validation_type,
                confirmation_count=post.valid_count,
                refutation_count=post.invalid_count,
            )

    # 新建记录（首次验证 或 切换后新建）
    validation = ValidationRecord(
        post_id=post_id,
        user_id=current_user.id,
        validation_type=canonical_type,
        comment=data.comment,
    )
    db.add(validation)

    # 更新 Post 旧统计字段
    if canonical_type == ValidationType.CONFIRMATION:
        post.valid_count += 1
    else:
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
        action="created",
        current_validation_type=validation.validation_type,
        confirmation_count=post.valid_count,
        refutation_count=post.invalid_count,
    )


@router.post("/posts/{post_id}/report", response_model=MessageResponse)
async def create_report(
    post_id: int,
    data: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    创建举报
    用户可以举报帖子

    TEN-02.3：跨校帖子统一返回 404。
    """
    # 查询帖子
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

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

    # 创建举报（report_type 为 ReportType 枚举，取其字符串值存入数据库）
    report = Report(
        post_id=post_id,
        reporter_id=current_user.id,
        report_type=data.report_type.value,
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
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取帖子的协同验证统计（2 类计数 + 当前用户验证类型）

    返回字段：
    - 旧 2 类（兼容）：valid_count / invalid_count
    - 2 类细分：confirmation_count / refutation_count
    - total_count: 总验证数（仅计入 confirmation + refutation + 旧别名）
    - validity_status: 综合有效性状态（valid/invalid/uncertain）
    - user_validation_type: 当前用户对此帖的验证类型（confirmation/refutation/None）

    TEN-02.3：跨校帖子统一返回 404。
    """
    # 查询帖子
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.is_deleted == False)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")

    # TEN-02.3: 资源级租户校验——跨校对象统一 404
    check_resource_in_tenant(post.school_id, tenant)

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

    # 2 类正式计数
    confirmation_count = counts_by_type.get("confirmation", 0)
    refutation_count = counts_by_type.get("refutation", 0)

    valid_count = confirmation_count
    invalid_count = refutation_count
    total = valid_count + invalid_count

    # 综合有效性状态：以 confirmation vs refutation 比例判定
    if valid_count > invalid_count:
        validity_status = "valid"
    elif invalid_count > valid_count:
        validity_status = "invalid"
    elif total > 0:
        validity_status = "uncertain"
    else:
        validity_status = "valid"

    # 查询当前用户对此帖的验证类型
    user_validation_type = None
    result = await db.execute(
        select(ValidationRecord.validation_type).where(
            ValidationRecord.post_id == post_id,
            ValidationRecord.user_id == current_user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        # 归一化为正式名（处理旧别名）
        user_validation_type = normalize_validation_type(row)

    return ValidationStatsResponse(
        post_id=post_id,
        valid_count=valid_count,
        invalid_count=invalid_count,
        confirmation_count=confirmation_count,
        refutation_count=refutation_count,
        total_count=total,
        validity_status=validity_status,
        user_validation_type=user_validation_type,
    )
