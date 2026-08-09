"""批量刷新地点 AI 摘要并自动审批（用于演示数据准备）。

用法（Windows PowerShell）：
    $env:APP_ENV="opengauss"
    python scripts/refresh_all_location_summaries.py           # 默认处理 10 个地点
    python scripts/refresh_all_location_summaries.py --limit 5 # 仅处理 5 个
    python scripts/refresh_all_location_summaries.py --all     # 处理全部地点
    python scripts/refresh_all_location_summaries.py --school jiangnan  # 仅处理指定学校
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import app.db_compat  # noqa: F401
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.database import async_session_maker
from app.models.location import Location
from app.models.location_review import LocationReview
from app.models.location_summary import LocationSummaryVersion
from app.models.post import Post
from app.models.school import School
from app.models.user import User
from app.services.location_summary import generate_location_summary, SUMMARY_POST_DAYS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
# 减少 SQL 引擎日志噪音
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def get_super_admin(db: AsyncSession) -> User:
    """获取第一个超管账号用于自动审批。"""
    admin = await db.scalar(
        select(User).where(User.role == "super_admin").order_by(User.id.asc()).limit(1)
    )
    if admin is None:
        raise RuntimeError("未找到 super_admin 用户，请先运行 seed_data.py")
    return admin


async def auto_approve_summary(
    db: AsyncSession,
    summary: LocationSummaryVersion,
    location: Location,
    reviewer: User,
) -> None:
    """将 pending_review 状态的摘要直接审批通过。"""
    if summary.status != "pending_review":
        return
    # 归档旧的已批准摘要
    if location.current_summary_id:
        old = await db.get(LocationSummaryVersion, location.current_summary_id)
        if old and old.status == "approved":
            old.status = "archived"
    summary.status = "approved"
    summary.reviewer_id = reviewer.id
    summary.review_reason = "脚本自动审批（演示数据）"
    summary.reviewed_at = datetime.now()
    location.current_summary_id = summary.id
    location.summary_dirty_at = None


async def count_dynamic_content(
    db: AsyncSession, location_id: int, school_id: int
) -> tuple[int, int]:
    """统计地点的近期动态内容数量（帖子数、不同作者数）。"""
    now = datetime.now()
    post_cutoff = now - timedelta(days=SUMMARY_POST_DAYS)

    # 近 7 天有效帖子数
    post_count = await db.scalar(
        select(func.count(Post.id)).where(
            Post.location_id == location_id,
            Post.school_id == school_id,
            Post.status == "published",
            Post.is_deleted == False,  # noqa: E712
            Post.created_at >= post_cutoff,
        )
    )
    # 近 30 天评价的不同作者数
    review_cutoff = now - timedelta(days=30)
    author_count = await db.scalar(
        select(func.count(func.distinct(LocationReview.user_id))).where(
            LocationReview.location_id == location_id,
            LocationReview.school_id == school_id,
            LocationReview.status == "published",
            LocationReview.is_deleted == False,  # noqa: E712
            LocationReview.created_at >= review_cutoff,
        )
    )
    return int(post_count or 0), int(author_count or 0)


async def process_locations(
    db: AsyncSession,
    limit: int | None,
    school_code: str | None,
    reviewer: User,
) -> dict:
    """处理指定数量的地点，生成摘要并自动审批。优先处理有更多动态内容的地点。"""
    # 构建查询：按帖子数+评价数降序，优先处理数据充足的地点
    query = (
        select(Location, School)
        .join(School, School.id == Location.school_id)
        .where(Location.is_deleted == False)  # noqa: E712
        .order_by(
            (Location.post_count + Location.review_count).desc(),
            Location.id.asc(),
        )
    )
    if school_code:
        query = query.where(School.code == school_code)
    if limit:
        query = query.limit(limit)

    rows = (await db.execute(query)).all()
    total = len(rows)
    logger.info(f"待处理地点数: {total}")

    stats = {"total": total, "success": 0, "ai_failed": 0, "no_data": 0, "error": 0}

    for idx, (location, school) in enumerate(rows, 1):
        logger.info(f"[{idx}/{total}] {school.name} - {location.name} (id={location.id}, posts={location.post_count}, reviews={location.review_count})")
        tenant = TenantContext(
            school_id=school.id,
            school_code=school.code,
            user=None,
            effective_role="super_admin",
            is_guest=False,
            membership=None,
        )

        # 预检是否有足够数据
        post_count, author_count = await count_dynamic_content(db, location.id, location.school_id)
        if post_count < 2 or author_count < 2:
            logger.info(f"  → 数据不足（近7天帖子={post_count}, 评价作者={author_count}，需要≥2），跳过")
            stats["no_data"] += 1
            continue

        try:
            summary = await generate_location_summary(db, location.id, tenant)
            if summary is None:
                logger.warning(f"  → AI 未能生成有效摘要（可能输出解析失败）")
                stats["ai_failed"] += 1
                # 短暂延迟避免连续失败触发限流
                await asyncio.sleep(1)
                continue
            # 自动审批
            await auto_approve_summary(db, summary, location, reviewer)
            await db.commit()
            logger.info(
                f"  → ✅ 成功! 置信度={summary.confidence_level}, "
                f"摘要长度={len(summary.summary_text or '')}, 来源数={summary.source_count}"
            )
            if summary.summary_text:
                preview = summary.summary_text[:80].replace("\n", " ")
                logger.info(f"     摘要预览: {preview}...")
            stats["success"] += 1
            # 每次成功后短暂延迟，避免 AI API 限流
            await asyncio.sleep(0.5)
        except Exception as exc:
            await db.rollback()
            logger.error(f"  → ❌ 异常: {type(exc).__name__}: {exc}")
            stats["error"] += 1
            await asyncio.sleep(2)

    return stats


async def main() -> int:
    parser = argparse.ArgumentParser(description="批量刷新地点 AI 摘要并自动审批")
    parser.add_argument("--limit", type=int, default=10, help="处理地点数量上限（默认10，用于测试）")
    parser.add_argument("--all", action="store_true", help="处理全部地点（覆盖 --limit）")
    parser.add_argument("--school", type=str, default=None, help="仅处理指定学校 code（jiangnan/fudan/zju）")
    args = parser.parse_args()

    limit = None if args.all else args.limit

    async with async_session_maker() as session:
        reviewer = await get_super_admin(session)
        logger.info(f"使用审批人: {reviewer.nickname} (id={reviewer.id}, role={reviewer.role})")
        stats = await process_locations(session, limit, args.school, reviewer)

    print("\n" + "=" * 55)
    print("处理完成！统计：")
    print(f"  总计:         {stats['total']}")
    print(f"  ✅ 成功:      {stats['success']}")
    print(f"  ⏭️  数据不足:  {stats['no_data']}")
    print(f"  ⚠️  AI未生成: {stats['ai_failed']}")
    print(f"  ❌ 异常:      {stats['error']}")
    print("=" * 55)

    return 0 if stats["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
