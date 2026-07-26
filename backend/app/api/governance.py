"""GOV-01.2: 协同治理 API

5 类协同验证 = 2 类互斥投票(validation_records: confirmation/refutation)
            + 3 类问题报告(post_change_reports: update/expiration_report/conflict_report)

端点：
- POST   /api/v1/posts/{post_id}/validations      提交有效性投票（作者禁投；每用户每帖一条，第二次替换）
- GET    /api/v1/posts/{post_id}/validations      聚合投票统计（confirmation_count/refutation_count + 最近记录）
- POST   /api/v1/posts/{post_id}/change-reports   提交问题报告（3 类，含 description/evidence）
- GET    /api/v1/posts/{post_id}/change-reports   报告列表（含处理状态）
- PUT    /api/v1/governance/reports/{report_id}   管理员处理报告 / 作者标记已处理（require_role admin 或作者）
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.validation_record import ValidationRecord
from app.models.post_change_report import PostChangeReport
from app.schemas.governance import (
    ValidationVoteCreate,
    ValidationVoteResponse,
    ValidationAggregation,
    ChangeReportCreate,
    ChangeReportResponse,
    ChangeReportListResponse,
    ChangeReportHandleRequest,
)
from app.schemas.post import UserBrief
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    ForbiddenException,
)
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.permissions import is_admin
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
    - update/expiration_report/conflict_report 请使用 /change-reports 端点（schema 层已拦截）
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
            detail="投票类型仅支持 confirmation/refutation；"
            "update/expiration_report/conflict_report 请使用 /change-reports 端点"
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


# ============================================================
# 3 类问题报告（post_change_reports: update/expiration_report/conflict_report）
# ============================================================

@router.post(
    "/posts/{post_id}/change-reports",
    response_model=ChangeReportResponse,
    status_code=201,
    summary="提交问题报告（GOV-01.2）",
)
async def create_change_report(
    post_id: int,
    data: ChangeReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """提交问题报告（update/expiration_report/conflict_report，3 类）

    - 含 description（说明）+ evidence_url（证据）
    - 同一用户对同一帖子同一类型若已有 open/in_review 报告，拒绝重复提交（400）
    - 作者本人也可提交报告（自报告更新/过期/冲突，用于主动标注）

    TEN-02.3：跨校帖子统一返回 404。
    """
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")
    check_resource_in_tenant(post.school_id, tenant)

    # 重复报告限制：同一用户对同一帖子同一类型，存在未结案报告时拒绝
    result = await db.execute(
        select(PostChangeReport).where(
            PostChangeReport.post_id == post_id,
            PostChangeReport.reporter_id == current_user.id,
            PostChangeReport.report_type == data.report_type,
            PostChangeReport.status.in_(["open", "in_review"]),
        )
    )
    if result.scalar_one_or_none() is not None:
        raise BadRequestException(detail="您已提交过该类型的报告，请等待处理")

    report = PostChangeReport(
        post_id=post_id,
        reporter_id=current_user.id,
        report_type=data.report_type,
        description=data.description,
        evidence_url=data.evidence_url,
        status="open",
    )
    db.add(report)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestException(detail="提交报告失败，请重试")

    await db.refresh(report)
    return ChangeReportResponse(
        id=report.id,
        post_id=report.post_id,
        reporter_id=report.reporter_id,
        report_type=report.report_type,
        description=report.description,
        evidence_url=report.evidence_url,
        status=report.status,
        handler_id=report.handler_id,
        handler_note=report.handler_note,
        handled_at=report.handled_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        reporter=UserBrief(id=current_user.id, nickname=current_user.nickname, avatar_url=current_user.avatar_url),
        handler=None,
    )


@router.get(
    "/posts/{post_id}/change-reports",
    response_model=ChangeReportListResponse,
    summary="问题报告列表（GOV-01.2）",
)
async def list_change_reports(
    post_id: int,
    status_filter: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取帖子的问题报告列表（含处理状态）

    TEN-02.3：跨校帖子统一返回 404。
    """
    result = await db.execute(select(Post).where(Post.id == post_id, Post.is_deleted == False))
    post = result.scalar_one_or_none()
    if not post:
        raise NotFoundException(detail="帖子不存在")
    check_resource_in_tenant(post.school_id, tenant)

    query = (
        select(PostChangeReport)
        .where(PostChangeReport.post_id == post_id)
        .order_by(PostChangeReport.created_at.desc())
        .options(selectinload(PostChangeReport.reporter), selectinload(PostChangeReport.handler))
    )
    if status_filter:
        query = query.where(PostChangeReport.status == status_filter)

    result = await db.execute(query)
    reports = result.scalars().all()

    items = [
        ChangeReportResponse(
            id=r.id,
            post_id=r.post_id,
            reporter_id=r.reporter_id,
            report_type=r.report_type,
            description=r.description,
            evidence_url=r.evidence_url,
            status=r.status,
            handler_id=r.handler_id,
            handler_note=r.handler_note,
            handled_at=r.handled_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
            reporter=UserBrief(id=r.reporter.id, nickname=r.reporter.nickname, avatar_url=r.reporter.avatar_url)
            if r.reporter else None,
            handler=UserBrief(id=r.handler.id, nickname=r.handler.nickname, avatar_url=r.handler.avatar_url)
            if r.handler else None,
        )
        for r in reports
    ]

    open_count = sum(1 for r in reports if r.status in ("open", "in_review"))

    return ChangeReportListResponse(
        post_id=post_id,
        items=items,
        total=len(items),
        open_count=open_count,
    )


# ============================================================
# 管理员处理报告 / 作者响应报告
# ============================================================

@router.put(
    "/governance/reports/{report_id}",
    response_model=ChangeReportResponse,
    summary="处理问题报告（GOV-01.2 管理员/作者）",
)
async def handle_change_report(
    report_id: int,
    data: ChangeReportHandleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """处理问题报告（状态/处理人/原因）

    权限：
    - 管理员（admin/super_admin）：可流转至任意状态 open/in_review/resolved/dismissed
    - 帖子作者：仅可标记为 resolved（标记已更新/已处理）；其它状态返回 403
    - 其他用户：403

    作者响应 update/过期/冲突报告：标记已处理（resolved），handler_id 记为作者本人。

    TEN-02.3：跨校报告统一返回 404。
    """
    result = await db.execute(
        select(PostChangeReport)
        .where(PostChangeReport.id == report_id)
        .options(selectinload(PostChangeReport.reporter), selectinload(PostChangeReport.handler))
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise NotFoundException(detail="报告不存在")

    # 加载关联帖子用于租户 + 作者校验
    post_result = await db.execute(select(Post).where(Post.id == report.post_id))
    post = post_result.scalar_one_or_none()
    if post is None:
        raise NotFoundException(detail="帖子不存在")
    check_resource_in_tenant(post.school_id, tenant)

    is_admin_user = is_admin(current_user)
    is_author = post.user_id == current_user.id

    if not is_admin_user and not is_author:
        raise ForbiddenException(detail="没有权限处理该报告")

    target_status = data.status
    # 状态合法性由 schema pattern 保证（open/in_review/resolved/dismissed）

    if is_admin_user:
        # 管理员：允许全部状态流转
        allowed = {"open", "in_review", "resolved", "dismissed"}
    else:
        # 作者：仅允许标记为 resolved（已处理/已更新）
        allowed = {"resolved"}
    if target_status not in allowed:
        raise ForbiddenException(
            detail=f"无权限流转到 {target_status} 状态"
            + ("（作者仅可标记为 resolved）" if not is_admin_user else "")
        )

    report.status = target_status
    report.handler_id = current_user.id
    report.handler_note = data.reason
    if target_status in ("resolved", "dismissed"):
        report.handled_at = datetime.now()
    else:
        report.handled_at = None
    report.updated_at = datetime.now()

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BadRequestException(detail="处理报告失败，请重试")

    await db.refresh(report)
    return ChangeReportResponse(
        id=report.id,
        post_id=report.post_id,
        reporter_id=report.reporter_id,
        report_type=report.report_type,
        description=report.description,
        evidence_url=report.evidence_url,
        status=report.status,
        handler_id=report.handler_id,
        handler_note=report.handler_note,
        handled_at=report.handled_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        reporter=UserBrief(id=report.reporter.id, nickname=report.reporter.nickname, avatar_url=report.reporter.avatar_url)
        if report.reporter else None,
        handler=UserBrief(id=current_user.id, nickname=current_user.nickname, avatar_url=current_user.avatar_url),
    )
