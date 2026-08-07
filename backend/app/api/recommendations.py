"""REC-01: 推荐接口

- GET /api/v1/recommendations —— 首页"为你推荐"
  - 登录用户开启个性化且有足够历史：基于浏览/搜索/订阅/新鲜度/验证结果打分
  - 游客 / 关闭个性化 / 历史不足：冷启动（本校热门 + 最新 + 管理员推荐）
  - 每条结果附带推荐原因 reason 与 score
  - 多租户隔离：所有查询按 tenant.school_id 过滤

- GET /api/v1/users/me/recommendation-preferences —— 获取个性化开关
- PUT /api/v1/users/me/recommendation-preferences —— 更新个性化开关（关闭时清除浏览历史）
- DELETE /api/v1/users/me/recommendation-history —— 清除推荐画像历史（浏览+搜索）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from math import ceil

from app.database import get_db
from app.dependencies import get_current_user, get_current_user_optional
from app.models.post import Post
from app.models.user import User
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.post import PostListResponse
from app.core.tenant import TenantContext, get_tenant_context
from app.core.identity_mask import apply_author_mask
from app.services.recommender import (
    get_recommendations,
    get_preference,
    update_preference,
)


router = APIRouter(tags=["推荐"])


# ============================================================
# 响应模型
# ============================================================
class RecommendationItem(PostListResponse):
    """推荐项 = PostListResponse + 推荐原因 + 综合分"""

    # reason / score 给默认值，避免 model_validate(Post) 时因缺少字段校验失败；
    # 实际值在 API 层从 ScoredPost 注入。
    reason: str = Field(default="", description="推荐原因（基于浏览历史/订阅/最新发布/热门/管理员推荐 等）")
    score: float = Field(default=0.0, description="综合分（确定性，可用于调试）")


class RecommendationMode(BaseModel):
    """推荐模式说明（前端用于展示当前是"个性化"还是"冷启动"）"""

    personalized: bool = Field(..., description="是否为个性化推荐（True=画像打分；False=冷启动）")
    reason_code: str = Field(
        ...,
        description="模式代码：personalized / cold_start_no_history / cold_start_disabled / cold_start_guest",
    )


class RecommendationResponse(BaseModel):
    """推荐列表响应（含模式说明）"""

    items: list[RecommendationItem] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)
    total: int = Field(default=0, ge=0)
    total_pages: int = Field(default=0, ge=0)
    has_more: bool = Field(default=False)
    mode: RecommendationMode = Field(..., description="推荐模式说明")


# ============================================================
# 推荐接口
# ============================================================
@router.get(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="REC-01.1: 首页为你推荐",
)
async def get_recommendation_feed(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=50, description="每页数量"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """获取"为你推荐"列表

    **REC-01.1 首页推荐**：
    - 登录用户开启个性化且浏览历史 ≥ 3 条：基于浏览/搜索/订阅/新鲜度/验证结果做确定性排序
    - 游客 / 关闭个性化 / 历史不足：冷启动（本校热门 + 最新 + 管理员推荐）
    - 每条结果附带推荐原因（基于浏览历史/订阅/最新发布/热门/管理员推荐 等）

    **REC-01.2 隐私**：
    - 关闭个性化后：不再使用浏览/搜索画像打分，但仍可看本校热门/最新/管理员推荐
    - 切换学校后：推荐理由与数据随租户变化（TEN-02.3 多租户隔离）

    **可见性**：仅返回当前学校 published / expired 帖子（与 /posts 列表一致）
    """
    offset = (page - 1) * page_size
    result = await get_recommendations(
        db, tenant, current_user, limit=page_size, offset=offset
    )

    # 构建响应项
    items: list[RecommendationItem] = []
    for s in result.items:
        post = s.post
        # 先用 model_validate 从 Post 构建基础字段（PostListResponse 部分），
        # 再注入 reason / score（避免 required 字段校验失败）
        item = RecommendationItem.model_validate(post)
        # 身份脱敏：匿名本人/管理员豁免可见真实作者
        apply_author_mask(item, post, current_user)
        # 封面图（取第一张）
        if post.post_images:
            item.cover_image = post.post_images[0].image_url
        item.reason = s.reason
        item.score = s.score
        items.append(item)

    # 推荐模式（直接使用服务返回的 reason_code，避免重复查询画像）
    mode = RecommendationMode(
        personalized=result.personalized,
        reason_code=result.reason_code,
    )

    # 计算分页元数据
    total_pages = ceil(result.total / page_size) if page_size > 0 else 0
    has_more = page < total_pages

    return RecommendationResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=result.total,
        total_pages=total_pages,
        has_more=has_more,
        mode=mode,
    )


# ============================================================
# 推荐隐私偏好接口
# ============================================================
class RecommendationPreferenceResponse(BaseModel):
    """推荐隐私偏好响应"""

    personalization_enabled: bool = Field(
        ..., description="是否启用个性化推荐"
    )
    updated_at: datetime = Field(..., description="最近更新时间")


class RecommendationPreferenceUpdate(BaseModel):
    """推荐隐私偏好更新请求

    关闭个性化时：后端会同步清除当前用户在所有学校的浏览历史（隐私要求）。
    """

    personalization_enabled: bool = Field(..., description="是否启用个性化推荐")


@router.get(
    "/users/me/recommendation-preferences",
    response_model=RecommendationPreferenceResponse,
    summary="REC-01.2: 获取推荐隐私偏好",
)
async def get_my_recommendation_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户推荐隐私偏好

    首次访问自动 upsert 默认行（personalization_enabled=True）。
    偏好按 user_id 隔离，跨校共用同一份开关（隐私设置不随学校切换而变）。
    """
    pref = await get_preference(db, current_user.id)
    await db.commit()
    return RecommendationPreferenceResponse(
        personalization_enabled=pref.personalization_enabled,
        updated_at=pref.updated_at,
    )


@router.put(
    "/users/me/recommendation-preferences",
    response_model=RecommendationPreferenceResponse,
    summary="REC-01.2: 更新推荐隐私偏好",
)
async def update_my_recommendation_preferences(
    payload: RecommendationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """更新当前用户推荐隐私偏好

    - 关闭个性化（personalization_enabled=False）：同步清除当前用户在所有学校的浏览历史
    - 开启个性化：不影响历史数据，重新开始积累画像
    - 关闭后：推荐接口走冷启动路径（本校热门 + 最新 + 管理员推荐）

    REC-01.2 隐私要求：
    - 用户可关闭个性化并清除历史
    - 关闭后普通热门/最新仍可用
    """
    pref = await update_preference(
        db, current_user.id, payload.personalization_enabled
    )
    await db.commit()
    await db.refresh(pref)

    return RecommendationPreferenceResponse(
        personalization_enabled=pref.personalization_enabled,
        updated_at=pref.updated_at,
    )


@router.delete(
    "/users/me/recommendation-history",
    response_model=MessageResponse,
    summary="REC-01.2: 清除推荐画像历史（浏览+搜索）",
)
async def clear_my_recommendation_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """清除当前用户的推荐画像历史（浏览历史 + 搜索历史）

    REC-01.2 隐私要求：
    - 用户可手动清除历史（不关闭个性化也能清除）
    - 清除后画像重建从零开始，下次推荐走冷启动
    - 仅清除当前用户数据，不影响其他用户

    注意：
    - 浏览历史按当前学校过滤清除（与 PRF-01.3 /users/me/view-history 一致）
    - 搜索历史不区分学校（搜索历史表无 school_id 字段），全部清除
    """
    from sqlalchemy import delete
    from app.models.browse_history import BrowseHistory
    from app.models.search_history import SearchHistory

    browse_result = await db.execute(
        delete(BrowseHistory).where(
            BrowseHistory.user_id == current_user.id,
            BrowseHistory.school_id == tenant.school_id,
        )
    )
    browse_deleted = browse_result.rowcount or 0

    search_result = await db.execute(
        delete(SearchHistory).where(SearchHistory.user_id == current_user.id)
    )
    search_deleted = search_result.rowcount or 0

    await db.commit()
    return MessageResponse(
        message=f"已清除 {browse_deleted} 条浏览历史与 {search_deleted} 条搜索历史",
        data={
            "browse_deleted": browse_deleted,
            "search_deleted": search_deleted,
            "school_id": tenant.school_id,
        },
    )
