"""管理员后台 Schema

包含：
- 仪表盘统计 DashboardStats
- 操作日志 AdminLogResponse
- 分类管理 CategoryCreate / CategoryUpdate / CategoryAdminResponse
- 标签管理 TagAdminResponse / TagUpdate / TagMergeRequest
- 批量操作请求 / 响应
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# ============ 仪表盘统计 ============
class DashboardStats(BaseModel):
    """仪表盘统计数据"""
    total_posts: int = Field(default=0, description="信息总数（未删除）")
    pending_posts: int = Field(default=0, description="待审核信息数")
    total_users: int = Field(default=0, description="用户总数（未删除）")
    active_users: int = Field(default=0, description="活跃用户数（is_active=True）")
    total_reports: int = Field(default=0, description="举报总数")
    pending_reports: int = Field(default=0, description="待处理举报数")
    total_comments: int = Field(default=0, description="评论总数")


# ============ 操作日志 ============
class AdminLogResponse(BaseModel):
    """操作日志响应"""
    id: int
    admin_id: int
    admin_name: Optional[str] = Field(None, description="管理员昵称")
    action: str
    target_type: str
    target_id: int
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============ 分类管理 ============
class CategoryCreate(BaseModel):
    """新建分类"""
    name: str = Field(..., min_length=1, max_length=50, description="分类名称")
    code: str = Field(..., min_length=1, max_length=30, pattern="^[a-z0-9_]+$", description="分类编码（小写字母+数字+下划线）")
    icon: str = Field(..., min_length=1, max_length=10, description="图标 emoji")
    description: Optional[str] = Field(None, max_length=200, description="描述")
    default_validity_days: int = Field(default=30, ge=1, le=3650, description="默认有效天数")
    sort_order: int = Field(default=0, ge=0, description="排序权重，越小越靠前")
    is_active: bool = Field(default=True, description="是否启用")


class CategoryUpdate(BaseModel):
    """更新分类（code 不可修改）"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    icon: Optional[str] = Field(None, min_length=1, max_length=10)
    description: Optional[str] = Field(None, max_length=200)
    default_validity_days: Optional[int] = Field(None, ge=1, le=3650)
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class CategoryAdminResponse(BaseModel):
    """分类管理响应（含禁用项与统计）"""
    id: int
    name: str
    code: str
    icon: str
    description: Optional[str] = None
    default_validity_days: int
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    post_count: int = Field(default=0, description="该分类下的信息数")

    model_config = ConfigDict(from_attributes=True)


# ============ 标签管理 ============
class TagAdminResponse(BaseModel):
    """标签管理响应（含已删项）"""
    id: int
    name: str
    slug: str
    usage_count: int
    is_official: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TagUpdate(BaseModel):
    """更新标签"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    is_official: Optional[bool] = None


class TagMergeRequest(BaseModel):
    """合并标签请求：将 source_tag_ids 的帖子关联迁移到 target_tag_id，并软删除源标签"""
    source_tag_ids: List[int] = Field(..., min_length=1, description="被合并的源标签ID列表")
    target_tag_id: int = Field(..., description="合并目标标签ID")


# ============ 批量操作 ============
class BatchApproveRequest(BaseModel):
    """批量审核通过请求"""
    post_ids: List[int] = Field(..., min_length=1, description="帖子ID列表")
    reason: Optional[str] = Field(None, max_length=500, description="审核备注")


class BatchRejectRequest(BaseModel):
    """批量审核拒绝请求"""
    post_ids: List[int] = Field(..., min_length=1, description="帖子ID列表")
    reason: str = Field(..., min_length=1, max_length=500, description="拒绝原因")


class BatchToggleActiveRequest(BaseModel):
    """批量启用/禁用用户请求"""
    user_ids: List[int] = Field(..., min_length=1, description="用户ID列表")
    is_active: bool = Field(..., description="是否启用")
    reason: Optional[str] = Field(None, max_length=500, description="操作原因")


class BatchOperationResponse(BaseModel):
    """批量操作响应"""
    total: int = Field(default=0, description="总数")
    success: int = Field(default=0, description="成功数")
    failed: int = Field(default=0, description="失败数")
    failed_ids: List[int] = Field(default_factory=list, description="失败的目标ID列表")
    message: str = Field(default="批量操作完成")
