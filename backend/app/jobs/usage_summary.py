"""COM-01.3 租户用量日汇总幂等任务。

设计要点：
1. summarize_usage(school_id, date) 基于当日实际 count 重算并覆盖；
   重复运行同一天数值不会翻倍累加。
2. AI 调用计数单独提供 increment_ai_calls(school_id, date) 方法，
   在 AI 入口被调用时累加 1，超限则由调用方降级普通搜索。
3. openGauss 不支持 PostgreSQL 的 ON CONFLICT 语法，改用「先 SELECT 再 INSERT/UPDATE」
   在事务中保证幂等。基于唯一约束 (school_id, usage_date) 防止重复行。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant_usage_daily import TenantUsageDaily
from app.models.school_membership import SchoolMembership
from app.models.post import Post


async def summarize_usage(
    db: AsyncSession,
    school_id: int,
    usage_date: Optional[date] = None,
    storage_used_mb: int = 0,
    ai_calls_count: Optional[int] = None,
) -> TenantUsageDaily:
    """重算并 UPSERT 当日用量（幂等：基于实际 count 重算并覆盖，不累加）。

    - members_count / posts_count 基于数据库实际 count 重算并覆盖（不累加）
    - storage_used_mb 由调用方传入（外部统计），覆盖
    - ai_calls_count:
        - 若传入非 None → 用该值覆盖（用于重算）
        - 若为 None → 保留原值不变（不重置当日 AI 计数；调用方应使用 increment_ai_calls 累加）

    实现说明：
        openGauss 不支持 PostgreSQL 的 INSERT ... ON CONFLICT DO UPDATE 语法，
        这里改用「SELECT → INSERT or UPDATE」在事务中保证幂等。
        表上的唯一约束 (school_id, usage_date) 防止并发场景下重复行。

    Returns:
        UPSERT 后的 TenantUsageDaily 行（重新查询返回完整对象）。
    """
    if usage_date is None:
        usage_date = date.today()

    # 重算成员数（active 状态）
    members_count = int(
        (await db.execute(
            select(func.count()).select_from(SchoolMembership).where(
                SchoolMembership.school_id == school_id,
                SchoolMembership.status == "active",
            )
        )).scalar()
        or 0
    )

    # 重算帖子数（非软删除的全部状态）
    posts_count = int(
        (await db.execute(
            select(func.count()).select_from(Post).where(
                Post.school_id == school_id,
                Post.is_deleted == False,  # noqa: E712
            )
        )).scalar()
        or 0
    )

    # 查询是否已存在当日记录
    existing = (await db.execute(
        select(TenantUsageDaily).where(
            TenantUsageDaily.school_id == school_id,
            TenantUsageDaily.usage_date == usage_date,
        )
    )).scalar_one_or_none()

    # 若调用方未传入 ai_calls_count，则保留原值
    if ai_calls_count is None:
        ai_calls_count = int(existing.ai_calls_count if existing else 0)

    if existing is None:
        # INSERT
        row = TenantUsageDaily(
            school_id=school_id,
            usage_date=usage_date,
            members_count=members_count,
            posts_count=posts_count,
            storage_used_mb=storage_used_mb,
            ai_calls_count=ai_calls_count,
        )
        db.add(row)
    else:
        # UPDATE（覆盖，不累加）
        existing.members_count = members_count
        existing.posts_count = posts_count
        existing.storage_used_mb = storage_used_mb
        existing.ai_calls_count = ai_calls_count
        row = existing

    await db.commit()
    await db.refresh(row)
    return row


async def increment_ai_calls(
    db: AsyncSession,
    school_id: int,
    usage_date: Optional[date] = None,
) -> int:
    """当日 AI 调用次数 +1（幂等：每次调用 +1，不会因重算翻倍）。

    AI 调用入口成功调用 AI 后调用本方法累加 1。
    若超限，调用方应降级普通搜索，并不应调用本方法（避免无效计数）。

    实现说明：
        openGauss 不支持 ON CONFLICT，改用 SELECT → INSERT/UPDATE 模式。

    Args:
        db: 异步会话
        school_id: 学校 ID
        usage_date: 统计日期；None 表示今天

    Returns:
        累加后的当日 AI 调用数。
    """
    if usage_date is None:
        usage_date = date.today()

    existing = (await db.execute(
        select(TenantUsageDaily).where(
            TenantUsageDaily.school_id == school_id,
            TenantUsageDaily.usage_date == usage_date,
        )
    )).scalar_one_or_none()

    if existing is None:
        # INSERT：ai_calls_count = 1，其余字段先填 0（由 summarize_usage 后续重算覆盖）
        row = TenantUsageDaily(
            school_id=school_id,
            usage_date=usage_date,
            members_count=0,
            posts_count=0,
            storage_used_mb=0,
            ai_calls_count=1,
        )
        db.add(row)
        new_count = 1
    else:
        existing.ai_calls_count = int(existing.ai_calls_count or 0) + 1
        new_count = existing.ai_calls_count

    await db.commit()
    return new_count


async def get_ai_calls_count(
    db: AsyncSession,
    school_id: int,
    usage_date: Optional[date] = None,
) -> int:
    """读取当日 AI 调用数；不存在则返回 0。"""
    if usage_date is None:
        usage_date = date.today()
    result = await db.execute(
        select(TenantUsageDaily.ai_calls_count).where(
            TenantUsageDaily.school_id == school_id,
            TenantUsageDaily.usage_date == usage_date,
        )
    )
    return int(result.scalar() or 0)
