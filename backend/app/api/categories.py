from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.category import Category
from app.models.location import Location
from app.models.school import School

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
    """地点响应"""
    id: int = Field(..., description="地点ID")
    name: str = Field(..., description="地点名称")
    latitude: float = Field(..., description="纬度")
    longitude: float = Field(..., description="经度")
    description: Optional[str] = Field(None, description="描述")
    building: Optional[str] = Field(None, description="建筑物")
    floor: Optional[str] = Field(None, description="楼层")


class LocationCreate(BaseModel):
    """创建地点"""
    name: str = Field(..., min_length=1, max_length=100, description="地点名称")
    latitude: float = Field(..., description="纬度")
    longitude: float = Field(..., description="经度")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    building: Optional[str] = Field(None, max_length=100, description="建筑物")
    floor: Optional[str] = Field(None, max_length=10, description="楼层")
    school_id: int = Field(..., description="学校ID")


@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(
    db: AsyncSession = Depends(get_db),
):
    """
    获取分类列表
    返回所有启用的分类，按排序字段排序
    """
    query = (
        select(Category)
        .where(Category.is_active == True)
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
    school_id: Optional[int] = Query(None, description="学校ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取地点列表
    支持按学校筛选
    """
    query = select(Location).where(Location.is_deleted == False)

    if school_id:
        query = query.where(Location.school_id == school_id)

    query = query.order_by(Location.name)

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
        )
        for loc in locations
    ]


@router.post("/locations", response_model=LocationResponse)
async def create_location(
    data: LocationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    创建地点
    需要用户认证
    """
    # 验证学校是否存在
    school_query = select(School).where(School.id == data.school_id, School.is_active == True)
    school_result = await db.execute(school_query)
    school = school_result.scalar_one_or_none()
    if not school:
        from app.core.exceptions import NotFoundException
        raise NotFoundException(detail="学校不存在")

    # 创建地点
    location = Location(
        school_id=data.school_id,
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
    )
