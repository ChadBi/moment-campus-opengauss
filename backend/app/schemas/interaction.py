from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime

from app.schemas.post import UserBrief
from app.schemas.enums import ReportType, ValidationTypeEnum


# 点赞响应
class LikeResponse(BaseModel):
    post_id: int
    like_count: int = Field(default=0, description="点赞总数")
    is_liked: bool = Field(default=True, description="是否已点赞")


class ValidationCreate(BaseModel):
    validation_type: ValidationTypeEnum = Field(..., description="验证类型：confirmation 或 refutation")
    comment: Optional[str] = Field(None, max_length=500, description="备注说明，最多500字符")


# 举报创建（FND-01.1: 使用共享 ReportType 枚举统一举报类型）
class ReportCreate(BaseModel):
    report_type: ReportType = Field(
        ...,
        description="举报类型：spam（垃圾信息）/ abuse（滥用）/ harassment（骚扰）/ "
                    "false_info（虚假信息）/ other（其他）"
    )
    description: Optional[str] = Field(None, max_length=1000, description="举报描述，最多1000字符")


# 有效性确认响应
class ValidationResponse(BaseModel):
    id: Optional[int] = None
    post_id: int
    user_id: int
    validation_type: Optional[ValidationTypeEnum] = None
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    action: Literal["created", "switched", "removed"]
    current_validation_type: Optional[ValidationTypeEnum] = None
    confirmation_count: int = 0
    refutation_count: int = 0

    # 关联数据
    user: Optional[UserBrief] = Field(None, description="确认者信息")

    model_config = ConfigDict(from_attributes=True)


# 有效性统计响应
class ValidationStatsResponse(BaseModel):
    post_id: int
    # 旧 2 类字段（向后兼容，对应 Post.valid_count / invalid_count）
    valid_count: int = Field(default=0, description="有效确认数（= confirmation 计数）")
    invalid_count: int = Field(default=0, description="无效确认数（= refutation 计数）")
    # 2 类细分计数
    confirmation_count: int = Field(default=0, description="证实数")
    refutation_count: int = Field(default=0, description="证伪数")
    total_count: int = Field(default=0, description="总验证数")
    validity_status: str = Field(default="valid", description="综合有效性状态")
    # 当前用户的验证类型（用于前端高亮按钮；None 表示未验证）
    user_validation_type: Optional[str] = Field(default=None, description="当前用户对此帖的验证类型（confirmation/refutation/None）")
    records: Optional[List[ValidationResponse]] = Field(default=None, description="确认记录列表")
