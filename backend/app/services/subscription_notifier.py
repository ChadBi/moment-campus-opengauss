"""SUB-01.2: 订阅通知触发服务（四类场景）

四类订阅通知触发场景：
1. 新帖通知（notify_new_post）：帖子首次 published 时，通知订阅其分类/地点/专题的用户
2. 更新通知（notify_post_updated）：已发布帖子被实质修改（published → pending 回审）时，通知订阅者
3. 过期通知（notify_post_expired）：帖子 published → expired 时，通知订阅者（与 GOV-02 联动）
4. 冲突通知（notify_post_conflict）：帖子被标记为 conflict 时，通知订阅者（与 GOV-01.5 联动）

设计要点：
1. 严格租户隔离：查询订阅者时强制 school_id == post.school_id，跨校订阅者不会收到通知。
2. 排除帖子作者：作者本人不接收自己帖子的订阅通知（避免自我打扰）。
3. 通知偏好尊重：检查 NotificationPreference.subscription_enabled，关闭订阅类的用户不接收。
   - 安全类别（system/audit）不可全关的约束不在此处生效（订阅类不属于安全类别）。
4. 批量写入：单次触发可能产生多条通知（订阅者众），通过 db.add_all 批量写入，由调用方统一 commit。
5. 幂等性：通过检查 notifications 表是否已存在同类型通知保证每帖每类只通知一次（与 expire_posts_job 模式一致）。
6. 通知类型常量：使用 subscription_new / subscription_update / subscription_expired / subscription_conflict
   四个细分类型，便于前端按需过滤；统一映射到 NotificationPreference.subscription 偏好类别。

与现有通知系统的关系：
- 帖子作者的 audit 通知（审核结果）由 admin.py 中的 add_review_notification 写入，本服务不重复。
- 帖子作者的 post_expired 通知由 expire_posts_job 写入，本服务针对"订阅者"补充通知。
- 帖子作者的冲突标记通知由 handle_governance_report 写入，本服务针对"订阅者"补充通知。
"""
from __future__ import annotations

import logging
from typing import Optional, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.subscription import UserSubscription
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.topic_collection_post import TopicCollectionPost

logger = logging.getLogger(__name__)


# ============================================================
# 通知类型常量（4 类细分，前端可按 type 过滤）
# ============================================================
class SubscriptionNotificationType:
    """订阅通知类型常量

    统一前缀 `subscription_` 便于前端按 `type LIKE 'subscription_%'` 聚合过滤；
    同时与 NotificationPreference.subscription_enabled 偏好类别一一对应。
    """
    NEW = "subscription_new"            # 新帖发布
    UPDATE = "subscription_update"      # 重要更新（实质修改）
    EXPIRED = "subscription_expired"    # 内容过期
    CONFLICT = "subscription_conflict"  # 冲突标记

    ALL = (NEW, UPDATE, EXPIRED, CONFLICT)


# 订阅目标类型常量（与 UserSubscription.target_type 对齐）
_TARGET_CATEGORY = "category"
_TARGET_LOCATION = "location"
_TARGET_TOPIC = "topic"


# ============================================================
# 内部辅助：查询订阅者 + 偏好过滤 + 幂等检查
# ============================================================

async def _collect_subscriber_ids(
    db: AsyncSession,
    post: Post,
    exclude_user_id: Optional[int] = None,
) -> set[int]:
    """收集帖子在当前学校内所有应被通知的订阅者 user_id（去重 + 偏好过滤 + 排除作者）

    订阅来源（取并集）：
    - category：post.category_id 对应的订阅者
    - location：post.location_id 对应的订阅者（若有）
    - topic：通过 topic_collection_posts 关联到 post 的所有专题的订阅者

    严格租户隔离：UserSubscription.school_id == post.school_id
    偏好过滤：NotificationPreference.subscription_enabled == True（或无偏好记录，默认开启）
    排除作者：exclude_user_id（默认 post.user_id）不参与通知

    Returns:
        去重后的 user_id 集合（可能为空）
    """
    school_id = post.school_id
    subscriber_ids: set[int] = set()

    # 1. category 订阅者
    if post.category_id is not None:
        rows = await db.execute(
            select(UserSubscription.user_id).where(
                UserSubscription.school_id == school_id,
                UserSubscription.target_type == _TARGET_CATEGORY,
                UserSubscription.target_id == post.category_id,
            )
        )
        for (uid,) in rows.all():
            subscriber_ids.add(uid)

    # 2. location 订阅者
    if post.location_id is not None:
        rows = await db.execute(
            select(UserSubscription.user_id).where(
                UserSubscription.school_id == school_id,
                UserSubscription.target_type == _TARGET_LOCATION,
                UserSubscription.target_id == post.location_id,
            )
        )
        for (uid,) in rows.all():
            subscriber_ids.add(uid)

    # 3. topic 订阅者：先查 post 关联的所有 topic_collection_id，再查这些专题的订阅者
    topic_rows = await db.execute(
        select(TopicCollectionPost.topic_collection_id).where(
            TopicCollectionPost.post_id == post.id
        )
    )
    topic_ids = [row[0] for row in topic_rows.all()]
    if topic_ids:
        rows = await db.execute(
            select(UserSubscription.user_id).where(
                UserSubscription.school_id == school_id,
                UserSubscription.target_type == _TARGET_TOPIC,
                UserSubscription.target_id.in_(topic_ids),
            )
        )
        for (uid,) in rows.all():
            subscriber_ids.add(uid)

    # 排除帖子作者（默认）
    if exclude_user_id is None:
        exclude_user_id = post.user_id
    if exclude_user_id is not None:
        subscriber_ids.discard(exclude_user_id)

    if not subscriber_ids:
        return set()

    # 偏好过滤：仅保留 subscription_enabled=True 或无偏好记录（默认开启）的用户
    # 一次性批量查询，避免逐用户查询
    pref_rows = await db.execute(
        select(NotificationPreference.user_id, NotificationPreference.subscription_enabled).where(
            NotificationPreference.user_id.in_(subscriber_ids)
        )
    )
    # 显式关闭订阅类的用户集合
    opted_out = {
        uid for (uid, enabled) in pref_rows.all() if enabled is False
    }
    subscriber_ids -= opted_out

    return subscriber_ids


async def _has_subscription_notification(
    db: AsyncSession,
    post_id: int,
    notif_type: str,
    user_id: int,
) -> bool:
    """幂等检查：指定用户对指定帖子是否已发过同类型的订阅通知。

    保证每帖每类每用户只通知一次（与 expire_posts_job 的 _has_expired_notification 模式一致）。
    """
    result = await db.execute(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == notif_type,
            Notification.target_type == "post",
            Notification.target_id == post_id,
            Notification.is_deleted == False,  # noqa: E712
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


def _build_notifications(
    post: Post,
    subscriber_ids: Iterable[int],
    notif_type: str,
    title: str,
    content: str,
    actor_id: Optional[int] = None,
) -> list[Notification]:
    """批量构造 Notification 对象（不写入数据库，由调用方统一 commit）"""
    return [
        Notification(
            user_id=uid,
            type=notif_type,
            title=title,
            content=content[:500],
            target_type="post",
            target_id=post.id,
            actor_id=actor_id,
            is_read=False,
        )
        for uid in subscriber_ids
    ]


# ============================================================
# 四类通知触发函数
# ============================================================

async def notify_new_post(
    db: AsyncSession,
    post: Post,
    actor_id: Optional[int] = None,
) -> int:
    """新帖发布通知：帖子首次 published 时通知订阅者

    场景：管理员审核通过（pending → published）时调用。
    幂等：若订阅者已收到该帖的 subscription_new 通知（如重复审核），不重复发送。

    Args:
        db: 异步会话（由调用方统一 commit）
        post: 已发布的帖子对象（应已 status=published）
        actor_id: 触发者（通常是审核管理员），用于通知 actor 字段

    Returns:
        本次新增的通知数量（0 表示无新增）
    """
    subscriber_ids = await _collect_subscriber_ids(db, post)
    if not subscriber_ids:
        return 0

    # 幂等过滤：仅对未发过 subscription_new 的用户发送
    new_recipients: set[int] = set()
    for uid in subscriber_ids:
        if not await _has_subscription_notification(db, post.id, SubscriptionNotificationType.NEW, uid):
            new_recipients.add(uid)

    if not new_recipients:
        return 0

    title = "订阅内容新发布"
    content = f"你订阅的分类/地点/专题有新内容《{post.title}》，点击查看详情。"
    notifications = _build_notifications(
        post, new_recipients,
        SubscriptionNotificationType.NEW,
        title, content,
        actor_id=actor_id,
    )
    db.add_all(notifications)
    return len(notifications)


async def notify_post_updated(
    db: AsyncSession,
    post: Post,
    actor_id: Optional[int] = None,
) -> int:
    """重要更新通知：已发布帖子被实质修改（published → pending 回审）时通知订阅者

    场景：作者在 update_post 中对已发布帖子做实质字段修改（title/content/category_id/
    post_type_id/location_id/lost_type），触发 published → pending 回审。
    此时通知订阅者"内容有重要更新（正在重新审核）"。

    幂等：每次实质修改只通知一次；重复保存（无实质字段变更）不会触发本函数。
    若同一帖子短时间内被多次实质修改，订阅者会收到多条 subscription_update（按业务语义合理）。

    Args:
        db: 异步会话（由调用方统一 commit）
        post: 被修改的帖子对象（修改后状态可能为 pending）
        actor_id: 触发者（通常是帖子作者）

    Returns:
        本次新增的通知数量
    """
    subscriber_ids = await _collect_subscriber_ids(db, post)
    if not subscriber_ids:
        return 0

    # 更新通知不做严格幂等（每次实质修改都应通知），但过滤掉已发过 subscription_update 的用户
    # 避免同一订阅者对同一帖子的更新通知堆积（保留最新的，旧的已读可忽略）
    # 这里采用：仅对未发过 subscription_update 的用户发送首条更新通知；
    # 后续重复修改不再追加通知（订阅者已被告知"内容在更新中"）。
    new_recipients: set[int] = set()
    for uid in subscriber_ids:
        if not await _has_subscription_notification(db, post.id, SubscriptionNotificationType.UPDATE, uid):
            new_recipients.add(uid)

    if not new_recipients:
        return 0

    title = "订阅内容有重要更新"
    content = (
        f"你订阅的内容《{post.title}》有重要更新，正在重新审核。"
        f"审核通过后会再次公开展示。"
    )
    notifications = _build_notifications(
        post, new_recipients,
        SubscriptionNotificationType.UPDATE,
        title, content,
        actor_id=actor_id,
    )
    db.add_all(notifications)
    return len(notifications)


async def notify_post_expired(
    db: AsyncSession,
    post: Post,
    actor_id: Optional[int] = None,
) -> int:
    """过期通知：帖子 published → expired 时通知订阅者

    场景：GOV-02 自动过期任务（expire_posts_job）扫描到期帖子时调用，
    与帖子作者的 post_expired 通知（由 expire_posts_job 写入）互补。

    幂等：每帖每用户只通知一次（通过 _has_subscription_notification 保证）。

    Args:
        db: 异步会话（由调用方统一 commit）
        post: 已过期的帖子对象（应已 status=expired）
        actor_id: 触发者（系统任务为 None）

    Returns:
        本次新增的通知数量
    """
    subscriber_ids = await _collect_subscriber_ids(db, post)
    if not subscriber_ids:
        return 0

    new_recipients: set[int] = set()
    for uid in subscriber_ids:
        if not await _has_subscription_notification(db, post.id, SubscriptionNotificationType.EXPIRED, uid):
            new_recipients.add(uid)

    if not new_recipients:
        return 0

    title = "订阅内容已过期"
    content = (
        f"你订阅的内容《{post.title}》已超过有效期，自动转为已过期状态。"
        f"如需继续展示，请等待作者续期或重新发布。"
    )
    notifications = _build_notifications(
        post, new_recipients,
        SubscriptionNotificationType.EXPIRED,
        title, content,
        actor_id=actor_id,
    )
    db.add_all(notifications)
    return len(notifications)


async def notify_post_conflict(
    db: AsyncSession,
    post: Post,
    actor_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> int:
    """冲突通知：帖子被标记为 conflict 时通知订阅者

    场景：管理员处理冲突报告（handle_governance_report with action=mark_conflict），
    帖子状态转为 conflict 时调用。

    幂等：每帖每用户只通知一次（避免重复标记冲突时多次通知）。

    Args:
        db: 异步会话（由调用方统一 commit）
        post: 被标记为冲突的帖子对象（应已 status=conflict）
        actor_id: 触发者（通常是处理报告的管理员）
        reason: 处理原因（可选，写入通知 content）

    Returns:
        本次新增的通知数量
    """
    subscriber_ids = await _collect_subscriber_ids(db, post)
    if not subscriber_ids:
        return 0

    new_recipients: set[int] = set()
    for uid in subscriber_ids:
        if not await _has_subscription_notification(db, post.id, SubscriptionNotificationType.CONFLICT, uid):
            new_recipients.add(uid)

    if not new_recipients:
        return 0

    title = "订阅内容存在冲突"
    content = f"你订阅的内容《{post.title}》被标记为冲突状态，请留意后续处理。"
    if reason:
        content = f"{content} 处理说明：{reason}"
    notifications = _build_notifications(
        post, new_recipients,
        SubscriptionNotificationType.CONFLICT,
        title, content,
        actor_id=actor_id,
    )
    db.add_all(notifications)
    return len(notifications)
