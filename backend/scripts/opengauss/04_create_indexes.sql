-- ============================================================
-- 脚本名称：04_create_indexes.sql
-- 用途：汇总 21 张表的所有索引（约 50 个现有 + 8 个新增部分索引）
-- 依据：
--   - docs/27_数据库物理模型设计.md 第 3 节
--   - backend/app/models/ 中各模型的 __table_args__
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. 主键索引由 PRIMARY KEY 自动创建，本脚本不重复
--   2. 外键字段统一建立索引，加速 JOIN 与级联操作
--   3. 复合索引遵循最左前缀原则
--   4. 部分索引（Partial Index）用于状态/软删除过滤场景
--   5. 使用 CREATE INDEX IF NOT EXISTS 保证可重复执行
--   6. 依赖 02_create_extensions.sql 中的 pg_trgm 扩展
--   7. 依赖 03_alter_tables.sql 中的 reputation_score 字段
-- ============================================================

-- ============================================================
-- 第一部分：现有索引汇总（来自代码 __table_args__）
-- ============================================================

-- ------------------------------------------------------------
-- 1. users 表（4 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_uidx ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_school ON users (school_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
CREATE INDEX IF NOT EXISTS idx_user_school ON users (school_id);
CREATE INDEX IF NOT EXISTS idx_user_role ON users (role);
CREATE INDEX IF NOT EXISTS idx_user_created ON users (created_at);

-- ------------------------------------------------------------
-- 2. schools 表（2 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_school_code ON schools (code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_school_code_uidx ON schools (code);
CREATE INDEX IF NOT EXISTS idx_school_active ON schools (is_active);

-- ------------------------------------------------------------
-- 3. posts 表（9 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_post_user ON posts (user_id);
CREATE INDEX IF NOT EXISTS idx_post_school_status ON posts (school_id, status);
CREATE INDEX IF NOT EXISTS idx_post_category ON posts (category_id);
CREATE INDEX IF NOT EXISTS idx_post_type ON posts (post_type_id);
CREATE INDEX IF NOT EXISTS idx_post_location ON posts (location_id);
CREATE INDEX IF NOT EXISTS idx_post_status_created ON posts (status, created_at);
CREATE INDEX IF NOT EXISTS idx_post_status_recommend ON posts (status, is_recommend, created_at);
CREATE INDEX IF NOT EXISTS idx_post_expire ON posts (expire_at);
CREATE INDEX IF NOT EXISTS idx_post_school_category ON posts (school_id, category_id, status);
CREATE INDEX IF NOT EXISTS idx_post_created ON posts (created_at);

-- ------------------------------------------------------------
-- 4. categories 表（2 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_category_code ON categories (code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_category_code_uidx ON categories (code);
CREATE INDEX IF NOT EXISTS idx_category_sort ON categories (sort_order);

-- ------------------------------------------------------------
-- 5. post_types 表（1 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_posttype_code ON post_types (code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_posttype_code_uidx ON post_types (code);

-- ------------------------------------------------------------
-- 6. tags 表（4 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_tag_name ON tags (name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tag_name_uidx ON tags (name);
CREATE INDEX IF NOT EXISTS idx_tag_slug ON tags (slug);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tag_slug_uidx ON tags (slug);
CREATE INDEX IF NOT EXISTS idx_tag_usage ON tags (usage_count);
CREATE INDEX IF NOT EXISTS idx_tag_official ON tags (is_official);

-- ------------------------------------------------------------
-- 7. locations 表（4 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_location_school ON locations (school_id);
CREATE INDEX IF NOT EXISTS idx_location_coords ON locations (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_location_school_name ON locations (school_id, name);
CREATE INDEX IF NOT EXISTS idx_location_verified ON locations (is_verified);

-- ------------------------------------------------------------
-- 8. comments 表（4 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_comment_post ON comments (post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comment_parent ON comments (parent_id);
CREATE INDEX IF NOT EXISTS idx_comment_user ON comments (user_id);
CREATE INDEX IF NOT EXISTS idx_comment_status ON comments (status);

-- ------------------------------------------------------------
-- 9. likes 表（2 个索引 + 1 唯一）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_like_post_user ON likes (post_id, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_like_post_user_uidx ON likes (post_id, user_id);
CREATE INDEX IF NOT EXISTS idx_like_user ON likes (user_id);

-- ------------------------------------------------------------
-- 10. favorites 表（2 个索引 + 1 唯一）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_favorite_post_user ON favorites (post_id, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_favorite_post_user_uidx ON favorites (post_id, user_id);
CREATE INDEX IF NOT EXISTS idx_favorite_user ON favorites (user_id, created_at);

-- ------------------------------------------------------------
-- 11. validation_records 表（3 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_validation_post ON validation_records (post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_validation_user ON validation_records (user_id);
CREATE INDEX IF NOT EXISTS idx_validation_post_type ON validation_records (post_id, validation_type);

-- ------------------------------------------------------------
-- 12. reports 表（3 个索引 + 1 唯一）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_report_post_reporter ON reports (post_id, reporter_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_report_post_reporter_uidx ON reports (post_id, reporter_id);
CREATE INDEX IF NOT EXISTS idx_report_status ON reports (status, created_at);
CREATE INDEX IF NOT EXISTS idx_report_handler ON reports (handler_id);

-- ------------------------------------------------------------
-- 13. notifications 表（3 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_notification_user_read ON notifications (user_id, is_read, created_at);
CREATE INDEX IF NOT EXISTS idx_notification_user_type ON notifications (user_id, type);
CREATE INDEX IF NOT EXISTS idx_notification_target ON notifications (target_type, target_id);

-- ------------------------------------------------------------
-- 14. post_tags 表（2 个索引 + 1 唯一）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_posttag_post_tag ON post_tags (post_id, tag_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_posttag_post_tag_uidx ON post_tags (post_id, tag_id);
CREATE INDEX IF NOT EXISTS idx_posttag_tag ON post_tags (tag_id);

-- ------------------------------------------------------------
-- 15. post_images 表（1 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_postimage_post ON post_images (post_id, sort_order);

-- ------------------------------------------------------------
-- 16. drafts 表（1 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_draft_user ON drafts (user_id, updated_at);

-- ------------------------------------------------------------
-- 17. topic_collections 表（3 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_topic_school ON topic_collections (school_id, status);
CREATE INDEX IF NOT EXISTS idx_topic_sort ON topic_collections (sort_order);
CREATE INDEX IF NOT EXISTS idx_topic_creator ON topic_collections (creator_id);

-- ------------------------------------------------------------
-- 18. topic_collection_posts 表（2 个索引 + 1 唯一）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_tcp_topic_post ON topic_collection_posts (topic_collection_id, post_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tcp_topic_post_uidx ON topic_collection_posts (topic_collection_id, post_id);
CREATE INDEX IF NOT EXISTS idx_tcp_post ON topic_collection_posts (post_id);

-- ------------------------------------------------------------
-- 19. browse_histories 表（2 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_browse_user ON browse_histories (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_browse_post ON browse_histories (post_id);

-- ------------------------------------------------------------
-- 20. search_histories 表（2 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_search_user ON search_histories (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_search_keyword ON search_histories (keyword);

-- ------------------------------------------------------------
-- 21. admin_operation_logs 表（4 个索引）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_adminlog_admin ON admin_operation_logs (admin_id, created_at);
CREATE INDEX IF NOT EXISTS idx_adminlog_action ON admin_operation_logs (action);
CREATE INDEX IF NOT EXISTS idx_adminlog_target ON admin_operation_logs (target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_adminlog_created ON admin_operation_logs (created_at);


-- ============================================================
-- 第二部分：新增 8 个部分索引 / GIN 索引（doc 27 第 3.3 节）
-- ============================================================

-- ------------------------------------------------------------
-- 3.3.1 posts 全文模糊搜索索引（GIN + pg_trgm）
--   优化场景：LIKE '%关键词%' 标题/内容模糊搜索
--   预期收益：从全表扫描降为索引扫描（500ms → 30ms）
--   注：openGauss 轻量版默认不携带 pg_trgm，缺失时跳过创建
-- ------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        CREATE INDEX IF NOT EXISTS idx_posts_title_trgm
            ON posts USING gin (title gin_trgm_ops);
        CREATE INDEX IF NOT EXISTS idx_posts_content_trgm
            ON posts USING gin (content gin_trgm_ops);
        RAISE NOTICE '已创建 pg_trgm GIN 索引';
    ELSE
        RAISE NOTICE 'pg_trgm 未安装，跳过 trgm GIN 索引创建';
    END IF;
END $$;

-- ------------------------------------------------------------
-- 3.3.2 posts 推荐排序索引（部分索引）
--   优化场景：首页推荐列表（置顶 + 推荐 + 创建时间）
--   预期收益：避免对 posts 全表排序（200ms → 5ms）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_post_recommend
    ON posts (is_top DESC, is_recommend DESC, created_at DESC)
    WHERE is_deleted = FALSE AND status = 'published';

-- ------------------------------------------------------------
-- 3.3.3 posts 过期扫描索引（部分索引）
--   优化场景：sp_mark_expired_posts 定时任务
--   预期收益：仅扫描活跃信息，减少 90% 数据量
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_post_expire_active
    ON posts (expire_at)
    WHERE is_deleted = FALSE AND status = 'published' AND expire_at IS NOT NULL;

-- ------------------------------------------------------------
-- 3.3.4 validation_records 复合部分索引
--   优化场景：可信度计算（按信息+类型聚合统计）
--   预期收益：加速 MV01 物化视图的 GROUP BY
--   注意：与现有 idx_validation_post_type 区别在于带 WHERE 条件
--   说明：validation_records 原表无 is_deleted 字段，需在
--         09_create_partitions.sql 分区改造后才会添加。
--         此处用 DO 块条件创建，避免原表阶段报错。
-- ------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='validation_records'
          AND column_name='is_deleted'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_validation_post_type_active
            ON validation_records (post_id, validation_type)
            WHERE is_deleted = FALSE;
        RAISE NOTICE '已创建 idx_validation_post_type_active';
    ELSE
        RAISE NOTICE 'validation_records 无 is_deleted 字段，跳过 idx_validation_post_type_active（将由 09 脚本创建）';
    END IF;
END $$;

-- ------------------------------------------------------------
-- 3.3.5 comments 评论树部分索引
--   优化场景：评论列表查询（按信息+创建时间排序）
--   预期收益：避免回表排序（120ms → 15ms）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_comment_post_created
    ON comments (post_id, created_at)
    WHERE is_deleted = FALSE;

-- ------------------------------------------------------------
-- 3.3.6 users 信誉排行部分索引
--   优化场景：用户排行榜（MV02 物化视图）
--   预期收益：加速 V08 视图（800ms → 20ms）
--   依赖：03_alter_tables.sql 中新增的 reputation_score 字段
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_user_reputation
    ON users (reputation_score DESC NULLS LAST)
    WHERE is_deleted = FALSE AND is_active = TRUE;

-- ------------------------------------------------------------
-- 3.3.7 notifications 未读统计部分索引
--   优化场景：首页未读消息计数（红点提示）
--   预期收益：仅扫描未读，加速首页红点（80ms → 3ms）
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_notification_unread
    ON notifications (user_id, created_at DESC)
    WHERE is_read = FALSE AND is_deleted = FALSE;

-- ------------------------------------------------------------
-- 3.3.8 admin_operation_logs 时间范围扫描索引
--   优化场景：日志查询（按时间范围筛选）
--   预期收益：范围扫描优化
--   注意：与现有 idx_adminlog_created 不同，本索引按 DESC 排序
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_adminlog_created_range
    ON admin_operation_logs (created_at DESC);


-- ============================================================
-- 第三部分：索引统计验证
-- ============================================================

-- ------------------------------------------------------------
-- 3.1 索引总数统计（按表）
-- ------------------------------------------------------------
SELECT
    schemaname,
    relname AS table_name,
    COUNT(*) AS index_count
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
GROUP BY schemaname, relname
ORDER BY index_count DESC, relname;

-- ------------------------------------------------------------
-- 3.2 部分索引验证（应列出 8 个）
-- ------------------------------------------------------------
SELECT
    n.nspname AS schema,
    c.relname AS table_name,
    c2.relname AS index_name,
    pg_get_indexdef(i.indexrelid) AS index_def
FROM pg_index i
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_class c2 ON c2.oid = i.indexrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND (i.indpred IS NOT NULL                       -- 部分索引
       OR c2.relname IN ('idx_posts_title_trgm', 'idx_posts_content_trgm',
                         'idx_adminlog_created_range'))
ORDER BY c.relname, c2.relname;
