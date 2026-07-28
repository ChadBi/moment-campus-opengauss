"""ANA-01.1 + ANA-01.2: 产品事件白名单 + 最小字段 + 幂等入库 + 环境标记

核心约束（来自 spec ANA-01）：
1. **白名单硬约束**：非白名单事件拒绝入库（track_event 抛 ValueError）。
2. **最小字段**：每个事件定义允许的字段集，多余字段被剔除；搜索类事件只记
   keyword_length / category 等聚合字段，**严禁**写正文 / 密码 / Token / 完整搜索关键词原文。
3. **幂等入库**：客户端传 event_id（UUID），重复 event_id 不重复入库。
   openGauss 不支持 PostgreSQL 的 INSERT ... ON CONFLICT DO NOTHING 语法，
   改用「SELECT → 不存在则 INSERT」+ 唯一约束兜底（并发场景捕获唯一冲突视为已存在）。
4. **环境标记**：environment ∈ {production, demo, test, seed}，从 settings.ANALYTICS_ENV
   读取；未配置时按 APP_ENV 推导。

事件字典（白名单）：
    school_viewed       浏览学校首页/地图/列表
    search_started      发起搜索（只记 keyword_length，不记关键词原文）
    search_succeeded    搜索成功（有结果）
    search_zero         搜索零结果
    post_viewed         帖子详情被浏览
    share_clicked       分享按钮被点击
    subscribed          订阅分类/地点/专题/官方主体
    draft_saved         草稿被保存（只记 has_title/has_image/content_length，不记内容）
    post_submitted      帖子被提交审核（不记标题/正文，只记 category_code）
    publisher_verified  官方主体认证状态变化
    tenant_activated    学校开通漏斗阶段推进
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.product_event import ProductEvent

logger = logging.getLogger(__name__)


# ============================================================
# 环境标记
# ============================================================
VALID_ENVIRONMENTS: frozenset[str] = frozenset({
    "production", "demo", "test", "seed",
})


def resolve_environment() -> str:
    """解析当前环境标记。

    优先级：
        1. settings.ANALYTICS_ENV（若为非空合法值）
        2. 按 APP_ENV 推导：
           - APP_ENV=test → test
           - APP_ENV=opengauss → demo（本地开发默认演示档）
           - TEST_DATABASE_URL 非空 → test
           - 其余 → demo
    """
    configured = (settings.ANALYTICS_ENV or "").strip()
    if configured in VALID_ENVIRONMENTS:
        return configured
    # 推导
    if settings.APP_ENV == "test":
        return "test"
    if os.environ.get("TEST_DATABASE_URL"):
        return "test"
    if settings.APP_ENV == "opengauss":
        return "demo"
    return "demo"


# ============================================================
# 事件白名单 + 最小字段定义
# ============================================================
# 每个事件允许的字段集（最小字段）。未列入白名单的字段在 track_event 中被剔除。
# 搜索类事件：只记 keyword_length / category_code 等聚合字段，**绝不**记关键词原文。
# 草稿/帖子类事件：只记 has_title/has_image/content_length 等布尔/数值字段，**绝不**记正文。
EVENT_WHITELIST: dict[str, frozenset[str]] = {
    # 学校浏览：来源页（home/map/search/detail/first-use 等）
    "school_viewed": frozenset({"source"}),
    # 搜索发起：keyword_length（0-200 整数，不记原文）/ category_code / source
    "search_started": frozenset({"keyword_length", "category_code", "source"}),
    # 搜索成功（有结果）：keyword_length / result_count / category_code / has_filter
    "search_succeeded": frozenset({
        "keyword_length", "result_count", "category_code", "has_filter",
    }),
    # 搜索零结果：keyword_length / category_code / has_filter
    "search_zero": frozenset({"keyword_length", "category_code", "has_filter"}),
    # 帖子浏览：post_id / source（list/search/map/topic/recommend/notification）
    "post_viewed": frozenset({"post_id", "source"}),
    # 分享点击：post_id / channel（native/copy_link/qr/other）
    "share_clicked": frozenset({"post_id", "channel"}),
    # 订阅：target_type（category/location/topic/publisher）/ target_id
    "subscribed": frozenset({"target_type", "target_id"}),
    # 草稿保存：post_id(可空)/has_title(bool)/has_image(bool)/content_length(int)
    # **严禁**记草稿标题或正文
    "draft_saved": frozenset({
        "post_id", "has_title", "has_image", "content_length",
    }),
    # 帖子提交审核：post_id / category_code / is_anonymous(bool)
    # **严禁**记标题/正文/标签原文
    # Task 1.2 调整：post_type_code 已随 PostType 模型删除移除
    "post_submitted": frozenset({
        "post_id", "category_code", "is_anonymous",
    }),
    # 官方主体认证：publisher_id / action（apply/approved/rejected/revoked）
    "publisher_verified": frozenset({"publisher_id", "action"}),
    # 学校开通漏斗阶段：stage（initial_brand/first_admin/first_location/
    # first_content/first_member/activated）
    "tenant_activated": frozenset({"stage"}),
}

# 隐私敏感字段名（小写匹配）：即便客户端误传也拒绝入库
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset({
    "password", "passwd", "pwd", "token", "access_token", "refresh_token",
    "authorization", "secret", "api_key", "apikey",
    "keyword", "query", "search_query",  # 搜索关键词原文
    "content", "body", "text", "title", "description",  # 帖子正文/标题
    "phone", "mobile", "email", "id_card",  # 个人联系方式
})


def is_allowed_event(event_name: str) -> bool:
    """判断事件名是否在白名单内。"""
    return event_name in EVENT_WHITELIST


def sanitize_fields(event_name: str, fields: dict[str, Any] | None) -> dict[str, Any]:
    """按白名单 schema 剔除多余字段，并拒绝敏感字段。

    - 非白名单事件：抛 ValueError
    - 字段不在该事件的白名单内：剔除
    - 字段名匹配敏感字段：抛 ValueError（隐私硬约束）

    Args:
        event_name: 事件名
        fields: 客户端上报的字段 dict（可为 None）

    Returns:
        经过清洗的最小字段 dict
    """
    if not is_allowed_event(event_name):
        raise ValueError(f"非白名单事件：{event_name!r}（拒绝入库）")

    if not fields:
        return {}

    allowed = EVENT_WHITELIST[event_name]
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        key_lower = key.lower()
        if key_lower in SENSITIVE_FIELD_NAMES:
            raise ValueError(
                f"事件 {event_name!r} 包含敏感字段 {key!r}（拒绝入库，隐私硬约束）"
            )
        if key not in allowed:
            # 非白名单字段：静默剔除（不抛错，便于客户端增量迭代）
            continue
        cleaned[key] = value
    return cleaned


# ============================================================
# 幂等入库
# ============================================================
async def track_event(
    db: AsyncSession,
    *,
    event_id: str,
    event_name: str,
    school_id: int,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
    fields: Optional[dict[str, Any]] = None,
    environment: Optional[str] = None,
    commit: bool = True,
) -> tuple[bool, Optional[ProductEvent]]:
    """幂等写入产品事件。

    流程：
        1. 校验 event_name 在白名单内，否则抛 ValueError
        2. sanitize_fields 清洗字段（剔除多余 + 拒绝敏感）
        3. SELECT event_id；若已存在 → 视为已入库（幂等返回），不重复 INSERT
        4. INSERT；若并发场景触发唯一约束冲突 → 回滚并视为已存在

    Args:
        db: 异步会话
        event_id: 客户端生成的 UUID（幂等键），<=64 字符
        event_name: 事件名（必须在白名单内）
        school_id: 学校 ID（来自 TenantContext，忽略载荷中的 school_id）
        user_id: 用户 ID；游客事件传 None
        session_id: 前端会话 ID
        trace_id: 关联 X-Request-ID
        occurred_at: 事件发生时间；None 表示 now()
        fields: 上报字段；经 sanitize_fields 清洗后写入 fields_json
        environment: 环境标记；None 表示 resolve_environment()
        commit: 是否在内部 commit；False 时由调用方统一提交（批量场景）

    Returns:
        (inserted, event_obj)
        - inserted=True：本次新插入
        - inserted=False：已存在（幂等命中），event_obj 为已存在的行（仅查到时填充，
          并发冲突场景可能为 None）

    Raises:
        ValueError: 非白名单事件 / 含敏感字段 / event_id 为空
    """
    if not event_id or not isinstance(event_id, str):
        raise ValueError("event_id 不能为空（幂等键）")
    if len(event_id) > 64:
        raise ValueError("event_id 长度不能超过 64 字符")

    # 1. 白名单 + 敏感字段校验
    cleaned_fields = sanitize_fields(event_name, fields)

    # 2. 环境标记
    env = environment or resolve_environment()
    if env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"非法 environment={env!r}，允许值：{sorted(VALID_ENVIRONMENTS)}"
        )

    occurred = occurred_at or datetime.now()

    # 3. 幂等：先 SELECT
    existing = (await db.execute(
        select(ProductEvent).where(ProductEvent.event_id == event_id)
    )).scalar_one_or_none()
    if existing is not None:
        # 幂等命中：重复上报不重复入库
        return False, existing

    # 4. INSERT（并发兜底：唯一约束）
    event = ProductEvent(
        event_id=event_id,
        event_name=event_name,
        school_id=school_id,
        user_id=user_id,
        session_id=session_id,
        trace_id=trace_id,
        occurred_at=occurred,
        received_at=datetime.now(),
        environment=env,
        fields_json=cleaned_fields or None,
    )
    db.add(event)
    try:
        if commit:
            await db.commit()
        else:
            await db.flush()
    except IntegrityError as exc:
        # 并发场景：另一事务已插入同 event_id → 视为已存在（幂等命中）
        if commit:
            await db.rollback()
        else:
            # flush 失败后由调用方决定如何处理；这里抛出让上层捕获
            raise
        logger.debug(
            f"track_event idempotent_conflict event_id={event_id} "
            f"event_name={event_name} detail={str(exc.orig)[:120]}"
        )
        # 重新查询已存在的行（用于返回）
        existing_after = (await db.execute(
            select(ProductEvent).where(ProductEvent.event_id == event_id)
        )).scalar_one_or_none()
        return False, existing_after

    if commit:
        await db.refresh(event)
    return True, event


async def track_events_batch(
    db: AsyncSession,
    events: list[dict[str, Any]],
    *,
    school_id: int,
    user_id: Optional[int] = None,
    trace_id: Optional[str] = None,
    environment: Optional[str] = None,
) -> list[dict[str, Any]]:
    """批量幂等写入产品事件（API 上报场景使用）。

    每个事件 dict 包含：
        event_id (必填), event_name (必填), occurred_at (可选),
        session_id (可选), fields (可选), user_id (可选，覆盖外层 user_id)

    非白名单事件 / 含敏感字段的事件被拒绝并记入 errors，不影响其他事件入库。
    每个事件使用独立 savepoint（嵌套事务），保证单个事件冲突不会回滚已成功的其他事件。

    Returns:
        [{"event_id": str, "inserted": bool, "error": Optional[str]}]
    """
    results: list[dict[str, Any]] = []
    for ev in events:
        ev_id = ev.get("event_id")
        ev_name = ev.get("event_name")
        try:
            if not ev_id or not isinstance(ev_id, str):
                raise ValueError("event_id 不能为空")
            if not ev_name or not isinstance(ev_name, str):
                raise ValueError("event_name 不能为空")

            # 使用 savepoint：单个事件失败/冲突只回滚到 savepoint，不影响其他事件
            async with db.begin_nested():
                inserted, _ = await track_event(
                    db,
                    event_id=ev_id,
                    event_name=ev_name,
                    school_id=school_id,
                    user_id=ev.get("user_id") or user_id,
                    session_id=ev.get("session_id"),
                    trace_id=trace_id,
                    occurred_at=ev.get("occurred_at"),
                    fields=ev.get("fields"),
                    environment=environment,
                    commit=False,
                )
                results.append({"event_id": ev_id, "inserted": inserted, "error": None})
        except IntegrityError:
            # savepoint 自动回滚；记为幂等命中
            results.append({
                "event_id": ev_id, "inserted": False,
                "error": "idempotent_conflict",
            })
        except ValueError as e:
            results.append({
                "event_id": ev_id, "inserted": False,
                "error": str(e),
            })
            logger.warning(
                f"track_events_batch reject event_id={ev_id} "
                f"event_name={ev_name} reason={e}"
            )

    await db.commit()
    return results
