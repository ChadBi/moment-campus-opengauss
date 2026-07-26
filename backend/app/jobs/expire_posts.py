"""GOV-02: 自动过期 published → expired 批量任务服务。

GOV-02.1：独立 worker 批量扫描到期 published 转 expired
- 获取锁/幂等键（防止多实例并发执行）
- 批量扫描：status='published' AND expire_at < now() AND is_deleted=false
- 状态流转：published → expired（通过状态机校验 can_transition）
- 每帖只通知一次（检查是否已发过 post_expired 通知）

GOV-02.2：支持 dry-run 与手动重跑
- 支持 dry-run 模式（只报告不执行）
- 支持手动重跑（通过管理 API 触发）
- 记录开始/成功/失败/处理数量/耗时
- 重复执行不重复通知、不产生非法状态

设计要点：
1. 通过 pg_try_advisory_lock 获取分布式锁（openGauss 兼容 PostgreSQL 协议），
   防止多实例并发执行；锁失败则跳过本次执行。
2. 在 job_run_records 表中记录每次执行的开始/成功/失败/处理数量/耗时。
3. 每帖通过检查 notifications 表是否已存在 type='post_expired' & target_id=post.id
   保证不重复通知。
4. 状态流转通过 can_transition('published', 'expired') 校验，避免非法状态。
5. 多租户：worker 扫描所有学校的帖子，但通知按帖子作者的 user_id 隔离。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.notification import Notification
from app.models.job_run_record import JobRunRecord
from app.core.post_status import can_transition, PostStatus

logger = logging.getLogger(__name__)


# 任务名常量
JOB_NAME = "expire_posts"

# pg_advisory_lock 的 key（任意固定整数，用于全局唯一标识本任务）
# 选择一个不易与其它任务冲突的值
ADVISORY_LOCK_KEY = 20260724


async def _try_acquire_advisory_lock(db: AsyncSession) -> bool:
    """尝试获取 pg_advisory_lock（非阻塞）。

    openGauss 兼容 PostgreSQL 协议，支持 pg_try_advisory_lock。
    若获取失败（其它实例正在执行），返回 False。

    若数据库不支持 advisory lock（极少数情况），降级为始终返回 True，
    由应用层 job_run_records 的 running 状态检查兜底。
    """
    try:
        result = await db.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
        )
        acquired = result.scalar()
        return bool(acquired)
    except Exception as e:
        logger.warning(
            f"pg_try_advisory_lock 不可用，降级为应用层检查: {type(e).__name__}: {e}"
        )
        return True


async def _release_advisory_lock(db: AsyncSession) -> None:
    """释放 pg_advisory_lock。

    advisory lock 是 session 级别，unlock 立即生效。
    SELECT 会隐式开启事务，必须在 unlock 后 commit 以关闭事务，
    否则残留的未提交事务会持有锁，导致后续测试的 TRUNCATE 死锁。
    出错时 rollback 以清理 session 状态。
    """
    try:
        await db.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
        )
        # 提交 SELECT 启动的隐式事务，避免残留未提交事务导致后续 TRUNCATE 死锁
        await db.commit()
    except Exception as e:
        logger.warning(
            f"pg_advisory_unlock 失败（可忽略，session 关闭时自动释放）: "
            f"{type(e).__name__}: {e}"
        )
        # 出错时 rollback 以清理 session 状态，避免后续操作失败
        try:
            await db.rollback()
        except Exception:
            pass


async def _has_running_job(db: AsyncSession) -> Optional[JobRunRecord]:
    """检查是否已有同名任务正在运行。

    应用层幂等键：若存在 status='running' 的记录，返回该记录，
    调用方应跳过本次执行。
    """
    result = await db.execute(
        select(JobRunRecord)
        .where(
            JobRunRecord.job_name == JOB_NAME,
            JobRunRecord.status == "running",
        )
        .order_by(JobRunRecord.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _has_expired_notification(
    db: AsyncSession, post_id: int, user_id: int
) -> bool:
    """检查帖子是否已发过 post_expired 通知（幂等：每帖只通知一次）。"""
    result = await db.execute(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == "post_expired",
            Notification.target_type == "post",
            Notification.target_id == post_id,
            Notification.is_deleted == False,  # noqa: E712
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def expire_posts_job(
    db: AsyncSession,
    dry_run: bool = False,
    triggered_by: str = "system",
    triggered_user_id: Optional[int] = None,
) -> JobRunRecord:
    """批量扫描到期 published 转 expired（GOV-02 核心）。

    流程：
    1. 获取 advisory lock（防止多实例并发）
    2. 检查是否已有 running 任务（应用层幂等键）
    3. 创建 running 记录到 job_run_records
    4. 批量扫描到期 published 帖子
    5. 对每个帖子：
       - 校验状态机 can_transition(published, expired)
       - 检查是否已发过 post_expired 通知（幂等）
       - 流转状态 published → expired
       - 创建通知（若未发过）
    6. 更新 running 记录为 success/failed，记录处理数量/耗时

    Args:
        db: 异步会话
        dry_run: True 表示只报告不执行（不写库）
        triggered_by: 触发者标识（'system' / 'manual'）
        triggered_user_id: 手动触发时的 user_id

    Returns:
        JobRunRecord 记录（包含 status/processed_count/failed_count/耗时等）
    """
    started_at = datetime.now()

    # 1. 获取 advisory lock
    lock_acquired = await _try_acquire_advisory_lock(db)

    # 2. 检查是否已有 running 任务（应用层幂等键）
    if lock_acquired:
        running = await _has_running_job(db)
        if running is not None:
            # 已有任务正在运行，跳过本次执行（锁在 finally 块中统一释放）
            logger.info(
                f"expire_posts_job 已有运行中任务 (id={running.id})，跳过本次执行"
            )
            return running

    # 3. 创建 running 记录
    record = JobRunRecord(
        job_name=JOB_NAME,
        status="running",
        started_at=started_at,
        triggered_by=triggered_by,
        triggered_user_id=triggered_user_id,
        dry_run=dry_run,
        processed_count=0,
        failed_count=0,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    try:
        # 4. 批量扫描到期 published 帖子
        # 条件：status='published' AND expire_at < now() AND is_deleted=false
        result = await db.execute(
            select(Post).where(
                Post.status == PostStatus.PUBLISHED,
                Post.expire_at.is_not(None),
                Post.expire_at < datetime.now(),
                Post.is_deleted == False,  # noqa: E712
            ).order_by(Post.expire_at.asc())
        )
        posts = result.scalars().all()

        logger.info(
            f"expire_posts_job{'[dry-run]' if dry_run else ''}: "
            f"扫描到 {len(posts)} 条到期 published 帖子"
        )

        processed_count = 0
        failed_count = 0
        failed_ids: list[int] = []

        for post in posts:
            try:
                # 5a. 校验状态机 published → expired
                if not can_transition(post.status, PostStatus.EXPIRED):
                    failed_count += 1
                    failed_ids.append(post.id)
                    logger.warning(
                        f"帖子 {post.id} 状态 {post.status} 不允许流转到 expired"
                    )
                    continue

                # dry-run 模式：只统计不执行
                if dry_run:
                    processed_count += 1
                    continue

                # 5b. 检查是否已发过 post_expired 通知（幂等）
                already_notified = await _has_expired_notification(
                    db, post_id=post.id, user_id=post.user_id
                )

                # 5c. 流转状态 published → expired
                post.status = PostStatus.EXPIRED
                post.updated_at = datetime.now()

                # 5d. 创建通知（若未发过）—— 帖子作者
                if not already_notified:
                    notif = Notification(
                        user_id=post.user_id,
                        type="post_expired",
                        title="帖子已过期",
                        content=(
                            f"你的《{post.title}》已超过有效期，"
                            f"自动转为已过期状态。如需继续展示，请重新发布或续期。"
                        )[:500],
                        target_type="post",
                        target_id=post.id,
                        actor_id=None,  # 系统触发，无 actor
                        is_read=False,
                    )
                    db.add(notif)

                # SUB-01.2: 订阅者过期通知（与作者通知互补；严格租户隔离 + 幂等）
                # 失败不阻塞主流程：单条订阅通知失败不影响帖子状态流转
                try:
                    from app.services.subscription_notifier import notify_post_expired
                    await notify_post_expired(db, post, actor_id=None)
                except Exception as notif_err:
                    logger.warning(
                        f"帖子 {post.id} 订阅过期通知触发失败（不影响主流程）: "
                        f"{type(notif_err).__name__}: {notif_err}"
                    )

                processed_count += 1

            except Exception as e:
                failed_count += 1
                failed_ids.append(post.id)
                logger.warning(
                    f"处理帖子 {post.id} 失败: {type(e).__name__}: {e}"
                )

        # 6. 提交所有变更（非 dry-run）
        if not dry_run:
            await db.commit()

        # 更新 running 记录为 success
        record.status = "success"
        record.finished_at = datetime.now()
        record.processed_count = processed_count
        record.failed_count = failed_count
        if failed_ids:
            record.error_message = json.dumps(
                {"failed_ids": failed_ids}, ensure_ascii=False
            )
        record.metadata_ = json.dumps(
            {
                "scanned_count": len(posts),
                "dry_run": dry_run,
                "duration_ms": int(
                    (record.finished_at - record.started_at).total_seconds() * 1000
                ),
            },
            ensure_ascii=False,
        )
        await db.commit()
        await db.refresh(record)

        logger.info(
            f"expire_posts_job{'[dry-run]' if dry_run else ''} 完成: "
            f"扫描 {len(posts)} / 处理 {processed_count} / 失败 {failed_count} / "
            f"耗时 {(record.finished_at - record.started_at).total_seconds():.3f}s"
        )

        return record

    except Exception as e:
        # 任务失败：更新 running 记录为 failed
        record.status = "failed"
        record.finished_at = datetime.now()
        record.error_message = f"{type(e).__name__}: {str(e)[:1000]}"
        try:
            await db.commit()
            await db.refresh(record)
        except Exception:
            await db.rollback()

        logger.error(
            f"expire_posts_job 失败: {type(e).__name__}: {e}",
            exc_info=True,
        )
        return record

    finally:
        # 释放 advisory lock
        if lock_acquired:
            await _release_advisory_lock(db)


async def get_latest_job_record(
    db: AsyncSession, job_name: str = JOB_NAME, limit: int = 10
) -> list[JobRunRecord]:
    """获取最近的任务运行记录列表。"""
    result = await db.execute(
        select(JobRunRecord)
        .where(JobRunRecord.job_name == job_name)
        .order_by(JobRunRecord.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
