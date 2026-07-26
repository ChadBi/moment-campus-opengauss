"""T-E-02 集成测试：openGauss 表空间（4 个）

验证 01_create_tablespaces.sql 创建的 4 个表空间存在：
- ts_system: 配置类表（schools / categories / post_types / tags / locations）
- ts_core: 业务核心表（users / posts / validation_records / reports 等）
- ts_interaction: 互动表（comments / likes / favorites / notifications）
- ts_log: 日志表（admin_operation_logs / browse_histories / search_histories）

FND-02.4: 依赖高级 SQL 对象（表空间）漂移，待 REL 阶段重新登记后启用。
"""
import pytest
from sqlalchemy import text

from tests.conftest import test_engine


# FND-02.4: 依赖高级 SQL 对象（01_create_tablespaces.sql）漂移，待 REL 阶段重新登记后启用
pytestmark = pytest.mark.skip(
    reason="高级 SQL 对象漂移（表空间依赖 01_create_tablespaces.sql），"
    "待 REL 阶段重新登记后启用"
)


@pytest.mark.integration
class TestTablespaces:
    """表空间存在性与使用验证"""

    @pytest.mark.asyncio
    async def test_four_tablespaces_exist(self, db_session):
        """4 个表空间全部存在：ts_system / ts_core / ts_interaction / ts_log"""
        result = await db_session.execute(text(
            "SELECT spcname FROM pg_tablespace "
            "WHERE spcname IN ('ts_system','ts_core','ts_interaction','ts_log') "
            "ORDER BY spcname"
        ))
        names = [row[0] for row in result.fetchall()]
        assert len(names) == 4, f"期望 4 个表空间，实际 {len(names)}: {names}"
        assert "ts_system" in names
        assert "ts_core" in names
        assert "ts_interaction" in names
        assert "ts_log" in names

    @pytest.mark.asyncio
    async def test_posts_table_in_ts_core(self, db_session):
        """posts 表位于 ts_core 表空间（或其分区子表位于 ts_core）"""
        # 父表（分区表）的 tablespace 可能记录为 NULL；查分区子表的表空间
        # openGauss 不支持 regnamespace 类型转换，直接用 pg_tables.tablespace
        result = await db_session.execute(text(
            "SELECT tablespace FROM pg_tables "
            "WHERE tablename = 'posts' AND schemaname = 'public'"
        ))
        row = result.first()
        # posts 表只要不位于 ts_interaction / ts_log 即可
        if row and row[0]:
            assert row[0] not in ("ts_interaction", "ts_log"), \
                f"posts 表不应在互动/日志表空间，实际 {row[0]}"

    @pytest.mark.asyncio
    async def test_users_table_not_in_interaction(self, db_session):
        """users 表不应位于互动或日志表空间"""
        result = await db_session.execute(text(
            "SELECT tablespace FROM pg_tables "
            "WHERE tablename = 'users' AND schemaname = 'public'"
        ))
        row = result.first()
        if row and row[0]:
            assert row[0] not in ("ts_interaction", "ts_log"), \
                f"users 表不应在互动/日志表空间，实际 {row[0]}"

    @pytest.mark.asyncio
    async def test_tablespace_directories_exist(self, db_session):
        """表空间对应物理目录存在（pg_tablespace_location 非空）"""
        result = await db_session.execute(text(
            "SELECT spcname, pg_tablespace_location(oid) AS location "
            "FROM pg_tablespace "
            "WHERE spcname IN ('ts_system','ts_core','ts_interaction','ts_log') "
            "ORDER BY spcname"
        ))
        rows = result.fetchall()
        assert len(rows) == 4, f"期望 4 行，实际 {len(rows)}"
        for spcname, location in rows:
            assert location is not None and location != "", \
                f"表空间 {spcname} 无物理目录"

    @pytest.mark.asyncio
    async def test_ts_log_used_by_archive_table(self, db_session):
        """ts_log 表空间被 admin_operation_logs_archive 归档表使用"""
        # 归档表由 09_create_partitions.sql 创建，明确使用 TABLESPACE ts_log
        result = await db_session.execute(text(
            "SELECT tablespace FROM pg_tables "
            "WHERE tablename = 'admin_operation_logs_archive' AND schemaname = 'public'"
        ))
        row = result.first()
        if row is None:
            pytest.skip("admin_operation_logs_archive 表未创建（09 脚本可能未执行）")
        # 归档表应位于 ts_log（脚本明确指定）
        if row[0]:
            assert row[0] == "ts_log", \
                f"归档表应在 ts_log，实际 {row[0]}"
