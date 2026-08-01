from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.post import Post
from app.models.post_image import PostImage
from app.models.location import Location
from app.core.tenant import TenantContext, get_tenant_context

router = APIRouter(tags=["地图"])


class MapMarker(BaseModel):
    """地图标记"""
    id: int = Field(..., description="帖子ID")
    post_id: int = Field(..., description="帖子ID")
    title: str = Field(..., description="标题")
    content_snippet: Optional[str] = Field(None, description="内容摘要")
    latitude: float = Field(..., description="GCJ-02 纬度")
    longitude: float = Field(..., description="GCJ-02 经度")
    location_name: str = Field(..., description="地点名称")
    category_id: int = Field(..., description="分类ID")
    category_name: Optional[str] = Field(None, description="分类名称")
    category_code: Optional[str] = Field(None, description="分类代码")
    status: str = Field(..., description="帖子状态")
    cover_image: Optional[str] = Field(None, description="封面图片")


class MapMarkersResponse(BaseModel):
    """地图标记响应"""
    markers: List[MapMarker]


@router.get("/map/markers", response_model=MapMarkersResponse)
async def get_map_markers(
    north: Optional[float] = Query(None, description="GCJ-02 边界北纬度"),
    south: Optional[float] = Query(None, description="GCJ-02 边界南纬度"),
    east: Optional[float] = Query(None, description="GCJ-02 边界东经度"),
    west: Optional[float] = Query(None, description="GCJ-02 边界西经度"),
    category_id: Optional[int] = Query(None, description="分类ID"),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    获取地图标记
    根据经纬度边界返回标记，最多100个

    DSC-01.2: 预加载 post_images 关联，消除每帖单独查询封面图的 N+1。
    TEN-02.3：按当前学校过滤，跨校标记不会出现
    """
    # 查询边界内的地点（TEN-02.3: 强制按当前学校过滤）
    # DSC-01.2: 使用 selectinload 预加载 PostImage，避免每帖单独查封面图
    conditions = [
        Location.is_deleted == False,
        Post.is_deleted == False,
        Post.status == "published",
        Post.school_id == tenant.school_id,
        Location.school_id == tenant.school_id,
    ]

    # 边界参数可选：全部提供时按边界过滤，否则返回学校内所有标记
    if all(v is not None for v in [north, south, east, west]):
        conditions.extend([
            Location.latitude <= north,
            Location.latitude >= south,
            Location.longitude <= east,
            Location.longitude >= west,
        ])

    query = (
        select(Location, Post)
        .join(Post, Post.location_id == Location.id)
        .where(*conditions)
        .options(
            selectinload(Post.post_images),
            joinedload(Post.category),
        )
        .limit(100)
    )

    if category_id:
        query = query.where(Post.category_id == category_id)

    result = await db.execute(query)
    rows = result.unique().all()

    markers = []
    for location, post in rows:
        # DSC-01.2: 从预加载的 post_images 中取第一张作为封面（按 sort_order 排序）
        # post_images 已通过 selectinload 一次性加载，无额外查询
        cover_image = None
        if post.post_images:
            # selectinload 默认按主键顺序返回，取 sort_order 最小的
            sorted_images = sorted(
                [img for img in post.post_images if not img.is_deleted],
                key=lambda x: x.sort_order,
            )
            if sorted_images:
                cover_image = sorted_images[0].image_url

        category_name = post.category.name if post.category else None
        category_code = post.category.code if post.category else None

        markers.append(MapMarker(
            id=post.id,
            post_id=post.id,
            title=post.title,
            content_snippet=post.content[:100] if post.content else None,
            latitude=float(location.latitude),
            longitude=float(location.longitude),
            location_name=location.name,
            category_id=post.category_id,
            category_name=category_name,
            category_code=category_code,
            status=post.status,
            cover_image=cover_image,
        ))

    return MapMarkersResponse(markers=markers)
