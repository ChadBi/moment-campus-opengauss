from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

from app.schemas.post import UserBrief


# 创建评论
class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000, description="评论内容，1-1000字符")
    parent_id: Optional[int] = Field(None, description="父评论ID，用于回复评论")
    reply_to_user_id: Optional[int] = Field(None, description="回复的用户ID")


# 评论响应
class CommentResponse(BaseModel):
    id: int
    post_id: int
    user_id: int
    parent_id: Optional[int] = None
    reply_to_user_id: Optional[int] = None
    content: str
    like_count: int = 0
    status: str
    created_at: datetime
    updated_at: datetime

    # 关联数据
    author: Optional[UserBrief] = Field(None, alias="user", description="评论者信息")
    reply_to_user: Optional[UserBrief] = Field(None, description="被回复者信息")
    
    # 子评论列表（用于嵌套展示）
    replies: Optional[List["CommentResponse"]] = Field(default=None, description="子评论列表")
    
    # 回复数量（用于分页加载）
    reply_count: int = Field(default=0, description="回复数量")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# 解决循环引用
CommentResponse.model_rebuild()
