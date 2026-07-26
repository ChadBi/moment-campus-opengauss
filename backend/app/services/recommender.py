"""REC-01: 租户级确定性推荐服务

设计原则（docs/33 8.8 SUB 与 5.2 推荐后端模块边界）：
1. 确定性排序，不依赖机器学习模型；同一输入 → 同一排序
2. 多租户隔离：所有查询按 tenant.school_id 过滤，跨校不污染
3. 个性化画像基于：浏览历史（PRF-01）/ 搜索历史 / 订阅（SUB-01）/ 验证结果（GOV-01）
4. 新鲜度：最近发布的帖子加权
5. 验证结果：证实数高的帖子加权（confirmation 票数）
6. 冷启动：新用户或关闭个性化时使用本校热门 / 最新 / 管理员推荐（is_recommend=True）
7. 关闭个性化后：普通热门/最新仍可用（不走画像打分）
8. 推荐原因：每条结果给出主要贡献因素（基于浏览历史/订阅/最新发布/热门/管理员推荐 等）

打分公式（确定性，可解释）：
    score = w_history * history_score        # 0..1，来自浏览/搜索画像匹配
          + w_subscription * sub_score       # 0..1，来自订阅分类/地点/专题
          + w_freshness * freshness_score    # 0..1，按 created_at 衰减
          + w_validation * validation_score  # 0..1，confirmation 票数归一化
          + w_hot * hot_score                # 0..1，浏览+点赞+评论归一化
          + w_admin * admin_bonus            # 0/1，is_recommend 加权

权重（可调）：
    w_history=3.0, w_subscription=2.0, w_freshness=1.5,
    w_validation=1.5, w_hot=1.0, w_admin=2.0
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.tenant import TenantContext
from app.models.browse_history import BrowseHistory
from app.models.post import Post
from app.models.post_tag import PostTag
from app.models.search_history import SearchHistory
from app.models.subscription import UserSubscription
from app.models.user import User
from app.models.user_recommendation_preference import UserRecommendationPreference
from app.models.validation_record import ValidationRecord


# ============================================================
# 权重与阈值
# ============================================================
WEIGHTS = {
    "history": 3.0,
    "subscription": 2.0,
    "freshness": 1.5,
    "validation": 1.5,
    "hot": 1.0,
    "admin": 2.0,
}

# 浏览历史回溯窗口（天）
HISTORY_LOOKBACK_DAYS = 30
# 搜索历史回溯窗口（天）
SEARCH_LOOKBACK_DAYS = 14
# 新鲜度半衰期（天）：created_at 距今 N 天内 freshness=1.0；之后按指数衰减
FRESHNESS_HALF_LIFE_DAYS = 7
# 个性化最小浏览数：低于此值视为冷启动
MIN_HISTORY_FOR_PERSONALIZATION = 3
# 验证数归一化上限（confirmation 票数达到此值即满分）
VALIDATION_NORM_MAX = 5
# 热度归一化上限（热度值达到此值即满分）
HOT_NORM_MAX = 50


# ============================================================
# 推荐模式（与 API 响应的 reason_code 对齐）
# ============================================================
# personalized:                 登录 + 开启个性化 + 历史足够 → 画像打分
# cold_start_no_history:        登录 + 开启个性化 + 历史不足 → 冷启动
# cold_start_disabled:          登录 + 关闭个性化             → 冷启动
# cold_start_guest:             游客                          → 冷启动
MODE_PERSONALIZED = "personalized"
MODE_COLD_NO_HISTORY = "cold_start_no_history"
MODE_COLD_DISABLED = "cold_start_disabled"
MODE_COLD_GUEST = "cold_start_guest"


# ============================================================
# 数据结构
# ============================================================
@dataclass
class ScoredPost:
    """打分后的帖子（含推荐原因）"""

    post: Post
    score: float
    reason: str
    # 各分项得分（用于调试与原因选取）
    breakdown: dict = field(default_factory=dict)


@dataclass
class UserProfile:
    """用户画像（基于浏览/搜索/订阅历史，按当前学校构建）

    跨校画像不污染：浏览/订阅仅取 school_id == tenant.school_id 的记录；
    搜索历史表无 school_id 字段，取全局但权重较低。
    """

    # 浏览过的分类 → 权重（按浏览次数 + 最近浏览时间加权）
    category_weights: dict[int, float] = field(default_factory=dict)
    # 浏览过的地点 → 权重
    location_weights: dict[int, float] = field(default_factory=dict)
    # 浏览过的帖子 ID 集合（用于排除已浏览）
    viewed_post_ids: set[int] = field(default_factory=set)
    # 搜索关键词列表（按频次排序，小写）
    top_keywords: list[str] = field(default_factory=list)
    # SUB-01: 订阅的分类/地点/专题 ID 集合（按当前学校过滤）
    subscribed_category_ids: set[int] = field(default_factory=set)
    subscribed_location_ids: set[int] = field(default_factory=set)
    subscribed_topic_ids: set[int] = field(default_factory=set)
    # 是否有足够历史做个性化
    has_enough_history: bool = False


@dataclass
class RecommendationResult:
    """推荐结果（含模式信息）

    让 API 层无需重新查询画像即可知道当前推荐模式。
    """

    items: list[ScoredPost]
    total: int
    personalized: bool
    reason_code: str


# ============================================================
# 公共入口
# ============================================================
async def get_recommendations(
    db: AsyncSession,
    tenant: TenantContext,
    current_user: Optional[User],
    *,
    limit: int = 10,
    offset: int = 0,
) -> RecommendationResult:
    """获取推荐列表

    Args:
        db: 异步数据库会话
        tenant: 租户上下文（决定 school_id 过滤）
        current_user: 当前用户（None 表示游客，走冷启动）
        limit: 返回条数
        offset: 偏移量（分页）

    Returns:
        RecommendationResult —— 含 items/total/personalized/reason_code

    Notes:
        - 游客：恒走冷启动（cold_start_guest）
        - 登录用户关闭个性化：走冷启动（cold_start_disabled）
        - 登录用户开启个性化但历史不足：走冷启动（cold_start_no_history）
        - 登录用户开启个性化且有足够历史：走画像打分（personalized）
        - 冷启动：管理员推荐（is_recommend=True）+ 热门 + 最新，按确定性规则排序
    """
    school_id = tenant.school_id

    # 判定是否走个性化
    use_personalization = False
    user_profile: Optional[UserProfile] = None
    if current_user is not None:
        pref = await _get_or_create_preference(db, current_user.id)
        if pref.personalization_enabled:
            user_profile = await _build_user_profile(db, tenant, current_user.id)
            use_personalization = user_profile.has_enough_history

    if use_personalization and user_profile is not None:
        items, total = await _personalized_recommendations(
            db, tenant, current_user, user_profile, limit=limit, offset=offset
        )
        return RecommendationResult(
            items=items,
            total=total,
            personalized=True,
            reason_code=MODE_PERSONALIZED,
        )

    items, total = await _cold_start_recommendations(
        db, tenant, limit=limit, offset=offset
    )
    # 区分冷启动原因
    if current_user is None:
        reason_code = MODE_COLD_GUEST
    elif user_profile is not None and not user_profile.has_enough_history:
        # 开启了个性化但历史不足
        reason_code = MODE_COLD_NO_HISTORY
    else:
        # 关闭了个性化（user_profile 为 None）
        reason_code = MODE_COLD_DISABLED
    return RecommendationResult(
        items=items,
        total=total,
        personalized=False,
        reason_code=reason_code,
    )


# ============================================================
# 偏好读写
# ============================================================
async def _get_or_create_preference(
    db: AsyncSession, user_id: int
) -> UserRecommendationPreference:
    """获取或创建用户推荐偏好（首次访问 upsert 默认行）"""
    result = await db.execute(
        select(UserRecommendationPreference).where(
            UserRecommendationPreference.user_id == user_id
        )
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = UserRecommendationPreference(user_id=user_id, personalization_enabled=True)
        db.add(pref)
        await db.flush()
    return pref


async def get_preference(
    db: AsyncSession, user_id: int
) -> UserRecommendationPreference:
    """公共入口：获取用户推荐偏好（不存在则创建默认）"""
    return await _get_or_create_preference(db, user_id)


async def update_preference(
    db: AsyncSession, user_id: int, personalization_enabled: bool
) -> UserRecommendationPreference:
    """更新个性化开关

    关闭个性化时：同步清除当前用户在所有学校的浏览历史（隐私要求：
    "关闭后不再用于推荐画像"，清除比"标记不用于"更彻底且符合用户预期）。
    """
    pref = await _get_or_create_preference(db, user_id)
    pref.personalization_enabled = personalization_enabled
    pref.updated_at = datetime.now()
    await db.flush()

    # 关闭个性化 → 清除浏览历史
    if not personalization_enabled:
        await db.execute(
            delete(BrowseHistory).where(BrowseHistory.user_id == user_id)
        )
    return pref


# ============================================================
# 用户画像构建
# ============================================================
async def _build_user_profile(
    db: AsyncSession, tenant: TenantContext, user_id: int
) -> UserProfile:
    """基于浏览/搜索/订阅历史构建用户画像（按当前学校隔离）"""
    profile = UserProfile()
    school_id = tenant.school_id
    now = datetime.now()
    history_since = now - timedelta(days=HISTORY_LOOKBACK_DAYS)
    search_since = now - timedelta(days=SEARCH_LOOKBACK_DAYS)

    # 1. 浏览历史（按当前学校过滤）—— 关联 Post 获取分类/地点
    browse_rows = (
        await db.execute(
            select(
                Post.category_id,
                Post.location_id,
                Post.id,
                BrowseHistory.viewed_at,
            )
            .select_from(BrowseHistory)
            .join(Post, Post.id == BrowseHistory.post_id)
            .where(
                BrowseHistory.user_id == user_id,
                BrowseHistory.school_id == school_id,
                BrowseHistory.viewed_at >= history_since,
                Post.is_deleted == False,
            )
            .order_by(BrowseHistory.viewed_at.desc())
            .limit(200)  # 上限保护：最多取最近 200 条
        )
    ).all()

    for category_id, location_id, post_id, viewed_at in browse_rows:
        # 时间衰减权重：最近浏览权重高
        days_ago = max((now - viewed_at).total_seconds() / 86400.0, 0.0)
        weight = max(1.0 - days_ago / HISTORY_LOOKBACK_DAYS, 0.1)
        if category_id is not None:
            profile.category_weights[category_id] = (
                profile.category_weights.get(category_id, 0.0) + weight
            )
        if location_id is not None:
            profile.location_weights[location_id] = (
                profile.location_weights.get(location_id, 0.0) + weight
            )
        profile.viewed_post_ids.add(post_id)

    profile.has_enough_history = (
        len(profile.viewed_post_ids) >= MIN_HISTORY_FOR_PERSONALIZATION
    )

    # 2. 搜索历史（不按学校过滤，但权重较低；用于补充关键词画像）
    search_rows = (
        await db.execute(
            select(SearchHistory.keyword, func.count(SearchHistory.id).label("cnt"))
            .where(
                SearchHistory.user_id == user_id,
                SearchHistory.created_at >= search_since,
            )
            .group_by(SearchHistory.keyword)
            .order_by(func.count(SearchHistory.id).desc())
            .limit(10)
        )
    ).all()
    profile.top_keywords = [
        (kw or "").strip().lower() for kw, _ in search_rows if (kw or "").strip()
    ]

    # 3. SUB-01: 订阅画像（按当前学校过滤，跨校订阅不污染）
    sub_rows = (
        await db.execute(
            select(UserSubscription.target_type, UserSubscription.target_id).where(
                UserSubscription.user_id == user_id,
                UserSubscription.school_id == school_id,
            )
        )
    ).all()
    for target_type, target_id in sub_rows:
        if target_type == "category":
            profile.subscribed_category_ids.add(target_id)
        elif target_type == "location":
            profile.subscribed_location_ids.add(target_id)
        elif target_type == "topic":
            profile.subscribed_topic_ids.add(target_id)

    return profile


# ============================================================
# 个性化推荐
# ============================================================
async def _personalized_recommendations(
    db: AsyncSession,
    tenant: TenantContext,
    current_user: User,
    profile: UserProfile,
    *,
    limit: int,
    offset: int,
) -> tuple[list[ScoredPost], int]:
    """个性化推荐：基于画像打分"""
    school_id = tenant.school_id

    # 候选池：当前学校 + published/expired + 未删除 + 排除已浏览（避免重复推荐）
    # 排除已浏览：让用户看到新内容；如已浏览过则不计入推荐（但仍可在浏览历史中查看）
    candidate_query = (
        select(Post)
        .where(
            Post.school_id == school_id,
            Post.is_deleted == False,
            Post.status.in_(["published", "expired"]),
        )
        .options(
            joinedload(Post.user),
            joinedload(Post.category),
            joinedload(Post.location),
            selectinload(Post.post_tags).selectinload(PostTag.tag),
            selectinload(Post.post_images),
        )
    )

    candidates = (await db.execute(candidate_query)).unique().scalars().all()
    if not candidates:
        return [], 0

    # 预取验证票数（按 post_id 聚合 confirmation）—— 一次性查全部候选
    validation_map = await _load_validation_counts(db, [p.id for p in candidates])

    # SUB-01: 若订阅了专题，预取这些专题包含的帖子 ID 集合（用于订阅画像匹配）
    topic_post_ids = await _load_subscribed_topic_post_ids(
        db, profile.subscribed_topic_ids
    )

    scored: list[ScoredPost] = []
    now = datetime.now()
    for post in candidates:
        # 跳过已浏览（避免重复推荐）
        if post.id in profile.viewed_post_ids:
            continue
        scored.append(_score_post(post, profile, validation_map, topic_post_ids, now))

    if not scored:
        # 极端情况：所有候选都已浏览 → 回退冷启动
        return await _cold_start_recommendations(
            db, tenant, limit=limit, offset=offset
        )

    # 排序：score desc → created_at desc → id desc（确定性）
    # 注意：created_at 是 datetime 对象，用负时间戳实现降序
    scored.sort(
        key=lambda s: (-s.score, -s.post.created_at.timestamp(), -s.post.id)
    )
    total = len(scored)
    page = scored[offset : offset + limit]
    return page, total


def _score_post(
    post: Post,
    profile: UserProfile,
    validation_map: dict[int, int],
    topic_post_ids: set[int],
    now: datetime,
) -> ScoredPost:
    """对单个帖子打分（确定性，可解释）"""
    breakdown: dict[str, float] = {}

    # 1. 浏览历史匹配：分类 + 地点
    history_score = 0.0
    cat_w = profile.category_weights.get(post.category_id, 0.0)
    history_score += min(cat_w, 5.0) / 5.0  # 归一化到 0..1
    if post.location_id is not None:
        loc_w = profile.location_weights.get(post.location_id, 0.0)
        history_score += min(loc_w, 5.0) / 5.0
    history_score = min(history_score / 2.0, 1.0)  # 平均后上限 1.0
    # 关键词匹配：标题/内容含搜索关键词 → 加分
    if profile.top_keywords:
        text = (f"{post.title} {post.content}").lower()
        kw_hits = sum(1 for kw in profile.top_keywords if kw in text)
        history_score += min(kw_hits / 3.0, 1.0) * 0.5
    history_score = min(history_score, 1.0)
    breakdown["history"] = history_score

    # 2. SUB-01 订阅画像：分类/地点/专题订阅匹配
    sub_score = 0.0
    if post.category_id is not None and post.category_id in profile.subscribed_category_ids:
        sub_score += 0.5
    if post.location_id is not None and post.location_id in profile.subscribed_location_ids:
        sub_score += 0.3
    if post.id in topic_post_ids:
        sub_score += 0.4
    sub_score = min(sub_score, 1.0)
    breakdown["subscription"] = sub_score

    # 3. 新鲜度：created_at 距今越近越高（指数衰减）
    days_old = max((now - post.created_at).total_seconds() / 86400.0, 0.0)
    freshness_score = 0.5 ** (days_old / FRESHNESS_HALF_LIFE_DAYS)
    freshness_score = min(freshness_score, 1.0)
    breakdown["freshness"] = freshness_score

    # 4. 验证结果：confirmation 票数归一化
    conf_count = validation_map.get(post.id, 0)
    validation_score = min(conf_count / VALIDATION_NORM_MAX, 1.0)
    breakdown["validation"] = validation_score

    # 5. 热度：浏览+点赞+评论归一化
    hot_value = (
        (post.view_count or 0) * 1
        + (post.like_count or 0) * 3
        + (post.comment_count or 0) * 2
    )
    hot_score = min(hot_value / HOT_NORM_MAX, 1.0)
    breakdown["hot"] = hot_score

    # 6. 管理员推荐加分
    admin_bonus = 1.0 if post.is_recommend else 0.0
    breakdown["admin"] = admin_bonus

    score = (
        WEIGHTS["history"] * history_score
        + WEIGHTS["subscription"] * sub_score
        + WEIGHTS["freshness"] * freshness_score
        + WEIGHTS["validation"] * validation_score
        + WEIGHTS["hot"] * hot_score
        + WEIGHTS["admin"] * admin_bonus
    )

    reason = _pick_reason(breakdown, post, profile, topic_post_ids)
    return ScoredPost(post=post, score=round(score, 4), reason=reason, breakdown=breakdown)


def _pick_reason(
    breakdown: dict,
    post: Post,
    profile: UserProfile,
    topic_post_ids: set[int],
) -> str:
    """根据各分项贡献选取主要推荐原因（确定性，可解释）"""
    # 加权后的贡献
    contributions = {
        "history": WEIGHTS["history"] * breakdown.get("history", 0.0),
        "subscription": WEIGHTS["subscription"] * breakdown.get("subscription", 0.0),
        "freshness": WEIGHTS["freshness"] * breakdown.get("freshness", 0.0),
        "validation": WEIGHTS["validation"] * breakdown.get("validation", 0.0),
        "hot": WEIGHTS["hot"] * breakdown.get("hot", 0.0),
        "admin": WEIGHTS["admin"] * breakdown.get("admin", 0.0),
    }

    # 优先级：管理员推荐 > 订阅 > 浏览历史 > 验证 > 新鲜度 > 热门
    # （管理员推荐显式标注，优先级最高）
    if contributions["admin"] > 0:
        return "管理员精选"

    # SUB-01: 订阅匹配（分类/地点/专题）
    if contributions["subscription"] >= 0.5:
        if post.category_id in profile.subscribed_category_ids:
            return "你订阅的分类"
        if post.location_id is not None and post.location_id in profile.subscribed_location_ids:
            return "你订阅的地点"
        if post.id in topic_post_ids:
            return "你订阅的专题"
        return "你订阅的内容"

    # 浏览历史贡献最大（且有意义）
    if contributions["history"] >= 0.3 and (
        profile.category_weights.get(post.category_id, 0.0) > 0
        or (
            post.location_id is not None
            and profile.location_weights.get(post.location_id, 0.0) > 0
        )
    ):
        # 进一步细化原因
        if profile.category_weights.get(post.category_id, 0.0) > 0 and (
            post.location_id is None
            or profile.location_weights.get(post.location_id, 0.0) == 0
        ):
            return "基于你的浏览历史"
        if (
            post.location_id is not None
            and profile.location_weights.get(post.location_id, 0.0) > 0
            and profile.category_weights.get(post.category_id, 0.0) == 0
        ):
            return "常去地点的新内容"
        return "基于你的浏览历史"

    if contributions["history"] >= 0.15 and profile.top_keywords:
        return "匹配你的搜索偏好"

    if contributions["validation"] >= 0.6:
        return "高证实数内容"

    if contributions["freshness"] >= 0.7:
        return "最新发布"

    if contributions["hot"] >= 0.5:
        return "本校热门"

    # 兜底
    return "为你推荐"


async def _load_validation_counts(
    db: AsyncSession, post_ids: list[int]
) -> dict[int, int]:
    """批量加载帖子的 confirmation 票数"""
    if not post_ids:
        return {}
    rows = (
        await db.execute(
            select(
                ValidationRecord.post_id,
                func.count(ValidationRecord.id).label("cnt"),
            )
            .where(
                ValidationRecord.post_id.in_(post_ids),
                ValidationRecord.validation_type == "confirmation",
                ValidationRecord.is_deleted == False,
            )
            .group_by(ValidationRecord.post_id)
        )
    ).all()
    return {row[0]: row[1] for row in rows}


async def _load_subscribed_topic_post_ids(
    db: AsyncSession, topic_ids: set[int]
) -> set[int]:
    """SUB-01: 加载订阅专题下的帖子 ID 集合

    通过 topic_collection_posts 关联表把专题映射到帖子，
    用于在打分时识别"帖子属于用户订阅的专题"。
    """
    if not topic_ids:
        return set()
    from app.models.topic_collection_post import TopicCollectionPost

    rows = (
        await db.execute(
            select(TopicCollectionPost.post_id).where(
                TopicCollectionPost.topic_collection_id.in_(topic_ids)
            )
        )
    ).all()
    return {row[0] for row in rows}


# ============================================================
# 冷启动推荐
# ============================================================
async def _cold_start_recommendations(
    db: AsyncSession,
    tenant: TenantContext,
    *,
    limit: int,
    offset: int,
) -> tuple[list[ScoredPost], int]:
    """冷启动：管理员推荐 + 热门 + 最新

    确定性排序规则：
        1. is_recommend=True 优先（管理员精选）
        2. 同 is_recommend 内按 (hot_value, created_at) 降序
        3. is_recommend=False 内按 (hot_value, created_at) 降序
        4. 兜底按 created_at 降序
    """
    school_id = tenant.school_id
    query = (
        select(Post)
        .where(
            Post.school_id == school_id,
            Post.is_deleted == False,
            Post.status.in_(["published", "expired"]),
        )
        .options(
            joinedload(Post.user),
            joinedload(Post.category),
            joinedload(Post.location),
            selectinload(Post.post_tags).selectinload(PostTag.tag),
            selectinload(Post.post_images),
        )
    )
    posts = (await db.execute(query)).unique().scalars().all()
    if not posts:
        return [], 0

    now = datetime.now()
    scored: list[ScoredPost] = []
    for post in posts:
        hot_value = (
            (post.view_count or 0) * 1
            + (post.like_count or 0) * 3
            + (post.comment_count or 0) * 2
        )
        days_old = max((now - post.created_at).total_seconds() / 86400.0, 0.0)
        freshness = 0.5 ** (days_old / FRESHNESS_HALF_LIFE_DAYS)
        breakdown = {
            "history": 0.0,
            "subscription": 0.0,
            "freshness": freshness,
            "validation": 0.0,
            "hot": min(hot_value / HOT_NORM_MAX, 1.0),
            "admin": 1.0 if post.is_recommend else 0.0,
        }
        # 冷启动综合分：管理员加分 + 热度 + 新鲜度
        score = (
            WEIGHTS["admin"] * breakdown["admin"]
            + WEIGHTS["hot"] * breakdown["hot"]
            + WEIGHTS["freshness"] * breakdown["freshness"]
        )
        # 选取原因
        if post.is_recommend:
            reason = "管理员精选"
        elif breakdown["freshness"] >= 0.7 and days_old < 1:
            reason = "最新发布"
        elif breakdown["hot"] >= 0.5:
            reason = "本校热门"
        elif breakdown["freshness"] >= 0.5:
            reason = "最新发布"
        else:
            reason = "本校热门"
        scored.append(
            ScoredPost(
                post=post,
                score=round(score, 4),
                reason=reason,
                breakdown=breakdown,
            )
        )

    # 排序：score desc → is_recommend desc（确定性，已含在 score 内）→ created_at desc → id desc
    # 注意：created_at 是 datetime 对象，用负时间戳实现降序
    scored.sort(
        key=lambda s: (-s.score, -s.post.created_at.timestamp(), -s.post.id)
    )
    total = len(scored)
    page = scored[offset : offset + limit]
    return page, total
