from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

from app.schemas.post import UserBrief


# 点赞响应
class LikeResponse(BaseModel):
    post_id: int
    like_count: int = Field(default=0, description="点赞总数")
    is_liked: bool = Field(default=True, description="是否已点赞")


# 收藏响应
class FavoriteResponse(BaseModel):
    post_id: int
    favorite_count: int = Field(default=0, description="收藏总数")
    is_favorited: bool = Field(default=True, description="是否已收藏")


# 有效性确认创建
class ValidationCreate(BaseModel):
    validation_type: str = Field(
        ...,
        pattern="^(valid|invalid|uncertain)$",
        description="有效性类型：valid（有效）/ invalid（无效）/ uncertain（不确定）"
    )
    comment: Optional[str] = Field(None, max_length=500, description="备注说明，最多500字符")


# 有效性确认响应
class ValidationResponse(BaseModel):
    id: int
    post_id: int
    user_id: int
    validation_type: str
    comment: Optional[str] = None
    created_at: datetime

    # 关联数据
    user: Optional[UserBrief] = Field(None, description="确认者信息")

    model_config = ConfigDict(from_attributes=True)


# 有效性统计响应
class ValidationStatsResponse(BaseModel):
    post_id: int
    valid_count: int = Field(default=0, description="有效确认数")
    invalid_count: int = Field(default=0, description="无效确认数")
    uncertain_count: int = Field(default=0, description="不确定确认数")
    validity_status: str = Field(default="valid", description="综合有效性状态")
    records: Optional[List[ValidationResponse]] = Field(default=None, description="确认记录列表")


# 收藏列表项响应
class FavoriteItemResponse(BaseModel):
    id: int
    post_id: int
    user_id: int
    created_at: datetime

    # 关联的帖子信息（简化版）
    post_title: Optional[str] = Field(None, description="帖子标题")
    post_cover_image: Optional[str] = Field(None, description="帖子封面图")
    post_status: Optional[str] = Field(None, description="帖子状态")

    model_config = ConfigDict(from_attributes=True)
