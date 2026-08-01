"""ANA-02: 数据分析服务（校级 / 平台级指标复算）。

设计要点（spec ANA-02）：
1. **平台只看学校级聚合**：平台层只统计每校聚合数字，不暴露跨校用户轨迹。
2. **隐私阈值保护**：零结果主题样本量 < PRIVACY_THRESHOLD 时不返回具体查询，
   只返回聚合数量与 `hidden_for_privacy=true` 标记。
3. **可复算**：所有指标从 `product_events` / `posts` / `ai_invocation_logs` /
   `reports` 等业务表实时复算，不预聚合。
4. **元数据透明**：每个指标附带 time_window / sample_size / last_updated_at /
   empty_state 四项元数据，前端可显示「数据空」状态。
5. **环境过滤**：默认排除 test / seed 环境，只统计 demo + production。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_event import ProductEvent
from app.models.post import Post
from app.models.ai_invocation_log import AIInvocationLog
from app.models.report import Report
from app.models.admin_operation_log import AdminOperationLog
from app.core.post_status import PostStatus as PS

logger = logging.getLogger(__name__)


# ============================================================
# 常量与配置
# ============================================================
# 隐私阈值：零结果主题样本量 < 该值时，不返回具体查询，只返回聚合
PRIVACY_THRESHOLD: int = 5

# 默认时间窗口（天）
DEFAULT_WINDOW_DAYS: int = 30

# 默认排除的环境（test / seed 视为非真实数据）
EXCLUDED_ENVIRONMENTS: frozenset[str] = frozenset({"test", "seed"})

# 7 日回访窗口
RETENTION_WINDOW_DAYS: int = 7


# ============================================================
# 元数据结构
# ============================================================
@dataclass
class MetricMeta:
    """指标元数据：保证「可复算 + 显示窗口/样本量/最后更新/空数据状态」。"""
    time_window_start: Optional[datetime]
    time_window_end: datetime
    sample_size: int
    last_updated_at: datetime
    empty_state: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_window_start": (
                self.time_window_start.isoformat() if self.time_window_start else None
            ),
            "time_window_end": self.time_window_end.isoformat(),
            "sample_size": self.sample_size,
            "last_updated_at": self.last_updated_at.isoformat(),
            "empty_state": self.empty_state,
        }


def _build_meta(
    sample_size: int,
    now: datetime,
    window_start: Optional[datetime],
) -> MetricMeta:
    """构造指标元数据。"""
    return MetricMeta(
        time_window_start=window_start,
        time_window_end=now,
        sample_size=int(sample_size),
        last_updated_at=now,
        empty_state=int(sample_size) == 0,
    )


# ============================================================
# 校级分析服务
# ============================================================
@dataclass
class SchoolAnalyticsMetrics:
    """ANA-02.2 校级分析指标集合。"""
    school_id: int
    school_code: Optional[str]
    school_name: Optional[str]
    # 漏斗（学校查看 → 搜索 → 发布 → 审核 → 公开）
    funnel: dict[str, Any]
    # 7 日回访率
    retention_7d: dict[str, Any]
    # 搜索成功率
    search_success_rate: dict[str, Any]
    # 零结果率
    search_zero_rate: dict[str, Any]
    # 分享订阅转化
    share_subscription_conversion: dict[str, Any]
    # 内容有效率
    content_valid_rate: dict[str, Any]
    # 审核治理 SLA
    governance_sla: dict[str, Any]
    # AI 用量指标
    ai_usage: dict[str, Any]
    # 元数据
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "school_id": self.school_id,
            "school_code": self.school_code,
            "school_name": self.school_name,
            "funnel": self.funnel,
            "retention_7d": self.retention_7d,
            "search_success_rate": self.search_success_rate,
            "search_zero_rate": self.search_zero_rate,
            "share_subscription_conversion": self.share_subscription_conversion,
            "content_valid_rate": self.content_valid_rate,
            "governance_sla": self.governance_sla,
            "ai_usage": self.ai_usage,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class ZeroResultTopic:
    """零结果主题项（经隐私阈值保护）。"""
    keyword_length: Optional[int]
    category_code: Optional[str]
    occurrences: int
    hidden_for_privacy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword_length": self.keyword_length,
            "category_code": self.category_code,
            "occurrences": self.occurrences,
            "hidden_for_privacy": self.hidden_for_privacy,
        }


@dataclass
class ZeroResultInsight:
    """ANA-02.1 零结果主题洞察。"""
    school_id: int
    school_code: Optional[str]
    total_zero_searches: int
    privacy_threshold: int
    topics: list[ZeroResultTopic] = field(default_factory=list)
    last_updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "school_id": self.school_id,
            "school_code": self.school_code,
            "total_zero_searches": self.total_zero_searches,
            "privacy_threshold": self.privacy_threshold,
            "topics": [t.to_dict() for t in self.topics],
            "last_updated_at": (
                self.last_updated_at.isoformat() if self.last_updated_at else None
            ),
        }


# ============================================================
# 校级分析服务实现
# ============================================================
class SchoolAnalyticsService:
    """ANA-02.2 校级分析服务：从事件表与业务表实时复算各项指标。

    所有查询都强制按 `school_id` 过滤，且默认排除 test/seed 环境，
    保证校级后台看到的是真实演示/生产数据。
    """

    def __init__(self, db: AsyncSession, school_id: int):
        self.db = db
        self.school_id = school_id

    async def _get_school_info(self) -> tuple[Optional[str], Optional[str]]:
        """获取学校 code / name（避免在指标响应里硬编码）。"""
        from app.models.school import School
        school = (await self.db.execute(
            select(School.code, School.name).where(School.id == self.school_id)
        )).one_or_none()
        if school is None:
            return None, None
        return school.code, school.name

    async def compute_all(
        self,
        window_days: int = DEFAULT_WINDOW_DAYS,
    ) -> SchoolAnalyticsMetrics:
        """计算校级全部指标。"""
        now = datetime.now()
        window_start = now - timedelta(days=window_days)
        school_code, school_name = await self._get_school_info()

        funnel = await self._compute_funnel(window_start, now)
        retention = await self._compute_retention_7d(now)
        search_success = await self._compute_search_success_rate(window_start, now)
        search_zero = await self._compute_search_zero_rate(window_start, now)
        conversion = await self._compute_share_subscription_conversion(window_start, now)
        content_valid = await self._compute_content_valid_rate(now)
        gov_sla = await self._compute_governance_sla(window_start, now)
        ai_usage = await self._compute_ai_usage(window_start, now)

        return SchoolAnalyticsMetrics(
            school_id=self.school_id,
            school_code=school_code,
            school_name=school_name,
            funnel=funnel,
            retention_7d=retention,
            search_success_rate=search_success,
            search_zero_rate=search_zero,
            share_subscription_conversion=conversion,
            content_valid_rate=content_valid,
            governance_sla=gov_sla,
            ai_usage=ai_usage,
            generated_at=now,
        )

    # -------------------- 漏斗 --------------------
    async def _compute_funnel(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """漏斗：学校查看 → 搜索 → 发布 → 审核 → 公开。"""
        # 各阶段计数（按 occurred_at / created_at 落在窗口内）
        school_views = await self._count_event(
            "school_viewed", window_start, now
        )
        search_started = await self._count_event(
            "search_started", window_start, now
        )
        post_submitted = await self._count_event(
            "post_submitted", window_start, now
        )
        # 审核 = pending 帖子数（窗口内创建的）
        pending_count = await self._count_posts_by_status(
            PS.PENDING, window_start, now
        )
        # 公开 = published 帖子数（窗口内创建的）
        published_count = await self._count_posts_by_status(
            PS.PUBLISHED, window_start, now
        )

        total_sample = school_views
        meta = _build_meta(total_sample, now, window_start)

        # 各阶段转化率（前一阶段 → 当前阶段）
        def _rate(prev: int, cur: int) -> float:
            return round(cur / prev, 4) if prev > 0 else 0.0

        return {
            "stages": [
                {"key": "school_viewed", "label": "学校查看", "count": school_views},
                {"key": "search_started", "label": "发起搜索", "count": search_started},
                {"key": "post_submitted", "label": "提交发布", "count": post_submitted},
                {"key": "pending_review", "label": "进入审核", "count": pending_count},
                {"key": "published", "label": "审核公开", "count": published_count},
            ],
            "conversion_rates": {
                "school_viewed_to_search": _rate(school_views, search_started),
                "search_to_post_submitted": _rate(search_started, post_submitted),
                "post_submitted_to_pending": _rate(post_submitted, pending_count),
                "pending_to_published": _rate(pending_count, published_count),
                "overall": _rate(school_views, published_count),
            },
            "meta": meta.to_dict(),
        }

    # -------------------- 7 日回访 --------------------
    async def _compute_retention_7d(self, now: datetime) -> dict[str, Any]:
        """7 日回访率：N 天前活跃用户在 N+7 天内再次出现。

        简化口径：
        - 取窗口起点（now - 14 天）到 now - 7 天之间的「有 user_id 事件」用户为基线
        - 在之后 7 天内（now - 7 天到 now）再次有事件的用户视为回访
        - 回访率 = 回访用户数 / 基线用户数
        """
        baseline_start = now - timedelta(days=14)
        baseline_end = now - timedelta(days=7)
        revisit_end = now

        # 基线用户：在 baseline 窗口内有过事件的 user_id
        baseline_users_rows = (await self.db.execute(
            select(func.distinct(ProductEvent.user_id)).where(
                ProductEvent.school_id == self.school_id,
                ProductEvent.user_id.isnot(None),
                ProductEvent.occurred_at >= baseline_start,
                ProductEvent.occurred_at < baseline_end,
                ~ProductEvent.environment.in_(EXCLUDED_ENVIRONMENTS),
            )
        )).scalars().all()
        baseline_users = set(baseline_users_rows)
        baseline_size = len(baseline_users)

        if baseline_size == 0:
            meta = _build_meta(0, now, baseline_start)
            return {
                "baseline_users": 0,
                "revisit_users": 0,
                "retention_rate": 0.0,
                "window_days": RETENTION_WINDOW_DAYS,
                "meta": meta.to_dict(),
            }

        # 回访用户：基线用户在 revisit 窗口内再次出现
        revisit_rows = (await self.db.execute(
            select(func.distinct(ProductEvent.user_id)).where(
                ProductEvent.school_id == self.school_id,
                ProductEvent.user_id.in_(baseline_users),
                ProductEvent.occurred_at >= baseline_end,
                ProductEvent.occurred_at < revisit_end,
                ~ProductEvent.environment.in_(EXCLUDED_ENVIRONMENTS),
            )
        )).scalars().all()
        revisit_users = len(set(revisit_rows))
        retention_rate = round(revisit_users / baseline_size, 4) if baseline_size > 0 else 0.0

        meta = _build_meta(baseline_size, now, baseline_start)
        return {
            "baseline_users": baseline_size,
            "revisit_users": revisit_users,
            "retention_rate": retention_rate,
            "window_days": RETENTION_WINDOW_DAYS,
            "meta": meta.to_dict(),
        }

    # -------------------- 搜索成功率 --------------------
    async def _compute_search_success_rate(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """搜索成功率 = search_succeeded / (search_succeeded + search_zero)。"""
        succeeded = await self._count_event("search_succeeded", window_start, now)
        zero = await self._count_event("search_zero", window_start, now)
        total = succeeded + zero
        rate = round(succeeded / total, 4) if total > 0 else 0.0
        meta = _build_meta(total, now, window_start)
        return {
            "succeeded_searches": succeeded,
            "zero_searches": zero,
            "total_searches": total,
            "success_rate": rate,
            "meta": meta.to_dict(),
        }

    # -------------------- 零结果率 --------------------
    async def _compute_search_zero_rate(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """零结果率 = search_zero / (search_succeeded + search_zero)。"""
        succeeded = await self._count_event("search_succeeded", window_start, now)
        zero = await self._count_event("search_zero", window_start, now)
        total = succeeded + zero
        rate = round(zero / total, 4) if total > 0 else 0.0
        meta = _build_meta(total, now, window_start)
        return {
            "zero_searches": zero,
            "total_searches": total,
            "zero_rate": rate,
            "meta": meta.to_dict(),
        }

    # -------------------- 分享订阅转化 --------------------
    async def _compute_share_subscription_conversion(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """分享订阅转化：share_clicked → subscribed。

        口径：
        - share_clicked_count：分享点击事件数
        - subscribed_count：订阅事件数
        - conversion_rate：subscribed / share_clicked（弱关联，只看整体转化趋势）
        """
        share_clicked = await self._count_event("share_clicked", window_start, now)
        subscribed = await self._count_event("subscribed", window_start, now)
        rate = round(subscribed / share_clicked, 4) if share_clicked > 0 else 0.0
        meta = _build_meta(share_clicked + subscribed, now, window_start)
        return {
            "share_clicked": share_clicked,
            "subscribed": subscribed,
            "conversion_rate": rate,
            "meta": meta.to_dict(),
        }

    # -------------------- 内容有效率 --------------------
    async def _compute_content_valid_rate(self, now: datetime) -> dict[str, Any]:
        """内容有效率 = (published 且未过期) / 总内容。

        口径：
        - 总内容 = 当前学校未删除的全部帖子
        - 有效 = published 且 (expire_at IS NULL OR expire_at > now)
        """
        total_posts = (await self.db.execute(
            select(func.count(Post.id)).where(
                Post.school_id == self.school_id,
                Post.is_deleted == False,  # noqa: E712
            )
        )).scalar() or 0

        valid_posts = (await self.db.execute(
            select(func.count(Post.id)).where(
                Post.school_id == self.school_id,
                Post.is_deleted == False,  # noqa: E712
                Post.status == PS.PUBLISHED,
                or_(Post.expire_at.is_(None), Post.expire_at > now),
            )
        )).scalar() or 0

        rate = round(valid_posts / total_posts, 4) if total_posts > 0 else 0.0
        meta = _build_meta(int(total_posts), now, None)
        return {
            "total_posts": int(total_posts),
            "valid_posts": int(valid_posts),
            "valid_rate": rate,
            "meta": meta.to_dict(),
        }

    # -------------------- 审核治理 SLA --------------------
    async def _compute_governance_sla(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """审核治理 SLA：平均审核时长 + 平均举报处理时长。

        口径：
        - 平均审核时长：AdminOperationLog 中 action in (approve_post, reject_post)
          的 created_at 与对应 Post.created_at 的差值平均（秒）
        - 平均举报处理时长：Report.handled_at - Report.created_at 的平均（秒）
        """
        # 平均审核时长（秒）
        review_rows = (await self.db.execute(
            select(AdminOperationLog.created_at, Post.created_at)
            .join(Post, AdminOperationLog.target_id == Post.id)
            .where(
                AdminOperationLog.action.in_(["approve_post", "reject_post"]),
                AdminOperationLog.target_type == "post",
                Post.school_id == self.school_id,
                AdminOperationLog.created_at >= window_start,
                AdminOperationLog.created_at <= now,
            )
        )).all()
        review_durations: list[float] = []
        for log_created, post_created in review_rows:
            if log_created and post_created:
                dur = (log_created - post_created).total_seconds()
                if dur >= 0:
                    review_durations.append(dur)
        avg_review_seconds = (
            round(sum(review_durations) / len(review_durations), 2)
            if review_durations else 0.0
        )

        # 平均举报处理时长
        report_rows = (await self.db.execute(
            select(Report.created_at, Report.handled_at)
            .outerjoin(Post, Report.post_id == Post.id)
            .where(
                Report.status == "handled",
                Report.handled_at.isnot(None),
                or_(Post.school_id == self.school_id, Post.id.is_(None)),
                Report.created_at >= window_start,
                Report.created_at <= now,
            )
        )).all()
        report_durations: list[float] = []
        for created, handled in report_rows:
            if created and handled:
                dur = (handled - created).total_seconds()
                if dur >= 0:
                    report_durations.append(dur)
        avg_report_seconds = (
            round(sum(report_durations) / len(report_durations), 2)
            if report_durations else 0.0
        )

        total_sample = (
            len(review_durations) + len(report_durations)
        )
        meta = _build_meta(total_sample, now, window_start)
        return {
            "avg_review_seconds": avg_review_seconds,
            "avg_report_handle_seconds": avg_report_seconds,
            "reviewed_count": len(review_durations),
            "reports_handled_count": len(report_durations),
            "meta": meta.to_dict(),
        }

    # -------------------- AI 用量 --------------------
    async def _compute_ai_usage(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """AI 每次成功检索用量 + 降级率。"""
        rows = (await self.db.execute(
            select(
                func.count(AIInvocationLog.id),
                func.count(AIInvocationLog.id).filter(
                    AIInvocationLog.output_status == "success"
                ),
                func.count(AIInvocationLog.id).filter(
                    AIInvocationLog.fallback_reason.isnot(None)
                ),
                func.avg(AIInvocationLog.latency_ms),
                func.avg(AIInvocationLog.candidate_count),
                func.avg(AIInvocationLog.result_count),
            ).where(
                AIInvocationLog.school_id == self.school_id,
                AIInvocationLog.created_at >= window_start,
                AIInvocationLog.created_at <= now,
            )
        )).one()

        total_calls = int(rows[0] or 0)
        success_calls = int(rows[1] or 0)
        fallback_calls = int(rows[2] or 0)
        avg_latency_ms = round(float(rows[3]), 2) if rows[3] is not None else 0.0
        avg_candidate_count = round(float(rows[4]), 2) if rows[4] is not None else 0.0
        avg_result_count = round(float(rows[5]), 2) if rows[5] is not None else 0.0

        success_rate = round(success_calls / total_calls, 4) if total_calls > 0 else 0.0
        fallback_rate = round(fallback_calls / total_calls, 4) if total_calls > 0 else 0.0

        meta = _build_meta(total_calls, now, window_start)
        return {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "fallback_calls": fallback_calls,
            "success_rate": success_rate,
            "fallback_rate": fallback_rate,
            "avg_latency_ms": avg_latency_ms,
            "avg_candidate_count": avg_candidate_count,
            "avg_result_count": avg_result_count,
            "meta": meta.to_dict(),
        }

    # -------------------- 零结果主题洞察 --------------------
    async def compute_zero_results_insight(
        self,
        window_days: int = DEFAULT_WINDOW_DAYS,
    ) -> ZeroResultInsight:
        """ANA-02.1 零结果主题洞察（经隐私阈值保护）。

        口径：
        - 从 search_zero 事件的 fields_json 中聚合 keyword_length + category_code
        - 单个主题样本量 < PRIVACY_THRESHOLD 时标记 hidden_for_privacy=true
        - 仍然计入总数，但不返回具体聚合字段
        """
        now = datetime.now()
        window_start = now - timedelta(days=window_days)
        school_code, _ = await self._get_school_info()

        # 拉取窗口内所有 search_zero 事件的 fields_json
        rows = (await self.db.execute(
            select(ProductEvent.fields_json).where(
                ProductEvent.school_id == self.school_id,
                ProductEvent.event_name == "search_zero",
                ProductEvent.occurred_at >= window_start,
                ProductEvent.occurred_at <= now,
                ~ProductEvent.environment.in_(EXCLUDED_ENVIRONMENTS),
            )
        )).scalars().all()

        # 聚合：(keyword_length, category_code) → count
        topic_map: dict[tuple[Optional[int], Optional[str]], int] = {}
        for fields in rows:
            if not fields:
                continue
            kw_len = fields.get("keyword_length")
            cat_code = fields.get("category_code")
            # 类型归一化
            if isinstance(kw_len, (int, float)) and kw_len >= 0:
                kw_len = int(kw_len)
            else:
                kw_len = None
            if not isinstance(cat_code, str):
                cat_code = None
            key = (kw_len, cat_code)
            topic_map[key] = topic_map.get(key, 0) + 1

        topics: list[ZeroResultTopic] = []
        for (kw_len, cat_code), count in sorted(
            topic_map.items(), key=lambda kv: kv[1], reverse=True
        ):
            hidden = count < PRIVACY_THRESHOLD
            topics.append(ZeroResultTopic(
                keyword_length=kw_len,
                category_code=cat_code,
                occurrences=count,
                hidden_for_privacy=hidden,
            ))

        return ZeroResultInsight(
            school_id=self.school_id,
            school_code=school_code,
            total_zero_searches=len(rows),
            privacy_threshold=PRIVACY_THRESHOLD,
            topics=topics,
            last_updated_at=now,
        )

    # -------------------- 内部辅助 --------------------
    async def _count_event(
        self,
        event_name: str,
        window_start: datetime,
        now: datetime,
    ) -> int:
        """统计窗口内某事件数（排除 test/seed 环境）。"""
        return int((await self.db.execute(
            select(func.count(ProductEvent.id)).where(
                ProductEvent.school_id == self.school_id,
                ProductEvent.event_name == event_name,
                ProductEvent.occurred_at >= window_start,
                ProductEvent.occurred_at <= now,
                ~ProductEvent.environment.in_(EXCLUDED_ENVIRONMENTS),
            )
        )).scalar() or 0)

    async def _count_posts_by_status(
        self,
        status: str,
        window_start: datetime,
        now: datetime,
    ) -> int:
        """统计窗口内创建的某状态帖子数。"""
        return int((await self.db.execute(
            select(func.count(Post.id)).where(
                Post.school_id == self.school_id,
                Post.status == status,
                Post.is_deleted == False,  # noqa: E712
                Post.created_at >= window_start,
                Post.created_at <= now,
            )
        )).scalar() or 0)


# ============================================================
# 平台分析服务（super_admin，跨校聚合）
# ============================================================
@dataclass
class PlatformAnalyticsMetrics:
    """ANA-02.1 平台分析指标：只看学校级聚合，不提供跨校用户轨迹。"""
    school_total: int
    school_active: int
    # 各校聚合指标（不暴露跨校用户维度）
    school_metrics: list[dict[str, Any]]
    # 全平台聚合
    platform_funnel: dict[str, Any]
    platform_search: dict[str, Any]
    platform_ai_usage: dict[str, Any]
    platform_governance: dict[str, Any]
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "school_total": self.school_total,
            "school_active": self.school_active,
            "school_metrics": self.school_metrics,
            "platform_funnel": self.platform_funnel,
            "platform_search": self.platform_search,
            "platform_ai_usage": self.platform_ai_usage,
            "platform_governance": self.platform_governance,
            "generated_at": self.generated_at.isoformat(),
        }


class PlatformAnalyticsService:
    """ANA-02.1 平台分析服务（super_admin，跨校聚合）。

    关键约束：
    - 只看学校级聚合：每个学校一行聚合指标，不暴露跨校用户轨迹
    - 所有指标都按 school_id 分组聚合后再返回
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_all(
        self,
        window_days: int = DEFAULT_WINDOW_DAYS,
    ) -> PlatformAnalyticsMetrics:
        now = datetime.now()
        window_start = now - timedelta(days=window_days)

        from app.models.school import School
        schools = (await self.db.execute(
            select(School.id, School.code, School.name, School.is_active)
            .order_by(School.created_at.asc())
        )).all()
        school_total = len(schools)
        school_active = sum(1 for s in schools if s.is_active)

        # 各校聚合指标
        school_metrics: list[dict[str, Any]] = []
        for s in schools:
            svc = SchoolAnalyticsService(self.db, s.id)
            metrics = await svc.compute_all(window_days=window_days)
            # 只保留聚合数字，不保留跨校用户维度
            school_metrics.append({
                "school_id": s.id,
                "school_code": s.code,
                "school_name": s.name,
                "is_active": s.is_active,
                "funnel_summary": {
                    "school_viewed": metrics.funnel["stages"][0]["count"],
                    "search_started": metrics.funnel["stages"][1]["count"],
                    "post_submitted": metrics.funnel["stages"][2]["count"],
                    "published": metrics.funnel["stages"][4]["count"],
                },
                "search_success_rate": metrics.search_success_rate["success_rate"],
                "search_zero_rate": metrics.search_zero_rate["zero_rate"],
                "ai_calls": metrics.ai_usage["total_calls"],
                "ai_fallback_rate": metrics.ai_usage["fallback_rate"],
            })

        # 平台聚合（跨校汇总，但仍是事件/业务计数，不含用户轨迹）
        platform_funnel = await self._compute_platform_funnel(window_start, now)
        platform_search = await self._compute_platform_search(window_start, now)
        platform_ai_usage = await self._compute_platform_ai_usage(window_start, now)
        platform_governance = await self._compute_platform_governance(window_start, now)

        return PlatformAnalyticsMetrics(
            school_total=school_total,
            school_active=school_active,
            school_metrics=school_metrics,
            platform_funnel=platform_funnel,
            platform_search=platform_search,
            platform_ai_usage=platform_ai_usage,
            platform_governance=platform_governance,
            generated_at=now,
        )

    async def _compute_platform_funnel(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """平台级漏斗聚合（跨校汇总事件计数，不暴露用户轨迹）。"""
        async def _count(event_name: str) -> int:
            return int((await self.db.execute(
                select(func.count(ProductEvent.id)).where(
                    ProductEvent.event_name == event_name,
                    ProductEvent.occurred_at >= window_start,
                    ProductEvent.occurred_at <= now,
                    ~ProductEvent.environment.in_(EXCLUDED_ENVIRONMENTS),
                )
            )).scalar() or 0)

        school_views = await _count("school_viewed")
        search_started = await _count("search_started")
        post_submitted = await _count("post_submitted")
        published = int((await self.db.execute(
            select(func.count(Post.id)).where(
                Post.status == PS.PUBLISHED,
                Post.is_deleted == False,  # noqa: E712
                Post.created_at >= window_start,
                Post.created_at <= now,
            )
        )).scalar() or 0)

        total_sample = school_views
        meta = _build_meta(total_sample, now, window_start)
        return {
            "stages": [
                {"key": "school_viewed", "label": "学校查看", "count": school_views},
                {"key": "search_started", "label": "发起搜索", "count": search_started},
                {"key": "post_submitted", "label": "提交发布", "count": post_submitted},
                {"key": "published", "label": "审核公开", "count": published},
            ],
            "overall_conversion": (
                round(published / school_views, 4) if school_views > 0 else 0.0
            ),
            "meta": meta.to_dict(),
        }

    async def _compute_platform_search(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """平台级搜索成功率 + 零结果率。"""
        async def _count(event_name: str) -> int:
            return int((await self.db.execute(
                select(func.count(ProductEvent.id)).where(
                    ProductEvent.event_name == event_name,
                    ProductEvent.occurred_at >= window_start,
                    ProductEvent.occurred_at <= now,
                    ~ProductEvent.environment.in_(EXCLUDED_ENVIRONMENTS),
                )
            )).scalar() or 0)

        succeeded = await _count("search_succeeded")
        zero = await _count("search_zero")
        total = succeeded + zero
        meta = _build_meta(total, now, window_start)
        return {
            "succeeded_searches": succeeded,
            "zero_searches": zero,
            "total_searches": total,
            "success_rate": round(succeeded / total, 4) if total > 0 else 0.0,
            "zero_rate": round(zero / total, 4) if total > 0 else 0.0,
            "meta": meta.to_dict(),
        }

    async def _compute_platform_ai_usage(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """平台级 AI 用量。"""
        rows = (await self.db.execute(
            select(
                func.count(AIInvocationLog.id),
                func.count(AIInvocationLog.id).filter(
                    AIInvocationLog.output_status == "success"
                ),
                func.count(AIInvocationLog.id).filter(
                    AIInvocationLog.fallback_reason.isnot(None)
                ),
                func.avg(AIInvocationLog.latency_ms),
            ).where(
                AIInvocationLog.created_at >= window_start,
                AIInvocationLog.created_at <= now,
            )
        )).one()

        total_calls = int(rows[0] or 0)
        success_calls = int(rows[1] or 0)
        fallback_calls = int(rows[2] or 0)
        avg_latency_ms = round(float(rows[3]), 2) if rows[3] is not None else 0.0

        meta = _build_meta(total_calls, now, window_start)
        return {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "fallback_calls": fallback_calls,
            "success_rate": (
                round(success_calls / total_calls, 4) if total_calls > 0 else 0.0
            ),
            "fallback_rate": (
                round(fallback_calls / total_calls, 4) if total_calls > 0 else 0.0
            ),
            "avg_latency_ms": avg_latency_ms,
            "meta": meta.to_dict(),
        }

    async def _compute_platform_governance(
        self, window_start: datetime, now: datetime
    ) -> dict[str, Any]:
        """平台级治理 SLA：全平台平均审核/举报处理时长。"""
        # 全平台平均审核时长
        review_rows = (await self.db.execute(
            select(AdminOperationLog.created_at, Post.created_at)
            .join(Post, AdminOperationLog.target_id == Post.id)
            .where(
                AdminOperationLog.action.in_(["approve_post", "reject_post"]),
                AdminOperationLog.target_type == "post",
                AdminOperationLog.created_at >= window_start,
                AdminOperationLog.created_at <= now,
            )
        )).all()
        review_durations: list[float] = []
        for log_created, post_created in review_rows:
            if log_created and post_created:
                dur = (log_created - post_created).total_seconds()
                if dur >= 0:
                    review_durations.append(dur)
        avg_review_seconds = (
            round(sum(review_durations) / len(review_durations), 2)
            if review_durations else 0.0
        )

        # 全平台平均举报处理时长
        report_rows = (await self.db.execute(
            select(Report.created_at, Report.handled_at).where(
                Report.status == "handled",
                Report.handled_at.isnot(None),
                Report.created_at >= window_start,
                Report.created_at <= now,
            )
        )).all()
        report_durations: list[float] = []
        for created, handled in report_rows:
            if created and handled:
                dur = (handled - created).total_seconds()
                if dur >= 0:
                    report_durations.append(dur)
        avg_report_seconds = (
            round(sum(report_durations) / len(report_durations), 2)
            if report_durations else 0.0
        )

        total_sample = len(review_durations) + len(report_durations)
        meta = _build_meta(total_sample, now, window_start)
        return {
            "avg_review_seconds": avg_review_seconds,
            "avg_report_handle_seconds": avg_report_seconds,
            "reviewed_count": len(review_durations),
            "reports_handled_count": len(report_durations),
            "meta": meta.to_dict(),
        }
