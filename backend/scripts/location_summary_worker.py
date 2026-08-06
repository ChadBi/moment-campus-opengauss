"""定时刷新地点 AI 摘要（结果进入管理员待审核队列）。"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import app.db_compat  # noqa: F401
from app.database import async_session_maker
from app.jobs.location_summary_worker import run_location_summary_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def main() -> int:
    parser = argparse.ArgumentParser(description="刷新地点 AI 摘要并进入管理员待审核队列")
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    async with async_session_maker() as session:
        record = await run_location_summary_job(session, batch_size=args.batch_size)
    print({"id": record.id, "status": record.status, "processed_count": record.processed_count, "failed_count": record.failed_count})
    return 0 if record.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

