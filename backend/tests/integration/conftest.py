"""集成测试专用 fixture

FND-02.4: 依赖高级 SQL 对象（表空间/分区/物化视图/存储过程/触发器）的集成测试
在未安装高级对象时全部跳过，不与核心 API 测试混合。

为 openGauss 物理对象（SP/TR/MV）集成测试提供：
- db_conn: asyncpg 原生连接，用于调用存储过程（绕过 ORM）
- ensure_physical_objects: session 级检查，缺失物理对象时 skip
- refresh_mvs: 每用例后刷新物化视图
"""
import os
from urllib.parse import urlparse

import pytest
import pytest_asyncio
import asyncpg
from sqlalchemy import text

from tests.conftest import test_engine, TEST_DATABASE_URL


# 从 TEST_DATABASE_URL 解析连接参数供 asyncpg 使用
# URL 形如 postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test
_parsed = urlparse(TEST_DATABASE_URL.replace("+asyncpg", ""))
_TEST_DB_HOST = _parsed.hostname or "localhost"
_TEST_DB_PORT = _parsed.port or 5432
_TEST_DB_USER = _parsed.username or "gaussdb"
# asyncpg 接受原始密码（无需 URL 解码，urlparse 已自动解码 %40 → @）
_TEST_DB_PASSWORD = _parsed.password or ""
_TEST_DB_NAME = _parsed.path.lstrip("/") if _parsed.path else "moment_campus_test"


class _AutoCommitProxy:
    """asyncpg 连接代理：每次写操作后自动 COMMIT。

    asyncpg 0.31.0 未暴露 set_autocommit 公共方法，默认每个连接处于
    隐式事务中，写入不会立即对其他连接（如 ORM 会话）可见。
    本代理包装 execute/fetchval/fetchrow/fetch，在调用后追加 COMMIT，
    实现 autocommit 语义。
    """

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        # 透传未包装的方法（如 is_in_transaction、transaction、close 等）
        return getattr(self._conn, name)

    async def _commit(self):
        # 仅在事务中才提交，避免无谓的 WARNING
        if self._conn.is_in_transaction():
            await self._conn.execute("COMMIT")

    async def execute(self, *args, **kwargs):
        result = await self._conn.execute(*args, **kwargs)
        await self._commit()
        return result

    async def fetchval(self, *args, **kwargs):
        result = await self._conn.fetchval(*args, **kwargs)
        await self._commit()
        return result

    async def fetchrow(self, *args, **kwargs):
        result = await self._conn.fetchrow(*args, **kwargs)
        await self._commit()
        return result

    async def fetch(self, *args, **kwargs):
        result = await self._conn.fetch(*args, **kwargs)
        await self._commit()
        return result


@pytest_asyncio.fixture
async def db_conn():
    """提供 asyncpg 原生连接（已包装为自动提交），用于调用存储过程（绕过 ORM）。

    FND-02: 连接独立测试库（从 TEST_DATABASE_URL 解析），不连开发库。
    asyncpg 0.31.0 无 set_autocommit，用 _AutoCommitProxy 包装实现自动提交。
    """
    conn = await asyncpg.connect(
        host=_TEST_DB_HOST,
        port=_TEST_DB_PORT,
        user=_TEST_DB_USER,
        password=_TEST_DB_PASSWORD,
        database=_TEST_DB_NAME,
    )
    proxy = _AutoCommitProxy(conn)
    try:
        yield proxy
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session")
async def ensure_physical_objects():
    """检查物理对象（SP/TR/MV）是否存在，缺失则跳过测试。

    集成测试依赖以下物理对象：
    - 存储过程 sp_recalc_credibility
    - 物化视图 mv_post_validation_stats
    - 触发器 trg_validation_after_insert

    FND-02.4: 测试库仅通过 Base.metadata.create_all() 创建 ORM 表，
    不含高级 SQL 对象，故此 fixture 会跳过。
    """
    async with test_engine.connect() as conn:
        sp_exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = 'public' AND p.proname = 'sp_recalc_credibility' "
                    "LIMIT 1"
                )
            )
        ).scalar()

        mv_exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = 'mv_post_validation_stats' "
                    "AND c.relkind = 'm' LIMIT 1"
                )
            )
        ).scalar()

        trg_exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid = t.tgrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND t.tgname = 'trg_validation_after_insert' "
                    "AND NOT t.tgisinternal LIMIT 1"
                )
            )
        ).scalar()

    if not (sp_exists and mv_exists and trg_exists):
        pytest.skip(
            "物理对象未创建（sp_recalc_credibility / mv_post_validation_stats / "
            "trg_validation_after_insert 缺失），请先执行 backend/scripts/opengauss/ 下的 SQL 脚本"
        )

    return True


@pytest_asyncio.fixture(autouse=True)
async def refresh_mvs(request):
    """每用例后刷新物化视图，保证后续用例读取到最新聚合结果。

    刷新 4 个物化视图：
    - mv_post_validation_stats
    - mv_user_reputation_ranking
    - mv_admin_dashboard
    - mv_location_post_count

    注：使用普通 REFRESH（非 CONCURRENTLY），避免对空视图/缺索引的场景报错。
    """
    yield
    if request.node.get_closest_marker("integration") is None:
        return
    async with test_engine.begin() as conn:
        for mv in (
            "mv_post_validation_stats",
            "mv_user_reputation_ranking",
            "mv_admin_dashboard",
            "mv_location_post_count",
        ):
            # 用 DO 块兜底：物化视图不存在时跳过（openGauss 不支持 IF EXISTS）
            await conn.execute(
                text(
                    f"DO $$ BEGIN "
                    f"EXECUTE 'REFRESH MATERIALIZED VIEW {mv}'; "
                    f"EXCEPTION WHEN undefined_table THEN NULL; "
                    f"END $$"
                )
            )
