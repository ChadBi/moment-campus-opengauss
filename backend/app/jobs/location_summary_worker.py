"""地点 AI 摘要异步刷新 worker。"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.models.job_run_record import JobRunRecord
from app.models.location import Location
from app.models.school import School
from app.services.location_summary import generate_location_summary

logger = logging.getLogger(__name__)

JOB_NAME = "location_summaries"
ADVISORY_LOCK_KEY = 20260806


async def run_location_summary_job(
    db: AsyncSession,
    batch_size: int = 20,
    triggered_by: str = "system",
    triggered_user_id: int | None = None,
) -> JobRunRecord:
    """处理 dirty 地点，生成待审核摘要；已批准摘要不会被自动替换。"""
    started_at = datetime.now()
    try:
        locked = bool((await db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY})).scalar())
    except Exception as exc:
        await db.rollback()
        logger.warning("地点摘要 worker 无法获取数据库锁: %s", exc)
        locked = False
    if not locked:
        record = JobRunRecord(
            job_name=JOB_NAME,
            status="failed",
            started_at=started_at,
            finished_at=datetime.now(),
            triggered_by=triggered_by,
            triggered_user_id=triggered_user_id,
            error_message="未获取到地点摘要任务数据库锁，任务未执行",
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    record = JobRunRecord(
        job_name=JOB_NAME,
        status="running",
        started_at=started_at,
        triggered_by=triggered_by,
        triggered_user_id=triggered_user_id,
        processed_count=0,
        failed_count=0,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    failed_ids: list[int] = []
    processed_count = 0
    failed_count = 0
    try:
        rows = (
            await db.execute(
                select(Location, School)
                .join(School, School.id == Location.school_id)
                .where(Location.summary_dirty_at.is_not(None), Location.is_deleted == False)
                .order_by(Location.summary_dirty_at.asc())
                .limit(max(1, min(batch_size, 100)))
            )
        ).all()
        for location, school in rows:
            tenant = TenantContext(
                school_id=school.id,
                school_code=school.code,
                user=None,
                effective_role="super_admin",
                is_guest=False,
                membership=None,
            )
            try:
                await generate_location_summary(db, location.id, tenant)
                processed_count += 1
            except Exception as exc:
                await db.rollback()
                failed_ids.append(location.id)
                failed_count += 1
                logger.exception("地点摘要生成失败 location_id=%s: %s", location.id, exc)
        record.processed_count = processed_count
        record.failed_count = failed_count
        record.status = "failed" if failed_ids else "success"
        record.finished_at = datetime.now()
        if failed_ids:
            record.error_message = json.dumps({"failed_location_ids": failed_ids}, ensure_ascii=False)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        record.processed_count = processed_count
        record.failed_count = failed_count
        record.status = "failed"
        record.finished_at = datetime.now()
        record.error_message = str(exc)[:2000]
        await db.commit()
    finally:
        try:
            await db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY})
            await db.commit()
        except Exception:
            await db.rollback()
    await db.refresh(record)
    return record
