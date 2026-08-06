"""AI-02.1: AI 搜索相关 Schema。

定义 AI 结构化搜索的请求/响应模型：
- AISearchRequest：用户自然语言查询 + 可编辑筛选覆盖项
- AISearchIntentFilters：AI 解析出的结构化筛选条件（白名单校验后）
- AISearchIntent：完整意图（自然语言概述 + 筛选 + 理由）
- AISearchResultItem：单条结果（含 PostListResponse + 分数 + 单条匹配理由）
- AISearchResponse：响应包装（带 fallback 标记 + 整体意图 + 分页元数据）

设计原则：
1. 所有字段都不可信 → API 层接收后再做白名单/范围校验。
2. fallback=true 时仍返回可用的普通搜索结果（不空响应）。
3. 地图范围 map_bounds 为可选，AI 可能不返回；返回时后端按 location 坐标过滤。
"""
from __future__ import annotations

from typing import Optional, List, Any
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# AI-02.1: 请求
# ============================================================
class AISearchOverrides(BaseModel):
    """用户可编辑的筛选覆盖项。

    用户在前端通过 Chip 编辑 AI 解析出的条件后，将最终条件作为 overrides 传回后端，
    后端用 overrides 覆盖 AI 解析结果，再执行检索（避免重新调用模型）。
    所有字段均可空，未提供时使用 AI 解析结果。
    """
    keyword: Optional[str] = Field(None, max_length=100, description="关键词覆盖")
    category_id: Optional[int] = Field(None, description="分类ID覆盖（白名单校验后）")
    location_id: Optional[int] = Field(None, description="地点ID覆盖")
    sort: Optional[str] = Field(
        None,
        pattern="^(latest|hottest|active|relevance)$",
        description="排序覆盖：latest/hottest/active/relevance",
    )
    date_from: Optional[datetime] = Field(None, description="起始时间覆盖")
    date_to: Optional[datetime] = Field(None, description="截止时间覆盖")


class AISearchRequest(BaseModel):
    """AI 搜索请求体。

    - query：自然语言查询（必填，长度 1-200）
    - overrides：用户编辑后的筛选条件（可选）；提供时覆盖 AI 解析结果
    - page / page_size：分页（与普通搜索对齐）
    """
    query: str = Field(..., min_length=1, max_length=200, description="自然语言查询")
    overrides: Optional[AISearchOverrides] = Field(
        None, description="用户编辑的筛选覆盖项（提供时不再调用模型解析）"
    )
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


# ============================================================
# AI-02.1: 响应
# ============================================================
class AISearchIntentFilters(BaseModel):
    """AI 解析出的结构化筛选条件（白名单校验后的最终值）。

    - category_id / category_name：分类（白名单校验后转为 ID；非法值置空）
    - sort：排序（白名单内；非法值回退 latest）
    - date_from / date_to：时间范围（已校验为合法 ISO 字符串）
    - map_bounds：地图范围（可选；AI 可能解析"江南大学附近"等表述）
    - keyword：关键词（用于检索与展示）
    """
    keyword: Optional[str] = Field(None, description="关键词")
    category_id: Optional[int] = Field(None, description="分类ID（白名单校验后）")
    category_name: Optional[str] = Field(None, description="分类名称（原始解析值，便于 Chip 展示）")
    location_id: Optional[int] = Field(None, description="地点ID（白名单校验后）")
    sort: str = Field("latest", description="排序方式")
    date_from: Optional[datetime] = Field(None, description="起始时间")
    date_to: Optional[datetime] = Field(None, description="截止时间")
    map_bounds: Optional[dict[str, float]] = Field(
        None, description="地图范围 {north, south, east, west}（可选）"
    )

    model_config = ConfigDict(extra="ignore")


class AISearchIntent(BaseModel):
    """AI 解析出的完整意图。"""
    intent: str = Field(..., description="用户意图的自然语言概述")
    filters: AISearchIntentFilters = Field(..., description="结构化筛选条件")
    reasons: List[str] = Field(default_factory=list, description="整体匹配理由（多条）")


class AISearchResultItem(BaseModel):
    """AI 搜索单条结果（在 PostListResponse 基础上附加分数与匹配理由）。"""
    post: Any = Field(..., description="帖子列表项（PostListResponse 结构）")
    score: float = Field(..., description="确定性分数（时间新鲜度 + 验证数 + 相关度）")
    match_reasons: List[str] = Field(default_factory=list, description="本条匹配理由（多条）")


class AISearchResponse(BaseModel):
    """AI 搜索响应。

    - fallback=true 时 intent 仍可能存在（部分降级场景）或为 None（完全降级）
    - fallback_reason 提供给前端展示降级提示
    - ai_log_id 用于关联 ai_invocation_logs（便于排查）
    """
    items: List[Any] = Field(default_factory=list, description="结果列表（PostListResponse 结构）")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    total: int = Field(0, ge=0)
    total_pages: int = Field(0, ge=0)
    has_more: bool = Field(False)
    intent: Optional[AISearchIntent] = Field(None, description="AI 解析的意图（降级时可能为 None）")
    match_reasons: dict[int, List[str]] = Field(
        default_factory=dict, description="post_id → 匹配理由列表"
    )
    scores: dict[int, float] = Field(
        default_factory=dict, description="post_id → 确定性分数（前端用于排序展示）"
    )
    fallback: bool = Field(False, description="是否已降级为普通搜索")
    fallback_reason: Optional[str] = Field(None, description="降级原因（可向用户展示）")
    ai_log_id: Optional[int] = Field(None, description="AI 调用日志 ID")
