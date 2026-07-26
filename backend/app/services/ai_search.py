"""AI-02.1: AI 搜索服务。

职责：
1. 输入校验：长度（schema 已强制）+ 频率（中间件限流）+ 敏感词检查
2. 意图解析：调用 invoke_ai（SEARCH_INTENT_SCHEMA 约束）→ 白名单校验分类/排序/时间/地图范围
3. 数据检索：openGauss 查询当前学校 published 且未过期未删除的帖子
4. 确定性排序：时间新鲜度（40%）+ 验证数（30%）+ 相关度（30%）
5. 理由生成：模板生成简短理由（不每次调模型）
6. 日志记录：通过 invoke_ai 自动记录 ai_invocation_logs + 补充 result_count
7. 降级：任一步失败 → fallback=true，返回普通搜索结果

安全约束：
- school_id 强制取自 TenantContext（三校隔离）
- 不向模型泄露其他学校数据（白名单只传当前学校的分类/地点）
- 不接受外部传入 school_id
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.ai.exceptions import OUTPUT_STATUS_SUCCESS
from app.ai.provider import AIInvokeOptions, AIProvider
from app.ai.schemas import SEARCH_INTENT_SCHEMA
from app.ai.service import invoke_ai, update_invocation_result
from app.core.tenant import TenantContext
from app.models.category import Category
from app.models.location import Location
from app.models.post import Post
from app.models.post_image import PostImage
from app.models.post_tag import PostTag
from app.models.user import User
from app.schemas.post import PostListResponse, TagBrief
from app.schemas.search import (
    AISearchIntent,
    AISearchIntentFilters,
    AISearchOverrides,
    AISearchRequest,
    AISearchResponse,
)

logger = logging.getLogger(__name__)


# ============================================================
# 常量
# ============================================================
# 允许的排序值（白名单）
_ALLOWED_SORTS = {"latest", "hottest", "nearest", "active", "relevance"}

# 敏感词基础清单（命中即降级普通搜索，不向模型发送）
# 注：生产环境应接入专门的内容安全服务，这里只做基础防护
_SENSITIVE_PATTERNS = [
    # 政治敏感
    re.compile(r"(?:法轮|六四|天安门|台独|港独|疆独|藏独)", re.IGNORECASE),
    # 暴力违法
    re.compile(r"(?:炸弹|枪支|毒品|杀人|自杀方法|恐怖袭击)", re.IGNORECASE),
    # 色情（基础过滤）
    re.compile(r"(?:黄色电影|裸聊|一夜情|找小姐)", re.IGNORECASE),
    # 个人隐私（避免用户在搜索框泄露他人隐私）
    re.compile(r"(?:身份证号|银行卡号|手机号\s*\d{7,})", re.IGNORECASE),
]

# 单次 AI 搜索允许的最大候选数（在内存中打分排序前先 SQL 限制）
_MAX_CANDIDATES = 200

# 确定性分数权重
_SCORE_WEIGHT_FRESHNESS = 0.4
_SCORE_WEIGHT_VALIDATION = 0.3
_SCORE_WEIGHT_RELEVANCE = 0.3

# 时间新鲜度衰减周期（天）：超过此天数后 freshness=0
_FRESHNESS_DECAY_DAYS = 30


# ============================================================
# 数据结构
# ============================================================
@dataclass
class _ScoredPost:
    """打分后的帖子中间结构。"""
    post: Post
    score: float
    match_reasons: list[str] = field(default_factory=list)


# ============================================================
# 1. 输入校验
# ============================================================
def _check_sensitive(text: str) -> Optional[str]:
    """敏感词检查。返回命中理由（None 表示通过）。"""
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(text):
            return "搜索内容包含敏感词，已降级普通搜索"
    return None


def _is_too_frequent() -> bool:
    """频率检查占位：实际限流由 RateLimitMiddleware 完成（10 次/分钟）。

    保留此函数便于未来扩展（如基于用户的更细粒度限流）。
    """
    return False


# ============================================================
# 2. 意图解析
# ============================================================
def _build_prompt(
    query: str,
    categories: list[Category],
    locations: list[Location],
) -> str:
    """构造模型提示词。

    提示词包含：
    - 任务说明（返回严格 JSON）
    - 当前学校可用的分类白名单（防止模型编造不存在的分类）
    - 当前学校可用的地点白名单（防止模型编造不存在的地点）
    - 当前日期（便于解析"最近一周"等时间表述）
    - 用户的自然语言查询
    """
    now = datetime.now().strftime("%Y-%m-%d")
    cat_list = "、".join(f"{c.name}（code={c.code}）" for c in categories[:30]) or "（暂无分类）"
    loc_list = "、".join(c.name for c in locations[:30]) or "（暂无地点）"

    return f"""你是校园信息搜索助手。请把用户的自然语言查询解析为结构化搜索意图。

# 任务
将用户查询转换为 JSON，字段如下：
{{
  "intent": "用户意图的自然语言概述（一句话）",
  "filters": {{
    "keyword": "用于检索的关键词（提取核心名词，去除停用词；可空）",
    "category": "分类名称（必须从下方分类白名单中选取；用户未明确则填 null）",
    "sort": "排序方式：latest（最新）/ hottest（最热）/ nearest（最近活动）/ active（综合活动）/ relevance（相关度）；默认 latest",
    "date_from": "起始日期 ISO 字符串（如 2026-07-01T00:00:00）；用户提到时间范围时填，否则 null",
    "date_to": "截止日期 ISO 字符串；用户提到时间范围时填，否则 null",
    "map_bounds": {{"north": 数字, "south": 数字, "east": 数字, "west": 数字}}
  }},
  "reasons": ["整体匹配理由（1-3 条简短说明）"]
}}

# 重要约束
1. category 必须从下方分类白名单中选取，不得编造不存在的分类
2. 不得编造不存在的地点/时间/活动名称
3. map_bounds 仅在用户明确提到地理范围（如"图书馆附近"）时填，否则填 null
4. 如果用户查询过于模糊或无法解析，filters 内字段可全部为 null，intent 填用户原话
5. 只返回 JSON，不要任何额外文字

# 上下文
- 当前日期：{now}
- 当前学校可用分类：{cat_list}
- 当前学校可用地点：{loc_list}

# 用户查询
{query}
"""


async def _load_whitelists(
    db: AsyncSession,
    school_id: int,
) -> tuple[list[Category], list[Location]]:
    """加载当前学校的分类与地点白名单（用于提示词与解析后校验）。"""
    cat_result = await db.execute(
        select(Category)
        .where(Category.school_id == school_id, Category.is_active == True)
        .order_by(Category.sort_order, Category.id)
    )
    categories = list(cat_result.scalars().all())

    loc_result = await db.execute(
        select(Location)
        .where(Location.school_id == school_id, Location.is_deleted == False)
        .order_by(Location.name)
    )
    locations = list(loc_result.scalars().all())

    return categories, locations


def _parse_datetime(value: Any) -> Optional[datetime]:
    """安全解析 ISO 日期时间字符串。失败返回 None。"""
    if value is None or not isinstance(value, str):
        return None
    try:
        # 兼容带/不带时区的 ISO 字符串
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _validate_intent(
    parsed: dict[str, Any],
    categories: list[Category],
    locations: list[Location],
    overrides: Optional[AISearchOverrides],
) -> AISearchIntent:
    """对模型解析结果做白名单校验，并应用用户 overrides。

    校验规则：
    - category：必须在白名单中（按 name 或 code 匹配）；非法值置空
    - sort：必须在 _ALLOWED_SORTS 中；非法值回退 latest
    - date_from / date_to：解析失败置空
    - map_bounds：四字段齐全且数值合理才采用
    - overrides：提供时覆盖 AI 解析结果（不再调模型）
    """
    filters_data = parsed.get("filters") or {}

    # 关键词
    keyword = filters_data.get("keyword") or None
    if isinstance(keyword, str):
        keyword = keyword.strip()[:100] or None

    # 分类白名单校验
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    raw_category = filters_data.get("category")
    if raw_category and isinstance(raw_category, str):
        # 按 name 或 code 匹配
        matched = next(
            (c for c in categories if c.name == raw_category or c.code == raw_category),
            None,
        )
        if matched is not None:
            category_id = matched.id
            category_name = matched.name
        # 非法值直接丢弃（不向用户报错，降级为不按分类筛选）

    # 排序白名单校验
    sort = filters_data.get("sort") or "latest"
    if sort not in _ALLOWED_SORTS:
        sort = "latest"

    # 时间解析
    date_from = _parse_datetime(filters_data.get("date_from"))
    date_to = _parse_datetime(filters_data.get("date_to"))

    # 地图范围校验
    map_bounds: Optional[dict[str, float]] = None
    raw_bounds = filters_data.get("map_bounds")
    if isinstance(raw_bounds, dict):
        try:
            north = float(raw_bounds.get("north"))
            south = float(raw_bounds.get("south"))
            east = float(raw_bounds.get("east"))
            west = float(raw_bounds.get("west"))
            # 基本合理性校验
            if north > south and east > west and -90 <= south < north <= 90 and -180 <= west < east <= 180:
                map_bounds = {"north": north, "south": south, "east": east, "west": west}
        except (TypeError, ValueError):
            map_bounds = None

    # 应用用户 overrides（覆盖 AI 解析结果）
    if overrides is not None:
        if overrides.keyword is not None:
            keyword = overrides.keyword.strip()[:100] or None
        if overrides.category_id is not None:
            # 校验 overrides.category_id 属于当前学校
            matched = next((c for c in categories if c.id == overrides.category_id), None)
            if matched is not None:
                category_id = matched.id
                category_name = matched.name
            else:
                # 非法 category_id 置空
                category_id = None
                category_name = None
        if overrides.location_id is not None:
            # location_id 由 API 层注入 filters，这里不直接覆盖（保留 AI 的 map_bounds）
            pass
        if overrides.sort is not None and overrides.sort in _ALLOWED_SORTS:
            sort = overrides.sort
        if overrides.date_from is not None:
            date_from = overrides.date_from
        if overrides.date_to is not None:
            date_to = overrides.date_to

    filters = AISearchIntentFilters(
        keyword=keyword,
        category_id=category_id,
        category_name=category_name,
        location_id=None,  # 由 overrides 单独处理（location_id 不来自模型）
        sort=sort,
        date_from=date_from,
        date_to=date_to,
        map_bounds=map_bounds,
    )

    reasons_list = parsed.get("reasons") or []
    if not isinstance(reasons_list, list):
        reasons_list = []
    reasons = [str(r) for r in reasons_list if r][:5]

    return AISearchIntent(
        intent=str(parsed.get("intent") or "搜索"),
        filters=filters,
        reasons=reasons,
    )


# ============================================================
# 3. 数据检索
# ============================================================
async def _query_posts(
    db: AsyncSession,
    tenant: TenantContext,
    intent: AISearchIntent,
    overrides: Optional[AISearchOverrides],
) -> list[Post]:
    """根据意图查询当前学校 published 且未过期未删除的帖子。

    严格过滤：
    - school_id = tenant.school_id（三校隔离）
    - is_deleted = False
    - status = 'published'（AI 搜索只检索已发布，不含 expired）
    - expire_at IS NULL OR expire_at > now（未过期）
    """
    school_id = tenant.school_id
    filters = intent.filters
    now = datetime.now()

    query = select(Post).where(
        Post.is_deleted == False,
        Post.status == "published",
        Post.school_id == school_id,
        or_(Post.expire_at.is_(None), Post.expire_at > now),
    )

    # 关键词模糊匹配
    keyword = filters.keyword
    if keyword:
        keyword_pattern = f"%{keyword}%"
        query = query.where(
            or_(
                Post.title.ilike(keyword_pattern),
                Post.content.ilike(keyword_pattern),
                Post.contact_info.ilike(keyword_pattern),
            )
        )

    # 分类筛选
    if filters.category_id is not None:
        query = query.where(Post.category_id == filters.category_id)

    # overrides 中的 location_id 直接覆盖（AI 不解析 location_id）
    if overrides is not None and overrides.location_id is not None:
        query = query.where(Post.location_id == overrides.location_id)
    elif filters.location_id is not None:
        query = query.where(Post.location_id == filters.location_id)

    # 时间范围
    if filters.date_from is not None:
        query = query.where(Post.created_at >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(Post.created_at <= filters.date_to)

    # 地图范围（通过 join Location 过滤坐标）
    if filters.map_bounds is not None:
        b = filters.map_bounds
        # 子查询：当前学校且在范围内的 location_id 集合
        loc_subq = select(Location.id).where(
            Location.school_id == school_id,
            Location.is_deleted == False,
            Location.latitude <= b["north"],
            Location.latitude >= b["south"],
            Location.longitude <= b["east"],
            Location.longitude >= b["west"],
        )
        query = query.where(Post.location_id.in_(loc_subq))

    # 限制候选数（避免大结果集在内存中打分过慢）
    query = query.limit(_MAX_CANDIDATES)

    # 预加载关联（与 posts 列表保持一致，消除 N+1）
    query = query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        joinedload(Post.post_type),
        selectinload(Post.post_tags).selectinload(PostTag.tag),
        selectinload(Post.post_images),
    )

    result = await db.execute(query)
    return list(result.unique().scalars().all())


# ============================================================
# 4. 确定性打分
# ============================================================
def _compute_score(
    post: Post,
    keyword: Optional[str],
    now: datetime,
) -> tuple[float, list[str]]:
    """计算确定性分数 + 生成单条匹配理由。

    分数 = 0.4 * 时间新鲜度 + 0.3 * 验证数 + 0.3 * 相关度
    取值范围 [0, 1]，确定性（同输入同输出）。

    Returns:
        (score, match_reasons)
    """
    reasons: list[str] = []

    # ---- 时间新鲜度 ----
    days_old = max(0.0, (now - post.created_at).total_seconds() / 86400.0)
    freshness = max(0.0, 1.0 - days_old / _FRESHNESS_DECAY_DAYS)
    if days_old < 1:
        reasons.append("今日发布")
    elif days_old < 7:
        reasons.append(f"{int(days_old)} 天内发布")
    elif days_old < 30:
        reasons.append("近一个月发布")

    # ---- 验证数 ----
    # Post.valid_count 为证实票数；invalid_count 为证伪票数
    confirmation = max(0, post.valid_count)
    validation_score = min(confirmation, 10) / 10.0
    if confirmation > 0:
        reasons.append(f"获 {confirmation} 次证实")

    # ---- 相关度 ----
    relevance = 0.5  # 默认中性
    if keyword:
        kw_lower = keyword.lower()
        title_lower = (post.title or "").lower()
        content_lower = (post.content or "").lower()
        contact_lower = (post.contact_info or "").lower()
        if kw_lower in title_lower:
            relevance = 1.0
            reasons.append(f"标题包含「{keyword}」")
        elif kw_lower in content_lower:
            relevance = 0.6
            reasons.append(f"内容描述匹配「{keyword}」")
        elif kw_lower in contact_lower:
            relevance = 0.3
            reasons.append(f"联系方式匹配「{keyword}」")
        else:
            # 关键词未直接匹配（可能因筛选条件命中，如分类/时间）
            relevance = 0.4
    else:
        # 无关键词时，相关度由其他因素决定，保持中性
        relevance = 0.5

    # ---- 关联信息理由 ----
    if post.location is not None and post.location.name:
        reasons.append(f"地点：{post.location.name}")
    if post.category is not None and post.category.name:
        reasons.append(f"分类：{post.category.name}")
    if post.like_count > 0:
        reasons.append(f"{post.like_count} 人点赞")

    score = (
        _SCORE_WEIGHT_FRESHNESS * freshness
        + _SCORE_WEIGHT_VALIDATION * validation_score
        + _SCORE_WEIGHT_RELEVANCE * relevance
    )
    # 保留 4 位小数，确保确定性
    score = round(score, 4)
    return score, reasons


def _sort_posts(
    posts: list[Post],
    keyword: Optional[str],
    sort: str,
    now: datetime,
) -> list[_ScoredPost]:
    """对候选帖子打分并排序。

    - sort=relevance：按确定性分数降序
    - sort=latest：按 created_at 降序（分数仍计算用于展示）
    - sort=hottest：按 like_count 降序
    - sort=active：按 updated_at 降序
    - sort=nearest：按 updated_at 降序（与 DSC-01 语义一致）
    """
    scored: list[_ScoredPost] = []
    for p in posts:
        score, reasons = _compute_score(p, keyword, now)
        scored.append(_ScoredPost(post=p, score=score, match_reasons=reasons))

    if sort == "relevance":
        scored.sort(key=lambda x: (-x.score, -x.post.created_at.timestamp()))
    elif sort == "latest":
        scored.sort(key=lambda x: (-x.post.created_at.timestamp(), -x.score))
    elif sort == "hottest":
        scored.sort(key=lambda x: (-x.post.like_count, -x.post.created_at.timestamp()))
    elif sort == "active":
        scored.sort(key=lambda x: (-x.post.updated_at.timestamp(), -x.post.created_at.timestamp()))
    elif sort == "nearest":
        scored.sort(key=lambda x: (-x.post.updated_at.timestamp(), -x.score))
    else:
        scored.sort(key=lambda x: (-x.score, -x.post.created_at.timestamp()))

    return scored


# ============================================================
# 5. 响应构造
# ============================================================
def _to_post_list_response(post: Post) -> PostListResponse:
    """将 Post ORM 对象转为 PostListResponse（与 posts 列表保持一致）。"""
    post_data = PostListResponse.model_validate(post)
    if post.is_anonymous:
        post_data.author = None
    elif post.user:
        post_data.author = {
            "id": post.user.id,
            "nickname": post.user.nickname,
            "avatar_url": post.user.avatar_url,
        }
    if post.post_images:
        post_data.cover_image = post.post_images[0].image_url
    if post.post_tags:
        post_data.tags = [
            TagBrief.model_validate(pt.tag)
            for pt in post.post_tags
            if pt.tag
        ]
    return post_data


def _paginate(items: list[Any], page: int, page_size: int) -> tuple[list[Any], int, int, bool]:
    """内存分页（已通过 SQL limit 限制候选数）。返回 (page_items, total, total_pages, has_more)。"""
    total = len(items)
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    has_more = page < total_pages
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total, total_pages, has_more


# ============================================================
# 6. 降级普通搜索
# ============================================================
async def _fallback_search(
    db: AsyncSession,
    tenant: TenantContext,
    query: str,
    overrides: Optional[AISearchOverrides],
    page: int,
    page_size: int,
    fallback_reason: str,
    ai_log_id: Optional[int],
) -> AISearchResponse:
    """降级为普通搜索：用 query 作为关键词，应用 overrides 中的筛选项。"""
    school_id = tenant.school_id
    now = datetime.now()

    # 关键词：优先 overrides，其次用原始 query
    keyword = None
    if overrides is not None and overrides.keyword is not None:
        keyword = overrides.keyword.strip()[:100] or None
    elif query:
        keyword = query.strip()[:100] or None

    base_query = select(Post).where(
        Post.is_deleted == False,
        Post.status == "published",
        Post.school_id == school_id,
        or_(Post.expire_at.is_(None), Post.expire_at > now),
    )

    if keyword:
        kw_pattern = f"%{keyword}%"
        base_query = base_query.where(
            or_(
                Post.title.ilike(kw_pattern),
                Post.content.ilike(kw_pattern),
                Post.contact_info.ilike(kw_pattern),
            )
        )

    if overrides is not None:
        if overrides.category_id is not None:
            base_query = base_query.where(Post.category_id == overrides.category_id)
        if overrides.location_id is not None:
            base_query = base_query.where(Post.location_id == overrides.location_id)
        if overrides.date_from is not None:
            base_query = base_query.where(Post.created_at >= overrides.date_from)
        if overrides.date_to is not None:
            base_query = base_query.where(Post.created_at <= overrides.date_to)

    # 排序：降级场景按 latest（与普通搜索默认一致）
    sort = "latest"
    if overrides is not None and overrides.sort in {"latest", "hottest", "nearest", "active"}:
        sort = overrides.sort
    if sort == "latest":
        base_query = base_query.order_by(Post.created_at.desc())
    elif sort == "hottest":
        base_query = base_query.order_by(Post.like_count.desc(), Post.created_at.desc())
    elif sort == "active":
        base_query = base_query.order_by(Post.updated_at.desc(), Post.created_at.desc())
    elif sort == "nearest":
        base_query = base_query.order_by(Post.updated_at.desc())

    # 总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    base_query = base_query.offset(offset).limit(page_size)
    base_query = base_query.options(
        joinedload(Post.user),
        joinedload(Post.category),
        joinedload(Post.location),
        joinedload(Post.post_type),
        selectinload(Post.post_tags).selectinload(PostTag.tag),
        selectinload(Post.post_images),
    )

    result = await db.execute(base_query)
    posts = list(result.unique().scalars().all())

    items = [_to_post_list_response(p) for p in posts]
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    has_more = page < total_pages

    # 更新日志的 result_count（如果 log_id 存在）
    if ai_log_id is not None:
        try:
            await update_invocation_result(
                db, ai_log_id,
                candidate_count=total,
                result_count=len(items),
                fallback_reason=fallback_reason,
            )
        except Exception:  # noqa: BLE001  日志更新失败不影响主流程
            logger.warning("update_invocation_result failed in fallback ai_log_id=%s", ai_log_id)

    return AISearchResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_more=has_more,
        intent=None,
        match_reasons={},
        scores={},
        fallback=True,
        fallback_reason=fallback_reason,
        ai_log_id=ai_log_id,
    )


# ============================================================
# 7. 主入口
# ============================================================
async def execute_ai_search(
    request: AISearchRequest,
    tenant: TenantContext,
    db: AsyncSession,
    user: Optional[User] = None,
    trace_id: Optional[str] = None,
    provider: Optional[AIProvider] = None,
) -> AISearchResponse:
    """AI 搜索主入口。

    流程：
    1. 敏感词检查 → 命中降级
    2. 加载白名单（分类/地点）
    3. overrides 提供时跳过模型调用，直接构造意图
    4. 否则调用 invoke_ai 解析意图 → 白名单校验
    5. 查询当前学校 published 未过期未删除帖子
    6. 确定性打分 + 排序
    7. 模板理由生成
    8. 分页 + 返回响应
    9. 任一步失败 → 降级普通搜索
    """
    query = request.query.strip()
    page = request.page
    page_size = request.page_size
    overrides = request.overrides

    # ---- 1. 敏感词检查 ----
    sensitive_hit = _check_sensitive(query)
    if sensitive_hit is not None:
        return await _fallback_search(
            db, tenant, query, overrides, page, page_size,
            fallback_reason=sensitive_hit,
            ai_log_id=None,
        )

    # ---- 2. 加载白名单 ----
    try:
        categories, locations = await _load_whitelists(db, tenant.school_id)
    except Exception as exc:  # noqa: BLE001  DB 异常降级
        logger.warning("ai_search_load_whitelist_failed school_id=%s err=%s", tenant.school_id, exc)
        return await _fallback_search(
            db, tenant, query, overrides, page, page_size,
            fallback_reason="AI 服务暂时不可用，已降级普通搜索",
            ai_log_id=None,
        )

    # ---- 3/4. 意图解析 ----
    intent: Optional[AISearchIntent] = None
    ai_log_id: Optional[int] = None

    if overrides is not None and overrides.keyword is not None:
        # 用户提供 overrides 且明确覆盖 keyword → 不调模型
        intent = _validate_intent(
            {"intent": query, "filters": {}, "reasons": []},
            categories, locations, overrides,
        )
    else:
        # 调用模型解析
        prompt = _build_prompt(query, categories, locations)
        outcome = await invoke_ai(
            prompt=prompt,
            schema=SEARCH_INTENT_SCHEMA,
            scene="search_intent",
            tenant=tenant,
            db=db,
            user=user,
            options=AIInvokeOptions(temperature=0.1, max_tokens=600),
            trace_id=trace_id,
            provider=provider,
        )
        ai_log_id = outcome.log_id

        if outcome.fallback or outcome.response is None:
            # 模型失败 → 降级普通搜索
            fallback_reason = outcome.fallback_reason or "AI 服务暂时不可用，已降级普通搜索"
            return await _fallback_search(
                db, tenant, query, overrides, page, page_size,
                fallback_reason=fallback_reason,
                ai_log_id=ai_log_id,
            )

        # 白名单校验
        try:
            parsed = outcome.response.parsed
            if not isinstance(parsed, dict):
                raise ValueError("parsed intent is not a dict")
            intent = _validate_intent(parsed, categories, locations, overrides)
        except Exception as exc:  # noqa: BLE001  校验失败降级
            logger.warning("ai_search_validate_intent_failed school_id=%s err=%s",
                           tenant.school_id, exc)
            return await _fallback_search(
                db, tenant, query, overrides, page, page_size,
                fallback_reason="AI 输出解析失败，已降级普通搜索",
                ai_log_id=ai_log_id,
            )

    assert intent is not None  # 上面两个分支必赋值

    # ---- 5. 查询 ----
    try:
        posts = await _query_posts(db, tenant, intent, overrides)
    except Exception as exc:  # noqa: BLE001  查询失败降级
        logger.warning("ai_search_query_failed school_id=%s err=%s", tenant.school_id, exc)
        return await _fallback_search(
            db, tenant, query, overrides, page, page_size,
            fallback_reason="AI 检索失败，已降级普通搜索",
            ai_log_id=ai_log_id,
        )

    # ---- 6. 打分 + 排序 ----
    try:
        now = datetime.now()
        sort = intent.filters.sort
        scored_posts = _sort_posts(posts, intent.filters.keyword, sort, now)
    except Exception as exc:  # noqa: BLE001  打分失败降级
        logger.warning("ai_search_score_failed school_id=%s err=%s", tenant.school_id, exc)
        return await _fallback_search(
            db, tenant, query, overrides, page, page_size,
            fallback_reason="AI 排序失败，已降级普通搜索",
            ai_log_id=ai_log_id,
        )

    # ---- 7/8. 分页 + 响应构造 ----
    total = len(scored_posts)
    page_items, _, total_pages, has_more = _paginate(scored_posts, page, page_size)

    items: list[Any] = []
    match_reasons: dict[int, list[str]] = {}
    scores: dict[int, float] = {}
    for sp in page_items:
        post_resp = _to_post_list_response(sp.post)
        items.append(post_resp)
        match_reasons[sp.post.id] = sp.match_reasons
        scores[sp.post.id] = sp.score

    # 整体意图理由补充（无关键词时给出友好说明）
    intent_reasons = list(intent.reasons)
    if not intent_reasons:
        intent_reasons.append(_build_default_intent_reason(intent, total))

    final_intent = AISearchIntent(
        intent=intent.intent,
        filters=intent.filters,
        reasons=intent_reasons,
    )

    # ---- 9. 更新日志 result_count ----
    if ai_log_id is not None:
        try:
            await update_invocation_result(
                db, ai_log_id,
                candidate_count=total,
                result_count=len(items),
            )
        except Exception:  # noqa: BLE001  日志更新失败不影响主流程
            logger.warning("update_invocation_result failed ai_log_id=%s", ai_log_id)

    return AISearchResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_more=has_more,
        intent=final_intent,
        match_reasons=match_reasons,
        scores=scores,
        fallback=False,
        fallback_reason=None,
        ai_log_id=ai_log_id,
    )


def _build_default_intent_reason(intent: AISearchIntent, total: int) -> str:
    """无模型理由时生成默认理由。"""
    parts: list[str] = []
    if intent.filters.keyword:
        parts.append(f"按关键词「{intent.filters.keyword}」检索")
    if intent.filters.category_name:
        parts.append(f"分类筛选：{intent.filters.category_name}")
    if intent.filters.date_from or intent.filters.date_to:
        parts.append("限定时间范围")
    if not parts:
        parts.append("按相关度排序")
    parts.append(f"共 {total} 条结果")
    return "，".join(parts)
