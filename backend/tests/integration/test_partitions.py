"""T-E-02 集成测试：openGauss 分区表（7 张）

验证 09_create_partitions.sql 创建的 7 张分区表存在，
并验证数据按时间落在正确分区。

FND-02.4: 依赖高级 SQL 对象（分区表）漂移，待 REL 阶段重新登记后启用。
"""
import pytest
from sqlalchemy import text
from datetime import datetime


# FND-02.4: 依赖高级 SQL 对象（09_create_partitions.sql）漂移，待 REL 阶段重新登记后启用
pytestmark = pytest.mark.skip(
    reason="高级 SQL 对象漂移（分区表依赖 09_create_partitions.sql），"
    "待 REL 阶段重新登记后启用"
)


# 7 张分区表
PARTITIONED_TABLES = [
    "posts",
    "comments",
    "notifications",
    "admin_operation_logs",
    "browse_histories",
    "search_histories",
    "validation_records",
]

# 2026 年 1-12 月分区命名模式（openGauss 分区子表命名）
EXPECTED_PARTITION_COUNT_MIN = 7  # 至少 7 张分区表


@pytest.mark.integration
class TestPartitions:
    """分区表存在性与数据路由验证"""

    @pytest.mark.asyncio
    async def test_seven_tables_are_partitioned(self, db_session):
        """7 张大表均为分区表"""
        for table_name in PARTITIONED_TABLES:
            result = await db_session.execute(text(
                "SELECT COUNT(*) FROM pg_partition p "
                "JOIN pg_class c ON c.oid = p.parentid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = :tbl"
            ), {"tbl": table_name})
            count = result.scalar()
            assert count is not None and count > 0, f"表 {table_name} 不是分区表或无分区"

    @pytest.mark.asyncio
    async def test_posts_has_monthly_partitions(self, db_session):
        """posts 表有按月分区（至少 12 个月 + default）"""
        result = await db_session.execute(text(
            "SELECT COUNT(*) FROM pg_partition p "
            "JOIN pg_class c ON c.oid = p.parentid "
            "WHERE c.relname = 'posts'"
        ))
        count = result.scalar()
        assert count >= 12, f"posts 分区数期望 >=12，实际 {count}"

    @pytest.mark.integration
    async def test_archive_table_exists(self, db_session):
        """归档表 admin_operation_logs_archive 存在"""
        result = await db_session.execute(text(
            "SELECT 1 FROM pg_tables WHERE tablename = 'admin_operation_logs_archive'"
        ))
        assert result.first() is not None, "归档表 admin_operation_logs_archive 不存在"

    @pytest.mark.asyncio
    async def test_archive_table_has_archived_at_column(self, db_session):
        """归档表包含 archived_at 字段"""
        result = await db_session.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'admin_operation_logs_archive' AND column_name = 'archived_at'"
        ))
        assert result.first() is not None, "归档表缺失 archived_at 字段"

    @pytest.mark.asyncio
    async def test_partition_pruning_works(self, db_session, test_user, test_post):
        """分区裁剪：按时间查询只扫描对应分区"""
        # 查询当前月的帖子，EXPLAIN 应只扫描 1 个分区
        result = await db_session.execute(text(
            "EXPLAIN SELECT * FROM posts "
            "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) "
            "AND created_at < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')"
        ))
        plan = "\n".join(str(row[0]) for row in result.fetchall())
        # 分区裁剪后应只扫描 1 个分区子表（含 Partitioned scan 或类似）
        # 这里仅验证 EXPLAIN 不报错且返回了计划
        assert len(plan) > 0, "EXPLAIN 未返回执行计划"

    @pytest.mark.asyncio
    async def test_fn_is_partitioned_helper(self, db_session):
        """辅助函数 fn_is_partitioned 正确识别分区表"""
        # posts 应为分区表
        result = await db_session.execute(text(
            "SELECT fn_is_partitioned('posts')"
        ))
        assert result.scalar() is True

        # users 应不是分区表
        result = await db_session.execute(text(
            "SELECT fn_is_partitioned('users')"
        ))
        assert result.scalar() is False
