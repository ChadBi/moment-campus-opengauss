-- ============================================================
-- 脚本名称：09_create_partitions.sql
-- 用途：将 7 张大表改造为按月 RANGE 分区表 + 创建日志归档表
-- 依据：docs/27_数据库物理模型设计.md 第 7 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. 7 张大表：posts, comments, notifications, admin_operation_logs,
--                browse_histories, search_histories, validation_records
--   2. 每张表创建 2026 年 12 个月分区 + default 分区
--   3. 分区改造为破坏性操作，脚本使用临时表过渡数据
--   4. 执行前请确保已备份重要数据
--   5. 归档表 admin_operation_logs_archive 与原表结构一致，无分区
--   6. 重要：分区表的主键必须包含分区键，故使用 (id, created_at) 复合主键
--   7. 本脚本应在 03_alter_tables.sql 之后、07_create_functions.sql 之后执行
--      但 SP05 sp_archive_logs 调用时才检查归档表存在，故可在 07 之后执行
-- ============================================================

-- ============================================================
-- 第一部分：创建归档表 admin_operation_logs_archive
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_operation_logs_archive (
    id              BIGSERIAL,
    admin_id        BIGINT      NOT NULL,
    action          VARCHAR(50) NOT NULL,
    target_type     VARCHAR(50) NOT NULL,
    target_id       BIGINT      NOT NULL,
    detail          TEXT,
    ip_address      VARCHAR(45),
    user_agent      VARCHAR(500),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    archived_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
) TABLESPACE ts_log;

CREATE INDEX IF NOT EXISTS idx_adminlog_archive_admin
    ON admin_operation_logs_archive (admin_id, created_at);
CREATE INDEX IF NOT EXISTS idx_adminlog_archive_action
    ON admin_operation_logs_archive (action);
CREATE INDEX IF NOT EXISTS idx_adminlog_archive_created
    ON admin_operation_logs_archive (created_at);
CREATE INDEX IF NOT EXISTS idx_adminlog_archive_target
    ON admin_operation_logs_archive (target_type, target_id);

COMMENT ON TABLE admin_operation_logs_archive IS '管理员操作日志归档表（90 天前日志迁移至此）';

-- ============================================================
-- 第二部分：分区表迁移辅助函数
-- 功能：检查表是否为分区表
-- 注：openGauss 使用 pg_partition 系统表（非 PostgreSQL 的 pg_partitioned_table）
-- ============================================================
CREATE OR REPLACE FUNCTION fn_is_partitioned(p_table_name VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    v_count INTEGER;
BEGIN
    -- openGauss 中分区子表记录在 pg_partition，parentid 指向父表 oid
    SELECT COUNT(*) INTO v_count
    FROM pg_partition p
    JOIN pg_class c ON c.oid = p.parentid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = p_table_name;
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 第三部分：posts 表分区改造
-- 分区键：created_at（按月）
-- ============================================================
DO $$
BEGIN
    IF fn_is_partitioned('posts') THEN
        RAISE NOTICE 'posts 已是分区表，跳过迁移';
    ELSE
        -- 1. 备份原表数据
        DROP TABLE IF EXISTS _backup_posts;
        CREATE TABLE _backup_posts AS SELECT * FROM posts;
        RAISE NOTICE 'posts 备份完成：% 行', (SELECT COUNT(*) FROM _backup_posts);

        -- 2. 删除原表（含索引、约束、触发器）
        DROP TABLE IF EXISTS posts CASCADE;

        -- 3. 创建分区主表
        CREATE TABLE posts (
            id                  BIGSERIAL,
            user_id             BIGINT      NOT NULL,
            school_id           BIGINT      NOT NULL,
            category_id         BIGINT      NOT NULL,
            location_id         BIGINT,
            title               VARCHAR(200) NOT NULL,
            content             TEXT        NOT NULL,
            is_anonymous        BOOLEAN     DEFAULT FALSE NOT NULL,
            status              VARCHAR(20) DEFAULT 'pending' NOT NULL,
            view_count          INTEGER     DEFAULT 0 NOT NULL,
            like_count          INTEGER     DEFAULT 0 NOT NULL,
            comment_count       INTEGER     DEFAULT 0 NOT NULL,
            favorite_count      INTEGER     DEFAULT 0 NOT NULL,
            valid_count         INTEGER     DEFAULT 0 NOT NULL,
            invalid_count       INTEGER     DEFAULT 0 NOT NULL,
            credibility_score   NUMERIC(5,2),
            expire_at           TIMESTAMP WITH TIME ZONE,
            activity_start_at   TIMESTAMP WITH TIME ZONE,
            activity_end_at     TIMESTAMP WITH TIME ZONE,
            lost_type           VARCHAR(10),
            contact_info        VARCHAR(255),
            is_top              BOOLEAN     DEFAULT FALSE NOT NULL,
            is_recommend        BOOLEAN     DEFAULT FALSE NOT NULL,
            created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            is_deleted          BOOLEAN     DEFAULT FALSE NOT NULL,
            deleted_at          TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (id, created_at)
        ) TABLESPACE ts_core
        PARTITION BY RANGE (created_at) (
            PARTITION posts_2026_01 VALUES LESS THAN ('2026-02-01') TABLESPACE ts_core,
            PARTITION posts_2026_02 VALUES LESS THAN ('2026-03-01') TABLESPACE ts_core,
            PARTITION posts_2026_03 VALUES LESS THAN ('2026-04-01') TABLESPACE ts_core,
            PARTITION posts_2026_04 VALUES LESS THAN ('2026-05-01') TABLESPACE ts_core,
            PARTITION posts_2026_05 VALUES LESS THAN ('2026-06-01') TABLESPACE ts_core,
            PARTITION posts_2026_06 VALUES LESS THAN ('2026-07-01') TABLESPACE ts_core,
            PARTITION posts_2026_07 VALUES LESS THAN ('2026-08-01') TABLESPACE ts_core,
            PARTITION posts_2026_08 VALUES LESS THAN ('2026-09-01') TABLESPACE ts_core,
            PARTITION posts_2026_09 VALUES LESS THAN ('2026-10-01') TABLESPACE ts_core,
            PARTITION posts_2026_10 VALUES LESS THAN ('2026-11-01') TABLESPACE ts_core,
            PARTITION posts_2026_11 VALUES LESS THAN ('2026-12-01') TABLESPACE ts_core,
            PARTITION posts_2026_12 VALUES LESS THAN ('2027-01-01') TABLESPACE ts_core,
            PARTITION posts_default VALUES LESS THAN (MAXVALUE) TABLESPACE ts_core
        );

        -- 5. 导入备份数据（按列名匹配，不导入 id 让其重新生成）
        INSERT INTO posts (
            user_id, school_id, category_id, location_id,
            title, content, is_anonymous, status,
            view_count, like_count, comment_count, favorite_count,
            valid_count, invalid_count, credibility_score,
            expire_at, activity_start_at, activity_end_at,
            lost_type, contact_info, is_top, is_recommend,
            created_at, updated_at, is_deleted, deleted_at
        )
        SELECT
            user_id, school_id, category_id, location_id,
            title, content, is_anonymous, status,
            view_count, like_count, comment_count, favorite_count,
            valid_count, invalid_count, credibility_score,
            expire_at, activity_start_at, activity_end_at,
            lost_type, contact_info, is_top, is_recommend,
            created_at, updated_at, is_deleted, deleted_at
        FROM _backup_posts;

        -- 6. 清理临时表
        DROP TABLE _backup_posts;
        RAISE NOTICE 'posts 分区表迁移完成';
    END IF;
END $$;

-- 重建 posts 表索引（分区表会自动应用到所有分区）
CREATE INDEX IF NOT EXISTS idx_post_user ON posts (user_id);
CREATE INDEX IF NOT EXISTS idx_post_school_status ON posts (school_id, status);
CREATE INDEX IF NOT EXISTS idx_post_category ON posts (category_id);
CREATE INDEX IF NOT EXISTS idx_post_location ON posts (location_id);
CREATE INDEX IF NOT EXISTS idx_post_status_created ON posts (status, created_at);
CREATE INDEX IF NOT EXISTS idx_post_status_recommend ON posts (status, is_recommend, created_at);
CREATE INDEX IF NOT EXISTS idx_post_expire ON posts (expire_at);
CREATE INDEX IF NOT EXISTS idx_post_school_category ON posts (school_id, category_id, status);
-- 注：openGauss 分区表不支持部分索引（WHERE 子句），改用普通索引
CREATE INDEX IF NOT EXISTS idx_post_recommend
    ON posts (is_top DESC, is_recommend DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_post_expire_active
    ON posts (expire_at);

-- ============================================================
-- 第四部分：comments 表分区改造
-- 分区键：created_at（按月）
-- ============================================================
DO $$
BEGIN
    IF fn_is_partitioned('comments') THEN
        RAISE NOTICE 'comments 已是分区表，跳过迁移';
    ELSE
        DROP TABLE IF EXISTS _backup_comments;
        CREATE TABLE _backup_comments AS SELECT * FROM comments;

        DROP TABLE IF EXISTS comments CASCADE;

        CREATE TABLE comments (
            id              BIGSERIAL,
            post_id         BIGINT      NOT NULL,
            user_id         BIGINT      NOT NULL,
            parent_id       BIGINT,
            reply_to_user_id BIGINT,
            content         TEXT        NOT NULL,
            like_count      INTEGER     DEFAULT 0 NOT NULL,
            status          VARCHAR(20) DEFAULT 'pending' NOT NULL,
            created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            is_deleted      BOOLEAN     DEFAULT FALSE NOT NULL,
            deleted_at      TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (id, created_at)
        ) TABLESPACE ts_interaction
        PARTITION BY RANGE (created_at) (
            PARTITION comments_2026_01 VALUES LESS THAN ('2026-02-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_02 VALUES LESS THAN ('2026-03-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_03 VALUES LESS THAN ('2026-04-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_04 VALUES LESS THAN ('2026-05-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_05 VALUES LESS THAN ('2026-06-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_06 VALUES LESS THAN ('2026-07-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_07 VALUES LESS THAN ('2026-08-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_08 VALUES LESS THAN ('2026-09-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_09 VALUES LESS THAN ('2026-10-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_10 VALUES LESS THAN ('2026-11-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_11 VALUES LESS THAN ('2026-12-01') TABLESPACE ts_interaction,
            PARTITION comments_2026_12 VALUES LESS THAN ('2027-01-01') TABLESPACE ts_interaction,
            PARTITION comments_default VALUES LESS THAN (MAXVALUE) TABLESPACE ts_interaction
        );

        INSERT INTO comments (post_id, user_id, parent_id, reply_to_user_id,
                              content, like_count, status,
                              created_at, updated_at, is_deleted, deleted_at)
        SELECT post_id, user_id, parent_id, reply_to_user_id,
               content, like_count, status,
               created_at, updated_at, is_deleted, deleted_at
        FROM _backup_comments;

        DROP TABLE _backup_comments;
        RAISE NOTICE 'comments 分区表迁移完成';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_comment_post ON comments (post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comment_parent ON comments (parent_id);
CREATE INDEX IF NOT EXISTS idx_comment_user ON comments (user_id);
CREATE INDEX IF NOT EXISTS idx_comment_status ON comments (status);
CREATE INDEX IF NOT EXISTS idx_comment_post_created
    ON comments (post_id, created_at);

-- ============================================================
-- 第五部分：notifications 表分区改造
-- 分区键：created_at（按月）
-- ============================================================
DO $$
BEGIN
    IF fn_is_partitioned('notifications') THEN
        RAISE NOTICE 'notifications 已是分区表，跳过迁移';
    ELSE
        DROP TABLE IF EXISTS _backup_notifications;
        CREATE TABLE _backup_notifications AS SELECT * FROM notifications;

        DROP TABLE IF EXISTS notifications CASCADE;

        CREATE TABLE notifications (
            id              BIGSERIAL,
            user_id         BIGINT      NOT NULL,
            type            VARCHAR(30) NOT NULL,
            title           VARCHAR(200) NOT NULL,
            content         VARCHAR(500),
            target_type     VARCHAR(50),
            target_id       BIGINT,
            actor_id        BIGINT,
            is_read         BOOLEAN     DEFAULT FALSE NOT NULL,
            read_at         TIMESTAMP WITH TIME ZONE,
            created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            is_deleted      BOOLEAN     DEFAULT FALSE NOT NULL,
            deleted_at      TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (id, created_at)
        ) TABLESPACE ts_interaction
        PARTITION BY RANGE (created_at) (
            PARTITION notifications_2026_01 VALUES LESS THAN ('2026-02-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_02 VALUES LESS THAN ('2026-03-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_03 VALUES LESS THAN ('2026-04-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_04 VALUES LESS THAN ('2026-05-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_05 VALUES LESS THAN ('2026-06-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_06 VALUES LESS THAN ('2026-07-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_07 VALUES LESS THAN ('2026-08-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_08 VALUES LESS THAN ('2026-09-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_09 VALUES LESS THAN ('2026-10-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_10 VALUES LESS THAN ('2026-11-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_11 VALUES LESS THAN ('2026-12-01') TABLESPACE ts_interaction,
            PARTITION notifications_2026_12 VALUES LESS THAN ('2027-01-01') TABLESPACE ts_interaction,
            PARTITION notifications_default VALUES LESS THAN (MAXVALUE) TABLESPACE ts_interaction
        );

        INSERT INTO notifications (user_id, type, title, content,
                                   target_type, target_id, actor_id,
                                   is_read, read_at, created_at, is_deleted, deleted_at)
        SELECT user_id, type, title, content,
               target_type, target_id, actor_id,
               is_read, read_at, created_at, is_deleted, deleted_at
        FROM _backup_notifications;

        DROP TABLE _backup_notifications;
        RAISE NOTICE 'notifications 分区表迁移完成';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_notification_user_read ON notifications (user_id, is_read, created_at);
CREATE INDEX IF NOT EXISTS idx_notification_user_type ON notifications (user_id, type);
CREATE INDEX IF NOT EXISTS idx_notification_target ON notifications (target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_notification_unread
    ON notifications (user_id, created_at DESC);

-- ============================================================
-- 第六部分：admin_operation_logs 表分区改造
-- 分区键：created_at（按月）
-- ============================================================
DO $$
BEGIN
    IF fn_is_partitioned('admin_operation_logs') THEN
        RAISE NOTICE 'admin_operation_logs 已是分区表，跳过迁移';
    ELSE
        DROP TABLE IF EXISTS _backup_adminlog;
        CREATE TABLE _backup_adminlog AS SELECT * FROM admin_operation_logs;

        DROP TABLE IF EXISTS admin_operation_logs CASCADE;

        CREATE TABLE admin_operation_logs (
            id              BIGSERIAL,
            admin_id        BIGINT      NOT NULL,
            action          VARCHAR(50) NOT NULL,
            target_type     VARCHAR(50) NOT NULL,
            target_id       BIGINT      NOT NULL,
            detail          TEXT,
            ip_address      VARCHAR(45),
            user_agent      VARCHAR(500),
            created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY (id, created_at)
        ) TABLESPACE ts_log
        PARTITION BY RANGE (created_at) (
            PARTITION admin_operation_logs_2026_01 VALUES LESS THAN ('2026-02-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_02 VALUES LESS THAN ('2026-03-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_03 VALUES LESS THAN ('2026-04-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_04 VALUES LESS THAN ('2026-05-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_05 VALUES LESS THAN ('2026-06-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_06 VALUES LESS THAN ('2026-07-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_07 VALUES LESS THAN ('2026-08-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_08 VALUES LESS THAN ('2026-09-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_09 VALUES LESS THAN ('2026-10-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_10 VALUES LESS THAN ('2026-11-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_11 VALUES LESS THAN ('2026-12-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_2026_12 VALUES LESS THAN ('2027-01-01') TABLESPACE ts_log,
            PARTITION admin_operation_logs_default VALUES LESS THAN (MAXVALUE) TABLESPACE ts_log
        );

        INSERT INTO admin_operation_logs (admin_id, action, target_type, target_id,
                                          detail, ip_address, user_agent, created_at)
        SELECT admin_id, action, target_type, target_id,
               detail, ip_address, user_agent, created_at
        FROM _backup_adminlog;

        DROP TABLE _backup_adminlog;
        RAISE NOTICE 'admin_operation_logs 分区表迁移完成';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_adminlog_admin ON admin_operation_logs (admin_id, created_at);
CREATE INDEX IF NOT EXISTS idx_adminlog_action ON admin_operation_logs (action);
CREATE INDEX IF NOT EXISTS idx_adminlog_target ON admin_operation_logs (target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_adminlog_created ON admin_operation_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_adminlog_created_range ON admin_operation_logs (created_at DESC);

-- ============================================================
-- 第七部分：browse_histories 表分区改造
-- 分区键：created_at（按月）
-- ============================================================
DO $$
BEGIN
    IF fn_is_partitioned('browse_histories') THEN
        RAISE NOTICE 'browse_histories 已是分区表，跳过迁移';
    ELSE
        DROP TABLE IF EXISTS _backup_browse;
        CREATE TABLE _backup_browse AS SELECT * FROM browse_histories;

        DROP TABLE IF EXISTS browse_histories CASCADE;

        CREATE TABLE browse_histories (
            id              BIGSERIAL,
            user_id         BIGINT      NOT NULL,
            post_id         BIGINT      NOT NULL,
            created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY (id, created_at)
        ) TABLESPACE ts_log
        PARTITION BY RANGE (created_at) (
            PARTITION browse_histories_2026_01 VALUES LESS THAN ('2026-02-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_02 VALUES LESS THAN ('2026-03-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_03 VALUES LESS THAN ('2026-04-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_04 VALUES LESS THAN ('2026-05-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_05 VALUES LESS THAN ('2026-06-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_06 VALUES LESS THAN ('2026-07-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_07 VALUES LESS THAN ('2026-08-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_08 VALUES LESS THAN ('2026-09-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_09 VALUES LESS THAN ('2026-10-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_10 VALUES LESS THAN ('2026-11-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_11 VALUES LESS THAN ('2026-12-01') TABLESPACE ts_log,
            PARTITION browse_histories_2026_12 VALUES LESS THAN ('2027-01-01') TABLESPACE ts_log,
            PARTITION browse_histories_default VALUES LESS THAN (MAXVALUE) TABLESPACE ts_log
        );

        INSERT INTO browse_histories (user_id, post_id, created_at)
        SELECT user_id, post_id, created_at
        FROM _backup_browse;

        DROP TABLE _backup_browse;
        RAISE NOTICE 'browse_histories 分区表迁移完成';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_browse_user ON browse_histories (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_browse_post ON browse_histories (post_id);

-- ============================================================
-- 第八部分：search_histories 表分区改造
-- 分区键：created_at（按月）
-- ============================================================
DO $$
BEGIN
    IF fn_is_partitioned('search_histories') THEN
        RAISE NOTICE 'search_histories 已是分区表，跳过迁移';
    ELSE
        DROP TABLE IF EXISTS _backup_search;
        CREATE TABLE _backup_search AS SELECT * FROM search_histories;

        DROP TABLE IF EXISTS search_histories CASCADE;

        CREATE TABLE search_histories (
            id              BIGSERIAL,
            user_id         BIGINT      NOT NULL,
            keyword         VARCHAR(200) NOT NULL,
            result_count    INTEGER,
            created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            PRIMARY KEY (id, created_at)
        ) TABLESPACE ts_log
        PARTITION BY RANGE (created_at) (
            PARTITION search_histories_2026_01 VALUES LESS THAN ('2026-02-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_02 VALUES LESS THAN ('2026-03-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_03 VALUES LESS THAN ('2026-04-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_04 VALUES LESS THAN ('2026-05-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_05 VALUES LESS THAN ('2026-06-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_06 VALUES LESS THAN ('2026-07-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_07 VALUES LESS THAN ('2026-08-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_08 VALUES LESS THAN ('2026-09-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_09 VALUES LESS THAN ('2026-10-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_10 VALUES LESS THAN ('2026-11-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_11 VALUES LESS THAN ('2026-12-01') TABLESPACE ts_log,
            PARTITION search_histories_2026_12 VALUES LESS THAN ('2027-01-01') TABLESPACE ts_log,
            PARTITION search_histories_default VALUES LESS THAN (MAXVALUE) TABLESPACE ts_log
        );

        INSERT INTO search_histories (user_id, keyword, result_count, created_at)
        SELECT user_id, keyword, result_count, created_at
        FROM _backup_search;

        DROP TABLE _backup_search;
        RAISE NOTICE 'search_histories 分区表迁移完成';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_search_user ON search_histories (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_search_keyword ON search_histories (keyword);

-- ============================================================
-- 第九部分：validation_records 表分区改造
-- 分区键：created_at（按月）
-- ============================================================
DO $$
BEGIN
    IF fn_is_partitioned('validation_records') THEN
        RAISE NOTICE 'validation_records 已是分区表，跳过迁移';
    ELSE
        DROP TABLE IF EXISTS _backup_validation;
        CREATE TABLE _backup_validation AS SELECT * FROM validation_records;

        DROP TABLE IF EXISTS validation_records CASCADE;

        CREATE TABLE validation_records (
            id              BIGSERIAL,
            post_id         BIGINT      NOT NULL,
            user_id         BIGINT      NOT NULL,
            validation_type VARCHAR(30) NOT NULL,
            comment         VARCHAR(500),
            created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
            is_deleted      BOOLEAN     DEFAULT FALSE NOT NULL,
            deleted_at      TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (id, created_at)
        ) TABLESPACE ts_core
        PARTITION BY RANGE (created_at) (
            PARTITION validation_records_2026_01 VALUES LESS THAN ('2026-02-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_02 VALUES LESS THAN ('2026-03-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_03 VALUES LESS THAN ('2026-04-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_04 VALUES LESS THAN ('2026-05-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_05 VALUES LESS THAN ('2026-06-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_06 VALUES LESS THAN ('2026-07-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_07 VALUES LESS THAN ('2026-08-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_08 VALUES LESS THAN ('2026-09-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_09 VALUES LESS THAN ('2026-10-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_10 VALUES LESS THAN ('2026-11-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_11 VALUES LESS THAN ('2026-12-01') TABLESPACE ts_core,
            PARTITION validation_records_2026_12 VALUES LESS THAN ('2027-01-01') TABLESPACE ts_core,
            PARTITION validation_records_default VALUES LESS THAN (MAXVALUE) TABLESPACE ts_core
        );

        INSERT INTO validation_records (post_id, user_id, validation_type, comment,
                                        created_at, is_deleted, deleted_at)
        SELECT post_id, user_id, validation_type, comment,
               created_at, is_deleted, deleted_at
        FROM _backup_validation;

        DROP TABLE _backup_validation;
        RAISE NOTICE 'validation_records 分区表迁移完成';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_validation_post ON validation_records (post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_validation_user ON validation_records (user_id);
CREATE INDEX IF NOT EXISTS idx_validation_post_type ON validation_records (post_id, validation_type);
CREATE INDEX IF NOT EXISTS idx_validation_post_type_active
    ON validation_records (post_id, validation_type);

-- ============================================================
-- 第十部分：分区表验证
-- 注：openGauss 使用 pg_partition 系统表（非 pg_partitioned_table）
-- ============================================================
SELECT
    n.nspname AS schema,
    c.relname AS parent_table,
    p.partstrategy AS partition_strategy
FROM pg_partition p
JOIN pg_class c ON c.oid = p.parentid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND p.parttype = 'r'  -- 仅父表记录（range 分区）
ORDER BY c.relname;

-- 各分区表的分区数统计（子分区数）
SELECT
    n.nspname AS schema,
    c.relname AS parent_table,
    COUNT(*) AS partition_count
FROM pg_partition p
JOIN pg_class c ON c.oid = p.parentid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND p.parttype = 'p'  -- 子分区记录
GROUP BY n.nspname, c.relname
ORDER BY c.relname;
