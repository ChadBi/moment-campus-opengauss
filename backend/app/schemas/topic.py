"""TOPIC-01: 专题 Schema

包含：
- 用户端：TopicListItem / TopicDetail / TopicPostItem
- 管理端：TopicAdminResponse / TopicCreate / TopicUpdate / TopicSortItem / TopicPostRef
- TopicStatus 常量（draft / published / archived）
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# ============================================================
# TOPIC-01: 专题状态常量
# ============================================================
class TopicStatus:
    """专题状态：3 态
    - draft: 草稿（默认初始态，用户端不可见）
    - published: 已发布（用户端可见）
    - archived: 已下线（用户端不可见，保留历史数据）
    """
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

    ALL: tuple = (DRAFT, PUBLISHED, ARCHIVED)


# ============================================================
# 用户端 Schema
# ============================================================
class TopicListItem(BaseModel):
    """专题列表项（用户端）"""
    id: int
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    post_count: int = 0
    view_count: int = 0
    sort_order: int = 0
    published_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopicPostItem(BaseModel):
    """专题内的帖子项（用户端，仅展示已发布/已过期的帖子）"""
    id: int
    title: str
    content: str
    status: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    post_type_id: Optional[int] = None
    post_type_name: Optional[str] = None
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    cover_image_url: Optional[str] = None
    sort_order: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopicDetail(BaseModel):
    """专题详情（用户端，含关联帖子）"""
    id: int
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    post_count: int = 0
    view_count: int = 0
    sort_order: int = 0
    published_at: Optional[datetime] = None
    created_at: datetime
    posts: List[TopicPostItem] = Field(default_factory=list, description="专题内的帖子列表（按 sort_order 排序）")

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# 管理端 Schema
# ============================================================
class TopicAdminResponse(BaseModel):
    """专题管理响应（含全部状态）"""
    id: int
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    school_id: int
    creator_id: int
    creator_name: Optional[str] = None
    post_count: int = 0
    view_count: int = 0
    status: str = Field(..., description="draft / published / archived")
    sort_order: int = 0
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopicCreate(BaseModel):
    """新建专题请求"""
    title: str = Field(..., min_length=1, max_length=200, description="专题标题")
    description: Optional[str] = Field(None, max_length=2000, description="专题描述")
    cover_url: Optional[str] = Field(None, max_length=500, description="封面图 URL")
    sort_order: int = Field(default=0, ge=0, description="排序权重，越小越靠前")
    status: str = Field(
        default=TopicStatus.DRAFT,
        pattern="^(draft|published)$",
        description="初始状态：草稿或直接发布",
    )


class TopicUpdate(BaseModel):
    """更新专题请求（部分更新）"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    cover_url: Optional[str] = Field(None, max_length=500)
    sort_order: Optional[int] = Field(None, ge=0)


class TopicSortItem(BaseModel):
    """专题排序单项"""
    id: int = Field(..., description="专题 ID")
    sort_order: int = Field(..., ge=0, description="排序权重")


class TopicSortRequest(BaseModel):
    """批量排序专题请求"""
    items: List[TopicSortItem] = Field(..., min_length=1, description="待排序的专题列表")


class TopicPostRef(BaseModel):
    """专题-帖子关联项（编排用）"""
    post_id: int = Field(..., description="帖子 ID")
    sort_order: int = Field(default=0, ge=0, description="在专题内的排序")


class TopicAddPostsRequest(BaseModel):
    """向专题添加帖子请求"""
    posts: List[TopicPostRef] = Field(..., min_length=1, description="待添加的帖子列表")


class TopicPostAdminItem(BaseModel):
    """管理端专题内的帖子项（含全部状态）"""
    id: int = Field(..., description="topic_collection_posts.id")
    topic_collection_id: int
    post_id: int
    post_title: Optional[str] = None
    post_status: Optional[str] = None
    post_school_id: Optional[int] = None
    sort_order: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopicAdminDetail(TopicAdminResponse):
    """专题管理详情（含关联帖子）"""
    posts: List[TopicPostAdminItem] = Field(default_factory=list, description="专题内的帖子列表（按 sort_order 排序）")
