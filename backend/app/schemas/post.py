from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime

from app.schemas.enums import PostStatusEnum


# 关联数据的简化响应
class UserBrief(BaseModel):
    id: int
    nickname: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GovernanceSummary(BaseModel):
    """帖子详情中的两类验证聚合。"""
    confirmation_count: int = 0
    refutation_count: int = 0
    total_validation_count: int = 0
    validity_status: str = "valid"
    user_validation_type: Optional[str] = Field(
        default=None,
        description="当前用户的验证类型；游客或未验证时为 null",
    )


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
    building: Optional[str] = None
    floor: Optional[str] = None

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
    location_id: Optional[int] = Field(None, description="地点ID（已存在的地点）")
    # 支持地图点选发帖：直接传地点名称+坐标，后端自动创建 Location
    location_name: Optional[str] = Field(None, max_length=100, description="地点名称（与 location_lat/lng 配合使用，自动创建地点）")
    location_lat: Optional[float] = Field(None, ge=-90, le=90, description="GCJ-02 纬度（与 location_name 配合使用）")
    location_lng: Optional[float] = Field(None, ge=-180, le=180, description="GCJ-02 经度（与 location_name 配合使用）")
    is_anonymous: bool = Field(default=False, description="是否匿名")
    image_urls: Optional[List[str]] = Field(default=None, max_length=9, description="图片URL列表，最多9个")
    expire_at: Optional[datetime] = Field(None, description="信息截止时间")
    lost_type: Optional[str] = Field(None, max_length=10, description="丢失类型")
    contact_info: Optional[str] = Field(None, max_length=255, description="联系方式")
    # T-B-06: 支持创建时指定初始状态（draft 草稿 / pending 提交审核）
    # FND-01.2: 创建时只允许 draft / pending；其余 4 态由状态机服务管理。
    status: Optional[PostStatusEnum] = Field(
        default=PostStatusEnum.PENDING,
        description="初始状态：draft（存为草稿）/ pending（提交审核，默认）",
    )
    # ORG-01: 关联官方发布主体（已下线，字段移除）

    @field_validator("status")
    @classmethod
    def validate_create_status(cls, v: Optional[PostStatusEnum]) -> PostStatusEnum:
        """FND-01.2: 创建时只允许 draft 或 pending，其余状态由状态机服务统一管理。"""
        if v is None:
            return PostStatusEnum.PENDING
        allowed = {PostStatusEnum.DRAFT, PostStatusEnum.PENDING}
        if v not in allowed:
            raise ValueError(
                "创建时 status 只能为 draft 或 pending；"
                "published/expired/conflict/archived 必须通过状态机服务流转。"
            )
        return v


# 更新信息
# FND-01.2: 移除 status / is_recommend 字段——状态变化只走状态机服务（FND-03），
# is_recommend 由管理员后台单独管理。客户端传入这两个字段会被 Pydantic 默认忽略。
class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200, description="标题")
    content: Optional[str] = Field(None, min_length=10, max_length=5000, description="内容描述")
    category_id: Optional[int] = Field(None, description="分类ID")
    location_id: Optional[int] = Field(None, description="地点ID")
    is_anonymous: Optional[bool] = Field(None, description="是否匿名")
    image_urls: Optional[List[str]] = Field(None, max_length=9, description="图片URL列表")
    expire_at: Optional[datetime] = Field(None, description="信息截止时间")
    lost_type: Optional[str] = Field(None, max_length=10, description="丢失类型")
    contact_info: Optional[str] = Field(None, max_length=255, description="联系方式")


# 信息响应（包含关联数据）
class PostResponse(BaseModel):
    id: int
    user_id: int
    school_id: int
    category_id: int
    location_id: Optional[int] = None
    title: str
    content: str
    is_anonymous: bool
    status: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    expire_at: Optional[datetime] = None
    lost_type: Optional[str] = None
    contact_info: Optional[str] = None
    is_recommend: bool = False
    created_at: datetime
    updated_at: datetime

    # 关联数据
    author: Optional[UserBrief] = None
    category: Optional[CategoryBrief] = None
    location: Optional[LocationBrief] = None
    images: Optional[List[PostImageBrief]] = Field(default=None, description="图片列表")

    # 前端需要的额外字段
    is_liked: bool = Field(default=False, description="当前用户是否已点赞")

    # GOV-01.4: 协同治理聚合（验证数量/时间/说明/处理状态）
    governance: Optional["GovernanceSummary"] = Field(
        default=None, description="协同治理聚合（仅详情端点返回）"
    )

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


# 信息列表响应（简化版，用于列表展示）
class PostListResponse(BaseModel):
    id: int
    user_id: int
    title: str
    content: str = Field(description="内容（完整内容，前端用 CSS line-clamp 控制显示行数）")
    is_anonymous: bool = False
    # PUB-02: 列表项携带状态（我的发布按状态分组展示草稿/待审核/已发布等）
    status: str = "published"
    category: Optional[CategoryBrief] = None
    location: Optional[LocationBrief] = None
    author: Optional[UserBrief] = None
    cover_image: Optional[str] = Field(None, description="封面图片")
    like_count: int = 0
    comment_count: int = 0
    view_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    is_recommend: bool = False
    created_at: datetime
    expire_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


# T-B-04: 状态流转请求
class PostTransitionCreate(BaseModel):
    target_status: str = Field(
        ...,
        pattern="^(draft|pending|published|expired|conflict|archived|pending_review)$",
        description="目标状态（6 态）：draft/pending/published/expired/conflict/archived。"
                    "pending_review 为 pending 的历史别名，将被归一化为 pending",
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


PostResponse.model_rebuild()

