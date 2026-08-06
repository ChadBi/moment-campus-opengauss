from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

from app.schemas.post import UserBrief
from app.schemas.location_knowledge import LocationFactResponse, LocationSummaryResponse


# 地点列表/详情响应
class LocationResponse(BaseModel):
    id: int
    school_id: int
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    floor: Optional[str] = None
    building: Optional[str] = None
    post_count: int = 0
    is_verified: bool = False
    # REV-01: 评分汇总
    avg_score: float = Field(default=0, description="平均评分（1-5，保留 2 位）")
    rating_count: int = Field(default=0, description="评分人数")
    review_count: int = Field(default=0, description="评价条数")
    model_config = ConfigDict(from_attributes=True)


# 创建/更新评价
class LocationReviewCreate(BaseModel):
    score: int = Field(..., ge=1, le=5, description="评分 1-5")
    content: Optional[str] = Field(default=None, max_length=500, description="评价内容，最多 500 字")


# 评价响应
class LocationReviewResponse(BaseModel):
    id: int
    location_id: int
    user_id: int
    score: int
    content: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    author: Optional[UserBrief] = None

    model_config = ConfigDict(from_attributes=True)


# 地点详情（含评分汇总 + 我是否已评价）
class LocationDetailResponse(BaseModel):
    location: LocationResponse
    my_review: Optional[LocationReviewResponse] = Field(
        default=None, description="当前登录用户我的评价（未登录/未评价为 None）"
    )
    facts: list[LocationFactResponse] = Field(default_factory=list, description="已审核地点稳定资料")
    summary: LocationSummaryResponse = Field(default_factory=LocationSummaryResponse, description="已审核 AI 地点摘要")
