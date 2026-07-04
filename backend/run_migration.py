"""数据库迁移执行脚本

执行 04_drop_favorites_and_simplify_validation.sql
通过 asyncpg 直接执行 SQL 文件
"""
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import asyncpg


# 从 backend/.env.opengauss 读取 DATABASE_URL
def load_db_url() -> str:
    env_path = Path(__file__).parent / ".env.opengauss"
    if not env_path.exists():
        raise FileNotFoundError(f"找不到配置文件: {env_path}")

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                # 格式：postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus
                url = line.split("=", 1)[1]
                # 转换为 asyncpg 可用的格式：postgresql://...
                if url.startswith("postgresql+asyncpg://"):
                    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
                return url
    raise ValueError("DATABASE_URL not found in .env.opengauss")


async def run_migration():
    # 读取 SQL 文件
    sql_path = Path(__file__).parent / "scripts" / "opengauss" / "04_drop_favorites_and_simplify_validation.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"找不到迁移脚本: {sql_path}")

    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    print(f"=" * 60)
    print(f"执行迁移脚本: {sql_path.name}")
    print(f"=" * 60)

    # 解析 DATABASE_URL
    db_url = load_db_url()
    parsed = urlparse(db_url)
    user = parsed.username
    # urlparse 不会自动解码 %40，需要手动处理
    from urllib.parse import unquote
    password = unquote(parsed.password) if parsed.password else None
    host = parsed.hostname
    port = parsed.port or 5432
    database = parsed.path.lstrip("/")

    print(f"连接数据库: {user}@{host}:{port}/{database}")
    print(f"密码: {password}")
    print()

    # 连接数据库
    conn = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )

    try:
        # 执行迁移（整个脚本作为一个事务）
        # 注意：asyncpg 的 execute 不支持 DO $$ 块，需要用 execute 配合简单查询协议
        # 改用 executemany 或逐条执行
        # 实际上 asyncpg 的 execute 可以执行多个语句，但不支持 DO 块
        # 改为逐条执行

        # 拆分 SQL 为多个语句（按分号分割，但要小心 DO $$...$$ 中的分号）
        # 简化方案：直接使用 conn.execute 执行整个脚本
        # asyncpg 不支持多语句，需要逐条执行

        # 手动逐条执行
        statements = []

        # 提取 BEGIN 和 COMMIT 之间的语句
        # 简化处理：直接按分号分割，但保留 DO $$ ... $$ 为一个整体

        # 先按行处理，识别 DO $$ 块
        lines = sql_content.split("\n")
        current_stmt = []
        in_do_block = False
        skip_do_block = False  # DO 块由 Python 层处理，跳过

        for line in lines:
            stripped = line.strip()

            # 跳过注释行（-- 开头）
            if stripped.startswith("--"):
                continue

            # 跳过空行
            if not stripped:
                continue

            # 跳过 BEGIN 和 COMMIT
            if stripped.upper() in ("BEGIN;", "BEGIN", "COMMIT;", "COMMIT"):
                continue

            # 检测 DO $$ 块开始 —— 跳过，由 Python 层处理
            if "DO $$" in line or "DO$$" in line:
                skip_do_block = True
                continue

            # 在 DO 块内 —— 跳过所有内容
            if skip_do_block:
                if "$$" in line and (line.strip().endswith("$$;") or "END $$" in line):
                    skip_do_block = False
                continue

            # 普通语句：累积到 current_stmt
            current_stmt.append(line)
            if stripped.endswith(";"):
                stmt = "\n".join(current_stmt)
                statements.append(stmt)
                current_stmt = []

        # 处理剩余的语句
        if current_stmt:
            stmt = "\n".join(current_stmt)
            if stmt.strip():
                statements.append(stmt)

        print(f"共 {len(statements)} 条 SQL 语句需要执行（DO 块由 Python 层处理）")
        print("-" * 60)

        # 开始事务
        async with conn.transaction():
            for i, stmt in enumerate(statements, 1):
                stmt_preview = stmt.replace("\n", " ")[:80]
                if len(stmt.replace("\n", " ")) > 80:
                    stmt_preview += "..."
                print(f"[{i}/{len(statements)}] 执行: {stmt_preview}")

                try:
                    await conn.execute(stmt)
                    print(f"         ✓ 成功")
                except Exception as e:
                    error_msg = str(e)
                    # 对于 IF EXISTS 类的 DROP，如果对象不存在是正常的
                    if "does not exist" in error_msg.lower() or "already exists" in error_msg.lower():
                        print(f"         ⚠ 跳过（对象不存在或已存在）: {error_msg[:100]}")
                    else:
                        print(f"         ✗ 失败: {error_msg}")
                        raise

            # 处理 DO $$ 块：检查并创建唯一索引
            print(f"[6/7] 执行: CREATE UNIQUE INDEX IF NOT EXISTS idx_validation_post_user_unique")
            idx_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = 'validation_records' AND indexname = 'idx_validation_post_user_unique')"
            )
            if idx_exists:
                print(f"         ⚠ 跳过（索引已存在）")
            else:
                await conn.execute(
                    "CREATE UNIQUE INDEX idx_validation_post_user_unique ON validation_records (post_id, user_id)"
                )
                print(f"         ✓ 成功")

        print("-" * 60)
        print("✓ 迁移完成")

        # 验证迁移结果
        print()
        print("=" * 60)
        print("验证迁移结果")
        print("=" * 60)

        # 1. 检查 favorites 表是否已删除
        table_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'favorites')"
        )
        print(f"1. favorites 表存在: {table_exists}（应为 False）")

        # 2. 检查 posts.favorite_count 字段是否已删除
        col_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'posts' AND column_name = 'favorite_count')"
        )
        print(f"2. posts.favorite_count 字段存在: {col_exists}（应为 False）")

        # 3. 检查 validation_records 中的类型分布
        rows = await conn.fetch(
            "SELECT validation_type, COUNT(*) as cnt FROM validation_records GROUP BY validation_type ORDER BY validation_type"
        )
        print(f"3. validation_records 类型分布:")
        for row in rows:
            print(f"   - {row['validation_type']}: {row['cnt']} 条")

        # 4. 检查唯一索引是否存在
        idx_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = 'validation_records' AND indexname = 'idx_validation_post_user_unique')"
        )
        print(f"4. 唯一索引 idx_validation_post_user_unique 存在: {idx_exists}（应为 True）")

        # 5. 检查是否有重复的 (post_id, user_id) 记录
        duplicate_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM (
                SELECT post_id, user_id, COUNT(*) as cnt
                FROM validation_records
                GROUP BY post_id, user_id
                HAVING COUNT(*) > 1
            ) t
            """
        )
        print(f"5. 重复的 (post_id, user_id) 记录数: {duplicate_count}（应为 0）")

        # 6. 总记录数
        total_count = await conn.fetchval("SELECT COUNT(*) FROM validation_records")
        print(f"6. validation_records 总记录数: {total_count}")

    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_migration())
        print("\n✓ 全部完成")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
