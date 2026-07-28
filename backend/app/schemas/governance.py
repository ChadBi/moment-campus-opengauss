"""GOV-01: 协同治理 Schema

5 类协同验证原设计 = 2 类互斥投票(validation_records: confirmation/refutation)
            + 3 类问题报告(post_change_reports: update/expiration_report/conflict_report)

调整后：问题报告功能整体移除（与评论/举报功能冲突），
仅保留 2 类互斥投票（证实/证伪）+ 举报（reports 表）+ 评论。
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    # 仅用于类型注解；运行时在模块底部延迟导入，避免与 schemas.post 循环依赖
    from app.schemas.post import UserBrief


# ============================================================
# 2 类互斥投票（validation_records）
# ============================================================

class ValidationVoteCreate(BaseModel):
    """提交有效性投票（仅 confirmation/refutation）"""
    validation_type: str = Field(
        ...,
        pattern="^(confirmation|refutation|valid|invalid)$",
        description="投票类型：confirmation（证实）/ refutation（证伪）。"
                    "向后兼容旧值：valid→confirmation / invalid→refutation。",
    )
    comment: Optional[str] = Field(None, max_length=500, description="备注说明，最多500字符")


class ValidationVoteResponse(BaseModel):
    """投票记录响应"""
    id: int
    post_id: int
    user_id: int
    validation_type: str
    comment: Optional[str] = None
    created_at: datetime
    user: Optional["UserBrief"] = None

    model_config = ConfigDict(from_attributes=True)


class ValidationAggregation(BaseModel):
    """GET /posts/{id}/validations 聚合投票统计"""
    post_id: int
    confirmation_count: int = Field(default=0, description="证实数")
    refutation_count: int = Field(default=0, description="证伪数")
    total_count: int = Field(default=0, description="总投票数")
    validity_status: str = Field(default="valid", description="综合有效性状态：valid/invalid/uncertain")
    user_validation_type: Optional[str] = Field(
        default=None,
        description="当前用户对此帖的投票类型（confirmation/refutation/None）",
    )
    recent_records: List[ValidationVoteResponse] = Field(
        default_factory=list,
        description="最近的投票记录（含时间/说明，默认 10 条）",
    )


# ============================================================
# 详情聚合（嵌入 PostResponse.governance）
# ============================================================

class GovernanceSummary(BaseModel):
    """GOV-01.4: 帖子详情聚合——验证数量/时间/说明/处理状态

    DSC-02.1: user_validation_type 仅在登录用户访问时返回（用于前端高亮"已证实/已证伪"按钮）；
    游客访问时为 None，前端据此隐藏投票按钮（游客不请求需登录的投票接口）。
    """
    confirmation_count: int = 0
    refutation_count: int = 0
    total_validation_count: int = 0
    validity_status: str = "valid"
    user_validation_type: Optional[str] = Field(
        default=None,
        description="当前登录用户对此帖的投票类型（confirmation/refutation/None）。"
                    "游客访问时恒为 None；登录用户访问时返回其投票类型，前端据此高亮按钮。",
    )


# ============================================================
# 循环依赖处理：底部延迟导入 UserBrief 并重建含前向引用的模型
# ============================================================
from app.schemas.post import UserBrief  # noqa: E402

ValidationVoteResponse.model_rebuild()
