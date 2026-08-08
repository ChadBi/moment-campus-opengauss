"""AI-03: AI 辅助发布建议 Schema。

定义 AI 辅助发布建议的请求/响应模型：
- AIPublishSuggestRequest：草稿内容（标题/正文/当前分类/地点等），用于请求 AI 建议
- AIPublishSuggestions：AI 返回的结构化建议（标题/正文优化、摘要/分类/标签/默认信息截止天数）
- AIPublishSuggestionResponse：完整响应（建议 + 遗漏信息 + 敏感提醒 + 降级标记）

设计原则：
1. 所有字段都不可信 → service 层接收后再做白名单/范围校验。
2. fallback=true 时 suggestions 仍可能存在（部分降级场景）或为 None（完全降级）
3. 不修改原文：响应只返回"建议"，是否采纳由用户在前端逐项确认
4. 不自动过审：本接口仅生成建议，不修改帖子状态、不修改坐标
5. 失败不阻塞：fallback=true 时前端仍可继续手动发布
"""
from __future__ import annotations

from typing import Optional, List, Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# AI-03.1: 请求
# ============================================================
class AIPublishSuggestRequest(BaseModel):
    """AI 发布建议请求体。

    字段全部可选（用户可能只填了标题就开始请求建议）：
    - title / content：草稿正文（必填，至少有标题或内容才好建议）
    - category_id：当前已选分类（用于推断默认信息截止天数）
    - location_id：当前已选地点
    - tags：当前已填标签
    - contact_info：联系方式（用于敏感信息检测）
    - lost_type：失物类型
    - expire_at：当前已设置的信息截止时间
    """

    title: str = Field("", max_length=200, description="草稿标题")
    content: str = Field("", max_length=5000, description="草稿正文")
    category_id: Optional[int] = Field(None, description="当前已选分类ID")
    location_id: Optional[int] = Field(None, description="当前已选地点ID")
    tags: Optional[List[str]] = Field(None, max_length=5, description="当前已填标签列表")
    contact_info: Optional[str] = Field(None, max_length=255, description="联系方式（用于敏感信息检测）")
    lost_type: Optional[str] = Field(None, max_length=10, description="失物类型 lost/found")
    expire_at: Optional[str] = Field(None, description="当前已设置的信息截止时间（ISO 字符串）")


# ============================================================
# AI-03.1: 响应
# ============================================================
class AIPublishSuggestions(BaseModel):
    """AI 返回的结构化建议（每项均可空，表示无建议）。

    - title：建议标题（兼容旧版字段；仅在原文标题较弱时给出）
    - optimized_title：优化后的标题（不改变事实；无需优化时为 null）
    - optimized_content：优化后的正文（不新增事实；无需优化时为 null）
    - summary：建议摘要（适合列表展示 / SEO）
    - category：建议分类名（白名单校验后转为 category_id；非法值置空）
    - tags：建议标签列表（白名单校验后只保留当前学校存在的标签）
    - default_validity_days：建议默认信息截止天数（来自当前学校分类配置）
    """

    title: Optional[str] = Field(None, description="建议标题（仅在原文标题较弱时给出）")
    optimized_title: Optional[str] = Field(
        None, description="优化后的标题（不改变事实；无需优化时为空）"
    )
    optimized_content: Optional[str] = Field(
        None, description="优化后的正文（不新增事实；无需优化时为空）"
    )
    summary: Optional[str] = Field(None, description="建议摘要")
    category: Optional[str] = Field(None, description="建议分类名（白名单校验前的原始值）")
    category_id: Optional[int] = Field(
        None, description="建议分类ID（白名单校验后的最终值；非法置空）"
    )
    tags: List[str] = Field(default_factory=list, description="建议标签列表（白名单校验后的最终值）")
    default_validity_days: Optional[int] = Field(
        None, description="建议默认信息截止天数（来自当前学校分类配置）"
    )


class AIPublishSuggestionResponse(BaseModel):
    """AI 发布建议响应。

    - suggestions：结构化建议（降级时可能为 None）
    - missing_info：遗漏信息提示（前端逐项展示）
    - sensitive_warnings：敏感信息提醒（前端高亮展示）
    - sensitive_findings：敏感信息命中明细（type→matched 串列表，便于前端定位）
    - fallback：是否已降级（AI 失败 / 敏感词命中 / 输入过短等）
    - fallback_reason：降级原因（可向用户展示）
    - ai_log_id：AI 调用日志 ID（便于排查）
    """

    suggestions: Optional[AIPublishSuggestions] = Field(None, description="结构化建议（降级时可能为 None）")
    missing_info: List[str] = Field(default_factory=list, description="遗漏信息提示")
    sensitive_warnings: List[str] = Field(default_factory=list, description="敏感信息提醒")
    sensitive_findings: dict[str, List[str]] = Field(
        default_factory=dict,
        description="敏感信息命中明细 type→[matched...]，便于前端定位高亮",
    )
    fallback: bool = Field(False, description="是否已降级（AI 失败 / 敏感词命中 / 输入过短等）")
    fallback_reason: Optional[str] = Field(None, description="降级原因（可向用户展示）")
    ai_log_id: Optional[int] = Field(None, description="AI 调用日志 ID（便于排查）")
