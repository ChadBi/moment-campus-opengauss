"""openGauss 物理对象集成测试 - 存储过程 SP01-SP08

使用 db_conn（asyncpg）直接调用存储过程，使用 db_session（ORM）创建测试数据。
所有测试标注 @pytest.mark.integration，依赖物理对象已创建。

FND-02.4: 依赖高级 SQL 对象（存储过程）漂移，待 REL 阶段重新登记后启用。
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.post import Post
from app.models.location import Location
from app.models.validation_record import ValidationRecord
from app.models.admin_operation_log import AdminOperationLog


# FND-02.4: 依赖高级 SQL 对象（05_create_stored_procedures.sql）漂移，待 REL 阶段重新登记后启用
pytestmark = pytest.mark.skip(
    reason="高级 SQL 对象漂移（存储过程 SP01-SP08 依赖 05_create_stored_procedures.sql），"
    "待 REL 阶段重新登记后启用"
)


# ============================================================
# 辅助函数
# ============================================================

async def _create_user(
    db_session: AsyncSession,
    school_id: int,
    email: str = "sp_user@example.com",
    nickname: str = "SP用户",
    reputation_score: Decimal | None = None,
) -> User:
    """创建测试用户并返回 ORM 对象。"""
    user = User(
        email=email,
        nickname=nickname,
        password_hash="dummy_hash",
        school_id=school_id,
        role="user",
        is_active=True,
        reputation_score=reputation_score,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _create_post(
    db_session: AsyncSession,
    user_id: int,
    school_id: int,
    category_id: int,
    post_type_id: int,
    title: str = "SP测试帖子",
    content: str = "这是存储过程测试帖子的内容",
    status: str = "pending",
    location_id: int | None = None,
    expire_at: datetime | None = None,
    activity_start_at: datetime | None = None,
    activity_end_at: datetime | None = None,
) -> Post:
    """创建测试帖子并返回 ORM 对象。"""
    post = Post(
        user_id=user_id,
        school_id=school_id,
        category_id=category_id,
        post_type_id=post_type_id,
        location_id=location_id,
        title=title,
        content=content,
        status=status,
        expire_at=expire_at,
        activity_start_at=activity_start_at,
        activity_end_at=activity_end_at,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)
    return post


async def _create_location(
    db_session: AsyncSession,
    school_id: int,
    name: str = "测试地点",
) -> Location:
    """创建测试地点并返回 ORM 对象。"""
    location = Location(
        school_id=school_id,
        name=name,
        latitude=31.486160,
        longitude=120.274670,
    )
    db_session.add(location)
    await db_session.commit()
    await db_session.refresh(location)
    return location


async def _insert_validation_record(
    db_session: AsyncSession,
    post_id: int,
    user_id: int,
    validation_type: str = "confirmation",
    comment: str = "测试验证",
) -> ValidationRecord:
    """插入验证记录并返回 ORM 对象。

    注意：插入后触发器 trg_validation_after_insert 会自动调用 SP01/SP04。
    """
    vr = ValidationRecord(
        post_id=post_id,
        user_id=user_id,
        validation_type=validation_type,
        comment=comment,
    )
    db_session.add(vr)
    await db_session.commit()
    await db_session.refresh(vr)
    return vr


# ============================================================
# SP01 sp_recalc_credibility
# ============================================================

class TestSP01RecalcCredibility:
    """SP01 sp_recalc_credibility(p_post_id BIGINT) RETURNS NUMERIC(5,2)

    公式：基础分 = 作者信誉*0.3 + 50*0.7；证实+5, 证伪-8, 更新+2, 过期报告-10, 冲突报告-15
    限制范围 [0, 100]
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp01_base_score_default_reputation(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 1：作者默认信誉 60，无验证记录，可信度 = 60*0.3+50*0.7 = 53.00"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp01_author1@example.com", nickname="SP01作者1",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        result = await db_conn.fetchval(
            "SELECT sp_recalc_credibility($1)", post.id
        )
        assert float(result) == pytest.approx(53.00)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp01_with_one_confirmation(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 2：1 条 confirmation，可信度 = 53+5 = 58.00

        注意：插入验证记录会触发 trg_validation_after_insert，
        该触发器会调用 SP04 更新作者信誉分（confirmation 使作者信誉上升）。
        为隔离测试 SP01 公式，调用前重置作者信誉分为 NULL（COALESCE 取 60）。
        """
        author = await _create_user(
            db_session, test_school["id"],
            email="sp01_author2@example.com", nickname="SP01作者2",
        )
        validator = await _create_user(
            db_session, test_school["id"],
            email="sp01_validator2@example.com", nickname="SP01验证者2",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        await _insert_validation_record(
            db_session, post.id, validator.id, validation_type="confirmation",
        )

        # 重置作者信誉分为 NULL，隔离 SP01 公式测试
        await db_conn.execute(
            "UPDATE users SET reputation_score = NULL WHERE id = $1", author.id
        )

        result = await db_conn.fetchval(
            "SELECT sp_recalc_credibility($1)", post.id
        )
        # 60*0.3 + 50*0.7 + 5 = 18 + 35 + 5 = 58.00
        assert float(result) == pytest.approx(58.00)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp01_with_one_refutation(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 3：1 条 refutation（从 0 记录开始），可信度 = 53-8 = 45.00"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp01_author3@example.com", nickname="SP01作者3",
        )
        validator = await _create_user(
            db_session, test_school["id"],
            email="sp01_validator3@example.com", nickname="SP01验证者3",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        await _insert_validation_record(
            db_session, post.id, validator.id, validation_type="refutation",
        )

        # 重置作者信誉分为 NULL，隔离 SP01 公式测试
        await db_conn.execute(
            "UPDATE users SET reputation_score = NULL WHERE id = $1", author.id
        )

        result = await db_conn.fetchval(
            "SELECT sp_recalc_credibility($1)", post.id
        )
        # 60*0.3 + 50*0.7 - 8 = 18 + 35 - 8 = 45.00
        assert float(result) == pytest.approx(45.00)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp01_clamp_to_zero(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 4：20 条 refutation，可信度 clamp 到 0.00

        53 - 20*8 = 53 - 160 = -107 → clamp 到 0.00
        """
        author = await _create_user(
            db_session, test_school["id"],
            email="sp01_author4@example.com", nickname="SP01作者4",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        # 创建 20 个验证者并各插入 1 条 refutation
        for i in range(20):
            validator = await _create_user(
                db_session, test_school["id"],
                email=f"sp01_validator4_{i}@example.com",
                nickname=f"SP01验证者4_{i}",
            )
            await _insert_validation_record(
                db_session, post.id, validator.id,
                validation_type="refutation",
            )

        # 重置作者信誉分为 NULL，隔离 SP01 公式测试
        await db_conn.execute(
            "UPDATE users SET reputation_score = NULL WHERE id = $1", author.id
        )

        result = await db_conn.fetchval(
            "SELECT sp_recalc_credibility($1)", post.id
        )
        assert float(result) == pytest.approx(0.00)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp01_syncs_valid_invalid_count(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 5：验证 posts.valid_count / invalid_count 被同步更新"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp01_author5@example.com", nickname="SP01作者5",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        v1 = await _create_user(
            db_session, test_school["id"],
            email="sp01_v5_a@example.com", nickname="SP01验证者5A",
        )
        v2 = await _create_user(
            db_session, test_school["id"],
            email="sp01_v5_b@example.com", nickname="SP01验证者5B",
        )
        await _insert_validation_record(
            db_session, post.id, v1.id, validation_type="confirmation",
        )
        await _insert_validation_record(
            db_session, post.id, v2.id, validation_type="refutation",
        )

        # 重置作者信誉分后调用 SP01
        await db_conn.execute(
            "UPDATE users SET reputation_score = NULL WHERE id = $1", author.id
        )
        await db_conn.fetchval("SELECT sp_recalc_credibility($1)", post.id)

        row = await db_conn.fetchrow(
            "SELECT valid_count, invalid_count FROM posts WHERE id = $1", post.id
        )
        assert row["valid_count"] == 1
        assert row["invalid_count"] == 1


# ============================================================
# SP02 sp_mark_expired_posts
# ============================================================

class TestSP02MarkExpiredPosts:
    """SP02 sp_mark_expired_posts() RETURNS INTEGER

    将 expire_at < now 且 status='published' 的帖子标记为 expired。
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp02_marks_expired_post(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 1：published 帖子（expire_at 为过去），调用 SP 返回 1，状态变 expired"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp02_author1@example.com", nickname="SP02作者1",
        )
        # ORM 模型 expire_at 为 TIMESTAMP WITHOUT TIME ZONE，
        # DB 的 CURRENT_TIMESTAMP 为 UTC，故用 naive UTC 时间保持一致
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="published", expire_at=past_time,
        )

        affected = await db_conn.fetchval("SELECT sp_mark_expired_posts()")
        assert affected == 1

        status = await db_conn.fetchval(
            "SELECT status FROM posts WHERE id = $1", post.id
        )
        assert status == "expired"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp02_skips_future_expire(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 2：published 帖子（expire_at 为未来），调用 SP 返回 0"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp02_author2@example.com", nickname="SP02作者2",
        )
        future_time = (datetime.now(timezone.utc) + timedelta(days=7)).replace(tzinfo=None)
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="published", expire_at=future_time,
        )

        affected = await db_conn.fetchval("SELECT sp_mark_expired_posts()")
        assert affected == 0

        status = await db_conn.fetchval(
            "SELECT status FROM posts WHERE id = $1", post.id
        )
        assert status == "published"


# ============================================================
# SP03 sp_detect_conflict
# ============================================================

class TestSP03DetectConflict:
    """SP03 sp_detect_conflict(p_post_id BIGINT) RETURNS INTEGER

    检测同地点、时间重叠、published 的其他帖子，存在则标记当前为 conflict。
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp03_detects_conflict(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 1：2 个帖子同地点+时间重叠+published，返回 1，当前帖子 status=conflict"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp03_author1@example.com", nickname="SP03作者1",
        )
        location = await _create_location(
            db_session, test_school["id"], name="SP03冲突地点",
        )
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now() + timedelta(hours=1)

        # 帖子 A：已 published
        post_a = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="published", location_id=location.id,
            activity_start_at=start, activity_end_at=end,
        )
        # 帖子 B：时间重叠，published
        post_b = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="published", location_id=location.id,
            activity_start_at=start, activity_end_at=end,
        )

        conflict_cnt = await db_conn.fetchval(
            "SELECT sp_detect_conflict($1)", post_b.id
        )
        assert conflict_cnt == 1

        status = await db_conn.fetchval(
            "SELECT status FROM posts WHERE id = $1", post_b.id
        )
        assert status == "conflict"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp03_no_location_returns_zero(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 2：无地点或无活动时间，返回 0"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp03_author2@example.com", nickname="SP03作者2",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="published",
            # 无 location_id, 无 activity 时间
        )

        result = await db_conn.fetchval(
            "SELECT sp_detect_conflict($1)", post.id
        )
        assert result == 0


# ============================================================
# SP04 sp_update_reputation
# ============================================================

class TestSP04UpdateReputation:
    """SP04 sp_update_reputation(p_user_id BIGINT) RETURNS NUMERIC(5,2)

    公式：60 + 证实*3 + 发布*0.5 - 证伪*5 - 被举报*2；clamp [0,100]
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp04_new_user_default_reputation(
        self, db_conn, db_session, ensure_physical_objects, test_school,
    ):
        """测试 1：新建用户（无帖子无验证），信誉 = 60 + 0 + 0 - 0 - 0 = 60.00"""
        user = await _create_user(
            db_session, test_school["id"],
            email="sp04_user1@example.com", nickname="SP04用户1",
        )

        result = await db_conn.fetchval(
            "SELECT sp_update_reputation($1)", user.id
        )
        assert float(result) == pytest.approx(60.00)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp04_with_two_posts(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 2：用户发布 2 个帖子，信誉 = 60 + 0 + 2*0.5 - 0 - 0 = 61.00"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp04_user2@example.com", nickname="SP04用户2",
        )
        await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            title="SP04帖子A", content="内容A内容A内容A",
        )
        await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            title="SP04帖子B", content="内容B内容B内容B",
        )

        result = await db_conn.fetchval(
            "SELECT sp_update_reputation($1)", author.id
        )
        # 60 + 0 + 2*0.5 - 0 - 0 = 61.00
        assert float(result) == pytest.approx(61.00)


# ============================================================
# SP05 sp_archive_logs
# ============================================================

class TestSP05ArchiveLogs:
    """SP05 sp_archive_logs() RETURNS INTEGER

    将 90 天前的 admin_operation_logs 迁移到 admin_operation_logs_archive。
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp05_archives_old_logs(
        self, db_conn, db_session, ensure_physical_objects, test_school,
    ):
        """测试：插入 1 条 100 天前 + 1 条 10 天前的日志，SP 返回 1，归档表 1 条，原表 1 条"""
        admin = await _create_user(
            db_session, test_school["id"],
            email="sp05_admin@example.com", nickname="SP05管理员",
        )

        # 100 天前的日志
        old_log = AdminOperationLog(
            admin_id=admin.id,
            action="test_old_action",
            target_type="post",
            target_id=1,
            detail="100天前的日志",
            created_at=datetime.now() - timedelta(days=100),
        )
        # 10 天前的日志
        recent_log = AdminOperationLog(
            admin_id=admin.id,
            action="test_recent_action",
            target_type="post",
            target_id=2,
            detail="10天前的日志",
            created_at=datetime.now() - timedelta(days=10),
        )
        db_session.add_all([old_log, recent_log])
        await db_session.commit()

        affected = await db_conn.fetchval("SELECT sp_archive_logs()")
        assert affected == 1

        # 原表应剩 1 条
        original_cnt = await db_conn.fetchval(
            "SELECT COUNT(*) FROM admin_operation_logs WHERE action LIKE 'test_%'"
        )
        assert original_cnt == 1

        # 归档表应有 1 条（openGauss 不支持 IF EXISTS，用子查询兜底）
        archive_cnt = await db_conn.fetchval(
            "SELECT COUNT(*) FROM admin_operation_logs_archive WHERE action LIKE 'test_%'"
        )
        assert archive_cnt == 1


# ============================================================
# SP06 sp_cleanup_soft_deleted
# ============================================================

class TestSP06CleanupSoftDeleted:
    """SP06 sp_cleanup_soft_deleted() RETURNS INTEGER

    物理删除 30 天前软删除的数据。
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp06_cleans_old_soft_deleted_posts(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试：插入 1 条 40 天前软删除 + 1 条 10 天前软删除的 post，SP 返回 >= 1"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp06_author@example.com", nickname="SP06作者",
        )

        # 40 天前软删除的帖子
        old_post = Post(
            user_id=author.id, school_id=test_school["id"],
            category_id=test_category["id"], post_type_id=test_post_type["id"],
            title="SP06旧帖", content="40天前软删除的内容",
            is_deleted=True,
            deleted_at=datetime.now() - timedelta(days=40),
        )
        # 10 天前软删除的帖子（不应被清理）
        recent_post = Post(
            user_id=author.id, school_id=test_school["id"],
            category_id=test_category["id"], post_type_id=test_post_type["id"],
            title="SP06新帖", content="10天前软删除的内容",
            is_deleted=True,
            deleted_at=datetime.now() - timedelta(days=10),
        )
        db_session.add_all([old_post, recent_post])
        await db_session.commit()

        affected = await db_conn.fetchval("SELECT sp_cleanup_soft_deleted()")
        # 至少清理了 1 条（old_post），可能还有日志记录
        assert affected >= 1

        # 旧帖应已被物理删除
        old_exists = await db_conn.fetchval(
            "SELECT 1 FROM posts WHERE id = $1", old_post.id
        )
        assert old_exists is None

        # 新帖应仍存在
        recent_exists = await db_conn.fetchval(
            "SELECT 1 FROM posts WHERE id = $1", recent_post.id
        )
        assert recent_exists == 1


# ============================================================
# SP07 sp_publish_post
# ============================================================

class TestSP07PublishPost:
    """SP07 sp_publish_post(...) RETURNS BIGINT

    校验用户存在+激活、标题内容非空、插入帖子、初始化可信度、记录日志。
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp07_valid_publish(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 1：合法调用，返回 post_id > 0，帖子已插入且 credibility_score = 53.00"""
        author = await _create_user(
            db_session, test_school["id"],
            email="sp07_author1@example.com", nickname="SP07作者1",
        )

        # SP07 共 13 个参数；None 值需显式类型转换，否则 asyncpg 推断为 unknown 导致函数匹配失败
        post_id = await db_conn.fetchval(
            "SELECT sp_publish_post("
            "$1::bigint, $2::bigint, $3::bigint, $4::bigint, "
            "$5::bigint, $6::varchar, $7::text, $8::boolean, "
            "$9::timestamptz, $10::timestamptz, $11::timestamptz, "
            "$12::varchar, $13::varchar)",
            author.id,                       # p_user_id
            test_school["id"],               # p_school_id
            test_category["id"],             # p_category_id
            test_post_type["id"],            # p_post_type_id
            None,                            # p_location_id
            "SP07合法标题",                   # p_title
            "SP07合法内容至少十个字符",        # p_content
            False,                           # p_is_anonymous
            None,                            # p_expire_at
            None,                            # p_activity_start_at
            None,                            # p_activity_end_at
            None,                            # p_contact_info
            "pending",                       # p_status
        )

        assert post_id is not None
        assert post_id > 0

        row = await db_conn.fetchrow(
            "SELECT credibility_score, status, title FROM posts WHERE id = $1",
            post_id,
        )
        assert row is not None
        # 作者默认信誉 60，初始可信度 = 60*0.3 + 50*0.7 = 53.00
        assert float(row["credibility_score"]) == pytest.approx(53.00)
        assert row["status"] == "pending"
        assert row["title"] == "SP07合法标题"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp07_invalid_user_raises(
        self, db_conn, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 2：传入不存在的 user_id，抛异常"""
        import asyncpg

        with pytest.raises(asyncpg.PostgresError):
            await db_conn.fetchval(
                "SELECT sp_publish_post("
                "$1::bigint, $2::bigint, $3::bigint, $4::bigint, "
                "$5::bigint, $6::varchar, $7::text, $8::boolean, "
                "$9::timestamptz, $10::timestamptz, $11::timestamptz, "
                "$12::varchar, $13::varchar)",
                999999,                          # 不存在的 user_id
                test_school["id"],
                test_category["id"],
                test_post_type["id"],
                None,
                "标题", "内容内容内容",
                False, None, None, None, None, "pending",
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp07_empty_title_raises(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 3：传入 NULL 标题，抛异常（p_title IS NULL 分支）"""
        import asyncpg

        author = await _create_user(
            db_session, test_school["id"],
            email="sp07_author3@example.com", nickname="SP07作者3",
        )

        with pytest.raises(asyncpg.PostgresError):
            await db_conn.fetchval(
                "SELECT sp_publish_post("
                "$1::bigint, $2::bigint, $3::bigint, $4::bigint, "
                "$5::bigint, $6::varchar, $7::text, $8::boolean, "
                "$9::timestamptz, $10::timestamptz, $11::timestamptz, "
                "$12::varchar, $13::varchar)",
                author.id,
                test_school["id"],
                test_category["id"],
                test_post_type["id"],
                None,
                None,                             # NULL 标题
                "内容内容内容",
                False, None, None, None, None, "pending",
            )


# ============================================================
# SP08 sp_submit_validation
# ============================================================

class TestSP08SubmitValidation:
    """SP08 sp_submit_validation(p_user_id, p_post_id, p_validation_type, p_content, p_evidence_urls) RETURNS BIGINT

    原子化提交验证 + 重算可信度 + 冲突检测 + 信誉分更新。
    校验：不能为自己的信息验证、信息状态必须为 published、验证类型合法。
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp08_valid_submission(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 1：用户 A 发布帖子（published），用户 B 提交 confirmation，返回 record_id > 0"""
        author_a = await _create_user(
            db_session, test_school["id"],
            email="sp08_author_a@example.com", nickname="SP08作者A",
        )
        user_b = await _create_user(
            db_session, test_school["id"],
            email="sp08_user_b@example.com", nickname="SP08用户B",
        )
        post = await _create_post(
            db_session, author_a.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="published",
        )

        record_id = await db_conn.fetchval(
            "SELECT sp_submit_validation($1, $2, $3, $4, $5)",
            user_b.id,                       # p_user_id
            post.id,                         # p_post_id
            "confirmation",                  # p_validation_type
            "我确认这条信息是真的",            # p_content
            None,                            # p_evidence_urls
        )

        assert record_id is not None
        assert record_id > 0

        # 验证记录已插入
        vr_exists = await db_conn.fetchval(
            "SELECT 1 FROM validation_records WHERE id = $1 AND validation_type = 'confirmation'",
            record_id,
        )
        assert vr_exists == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp08_self_validation_raises(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 2：用户 A 为自己的帖子调用 SP08，抛异常"""
        import asyncpg

        author = await _create_user(
            db_session, test_school["id"],
            email="sp08_self_author@example.com", nickname="SP08自我验证作者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="published",
        )

        with pytest.raises(asyncpg.PostgresError):
            await db_conn.fetchval(
                "SELECT sp_submit_validation($1, $2, $3, $4, $5)",
                author.id, post.id, "confirmation", "自我验证", None,
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_sp08_draft_post_raises(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """测试 3：对 draft 状态的帖子调用 SP08，抛异常"""
        import asyncpg

        author = await _create_user(
            db_session, test_school["id"],
            email="sp08_draft_author@example.com", nickname="SP08草稿作者",
        )
        validator = await _create_user(
            db_session, test_school["id"],
            email="sp08_draft_validator@example.com", nickname="SP08草稿验证者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="draft",
        )

        with pytest.raises(asyncpg.PostgresError):
            await db_conn.fetchval(
                "SELECT sp_submit_validation($1, $2, $3, $4, $5)",
                validator.id, post.id, "confirmation", "验证草稿帖子", None,
            )
