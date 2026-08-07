r"""独立补写脚本：PostImage.thumbnail_url 历史数据补写。

用途
====
v2.2.9 升级配套：
    在 v2.2.9 之前，upload/image → formData.image_urls: string[] → PostCreate.image_urls: List[str]
    → db 写入时只保存了 image_url，PostImage.thumbnail_url 列全是 NULL，
    导致详情页缩略图虽然有 `img.thumbnail_url or img.image_url`，但仍在加载原图（浪费 ~90% 带宽）。

本脚本对所有 `thumbnail_url IS NULL` 且 `image_url LIKE '/uploads/<filename>'` 的行，
推导 thumbnail_url = '/uploads/thumb_' + <filename>，与 upload.py 的
缩略命名规则一致（300×300 居中裁切）。

特点
====
* 幂等：只 UPDATE WHERE thumbnail_url IS NULL，已有的绝不覆盖
* 安全：只修改 image_url 前缀为 '/uploads/' 且文件名长度 ≥ 1 字符的行
* 原子性：单条 UPDATE 语句 + 1 次 commit，全部成功或全部回滚
* 兼容：openGauss 7.0 / PostgreSQL 通用（使用标准 SQL || 与 SUBSTRING FROM pattern）

使用
====
> $env:APP_ENV = 'opengauss'
> cd backend
> .venv\Scripts\python scripts\fix_post_image_thumbnails.py            # 执行补写
> .venv\Scripts\python scripts\fix_post_image_thumbnails.py --dry-run  # 先查看会改多少行

验证 SQL
====
  SELECT count(*) FROM post_image WHERE thumbnail_url IS NULL;
  SELECT image_url, thumbnail_url FROM post_image ORDER BY id DESC LIMIT 5;
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 确保脚本能从 backend/ 目录 import app.*（与 seed_data.py 一致）
_BACKEND_DIR = Path(__file__).resolve().parents[1]  # backend/
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# openGauss 兼容性补丁：必须在 engine/meta 前导入
import app.db_compat  # noqa: F401  (side-effects only)

from sqlalchemy import text

from app.database import async_session_maker


WHERE_CLAUSE = (
    "WHERE thumbnail_url IS NULL "
    "AND image_url LIKE '/uploads/%' "
    "AND char_length(image_url) > char_length('/uploads/') + 1 "
    "AND substring(image_url FROM '/uploads/(.*)$') IS NOT NULL"
)


async def count_candidates() -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            text(f"SELECT COUNT(*) AS n FROM post_image {WHERE_CLAUSE};")
        )
        return int(result.scalar_one() or 0)


async def run_fix() -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            text(
                "UPDATE post_image "
                "SET thumbnail_url = '/uploads/thumb_' || substring(image_url FROM '/uploads/(.*)$') "
                f"{WHERE_CLAUSE};"
            )
        )
        updated = int(result.rowcount or 0)
        await session.commit()
        return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="补写历史 post_image.thumbnail_url 列（v2.2.9 升级配套，幂等、安全）",
        epilog="与 seed_data.py --only-fix-thumbnails 功能完全等价，只是一个独立脚本便于运维。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将被更新的行数，不做 UPDATE",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PostImage.thumbnail_url 历史数据补写（v2.2.9 升级配套）")
    print("=" * 60)
    print("规则：thumbnail_url = '/uploads/thumb_' + basename(image_url)")
    print("范围：仅 thumbnail_url IS NULL 且 image_url LIKE '/uploads/%'")
    print("幂等：已存在的 thumbnail_url 不会被覆盖")
    print()

    n_expected = asyncio.run(count_candidates())
    print(f"[DRY RUN] 候选行数（待补写）：{n_expected}")

    if n_expected == 0:
        print("✔ 没有需要补写的行，已退出（不执行 UPDATE / COMMIT）")
        return 0

    if args.dry_run:
        print("[DRY RUN] 已通过 --dry-run 跳过真实 UPDATE")
        print("\n真实执行命令：")
        print("  .venv\\Scripts\\python scripts\\fix_post_image_thumbnails.py")
        return 0

    n_updated = asyncio.run(run_fix())
    print(f"\n✅ 成功更新 {n_updated} 行 post_image.thumbnail_url")

    # 二次验证（幂等性验证）：再 COUNT 应该明显下降
    n_remaining = asyncio.run(count_candidates())
    print(f"   二次校验：剩余 thumbnail_url IS NULL 的行数 = {n_remaining}")

    if n_remaining == 0:
        print("   （所有候选行已全部补写完成）")
    else:
        print(
            "   （剩余行可能是 image_url 不以 /uploads/ 开头，"
            "或没有真实文件名——这些行本就不属于补写范围）"
        )

    print("\n建议的验证 SQL：")
    print("  SELECT count(*) FROM post_image WHERE thumbnail_url IS NULL;")
    print("  SELECT id, image_url, thumbnail_url FROM post_image ORDER BY id DESC LIMIT 5;")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
