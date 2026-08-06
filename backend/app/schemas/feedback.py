"""反馈 Schema（用户反馈：建议/问题/投诉/其他）"""
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# 反馈类型合法值
FEEDBACK_TYPES = ("suggestion", "bug", "complaint", "other")
# 反馈状态合法值
FEEDBACK_STATUSES = ("open", "in_review", "resolved")


class FeedbackCreate(BaseModel):
    """提交反馈请求"""
    feedback_type: str = Field(..., description="反馈类型：suggestion / bug / complaint / other")
    content: str = Field(..., min_length=1, max_length=2000, description="反馈内容")
    contact: Optional[str] = Field(None, max_length=200, description="联系方式（可空）")

    @field_validator("feedback_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in FEEDBACK_TYPES:
            raise ValueError("feedback_type 必须为 suggestion / bug / complaint / other 之一")
        return v


class FeedbackResponse(BaseModel):
    """反馈响应（用户端 / 管理端共用）"""
    id: int
    user_id: int
    school_id: int
    feedback_type: str
    content: str
    contact: Optional[str] = None
    status: str
    remark: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # 管理端展示用（用户端不填充）
    user_name: Optional[str] = None

    model_config = {"from_attributes": True}


class FeedbackAdminUpdate(BaseModel):
    """管理端处理反馈（部分更新）"""
    status: Optional[str] = Field(None, description="状态：open / in_review / resolved")
    remark: Optional[str] = Field(None, max_length=2000, description="处理备注")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in FEEDBACK_STATUSES:
            raise ValueError("status 必须为 open / in_review / resolved 之一")
        return v