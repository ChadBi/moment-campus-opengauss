"""GOV-02.1: 独立 worker 脚本 - 批量扫描到期 published 转 expired。

独立运行（不在 4 个 Web worker startup 启动），可由 systemd timer 或 cron 调度。

用法：
    # 系统定时触发（默认）
    python scripts/expire_posts_worker.py

    # dry-run 模式（只报告不执行）
    python scripts/expire_posts_worker.py --dry-run

    # 手动触发（记录触发者标识）
    python scripts/expire_posts_worker.py --manual --user-id 1

    # 手动触发 + dry-run
    python scripts/expire_posts_worker.py --manual --user-id 1 --dry-run

systemd 单位文件：
    deploy/bare-metal/moment-expire-posts.service
    deploy/bare-metal/moment-expire-posts.timer

设计要点：
1. 不依赖 FastAPI 应用上下文，直接使用 SQLAlchemy 引擎
2. 使用 app.database.async_session_maker 创建独立会话
3. 调用 app.jobs.expire_posts.expire_posts_job 执行核心逻辑
4. 通过 --dry-run / --manual / --user-id 参数支持不同模式
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# 确保 backend 目录在 Python 路径中
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 应用 openGauss 兼容性补丁（必须在创建引擎前导入）
import app.db_compat  # noqa: F401

from app.database import async_session_maker
from app.jobs.expire_posts import expire_posts_job, JOB_NAME


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("expire_posts_worker")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="GOV-02.1: 批量扫描到期 published 转 expired",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
    # 系统定时触发（默认）
    python scripts/expire_posts_worker.py

    # dry-run 模式（只报告不执行）
    python scripts/expire_posts_worker.py --dry-run

    # 手动触发（记录触发者 user_id）
    python scripts/expire_posts_worker.py --manual --user-id 1
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="dry-run 模式：只报告不执行（不写库、不发通知）",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="手动触发模式（记录 triggered_by='manual'）",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="手动触发时的 user_id（用于审计追踪）",
    )
    return parser.parse_args()


async def main() -> int:
    """worker 主入口。

    Returns:
        0 表示成功，1 表示失败，2 表示已有任务正在运行（跳过）
    """
    args = parse_args()

    triggered_by = "manual" if args.manual else "system"
    triggered_user_id = args.user_id if args.manual else None

    logger.info(
        f"启动 expire_posts_worker: dry_run={args.dry_run}, "
        f"triggered_by={triggered_by}, triggered_user_id={triggered_user_id}"
    )

    async with async_session_maker() as session:
        try:
            record = await expire_posts_job(
                db=session,
                dry_run=args.dry_run,
                triggered_by=triggered_by,
                triggered_user_id=triggered_user_id,
            )

            # 输出执行结果
            duration = (
                (record.finished_at - record.started_at).total_seconds()
                if record.finished_at
                else 0.0
            )
            print("\n" + "=" * 60)
            print(f"任务执行记录 (id={record.id})")
            print("=" * 60)
            print(f"  job_name:         {record.job_name}")
            print(f"  status:           {record.status}")
            print(f"  dry_run:          {record.dry_run}")
            print(f"  triggered_by:     {record.triggered_by}")
            print(f"  triggered_user_id:{record.triggered_user_id}")
            print(f"  started_at:       {record.started_at.isoformat()}")
            print(f"  finished_at:      "
                  f"{record.finished_at.isoformat() if record.finished_at else 'NULL'}")
            print(f"  processed_count:  {record.processed_count}")
            print(f"  failed_count:     {record.failed_count}")
            print(f"  duration:         {duration:.3f}s")
            if record.error_message:
                print(f"  error_message:    {record.error_message}")
            if record.metadata_:
                try:
                    meta = json.loads(record.metadata_)
                    print(f"  metadata:         {json.dumps(meta, ensure_ascii=False, indent=2)}")
                except (json.JSONDecodeError, TypeError):
                    print(f"  metadata:         {record.metadata_}")
            print("=" * 60)

            # 退出码：success=0, failed=1, running(跳过)=2
            if record.status == "success":
                logger.info("任务执行成功")
                return 0
            elif record.status == "failed":
                logger.error("任务执行失败")
                return 1
            elif record.status == "running":
                logger.info("已有任务正在运行，本次跳过")
                return 2
            else:
                logger.warning(f"未知状态: {record.status}")
                return 1

        except Exception as e:
            logger.error(
                f"worker 执行异常: {type(e).__name__}: {e}",
                exc_info=True,
            )
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
