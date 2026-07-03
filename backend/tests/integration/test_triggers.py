"""openGauss 物理对象集成测试 - 触发器 TR01-TR08

通过 ORM 插入测试数据，验证触发器自动执行效果（不手动调用 SP）。
所有测试标注 @pytest.mark.integration，依赖物理对象已创建。
"""
import pytest
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.like import Like
from app.models.favorite import Favorite
from app.models.validation_record import ValidationRecord


# ============================================================
# 辅助函数（与 test_stored_procedures.py 一致，避免跨测试模块导入）
# ============================================================

async def _create_user(
    db_session: AsyncSession,
    school_id: int,
    email: str = "tr_user@example.com",
    nickname: str = "TR用户",
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
    title: str = "TR测试帖子",
    content: str = "这是触发器测试帖子的内容",
    status: str = "pending",
    location_id: int | None = None,
    view_count: int = 0,
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
        view_count=view_count,
        expire_at=expire_at,
        activity_start_at=activity_start_at,
        activity_end_at=activity_end_at,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)
    return post


# ============================================================
# TR01 trg_validation_after_insert
# ============================================================

class TestTR01ValidationAfterInsert:
    """TR01 trg_validation_after_insert

    触发：AFTER INSERT ON validation_records
    功能：调用 SP01 重算可信度 + SP04 更新验证者/作者信誉 + 若 conflict_report 调用 SP03
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tr01_auto_updates_credibility(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """通过 ORM 插入 validation_record，验证 posts.credibility_score 被自动更新（不手动调用 SP）

        作者默认信誉 60，插入 1 条 confirmation：
        - 触发器调用 SP01：credibility = 60*0.3 + 50*0.7 + 5 = 58.00
        - 随后触发器调用 SP04 更新作者信誉，但 credibility 已在 SP04 前写入
        """
        author = await _create_user(
            db_session, test_school["id"],
            email="tr01_author@example.com", nickname="TR01作者",
        )
        validator = await _create_user(
            db_session, test_school["id"],
            email="tr01_validator@example.com", nickname="TR01验证者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        # 初始 credibility_score 应为 NULL（未调用 SP）
        initial_cred = await db_conn.fetchval(
            "SELECT credibility_score FROM posts WHERE id = $1", post.id
        )
        assert initial_cred is None

        # 插入 validation_record，触发器自动调用 SP01
        vr = ValidationRecord(
            post_id=post.id,
            user_id=validator.id,
            validation_type="confirmation",
            comment="TR01测试确认",
        )
        db_session.add(vr)
        await db_session.commit()

        # 验证 credibility_score 已被触发器自动更新为 58.00
        cred = await db_conn.fetchval(
            "SELECT credibility_score FROM posts WHERE id = $1", post.id
        )
        assert cred is not None
        # 60*0.3 + 50*0.7 + 5 = 58.00（SP01 在 SP04 更新信誉前执行）
        assert float(cred) == pytest.approx(58.00)


# ============================================================
# TR02 trg_validation_after_delete
# ============================================================

class TestTR02ValidationAfterDelete:
    """TR02 trg_validation_after_delete

    触发：AFTER DELETE ON validation_records
    功能：调用 SP01 重算可信度
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tr02_recalc_after_delete(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """插入 1 条 confirmation（可信度变 58），删除该记录，验证可信度回到 53

        注意：插入时触发器会调用 SP04 更新作者信誉分。
        删除前重置作者信誉分为 NULL，使 SP01 用默认 60 计算。
        """
        author = await _create_user(
            db_session, test_school["id"],
            email="tr02_author@example.com", nickname="TR02作者",
        )
        validator = await _create_user(
            db_session, test_school["id"],
            email="tr02_validator@example.com", nickname="TR02验证者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        # 插入 confirmation（触发器使 credibility = 58.00）
        vr = ValidationRecord(
            post_id=post.id,
            user_id=validator.id,
            validation_type="confirmation",
            comment="TR02测试确认",
        )
        db_session.add(vr)
        await db_session.commit()
        await db_session.refresh(vr)

        cred_after_insert = await db_conn.fetchval(
            "SELECT credibility_score FROM posts WHERE id = $1", post.id
        )
        assert float(cred_after_insert) == pytest.approx(58.00)

        # 重置作者信誉分为 NULL，隔离 TR02 的 SP01 计算
        await db_conn.execute(
            "UPDATE users SET reputation_score = NULL WHERE id = $1", author.id
        )

        # 删除 validation_record，触发器应调用 SP01 重算
        await db_conn.execute(
            "DELETE FROM validation_records WHERE id = $1", vr.id
        )

        cred_after_delete = await db_conn.fetchval(
            "SELECT credibility_score FROM posts WHERE id = $1", post.id
        )
        # 60*0.3 + 50*0.7 = 53.00（无验证记录）
        assert float(cred_after_delete) == pytest.approx(53.00)


# ============================================================
# TR03 trg_post_status_change
# ============================================================

class TestTR03PostStatusChange:
    """TR03 trg_post_status_change

    触发：AFTER UPDATE OF status ON posts
    功能：status 变更时向 admin_operation_logs 写日志
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tr03_logs_status_change(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """UPDATE posts SET status='published' WHERE id=X，验证 admin_operation_logs 新增 1 条 action='status_change'"""
        author = await _create_user(
            db_session, test_school["id"],
            email="tr03_author@example.com", nickname="TR03作者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            status="pending",
        )

        # 更新 status，触发器应记录日志
        await db_conn.execute(
            "UPDATE posts SET status = 'published' WHERE id = $1", post.id
        )

        log_cnt = await db_conn.fetchval(
            "SELECT COUNT(*) FROM admin_operation_logs "
            "WHERE action = 'status_change' AND target_id = $1",
            post.id,
        )
        assert log_cnt == 1


# ============================================================
# TR04 trg_comment_update_count
# ============================================================

class TestTR04CommentUpdateCount:
    """TR04 trg_comment_update_count

    触发：AFTER INSERT/DELETE ON comments
    功能：posts.comment_count 自动 +1/-1，用 GREATEST 防止负数
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tr04_insert_and_delete_comment(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """插入评论验证 comment_count=1，删除验证 comment_count=0"""
        author = await _create_user(
            db_session, test_school["id"],
            email="tr04_author@example.com", nickname="TR04作者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        # 插入评论
        comment = Comment(
            post_id=post.id,
            user_id=author.id,
            content="TR04测试评论内容",
        )
        db_session.add(comment)
        await db_session.commit()
        await db_session.refresh(comment)

        count_after_insert = await db_conn.fetchval(
            "SELECT comment_count FROM posts WHERE id = $1", post.id
        )
        assert count_after_insert == 1

        # 删除评论
        await db_conn.execute(
            "DELETE FROM comments WHERE id = $1", comment.id
        )

        count_after_delete = await db_conn.fetchval(
            "SELECT comment_count FROM posts WHERE id = $1", post.id
        )
        assert count_after_delete == 0


# ============================================================
# TR05 trg_like_update_count
# ============================================================

class TestTR05LikeUpdateCount:
    """TR05 trg_like_update_count

    触发：AFTER INSERT/DELETE ON likes
    功能：posts.like_count 自动 +1/-1
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tr05_insert_and_delete_like(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """插入点赞验证 like_count=1，删除验证 like_count=0"""
        author = await _create_user(
            db_session, test_school["id"],
            email="tr05_author@example.com", nickname="TR05作者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        # 插入点赞
        like = Like(
            post_id=post.id,
            user_id=author.id,
        )
        db_session.add(like)
        await db_session.commit()
        await db_session.refresh(like)

        count_after_insert = await db_conn.fetchval(
            "SELECT like_count FROM posts WHERE id = $1", post.id
        )
        assert count_after_insert == 1

        # 删除点赞
        await db_conn.execute(
            "DELETE FROM likes WHERE id = $1", like.id
        )

        count_after_delete = await db_conn.fetchval(
            "SELECT like_count FROM posts WHERE id = $1", post.id
        )
        assert count_after_delete == 0


# ============================================================
# TR06 trg_favorite_update_count
# ============================================================

class TestTR06FavoriteUpdateCount:
    """TR06 trg_favorite_update_count

    触发：AFTER INSERT/DELETE ON favorites
    功能：posts.favorite_count 自动 +1/-1
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tr06_insert_and_delete_favorite(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """插入收藏验证 favorite_count=1，删除验证 favorite_count=0"""
        author = await _create_user(
            db_session, test_school["id"],
            email="tr06_author@example.com", nickname="TR06作者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
        )

        # 插入收藏
        favorite = Favorite(
            post_id=post.id,
            user_id=author.id,
        )
        db_session.add(favorite)
        await db_session.commit()
        await db_session.refresh(favorite)

        count_after_insert = await db_conn.fetchval(
            "SELECT favorite_count FROM posts WHERE id = $1", post.id
        )
        assert count_after_insert == 1

        # 删除收藏
        await db_conn.execute(
            "DELETE FROM favorites WHERE id = $1", favorite.id
        )

        count_after_delete = await db_conn.fetchval(
            "SELECT favorite_count FROM posts WHERE id = $1", post.id
        )
        assert count_after_delete == 0


# ============================================================
# TR07 trg_post_update_view_count
# ============================================================

class TestTR07PostUpdateViewCount:
    """TR07 trg_post_update_view_count

    触发：AFTER UPDATE ON posts WHEN (NEW.view_count > OLD.view_count)
    功能：每 100 次浏览记录一次日志
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tr07_view_milestone_log(
        self, db_conn, db_session, ensure_physical_objects,
        test_school, test_category, test_post_type,
    ):
        """将 view_count 从 99 改为 100，验证 admin_operation_logs 新增 action='view_milestone'"""
        author = await _create_user(
            db_session, test_school["id"],
            email="tr07_author@example.com", nickname="TR07作者",
        )
        post = await _create_post(
            db_session, author.id, test_school["id"],
            test_category["id"], test_post_type["id"],
            view_count=99,
        )

        # 更新 view_count 从 99 → 100，应触发里程碑日志
        await db_conn.execute(
            "UPDATE posts SET view_count = 100 WHERE id = $1", post.id
        )

        log_cnt = await db_conn.fetchval(
            "SELECT COUNT(*) FROM admin_operation_logs "
            "WHERE action = 'view_milestone' AND target_id = $1",
            post.id,
        )
        assert log_cnt == 1


# ============================================================
# TR08 trg_user_soft_delete
# ============================================================

class TestTR08UserSoftDelete:
    """TR08 trg_user_soft_delete

    触发：BEFORE UPDATE ON users
    功能：is_deleted 从 FALSE 变 TRUE 时，自动设置 deleted_at + is_active=FALSE + 写日志
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tr08_soft_delete_auto_fills_fields(
        self, db_conn, db_session, ensure_physical_objects, test_school,
    ):
        """UPDATE users SET is_deleted=TRUE WHERE id=X，验证 deleted_at 填充、is_active=FALSE、日志有 user_soft_delete"""
        user = await _create_user(
            db_session, test_school["id"],
            email="tr08_user@example.com", nickname="TR08用户",
        )

        # 软删除前：deleted_at=NULL, is_active=TRUE
        before = await db_conn.fetchrow(
            "SELECT deleted_at, is_active FROM users WHERE id = $1", user.id
        )
        assert before["deleted_at"] is None
        assert before["is_active"] is True

        # 软删除：触发器应在 BEFORE UPDATE 时自动填充 deleted_at 和 is_active
        await db_conn.execute(
            "UPDATE users SET is_deleted = TRUE WHERE id = $1", user.id
        )

        after = await db_conn.fetchrow(
            "SELECT deleted_at, is_active, is_deleted FROM users WHERE id = $1", user.id
        )
        assert after["is_deleted"] is True
        assert after["deleted_at"] is not None
        assert after["is_active"] is False

        # 验证日志
        log_cnt = await db_conn.fetchval(
            "SELECT COUNT(*) FROM admin_operation_logs "
            "WHERE action = 'user_soft_delete' AND target_id = $1",
            user.id,
        )
        assert log_cnt == 1
