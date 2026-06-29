from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.post import Post
from app.models.location import Location

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
):
    """
    获取地图标记
    根据经纬度边界返回标记，最多100个
    """
    # 查询边界内的地点
    query = (
        select(Location, Post)
        .join(Post, Post.location_id == Location.id)
        .where(
            Location.is_deleted == False,
            Post.is_deleted == False,
            Post.status == "published",
            Location.latitude <= north,
            Location.latitude >= south,
            Location.longitude <= east,
            Location.longitude >= west,
        )
        .limit(100)
    )

    if category_id:
        query = query.where(Post.category_id == category_id)

    result = await db.execute(query)
    rows = result.all()

    markers = []
    for location, post in rows:
        # 获取封面图
        from app.models.post_image import PostImage
        image_query = (
            select(PostImage)
            .where(PostImage.post_id == post.id, PostImage.is_deleted == False)
            .order_by(PostImage.sort_order)
            .limit(1)
        )
        image_result = await db.execute(image_query)
        first_image = image_result.scalar_one_or_none()
        cover_image = first_image.image_url if first_image else None

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
