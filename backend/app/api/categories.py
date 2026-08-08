from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.category import Category
from app.models.location import Location
from app.models.school import School
from app.core.tenant import TenantContext, get_tenant_context, check_resource_in_tenant
from app.core.exceptions import NotFoundException
from app.core.permissions import require_campus_verified_or_admin

router = APIRouter(tags=["分类"])


class CategoryResponse(BaseModel):
    """分类响应"""
    id: int = Field(..., description="分类ID")
    name: str = Field(..., description="分类名称")
    code: str = Field(..., description="分类代码")
    icon: str = Field(..., description="图标")
    description: Optional[str] = Field(None, description="描述")
    sort_order: int = Field(..., description="排序")


class LocationResponse(BaseModel):
    """地点响应（含评分汇总，供地图/地点页展示）"""
    id: int = Field(..., description="地点ID")
    name: str = Field(..., description="地点名称")
    latitude: float = Field(..., description="GCJ-02 纬度")
    longitude: float = Field(..., description="GCJ-02 经度")
    description: Optional[str] = Field(None, description="描述")
    building: Optional[str] = Field(None, description="建筑物")
    floor: Optional[str] = Field(None, description="楼层")
    is_verified: bool = Field(..., description="是否已核验")
    # 评分汇总（REV-01 冗余列，由 _recalc_location_rating 维护）
    avg_score: float = Field(default=0, description="平均评分（1-5，保留 2 位）")
    rating_count: int = Field(default=0, description="评分人数")
    review_count: int = Field(default=0, description="评价条数")
    post_count: int = Field(default=0, description="相关帖子数")


class LocationCreate(BaseModel):
    """创建地点（TEN-02.1: school_id 字段被忽略，强制使用 TenantContext 解析的学校）"""
    name: str = Field(..., min_length=1, max_length=100, description="地点名称")
    latitude: float = Field(..., description="GCJ-02 纬度")
    longitude: float = Field(..., description="GCJ-02 经度")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    building: Optional[str] = Field(None, max_length=100, description="建筑物")
    floor: Optional[str] = Field(None, max_length=10, description="楼层")
    school_id: Optional[int] = Field(None, description="学校ID（已废弃，由租户上下文决定）")


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    获取分类列表
    返回当前学校所有启用的分类，按排序字段排序

    TEN-02.3：按当前学校过滤，跨校分类不会出现

    Task 1.2 调整：分类已重构为统一「信息分类」5 类
    （share/teamup/trade/lost_found/other）
    """
    query = (
        select(Category)
        .where(
            Category.is_active == True,
            Category.school_id == tenant.school_id,
        )
        .order_by(Category.sort_order, Category.id)
    )
    result = await db.execute(query)
    categories = result.scalars().all()

    return [
        CategoryResponse(
            id=cat.id,
            name=cat.name,
            code=cat.code,
            icon=cat.icon,
            description=cat.description,
            sort_order=cat.sort_order,
        )
        for cat in categories
    ]


@router.get("/locations", response_model=List[LocationResponse])
async def get_locations(
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    获取地点列表

    TEN-02.3：按当前学校过滤，跨校地点不会出现
    PUB-01.2：返回 is_verified 字段，前端用于区分已核验地点与用户自建地点
    """
    query = (
        select(Location)
        .where(
            Location.is_deleted == False,
            Location.school_id == tenant.school_id,
        )
        .order_by(Location.name)
    )

    result = await db.execute(query)
    locations = result.scalars().all()

    return [
        LocationResponse(
            id=loc.id,
            name=loc.name,
            latitude=float(loc.latitude),
            longitude=float(loc.longitude),
            description=loc.description,
            building=loc.building,
            floor=loc.floor,
            is_verified=loc.is_verified,
            avg_score=float(loc.avg_score or 0),
            rating_count=loc.rating_count,
            review_count=loc.review_count,
            post_count=loc.post_count,
        )
        for loc in locations
    ]


@router.post("/locations", response_model=LocationResponse)
async def create_location(
    data: LocationCreate,
    current_user: User = Depends(require_campus_verified_or_admin()),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    创建地点
    需要用户认证

    TEN-02.1: 忽略 body 里的 school_id，强制使用 TenantContext 解析的学校
    """
    # TEN-02.1: 强制使用 tenant.school_id（忽略 body 里的 school_id 字段）
    location = Location(
        school_id=tenant.school_id,
        name=data.name,
        latitude=data.latitude,
        longitude=data.longitude,
        description=data.description,
        building=data.building,
        floor=data.floor,
        is_verified=False,
    )
    db.add(location)
    await db.commit()
    await db.refresh(location)

    return LocationResponse(
        id=location.id,
        name=location.name,
        latitude=float(location.latitude),
        longitude=float(location.longitude),
        description=location.description,
        building=location.building,
        floor=location.floor,
        is_verified=location.is_verified,
    )


# 注：/templates 接口已随发布主体功能移除（post_templates 表已 drop），
# 前端 PostForm 的「发布模板」UI 已同步删除。

