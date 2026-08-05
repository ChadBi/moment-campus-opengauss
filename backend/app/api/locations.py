from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from typing import Optional
from math import radians, sin, cos, asin, sqrt
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

router = APIRouter(tags=["地点"])


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 距离（米），用于「附近」排序（GCJ-02 坐标近似）。"""
    R = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lng2 - lng1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _location_response(location: Location, distance: Optional[float] = None) -> LocationResponse:
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
        distance=distance,
    )


def _review_response(review: LocationReview) -> LocationReviewResponse:
    author = None
    if review.user:
        # campus_verified 字段由工作流 B（校园认证）新增；此处防御性读取
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


@router.get("/locations/nearby", response_model=PaginatedResponse[LocationResponse], summary="附近地点")
async def nearby_locations(
    lat: float = Query(..., description="当前纬度"),
    lng: float = Query(..., description="当前经度"),
    radius: float = Query(default=5000, ge=0, description="半径（米），默认 5000"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """以当前位置为中心，按距离升序返回附近地点（含评分、距离）。"""
    condition = [Location.school_id == tenant.school_id, Location.is_deleted == False]
    query = select(Location).where(*condition)
    result = (await db.execute(query)).scalars().all()

    scored = []
    for loc in result:
        d = _haversine(lat, lng, float(loc.latitude), float(loc.longitude))
        if d <= radius:
            scored.append((d, loc))
    scored.sort(key=lambda x: x[0])
    total = len(scored)
    start = (page - 1) * page_size
    items = [_location_response(loc, distance=round(d, 0)) for d, loc in scored[start:start + page_size]]
    return PaginatedResponse.create(items=items, page=page, page_size=page_size, total=total)


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

    return LocationDetailResponse(location=_location_response(location), my_review=my_review)


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


@router.post("/locations/{location_id}/reviews", response_model=LocationReviewResponse, status_code=201, summary="提交/更新地点评价")
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
    await db.commit()

    # 返回最新评价（含作者）
    fresh = (await db.execute(
        select(LocationReview).options(joinedload(LocationReview.user))
        .where(LocationReview.id == review.id)
    )).scalar_one()
    return _review_response(fresh)


@router.delete("/locations/{location_id}/reviews", summary="撤回我的地点评价")
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
        await db.commit()

    return {"message": "撤回成功"}