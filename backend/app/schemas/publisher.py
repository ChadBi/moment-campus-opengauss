"""ORG-01: 官方发布主体 Schema

包含：
- PublisherProfileCreate / PublisherProfileUpdate / PublisherProfileResponse（用户端）
- PublisherMembershipResponse（成员关系）
- PublisherAdminResponse / PublisherVerifyRequest（管理端）
- PostTemplateCreate / PostTemplateUpdate / PostTemplateResponse（模板）
- PublisherAggregationResponse（聚合效果）
- PublisherFeedbackRequest（有效性反馈/零结果聚合）
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime


# ============================================================
# 常量与枚举（用字符串 + 校验器，避免 ORM/序列化兼容性问题）
# ============================================================
PUBLISHER_TYPES: set[str] = {"department", "club", "service_org"}
VERIFIED_STATUSES: set[str] = {"pending", "verified", "revoked", "rejected"}
MEMBER_ROLES: set[str] = {"owner", "admin", "member"}
TEMPLATE_SCENES: set[str] = {
    "business_hours", "lecture", "lost", "notification", "other",
}


# ============================================================
# 用户端 Schema
# ============================================================
class PublisherProfileCreate(BaseModel):
    """发布主体申请创建

    ORG-01.1: 用户提交申请，verified_status 由后端强制设为 pending，
    不可自行设置（认证标识需 admin 审核）。
    """
    name: str = Field(..., min_length=1, max_length=100, description="主体名称")
    type: str = Field(..., description="主体类型：department/club/service_org")
    intro: Optional[str] = Field(None, max_length=2000, description="简介")
    logo_url: Optional[str] = Field(None, max_length=500, description="Logo URL")
    location_id: Optional[int] = Field(None, description="服务地点 ID")
    service_hours: Optional[str] = Field(None, max_length=200, description="服务时间")
    contact: Optional[str] = Field(None, max_length=255, description="联系方式")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in PUBLISHER_TYPES:
            raise ValueError(f"type 必须为 {PUBLISHER_TYPES} 之一")
        return v


class PublisherProfileUpdate(BaseModel):
    """发布主体更新（用户可编辑字段，verified_status 不可改）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    intro: Optional[str] = Field(None, max_length=2000)
    logo_url: Optional[str] = Field(None, max_length=500)
    location_id: Optional[int] = None
    service_hours: Optional[str] = Field(None, max_length=200)
    contact: Optional[str] = Field(None, max_length=255)


class PublisherBrief(BaseModel):
    """发布主体简要（列表用）"""
    id: int
    name: str
    type: str
    logo_url: Optional[str] = None
    verified_status: str
    intro: Optional[str] = None
    subscribe_count: int = 0
    view_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PublisherMembershipBrief(BaseModel):
    """成员关系简要"""
    id: int
    user_id: int
    role: str
    joined_at: datetime
    user_nickname: Optional[str] = None
    user_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PublisherPostBrief(BaseModel):
    """发布主体最近内容简要"""
    id: int
    title: str
    status: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    created_at: datetime
    view_count: int = 0
    like_count: int = 0


class PublisherProfileResponse(BaseModel):
    """发布主体详情（公开主页）

    ORG-01.1: 名称/类型/简介/Logo/服务地点/时间/联系方式/认证状态/最近内容
    """
    id: int
    school_id: int
    name: str
    type: str
    intro: Optional[str] = None
    logo_url: Optional[str] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    service_hours: Optional[str] = None
    contact: Optional[str] = None
    verified_status: str
    verified_at: Optional[datetime] = None
    view_count: int = 0
    subscribe_count: int = 0
    share_count: int = 0
    valid_feedback_count: int = 0
    invalid_feedback_count: int = 0
    zero_result_count: int = 0
    created_at: datetime
    updated_at: datetime
    is_member: bool = Field(False, description="当前用户是否为该主体成员")
    my_role: Optional[str] = Field(None, description="当前用户在该主体的角色（非成员为 None）")

    model_config = ConfigDict(from_attributes=True)


class PublisherDetailResponse(PublisherProfileResponse):
    """发布主体详情（含成员与最近内容，主页用）"""
    memberships: List[PublisherMembershipBrief] = Field(default_factory=list)
    recent_posts: List[PublisherPostBrief] = Field(default_factory=list, description="最近已发布内容")


class PublisherAggregationResponse(BaseModel):
    """ORG-01.4: 组织后台聚合效果（浏览/订阅/分享/有效性反馈/零结果关联需求聚合）"""
    publisher_id: int
    publisher_name: str
    view_count: int = 0
    subscribe_count: int = 0
    share_count: int = 0
    valid_feedback_count: int = 0
    invalid_feedback_count: int = 0
    zero_result_count: int = 0
    total_posts: int = Field(0, description="该主体已发布内容总数")
    published_posts: int = Field(0, description="已发布且未过期/未归档的内容数")
    pending_posts: int = Field(0, description="待审核内容数（认证不代表免审）")
    # 有效性反馈率（valid / (valid + invalid)），分母为 0 时返回 None
    valid_rate: Optional[float] = None


class PublisherFeedbackRequest(BaseModel):
    """ORG-01.4: 有效性反馈 / 零结果关联需求聚合

    - feedback_type=valid：内容有效（valid_feedback_count +1）
    - feedback_type=invalid：内容无效（invalid_feedback_count +1）
    - feedback_type=zero_result：未找到所需（zero_result_count +1）
    """
    feedback_type: str = Field(..., description="valid/invalid/zero_result")

    @field_validator("feedback_type")
    @classmethod
    def validate_feedback(cls, v: str) -> str:
        if v not in {"valid", "invalid", "zero_result"}:
            raise ValueError("feedback_type 必须为 valid/invalid/zero_result")
        return v


class PublisherShareRequest(BaseModel):
    """分享计数上报"""
    pass


# ============================================================
# 管理端 Schema
# ============================================================
class PublisherVerifyRequest(BaseModel):
    """ORG-01.2: admin 审核/认证/撤销发布主体

    action 流转规则：
    - approve：pending → verified（认证通过）
    - reject：pending → rejected（驳回申请）
    - revoke：verified → revoked（撤销认证）
    - restore：revoked/rejected → pending（恢复待审核，重新申请）
    """
    action: str = Field(..., description="approve/reject/revoke/restore")
    note: Optional[str] = Field(None, max_length=500, description="审核备注/原因")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in {"approve", "reject", "revoke", "restore"}:
            raise ValueError("action 必须为 approve/reject/revoke/restore")
        return v


class PublisherMemberAddRequest(BaseModel):
    """添加成员"""
    user_id: int = Field(..., description="被添加用户 ID")
    role: str = Field("member", description="角色：owner/admin/member")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in MEMBER_ROLES:
            raise ValueError(f"role 必须为 {MEMBER_ROLES} 之一")
        return v


class PublisherMemberUpdateRequest(BaseModel):
    """更新成员角色"""
    role: str = Field(..., description="角色：owner/admin/member")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in MEMBER_ROLES:
            raise ValueError(f"role 必须为 {MEMBER_ROLES} 之一")
        return v


class PublisherAdminResponse(BaseModel):
    """管理端发布主体详情（含审核字段）"""
    id: int
    school_id: int
    name: str
    type: str
    intro: Optional[str] = None
    logo_url: Optional[str] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    service_hours: Optional[str] = None
    contact: Optional[str] = None
    verified_status: str
    verified_at: Optional[datetime] = None
    verified_by: Optional[int] = None
    verified_by_name: Optional[str] = None
    verify_note: Optional[str] = None
    view_count: int = 0
    subscribe_count: int = 0
    share_count: int = 0
    valid_feedback_count: int = 0
    invalid_feedback_count: int = 0
    zero_result_count: int = 0
    created_at: datetime
    updated_at: datetime
    member_count: int = Field(0, description="成员总数")

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 模板 Schema
# ============================================================
class PostTemplateCreate(BaseModel):
    """ORG-01.3: 创建发布模板

    publisher_id 为空表示学校级公共模板（仅 admin 可创建）；
    非空表示主体专属模板（主体 owner/admin 可创建，需校验成员关系）。
    """
    publisher_id: Optional[int] = Field(None, description="关联发布主体（空表示学校级公共模板）")
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    title_template: str = Field(..., min_length=1, max_length=200, description="标题模板")
    content_template: str = Field(..., min_length=1, description="内容模板")
    category_id: Optional[int] = None
    scene: str = Field(..., description="场景：business_hours/lecture/lost/notification/other")
    sort_order: int = Field(0, ge=0)

    @field_validator("scene")
    @classmethod
    def validate_scene(cls, v: str) -> str:
        if v not in TEMPLATE_SCENES:
            raise ValueError(f"scene 必须为 {TEMPLATE_SCENES} 之一")
        return v


class PostTemplateUpdate(BaseModel):
    """更新发布模板"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    title_template: Optional[str] = Field(None, min_length=1, max_length=200)
    content_template: Optional[str] = Field(None, min_length=1)
    category_id: Optional[int] = None
    scene: Optional[str] = None
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

    @field_validator("scene")
    @classmethod
    def validate_scene(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in TEMPLATE_SCENES:
            raise ValueError(f"scene 必须为 {TEMPLATE_SCENES} 之一")
        return v


class PostTemplateResponse(BaseModel):
    """发布模板响应"""
    id: int
    school_id: int
    publisher_id: Optional[int] = None
    publisher_name: Optional[str] = None
    name: str
    title_template: str
    content_template: str
    category_id: Optional[int] = None
    scene: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
