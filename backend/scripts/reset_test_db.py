"""重置测试数据库：DROP + CREATE。"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def main():
    # 连接到默认 postgres 库
    e = create_async_engine(
        "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/postgres",
        isolation_level="AUTOCOMMIT",
    )
    async with e.connect() as c:
        # 终止所有连接到测试库的会话
        await c.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname='moment_campus_test' AND pid <> pg_backend_pid()"
        ))
        await c.execute(text("DROP DATABASE IF EXISTS moment_campus_test"))
        await c.execute(text("CREATE DATABASE moment_campus_test"))
    await e.dispose()
    print("Test database moment_campus_test recreated")


if __name__ == "__main__":
    asyncio.run(main())
