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


class BatchFailedItem(BaseModel):
    """ADM-01.4: 批量操作单项失败明细（成功/失败/原因不静默跳过）"""
    id: int = Field(..., description="失败的目标ID")
    reason: str = Field(..., description="失败原因")


class BatchOperationResponse(BaseModel):
    """批量操作响应"""
    total: int = Field(default=0, description="总数")
    success: int = Field(default=0, description="成功数")
    failed: int = Field(default=0, description="失败数")
    failed_ids: List[int] = Field(default_factory=list, description="失败的目标ID列表")
    failed_items: List[BatchFailedItem] = Field(
        default_factory=list, description="ADM-01.4: 每项失败明细（id + 原因）"
    )
    message: str = Field(default="批量操作完成")


# ============ ADM-01.1: 校级待办统计 ============
class TodoItem(BaseModel):
    """单个待办类别：计数 + 前端跳转路径（带筛选条件）"""
    key: str = Field(..., description="待办类别标识")
    label: str = Field(..., description="中文名称")
    count: int = Field(default=0, description="待办数量")
    queue_url: str = Field(..., description="前端队列路径（含筛选参数）")


class TodoStats(BaseModel):
    """ADM-01.1: 校级后台首页待办统计

    4 类待办：待审核 / 待处理举报 / 待核验地点 / 异常任务（最近失败的任务运行记录）。
    原 3 类问题报告（过期报告/冲突报告/更新建议）已移除（与评论/举报功能冲突）。

    REL-02.3: 额外返回本校最近 24h AI 调用降级率（采样监控），
    降级率 ≥50% 时由前端高亮提示。
    """
    pending_posts: int = Field(default=0, description="待审核内容数")
    pending_reports: int = Field(default=0, description="待处理举报数")
    unverified_locations: int = Field(default=0, description="待核验地点数")
    failed_jobs: int = Field(default=0, description="最近失败任务数（24h 内）")
    total: int = Field(default=0, description="待办合计")
    items: List[TodoItem] = Field(default_factory=list, description="待办卡片（含跳转路径）")
    # REL-02.3: AI 降级率（最近 24h 本校采样）
    ai_calls_24h: int = Field(default=0, description="最近 24h AI 调用次数（本校）")
    ai_fallback_24h: int = Field(default=0, description="最近 24h AI 降级次数（本校）")
    ai_fallback_rate: float = Field(default=0.0, description="最近 24h AI 降级率（0~1）")


# ============ ADM-01.2: 审核详情（管理专用接口） ============
class AuthorHistoryStats(BaseModel):
    """作者历史统计（审核详情辅助判断）"""
    total_posts: int = 0
    published_posts: int = 0
    rejected_posts: int = 0
    report_received_count: int = 0


class AdminPostDetail(BaseModel):
    """ADM-01.2: 审核详情（管理专用，不依赖公开帖子详情）

    含完整内容、分类、地点、有效期、图片、作者历史与治理概况。
    """
    id: int
    title: str
    content: str
    status: str
    is_anonymous: bool
    created_at: datetime
    updated_at: datetime
    expire_at: Optional[datetime] = None
    contact_info: Optional[str] = None
    lost_type: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    # 关联信息
    author_id: int
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    category_id: int
    category_name: Optional[str] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    location_verified: Optional[bool] = None
    images: List[str] = Field(default_factory=list, description="图片 URL 列表")
    # 审核辅助
    author_history: AuthorHistoryStats = Field(default_factory=AuthorHistoryStats)
    pending_user_reports: int = Field(default=0, description="待处理用户举报数")


# ============ ADM-01.3: 原因模板 ============
class ReasonTemplate(BaseModel):
    """审核原因模板"""
    code: str = Field(..., description="模板标识")
    label: str = Field(..., description="模板标题")
    text: str = Field(..., description="模板内容（可直接作为 reason）")


class ReasonTemplateResponse(BaseModel):
    """通过/驳回原因模板"""
    approve: List[ReasonTemplate] = Field(default_factory=list)
    reject: List[ReasonTemplate] = Field(default_factory=list)


# ============ ADM-01.5: 治理工作台 ============
# 调整后：原 3 类问题报告（update/expiration_report/conflict_report）已移除
# 帖子过期/冲突状态由管理员通过举报队列处理


# ============ ADM-01.6: 地点核验 ============
class LocationAdminResponse(BaseModel):
    """地点管理视图"""
    id: int
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    floor: Optional[str] = None
    building: Optional[str] = None
    post_count: int = 0
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============ ADM-02.1: 学校设置 ============
class SchoolSettingsResponse(BaseModel):
    """学校设置响应（ADM-02.1）

    后端真实存储，跨浏览器生效；body 里的 school_id 由 TenantContext 决定，
    不暴露给前端。
    """
    site_name: Optional[str] = Field(None, description="站点名称")
    description: Optional[str] = Field(None, description="站点说明")
    require_review: bool = Field(..., description="新信息是否需要审核")
    allow_anonymous: bool = Field(..., description="是否允许匿名发布")
    allow_comments: bool = Field(..., description="是否允许评论")
    publish_frequency: int = Field(..., description="每日发布上限（0 表示不限）")
    image_limit: int = Field(..., description="单帖图片上限")
    default_validity_days: int = Field(..., description="默认有效期天数")
    brand_color: Optional[str] = Field(None, description="品牌色（如 #1890ff）")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    updated_at: datetime = Field(..., description="最近一次更新时间")

    model_config = ConfigDict(from_attributes=True)


class SchoolSettingsUpdate(BaseModel):
    """更新学校设置请求（部分更新；全部字段可选）

    ADM-02.1: PUT /admin/settings 仅接收允许修改的字段；
    school_id 不可改（由 TenantContext 决定）。
    """
    site_name: Optional[str] = Field(None, max_length=100, description="站点名称")
    description: Optional[str] = Field(None, description="站点说明")
    require_review: Optional[bool] = Field(None, description="新信息是否需要审核")
    allow_anonymous: Optional[bool] = Field(None, description="是否允许匿名发布")
    allow_comments: Optional[bool] = Field(None, description="是否允许评论")
    publish_frequency: Optional[int] = Field(
        None, ge=0, le=1000, description="每日发布上限（0 表示不限）"
    )
    image_limit: Optional[int] = Field(
        None, ge=0, le=20, description="单帖图片上限"
    )
    default_validity_days: Optional[int] = Field(
        None, ge=1, le=3650, description="默认有效期天数"
    )
    brand_color: Optional[str] = Field(None, max_length=20, description="品牌色")
    logo_url: Optional[str] = Field(None, max_length=500, description="Logo URL")


# ============ GOV-02: 任务运行记录 ============
class ExpirePostsJobRequest(BaseModel):
    """GOV-02.2: 手动触发过期任务请求"""
    dry_run: bool = Field(default=False, description="dry-run 模式：只报告不执行")


class JobRunRecordResponse(BaseModel):
    """GOV-02.2: 任务运行记录响应"""
    id: int
    job_name: str
    status: str = Field(description="running / success / failed")
    started_at: datetime
    finished_at: Optional[datetime] = None
    processed_count: int = 0
    failed_count: int = 0
    error_message: Optional[str] = None
    triggered_by: str
    triggered_user_id: Optional[int] = None
    dry_run: bool = False
    metadata: Optional[str] = Field(None, description="JSON 文本（额外元数据）")
    duration_seconds: Optional[float] = Field(
        None, description="耗时（秒），由 finished_at - started_at 计算"
    )

    model_config = ConfigDict(from_attributes=True)
