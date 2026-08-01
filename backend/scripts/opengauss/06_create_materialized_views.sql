-- ============================================================
-- 脚本名称：06_create_materialized_views.sql
-- 用途：创建 4 个物化视图（MV01-MV04），用于缓存高频聚合查询
-- 依据：docs/27_数据库物理模型设计.md 第 6 节、第 9.2 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. 物化视图将聚合结果预计算并缓存，避免每次查询重新计算
--   2. 每个物化视图创建唯一索引，支持 REFRESH CONCURRENTLY 无锁刷新
--   3. MV03 为单行视图，使用常量列 id=1 作为唯一索引以支持并发刷新
--   4. 依赖 03_alter_tables.sql 中的 credibility_score / reputation_score 字段
--   5. 刷新频率由 crontab 调度（详见 crontab 文件）
-- ============================================================

-- ============================================================
-- MV01 mv_post_validation_stats（信息验证统计）
-- 对应逻辑视图：V06 v_post_validation_stats
-- 刷新频率：每小时
-- 用途：信息详情页验证统计缓存
-- 优化收益：信息详情（含统计）150ms → 10ms
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_post_validation_stats CASCADE;

CREATE MATERIALIZED VIEW mv_post_validation_stats AS
SELECT
    p.id AS post_id,
    p.title,
    COUNT(v.id) FILTER (WHERE v.validation_type = 'confirmation')      AS confirm_cnt,
    COUNT(v.id) FILTER (WHERE v.validation_type = 'refutation')       AS refute_cnt,
    COUNT(v.id)                                                       AS total_cnt,
    p.credibility_score,
    p.valid_count,
    p.invalid_count,
    p.status,
    p.is_deleted
FROM posts p
LEFT JOIN validation_records v
    ON v.post_id = p.id AND v.is_deleted = FALSE
WHERE p.is_deleted = FALSE
GROUP BY p.id, p.title, p.credibility_score, p.valid_count, p.invalid_count, p.status, p.is_deleted
WITH DATA;

-- 唯一索引（支持 CONCURRENTLY 刷新）
CREATE UNIQUE INDEX idx_mv_post_validation_pk
    ON mv_post_validation_stats (post_id);

COMMENT ON MATERIALIZED VIEW mv_post_validation_stats IS 'MV01 信息验证统计缓存（每小时刷新），对应 V06';

-- ============================================================
-- MV02 mv_user_reputation_ranking（用户信誉排行）
-- 对应逻辑视图：V08 v_user_reputation_ranking
-- 刷新频率：每日 03:00
-- 用途：用户信誉排行榜
-- 优化收益：用户信誉排行 800ms → 20ms
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_user_reputation_ranking CASCADE;

CREATE MATERIALIZED VIEW mv_user_reputation_ranking AS
SELECT
    u.id AS user_id,
    u.nickname,
    u.avatar_url,
    u.school_id,
    s.name AS school_name,
    u.reputation_score,
    u.is_active,
    -- 聚合统计
    (SELECT COUNT(*) FROM posts p
      WHERE p.user_id = u.id AND p.is_deleted = FALSE) AS post_count,
    (SELECT COUNT(*) FROM posts p
      WHERE p.user_id = u.id AND p.status = 'published' AND p.is_deleted = FALSE) AS published_count,
    (SELECT COUNT(DISTINCT v.post_id) FROM validation_records v
      JOIN posts p ON p.id = v.post_id
      WHERE p.user_id = u.id AND v.validation_type = 'confirmation'
        AND v.is_deleted = FALSE AND p.is_deleted = FALSE) AS confirmed_count,
    (SELECT COUNT(DISTINCT v.post_id) FROM validation_records v
      JOIN posts p ON p.id = v.post_id
      WHERE p.user_id = u.id AND v.validation_type = 'refutation'
        AND v.is_deleted = FALSE AND p.is_deleted = FALSE) AS refuted_count,
    (SELECT COUNT(*) FROM comments c
      WHERE c.user_id = u.id AND c.is_deleted = FALSE) AS comment_count,
    -- 排名（按信誉分降序）
    ROW_NUMBER() OVER (ORDER BY u.reputation_score DESC NULLS LAST) AS reputation_rank
FROM users u
LEFT JOIN schools s ON s.id = u.school_id
WHERE u.is_deleted = FALSE
WITH DATA;

-- 唯一索引（支持 CONCURRENTLY 刷新）
CREATE UNIQUE INDEX idx_mv_user_reputation_pk
    ON mv_user_reputation_ranking (user_id);

COMMENT ON MATERIALIZED VIEW mv_user_reputation_ranking IS 'MV02 用户信誉排行（每日 03:00 刷新），对应 V08';

-- ============================================================
-- MV03 mv_admin_dashboard（管理员仪表盘）
-- 对应逻辑视图：V09 v_admin_dashboard
-- 刷新频率：每 10 分钟
-- 用途：管理员首页聚合统计（15+ 子查询）
-- 优化收益：管理员仪表盘 1500ms → 30ms
-- 注：单行视图，使用常量列 id=1 作为唯一索引
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_admin_dashboard CASCADE;

CREATE MATERIALIZED VIEW mv_admin_dashboard AS
SELECT
    1 AS id,  -- 常量列，用于唯一索引
    -- ===== 用户统计 =====
    (SELECT COUNT(*) FROM users WHERE is_deleted = FALSE) AS total_users,
    (SELECT COUNT(*) FROM users WHERE is_deleted = FALSE AND is_active = TRUE) AS active_users,
    (SELECT COUNT(*) FROM users WHERE is_deleted = FALSE AND role = 'admin') AS admin_users,
    (SELECT COUNT(*) FROM users WHERE is_deleted = FALSE AND role = 'user') AS normal_users,
    -- ===== 信息统计 =====
    (SELECT COUNT(*) FROM posts WHERE is_deleted = FALSE) AS total_posts,
    (SELECT COUNT(*) FROM posts WHERE status = 'published' AND is_deleted = FALSE) AS published_posts,
    (SELECT COUNT(*) FROM posts WHERE status = 'pending' AND is_deleted = FALSE) AS pending_posts,
    (SELECT COUNT(*) FROM posts WHERE status = 'draft' AND is_deleted = FALSE) AS draft_posts,
    (SELECT COUNT(*) FROM posts WHERE status = 'archived' AND is_deleted = FALSE) AS archived_posts,
    (SELECT COUNT(*) FROM posts WHERE status = 'expired' AND is_deleted = FALSE) AS expired_posts,
    (SELECT COUNT(*) FROM posts WHERE status = 'conflict' AND is_deleted = FALSE) AS conflict_posts,
    -- ===== 互动统计 =====
    (SELECT COUNT(*) FROM comments WHERE is_deleted = FALSE) AS total_comments,
    (SELECT COUNT(*) FROM likes) AS total_likes,
    -- ===== 验证与举报 =====
    (SELECT COUNT(*) FROM validation_records WHERE is_deleted = FALSE) AS total_validations,
    (SELECT COUNT(*) FROM reports WHERE status = 'pending') AS pending_reports,
    (SELECT COUNT(*) FROM reports WHERE status = 'resolved') AS resolved_reports,
    -- ===== 通知与日志 =====
    (SELECT COUNT(*) FROM notifications WHERE is_deleted = FALSE) AS total_notifications,
    (SELECT COUNT(*) FROM notifications WHERE is_read = FALSE AND is_deleted = FALSE) AS unread_notifications,
    (SELECT COUNT(*) FROM admin_operation_logs) AS total_admin_logs,
    -- ===== 信誉统计 =====
    (SELECT AVG(reputation_score) FROM users WHERE is_deleted = FALSE AND is_active = TRUE) AS avg_reputation,
    (SELECT MAX(reputation_score) FROM users WHERE is_deleted = FALSE AND is_active = TRUE) AS max_reputation,
    -- ===== 可信度统计 =====
    (SELECT AVG(credibility_score) FROM posts WHERE is_deleted = FALSE AND status = 'published') AS avg_credibility,
    -- ===== 刷新时间戳 =====
    CURRENT_TIMESTAMP AS refreshed_at
WITH DATA;

-- 唯一索引（基于常量列，支持 CONCURRENTLY 刷新）
CREATE UNIQUE INDEX idx_mv_admin_dashboard_pk
    ON mv_admin_dashboard (id);

COMMENT ON MATERIALIZED VIEW mv_admin_dashboard IS 'MV03 管理员仪表盘（每 10 分钟刷新），对应 V09';

-- ============================================================
-- MV04 mv_location_post_count（地点信息统计）
-- 对应逻辑视图：V07 v_location_post_count
-- 刷新频率：每日
-- 用途：地图页地点热度统计
-- 优化收益：地图页聚合查询 200ms → 10ms
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_location_post_count CASCADE;

CREATE MATERIALIZED VIEW mv_location_post_count AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    l.school_id,
    s.name AS school_name,
    l.latitude,
    l.longitude,
    l.building,
    l.floor,
    l.is_verified,
    -- 信息统计
    COUNT(p.id) FILTER (WHERE p.is_deleted = FALSE) AS total_post_count,
    COUNT(p.id) FILTER (WHERE p.status = 'published' AND p.is_deleted = FALSE) AS published_count,
    COUNT(p.id) FILTER (WHERE p.status = 'expired' AND p.is_deleted = FALSE) AS expired_count,
    COUNT(p.id) FILTER (WHERE p.status = 'conflict' AND p.is_deleted = FALSE) AS conflict_count,
    -- 互动统计
    COALESCE(SUM(p.view_count) FILTER (WHERE p.is_deleted = FALSE), 0) AS total_views,
    COALESCE(SUM(p.like_count) FILTER (WHERE p.is_deleted = FALSE), 0) AS total_likes,
    COALESCE(SUM(p.comment_count) FILTER (WHERE p.is_deleted = FALSE), 0) AS total_comments,
    -- 平均可信度
    AVG(p.credibility_score) FILTER (WHERE p.is_deleted = FALSE AND p.status = 'published') AS avg_credibility,
    -- 最近信息时间
    MAX(p.created_at) FILTER (WHERE p.is_deleted = FALSE) AS last_post_at
FROM locations l
LEFT JOIN schools s ON s.id = l.school_id
LEFT JOIN posts p ON p.location_id = l.id
WHERE l.is_deleted = FALSE
GROUP BY l.id, l.name, l.school_id, s.name, l.latitude, l.longitude, l.building, l.floor, l.is_verified
WITH DATA;

-- 唯一索引（支持 CONCURRENTLY 刷新）
CREATE UNIQUE INDEX idx_mv_location_post_count_pk
    ON mv_location_post_count (location_id);

COMMENT ON MATERIALIZED VIEW mv_location_post_count IS 'MV04 地点信息统计（每日刷新），对应 V07';

-- ============================================================
-- 物化视图统计验证
-- ============================================================
SELECT
    c.relname AS mv_name,
    c.reltuples::BIGINT AS row_estimate,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'm'  -- m = materialized view
ORDER BY c.relname;
