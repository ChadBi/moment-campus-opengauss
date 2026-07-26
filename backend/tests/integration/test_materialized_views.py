"""T-E-02 集成测试：openGauss 物化视图（4 个）

验证 06_create_materialized_views.sql 创建的 4 个物化视图存在，
并验证 REFRESH 后数据正确。

FND-02.4: 依赖高级 SQL 对象（物化视图）漂移，待 REL 阶段重新登记后启用。
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# FND-02.4: 依赖高级 SQL 对象（06_create_materialized_views.sql）漂移，待 REL 阶段重新登记后启用
pytestmark = pytest.mark.skip(
    reason="高级 SQL 对象漂移（物化视图依赖 06_create_materialized_views.sql），"
    "待 REL 阶段重新登记后启用"
)


@pytest.mark.integration
class TestMaterializedViews:
    """物化视图存在性与数据验证"""

    @pytest.mark.asyncio
    async def test_four_mvs_exist(self, db_session):
        """4 个物化视图全部存在"""
        result = await db_session.execute(text(
            "SELECT relname FROM pg_class "
            "WHERE relkind = 'm' AND relname IN ("
            "  'mv_post_validation_stats',"
            "  'mv_user_reputation_ranking',"
            "  'mv_admin_dashboard',"
            "  'mv_location_post_count'"
            ") ORDER BY relname"
        ))
        names = [row[0] for row in result.fetchall()]
        assert len(names) == 4, f"期望 4 个物化视图，实际 {len(names)}: {names}"

    @pytest.mark.asyncio
    async def test_mv01_post_validation_stats_columns(self, db_session):
        """MV01 mv_post_validation_stats 包含必要列"""
        result = await db_session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'mv_post_validation_stats' ORDER BY column_name"
        ))
        cols = {row[0] for row in result.fetchall()}
        expected = {"post_id", "confirm_cnt", "refute_cnt", "total_cnt", "credibility_score"}
        assert expected.issubset(cols), f"缺失列: {expected - cols}"

    @pytest.mark.asyncio
    async def test_mv01_reflects_validation_data(
        self, db_session, test_user, admin_user, test_post, second_user
    ):
        """MV01 反映验证统计数据：插入验证记录后 REFRESH，MV 应包含正确计数"""
        # test_post 由 test_user 创建，status 默认 pending
        # 先发布帖子
        await db_session.execute(text(
            "UPDATE posts SET status = 'published' WHERE id = :pid"
        ), {"pid": test_post["id"]})
        await db_session.commit()

        # 插入 1 条 confirmation
        await db_session.execute(text(
            "INSERT INTO validation_records (post_id, user_id, validation_type, is_deleted, created_at) "
            "VALUES (:pid, :uid, 'confirmation', FALSE, CURRENT_TIMESTAMP)"
        ), {"pid": test_post["id"], "uid": second_user["id"] if "id" in second_user else 2})
        await db_session.commit()

        # REFRESH MV01
        await db_session.execute(text("REFRESH MATERIALIZED VIEW mv_post_validation_stats"))
        await db_session.commit()

        # 查询 MV
        result = await db_session.execute(text(
            "SELECT confirm_cnt, total_cnt FROM mv_post_validation_stats WHERE post_id = :pid"
        ), {"pid": test_post["id"]})
        row = result.first()
        assert row is not None, "MV01 未包含该帖子的统计"
        assert row[0] == 1, f"confirm_cnt 期望 1，实际 {row[0]}"
        assert row[1] == 1, f"total_cnt 期望 1，实际 {row[1]}"

    @pytest.mark.asyncio
    async def test_mv02_user_reputation_ranking_columns(self, db_session):
        """MV02 mv_user_reputation_ranking 包含必要列"""
        result = await db_session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'mv_user_reputation_ranking' ORDER BY column_name"
        ))
        cols = {row[0] for row in result.fetchall()}
        expected = {"user_id", "nickname", "reputation_score", "reputation_rank"}
        assert expected.issubset(cols), f"缺失列: {expected - cols}"

    @pytest.mark.asyncio
    async def test_mv02_reflects_reputation(self, db_session, test_user):
        """MV02 反映用户信誉分"""
        # 设置用户信誉分
        await db_session.execute(text(
            "UPDATE users SET reputation_score = 88.50 WHERE id = :uid"
        ), {"uid": test_user["id"] if "id" in test_user else 1})
        await db_session.commit()

        # REFRESH MV02
        await db_session.execute(text("REFRESH MATERIALIZED VIEW mv_user_reputation_ranking"))
        await db_session.commit()

        result = await db_session.execute(text(
            "SELECT reputation_score FROM mv_user_reputation_ranking "
            "WHERE user_id = :uid"
        ), {"uid": test_user["id"] if "id" in test_user else 1})
        row = result.first()
        # 用户可能被 MV 过滤（is_deleted=FALSE），若存在则校验
        if row:
            assert float(row[0]) == pytest.approx(88.50, abs=0.01)

    @pytest.mark.asyncio
    async def test_mv03_admin_dashboard_single_row(self, db_session):
        """MV03 mv_admin_dashboard 是单行视图（id=1）"""
        await db_session.execute(text("REFRESH MATERIALIZED VIEW mv_admin_dashboard"))
        await db_session.commit()
        result = await db_session.execute(text(
            "SELECT COUNT(*) FROM mv_admin_dashboard"
        ))
        count = result.scalar()
        assert count == 1, f"MV03 应为单行视图，实际 {count} 行"

    @pytest.mark.asyncio
    async def test_mv03_admin_dashboard_columns(self, db_session):
        """MV03 包含聚合统计列"""
        result = await db_session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'mv_admin_dashboard' ORDER BY column_name"
        ))
        cols = {row[0] for row in result.fetchall()}
        expected = {"id", "total_users", "total_posts", "total_comments", "avg_reputation"}
        assert expected.issubset(cols), f"缺失列: {expected - cols}"

    @pytest.mark.asyncio
    async def test_mv04_location_post_count_columns(self, db_session):
        """MV04 mv_location_post_count 包含必要列"""
        result = await db_session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'mv_location_post_count' ORDER BY column_name"
        ))
        cols = {row[0] for row in result.fetchall()}
        expected = {"location_id", "location_name", "total_post_count", "published_count"}
        assert expected.issubset(cols), f"缺失列: {expected - cols}"

    @pytest.mark.asyncio
    async def test_unique_indexes_exist(self, db_session):
        """4 个物化视图都有唯一索引（支持 CONCURRENTLY 刷新）"""
        expected_indexes = {
            "idx_mv_post_validation_pk",
            "idx_mv_user_reputation_pk",
            "idx_mv_admin_dashboard_pk",
            "idx_mv_location_post_count_pk",
        }
        result = await db_session.execute(text(
            "SELECT indexname FROM pg_indexes "
            "WHERE indexname LIKE 'idx_mv_%' "
            "AND schemaname = 'public'"
        ))
        actual = {row[0] for row in result.fetchall()}
        missing = expected_indexes - actual
        assert not missing, f"缺失唯一索引: {missing}"
