from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# 关联数据的简化响应
class UserBrief(BaseModel):
    id: int
    nickname: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CategoryBrief(BaseModel):
    id: int
    name: str
    code: str
    icon: str

    model_config = ConfigDict(from_attributes=True)


class LocationBrief(BaseModel):
    id: int
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class PostTypeBrief(BaseModel):
    id: int
    name: str
    code: str

    model_config = ConfigDict(from_attributes=True)


class TagBrief(BaseModel):
    id: int
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class PostImageBrief(BaseModel):
    id: int
    image_url: str
    thumbnail_url: Optional[str] = None
    sort_order: int = 0

    model_config = ConfigDict(from_attributes=True)


# 创建信息
class PostCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200, description="标题，5-200字符")
    content: str = Field(..., min_length=10, max_length=5000, description="内容描述，10-5000字符")
    category_id: int = Field(..., description="分类ID")
    location_id: Optional[int] = Field(None, description="地点ID")
    post_type_id: Optional[int] = Field(None, description="信息类型ID")
    is_anonymous: bool = Field(default=False, description="是否匿名")
    tags: Optional[List[str]] = Field(default=None, max_length=5, description="标签列表，最多5个")
    image_urls: Optional[List[str]] = Field(default=None, max_length=9, description="图片URL列表，最多9个")
    expire_at: Optional[datetime] = Field(None, description="过期时间")
    activity_start_at: Optional[datetime] = Field(None, description="活动开始时间")
    activity_end_at: Optional[datetime] = Field(None, description="活动结束时间")
    lost_type: Optional[str] = Field(None, max_length=10, description="丢失类型")
    contact_info: Optional[str] = Field(None, max_length=255, description="联系方式")
    # T-B-06: 支持创建时指定初始状态（draft 草稿 / pending 提交审核）
    status: Optional[str] = Field(
        default="pending",
        pattern="^(draft|pending)$",
        description="初始状态：draft（存为草稿）/ pending（提交审核，默认）",
    )


# 更新信息
class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200, description="标题")
    content: Optional[str] = Field(None, min_length=10, max_length=5000, description="内容描述")
    category_id: Optional[int] = Field(None, description="分类ID")
    location_id: Optional[int] = Field(None, description="地点ID")
    post_type_id: Optional[int] = Field(None, description="信息类型ID")
    is_anonymous: Optional[bool] = Field(None, description="是否匿名")
    tags: Optional[List[str]] = Field(None, max_length=5, description="标签列表")
    image_urls: Optional[List[str]] = Field(None, max_length=9, description="图片URL列表")
    expire_at: Optional[datetime] = Field(None, description="过期时间")
    activity_start_at: Optional[datetime] = Field(None, description="活动开始时间")
    activity_end_at: Optional[datetime] = Field(None, description="活动结束时间")
    lost_type: Optional[str] = Field(None, max_length=10, description="丢失类型")
    contact_info: Optional[str] = Field(None, max_length=255, description="联系方式")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    is_top: Optional[bool] = Field(None, description="是否置顶")
    is_recommend: Optional[bool] = Field(None, description="是否推荐")


# 信息响应（包含关联数据）
class PostResponse(BaseModel):
    id: int
    user_id: int
    school_id: int
    category_id: int
    post_type_id: Optional[int] = None
    location_id: Optional[int] = None
    title: str
    content: str
    is_anonymous: bool
    status: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    favorite_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    expire_at: Optional[datetime] = None
    activity_start_at: Optional[datetime] = None
    activity_end_at: Optional[datetime] = None
    lost_type: Optional[str] = None
    contact_info: Optional[str] = None
    is_top: bool = False
    is_recommend: bool = False
    created_at: datetime
    updated_at: datetime

    # 关联数据
    author: Optional[UserBrief] = Field(None, alias="user", description="作者信息")
    category: Optional[CategoryBrief] = None
    location: Optional[LocationBrief] = None
    post_type: Optional[PostTypeBrief] = None
    tags: Optional[List[TagBrief]] = Field(default=None, description="标签列表")
    images: Optional[List[PostImageBrief]] = Field(default=None, description="图片列表")

    # 前端需要的额外字段
    is_liked: bool = Field(default=False, description="当前用户是否已点赞")
    is_favorited: bool = Field(default=False, description="当前用户是否已收藏")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# 信息列表响应（简化版，用于列表展示）
class PostListResponse(BaseModel):
    id: int
    title: str
    content: str = Field(max_length=200, description="内容摘要")
    category: Optional[CategoryBrief] = None
    location: Optional[LocationBrief] = None
    author: Optional[UserBrief] = Field(None, alias="user", description="作者信息")
    cover_image: Optional[str] = Field(None, description="封面图片")
    tags: Optional[List[TagBrief]] = Field(default=None, description="标签列表")
    like_count: int = 0
    comment_count: int = 0
    favorite_count: int = 0
    view_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    is_top: bool = False
    is_recommend: bool = False
    created_at: datetime
    expire_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# T-B-04: 状态流转请求
class PostTransitionCreate(BaseModel):
    target_status: str = Field(
        ...,
        pattern="^(draft|pending|published|expired|conflict|archived|pending_review)$",
        description="目标状态：draft/pending/published/expired/conflict/archived。"
                    "pending_review 为 pending 的别名，将被归一化",
    )
    reason: Optional[str] = Field(None, max_length=500, description="流转原因（可选）")


# T-B-04: 状态流转响应
class PostTransitionResponse(BaseModel):
    post_id: int
    previous_status: str
    current_status: str
    transitioned_at: datetime
    transitioned_by: int

    model_config = ConfigDict(from_attributes=True)
