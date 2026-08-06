from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.models.location import Location
from app.models.location_review import LocationReview
from app.models.user import User
from app.schemas.location_review import (
    LocationResponse,
    LocationReviewCreate,
    LocationReviewResponse,
    LocationDetailResponse,
)
from app.schemas.common import PaginatedResponse
from app.schemas.post import UserBrief
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.permissions import require_campus_verified
from app.services.location_summary import (
    load_current_summary,
    load_location_facts,
    load_summary_sources,
    summary_response,
    mark_location_summary_dirty,
)

router = APIRouter(tags=["地点"])


def _location_response(location: Location) -> LocationResponse:
    return LocationResponse(
        id=location.id,
        school_id=location.school_id,
        name=location.name,
        description=location.description,
        latitude=float(location.latitude),
        longitude=float(location.longitude),
        floor=location.floor,
        building=location.building,
        post_count=location.post_count,
        is_verified=location.is_verified,
        avg_score=float(location.avg_score or 0),
        rating_count=location.rating_count,
        review_count=location.review_count,
    )


def _review_response(review: LocationReview) -> LocationReviewResponse:
    author = None
    if review.user:
        # campus_verified 字段由工作流 B（校园认证）新增；此处防御性读取
        if review.is_anonymous:
            # UC-01: 用户离校后评价匿名化——作者显示「已离校用户」，移除认证徽标
            author = UserBrief(
                id=review.user.id,
                nickname="已离校用户",
                avatar_url=None,
                is_verified=False,
            )
        else:
            author = UserBrief(
                id=review.user.id,
                nickname=review.user.nickname,
                avatar_url=review.user.avatar_url,
                is_verified=bool(getattr(review.user, "campus_verified", False)),
            )
    return LocationReviewResponse(
        id=review.id,
        location_id=review.location_id,
        user_id=review.user_id,
        score=review.score,
        content=review.content,
        created_at=review.created_at,
        updated_at=review.updated_at,
        author=author,
    )


async def _recalc_location_rating(db: AsyncSession, location: Location) -> None:
    """REV-01: 重算地点评分汇总（应用服务为唯一写入口，不引入触发器）。"""
    row = (
        await db.execute(
            select(
                func.count(LocationReview.id),
                func.coalesce(func.avg(LocationReview.score), 0),
            ).where(
                LocationReview.location_id == location.id,
                LocationReview.is_deleted == False,
            )
        )
    ).one()
    count, avg = row
    location.review_count = int(count)
    location.rating_count = int(count)
    location.avg_score = round(float(avg), 2)


@router.get("/locations/{location_id}", response_model=LocationDetailResponse, summary="地点详情")
async def get_location(
    location_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """地点详情（含评分汇总 + 我的评价）。跨校返回 404。"""
    result = await db.execute(
        select(Location).where(Location.id == location_id, Location.is_deleted == False)
    )
    location = result.scalar_one_or_none()
    if location is None:
        raise NotFoundException(detail="地点不存在")
    check_resource_in_tenant(location.school_id, tenant)

    my_review = None
    if current_user is not None:
        rr = await db.execute(
            select(LocationReview).options(joinedload(LocationReview.user)).where(
                LocationReview.location_id == location_id,
                LocationReview.user_id == current_user.id,
                LocationReview.is_deleted == False,
            )
        )
        review = rr.scalar_one_or_none()
        if review is not None:
            my_review = _review_response(review)

    facts = await load_location_facts(db, location.id, tenant.school_id)
    current_summary = await load_current_summary(db, location)
    sources = await load_summary_sources(db, current_summary, tenant) if current_summary else []
    return LocationDetailResponse(
        location=_location_response(location),
        my_review=my_review,
        facts=facts,
        summary=summary_response(current_summary, sources),
    )


@router.get("/locations/{location_id}/reviews", response_model=PaginatedResponse[LocationReviewResponse], summary="地点评价列表")
async def list_location_reviews(
    location_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    # 校验地点存在且属于当前学校
    lr = await db.execute(
        select(Location).where(Location.id == location_id, Location.is_deleted == False)
    )
    location = lr.scalar_one_or_none()
    if location is None:
        raise NotFoundException(detail="地点不存在")
    check_resource_in_tenant(location.school_id, tenant)

    base = select(LocationReview).where(
        LocationReview.location_id == location_id,
        LocationReview.is_deleted == False,
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    query = (
        base.options(joinedload(LocationReview.user))
        .order_by(LocationReview.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    reviews = (await db.execute(query)).scalars().all()
    items = [_review_response(r) for r in reviews]
    return PaginatedResponse.create(items=items, page=page, page_size=page_size, total=total)


@router.post("/locations/{location_id}/reviews", response_model=LocationReviewResponse, status_code=201, summary="提交/更新地点评价",
             dependencies=[Depends(require_campus_verified())])
async def upsert_location_review(
    location_id: int,
    data: LocationReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """提交本人评价（每地点每用户一条，重复提交=更新）。"""
    lr = await db.execute(
        select(Location).where(Location.id == location_id, Location.is_deleted == False)
    )
    location = lr.scalar_one_or_none()
    if location is None:
        raise NotFoundException(detail="地点不存在")
    check_resource_in_tenant(location.school_id, tenant)

    # 已有评价则更新，否则新增
    rr = await db.execute(
        select(LocationReview).where(
            LocationReview.location_id == location_id,
            LocationReview.user_id == current_user.id,
            LocationReview.is_deleted == False,
        )
    )
    review = rr.scalar_one_or_none()
    if review is None:
        review = LocationReview(
            location_id=location_id,
            user_id=current_user.id,
            school_id=tenant.school_id,
            score=data.score,
            content=data.content,
            status="published",
        )
        db.add(review)
    else:
        review.score = data.score
        review.content = data.content

    await db.flush()
    await _recalc_location_rating(db, location)
    await mark_location_summary_dirty(db, location.id)
    await db.commit()

    # 返回最新评价（含作者）
    fresh = (await db.execute(
        select(LocationReview).options(joinedload(LocationReview.user))
        .where(LocationReview.id == review.id)
    )).scalar_one()
    return _review_response(fresh)


@router.delete("/locations/{location_id}/reviews", summary="撤回我的地点评价",
               dependencies=[Depends(require_campus_verified())])
async def delete_location_review(
    location_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """撤回本人评价并重算评分。"""
    lr = await db.execute(
        select(Location).where(Location.id == location_id, Location.is_deleted == False)
    )
    location = lr.scalar_one_or_none()
    if location is None:
        raise NotFoundException(detail="地点不存在")
    check_resource_in_tenant(location.school_id, tenant)

    rr = await db.execute(
        select(LocationReview).where(
            LocationReview.location_id == location_id,
            LocationReview.user_id == current_user.id,
            LocationReview.is_deleted == False,
        )
    )
    review = rr.scalar_one_or_none()
    if review is not None:
        review.is_deleted = True
        review.deleted_at = datetime.now()
        await db.flush()
        await _recalc_location_rating(db, location)
        await mark_location_summary_dirty(db, location.id)
        await db.commit()

    return {"message": "撤回成功"}
