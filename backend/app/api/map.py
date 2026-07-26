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
    post_id: int = Field(..., description="帖子ID")
    title: str = Field(..., description="标题")
    latitude: float = Field(..., description="纬度")
    longitude: float = Field(..., description="经度")
    location_name: str = Field(..., description="地点名称")
    category_id: int = Field(..., description="分类ID")
    cover_image: Optional[str] = Field(None, description="封面图片")


@router.get("/map/markers", response_model=List[MapMarker])
async def get_map_markers(
    north: float = Query(..., description="边界北纬度"),
    south: float = Query(..., description="边界南纬度"),
    east: float = Query(..., description="边界东经度"),
    west: float = Query(..., description="边界西经度"),
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
    query = (
        select(Location, Post)
        .join(Post, Post.location_id == Location.id)
        .where(
            Location.is_deleted == False,
            Post.is_deleted == False,
            Post.status == "published",
            Post.school_id == tenant.school_id,
            Location.school_id == tenant.school_id,
            Location.latitude <= north,
            Location.latitude >= south,
            Location.longitude <= east,
            Location.longitude >= west,
        )
        .options(selectinload(Post.post_images))
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

        markers.append(MapMarker(
            post_id=post.id,
            title=post.title,
            latitude=float(location.latitude),
            longitude=float(location.longitude),
            location_name=location.name,
            category_id=post.category_id,
            cover_image=cover_image,
        ))

    return markers
