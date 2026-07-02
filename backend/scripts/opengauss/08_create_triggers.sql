-- ============================================================
-- 脚本名称：08_create_triggers.sql
-- 用途：创建 8 个触发器函数与触发器（TR01-TR08）
-- 依据：docs/27_数据库物理模型设计.md 第 5 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. 触发器函数返回 TRIGGER，使用 PL/pgSQL
--   2. openGauss 使用 EXECUTE PROCEDURE 语法（兼容 PostgreSQL）
--   3. 依赖 07_create_functions.sql 中的 SP01/SP03/SP04 存储过程
--   4. 计数类触发器（TR04-TR06）使用 GREATEST 防止负数
-- ============================================================

-- ============================================================
-- TR01 trg_validation_after_insert
-- 触发时机：AFTER INSERT ON validation_records
-- 功能：重算信息可信度 + 更新验证者/作者信誉分 + 冲突检测
-- ============================================================
CREATE OR REPLACE FUNCTION trg_func_validation_after_insert()
RETURNS TRIGGER AS $$
DECLARE
    v_post_author BIGINT;
BEGIN
    -- 重算信息可信度
    PERFORM sp_recalc_credibility(NEW.post_id);

    -- 获取信息作者
    SELECT user_id INTO v_post_author FROM posts WHERE id = NEW.post_id;

    -- 更新验证者信誉分
    PERFORM sp_update_reputation(NEW.user_id);

    -- 更新信息作者信誉分
    IF v_post_author IS NOT NULL AND v_post_author <> NEW.user_id THEN
        PERFORM sp_update_reputation(v_post_author);
    END IF;

    -- 若为冲突报告，触发冲突检测
    IF NEW.validation_type = 'conflict_report' THEN
        PERFORM sp_detect_conflict(NEW.post_id);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validation_after_insert ON validation_records;
CREATE TRIGGER trg_validation_after_insert
    AFTER INSERT ON validation_records
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_validation_after_insert();

COMMENT ON FUNCTION trg_func_validation_after_insert() IS 'TR01 验证记录插入后触发：重算可信度+更新信誉分+冲突检测';

-- ============================================================
-- TR02 trg_validation_after_delete
-- 触发时机：AFTER DELETE ON validation_records
-- 功能：重算信息可信度（验证记录被撤销时）
-- ============================================================
CREATE OR REPLACE FUNCTION trg_func_validation_after_delete()
RETURNS TRIGGER AS $$
BEGIN
    -- 重算信息可信度（验证记录被删除后重新统计）
    PERFORM sp_recalc_credibility(OLD.post_id);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validation_after_delete ON validation_records;
CREATE TRIGGER trg_validation_after_delete
    AFTER DELETE ON validation_records
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_validation_after_delete();

COMMENT ON FUNCTION trg_func_validation_after_delete() IS 'TR02 验证记录删除后触发：重算可信度';

-- ============================================================
-- TR03 trg_post_status_change
-- 触发时机：AFTER UPDATE OF status ON posts
-- 功能：状态变更时记录日志
-- ============================================================
CREATE OR REPLACE FUNCTION trg_func_post_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- 仅在 status 实际变更时记录日志
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO admin_operation_logs (admin_id, action, target_type, target_id, detail, created_at)
        VALUES (
            COALESCE(NEW.user_id, 0),
            'status_change',
            'post',
            NEW.id,
            '状态从 [' || COALESCE(OLD.status, 'NULL') || '] 变更为 [' || COALESCE(NEW.status, 'NULL') || ']',
            CURRENT_TIMESTAMP
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_post_status_change ON posts;
CREATE TRIGGER trg_post_status_change
    AFTER UPDATE OF status ON posts
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_post_status_change();

COMMENT ON FUNCTION trg_func_post_status_change() IS 'TR03 信息状态变更触发：记录变更日志';

-- ============================================================
-- TR04 trg_comment_update_count
-- 触发时机：AFTER INSERT/DELETE ON comments
-- 功能：更新 posts.comment_count
-- ============================================================
CREATE OR REPLACE FUNCTION trg_func_comment_update_count()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        UPDATE posts
        SET comment_count = comment_count + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.post_id;
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        UPDATE posts
        SET comment_count = GREATEST(0, comment_count - 1),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.post_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_comment_insert_count ON comments;
CREATE TRIGGER trg_comment_insert_count
    AFTER INSERT ON comments
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_comment_update_count();

DROP TRIGGER IF EXISTS trg_comment_delete_count ON comments;
CREATE TRIGGER trg_comment_delete_count
    AFTER DELETE ON comments
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_comment_update_count();

COMMENT ON FUNCTION trg_func_comment_update_count() IS 'TR04 评论计数触发：同步 posts.comment_count';

-- ============================================================
-- TR05 trg_like_update_count
-- 触发时机：AFTER INSERT/DELETE ON likes
-- 功能：更新 posts.like_count
-- ============================================================
CREATE OR REPLACE FUNCTION trg_func_like_update_count()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        UPDATE posts
        SET like_count = like_count + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.post_id;
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        UPDATE posts
        SET like_count = GREATEST(0, like_count - 1),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.post_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_like_insert_count ON likes;
CREATE TRIGGER trg_like_insert_count
    AFTER INSERT ON likes
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_like_update_count();

DROP TRIGGER IF EXISTS trg_like_delete_count ON likes;
CREATE TRIGGER trg_like_delete_count
    AFTER DELETE ON likes
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_like_update_count();

COMMENT ON FUNCTION trg_func_like_update_count() IS 'TR05 点赞计数触发：同步 posts.like_count';

-- ============================================================
-- TR06 trg_favorite_update_count
-- 触发时机：AFTER INSERT/DELETE ON favorites
-- 功能：更新 posts.favorite_count
-- ============================================================
CREATE OR REPLACE FUNCTION trg_func_favorite_update_count()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        UPDATE posts
        SET favorite_count = favorite_count + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.post_id;
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        UPDATE posts
        SET favorite_count = GREATEST(0, favorite_count - 1),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.post_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_favorite_insert_count ON favorites;
CREATE TRIGGER trg_favorite_insert_count
    AFTER INSERT ON favorites
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_favorite_update_count();

DROP TRIGGER IF EXISTS trg_favorite_delete_count ON favorites;
CREATE TRIGGER trg_favorite_delete_count
    AFTER DELETE ON favorites
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_favorite_update_count();

COMMENT ON FUNCTION trg_func_favorite_update_count() IS 'TR06 收藏计数触发：同步 posts.favorite_count';

-- ============================================================
-- TR07 trg_post_update_view_count
-- 触发时机：AFTER UPDATE ON posts
-- 功能：view_count 变化时触发推荐重排（记录日志，便于追踪热点）
-- 注：本触发器仅在 view_count 增加时记录日志，便于追踪热点
-- ============================================================
CREATE OR REPLACE FUNCTION trg_func_post_update_view_count()
RETURNS TRIGGER AS $$
BEGIN
    -- 仅在 view_count 实际增加时记录（避免循环触发）
    IF NEW.view_count > OLD.view_count
       AND NEW.view_count > 0
       AND (NEW.view_count % 100 = 0) THEN  -- 每 100 次浏览记录一次，避免日志爆炸
        INSERT INTO admin_operation_logs (admin_id, action, target_type, target_id, detail, created_at)
        VALUES (
            0,
            'view_milestone',
            'post',
            NEW.id,
            '浏览量里程碑：' || NEW.view_count,
            CURRENT_TIMESTAMP
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_post_update_view_count ON posts;
CREATE TRIGGER trg_post_update_view_count
    AFTER UPDATE ON posts
    FOR EACH ROW
    WHEN (NEW.view_count > OLD.view_count)
    EXECUTE PROCEDURE trg_func_post_update_view_count();

COMMENT ON FUNCTION trg_func_post_update_view_count() IS 'TR07 浏览量更新触发：记录里程碑日志';

-- ============================================================
-- TR08 trg_user_soft_delete
-- 触发时机：BEFORE UPDATE ON users
-- 功能：软删除时自动设置 deleted_at + is_active=FALSE，并清理关联资源
-- ============================================================
CREATE OR REPLACE FUNCTION trg_func_user_soft_delete()
RETURNS TRIGGER AS $$
BEGIN
    -- 当 is_deleted 从 FALSE 变为 TRUE 时，自动填充 deleted_at 与 is_active
    IF NEW.is_deleted = TRUE AND OLD.is_deleted = FALSE THEN
        -- 设置删除时间（若未提供）
        IF NEW.deleted_at IS NULL THEN
            NEW.deleted_at = CURRENT_TIMESTAMP;
        END IF;
        -- 同步禁用账户
        NEW.is_active = FALSE;

        -- 记录日志
        INSERT INTO admin_operation_logs (admin_id, action, target_type, target_id, detail, created_at)
        VALUES (
            0,
            'user_soft_delete',
            'user',
            NEW.id,
            '用户软删除：' || NEW.nickname || ' (' || NEW.email || ')',
            CURRENT_TIMESTAMP
        );
    END IF;

    -- 当 is_deleted 从 TRUE 变为 FALSE 时，清除 deleted_at
    IF NEW.is_deleted = FALSE AND OLD.is_deleted = TRUE THEN
        NEW.deleted_at = NULL;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_soft_delete ON users;
CREATE TRIGGER trg_user_soft_delete
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE trg_func_user_soft_delete();

COMMENT ON FUNCTION trg_func_user_soft_delete() IS 'TR08 用户软删除触发：自动填充 deleted_at+禁用账户+日志';

-- ============================================================
-- 触发器验证
-- ============================================================
SELECT
    n.nspname AS schema,
    c.relname AS table_name,
    t.tgname AS trigger_name,
    pg_get_triggerdef(t.oid) AS trigger_def
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND NOT t.tgisinternal  -- 排除内部触发器（如外键约束触发器）
ORDER BY c.relname, t.tgname;
