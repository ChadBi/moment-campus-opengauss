-- ============================================================
-- 脚本名称：performance_test.sql
-- 用途：8 个关键查询的 EXPLAIN ANALYZE 性能测试
-- 依据：docs/27_数据库物理模型设计.md 第 10.2 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 使用方法：
--   psql -d moment_campus -f performance_test.sql
--   或在 psql 中：\i performance_test.sql
-- 说明：
--   1. 8 个查询覆盖 doc 27 第 10.2 节列出的所有关键场景
--   2. 使用 EXPLAIN ANALYZE 输出实际执行计划与耗时
--   3. 验证索引/物化视图/分区表的优化效果
--   4. 期望性能对比（优化前 → 优化后）：
--      Q1 首页信息列表：     200ms → 5ms
--      Q2 信息详情含统计：   150ms → 10ms
--      Q3 用户信誉排行：     800ms → 20ms
--      Q4 管理员仪表盘：     1500ms → 30ms
--      Q5 标题模糊搜索：     500ms → 30ms
--      Q6 过期信息扫描：     100ms → 5ms
--      Q7 未读消息计数：     80ms → 3ms
--      Q8 评论树查询：       120ms → 15ms
-- ============================================================

\timing on

-- ============================================================
-- Q1 首页信息列表（推荐排序）
-- 优化索引：idx_post_recommend（部分索引）
-- 测试点：是否使用 idx_post_recommend 部分索引，避免全表排序
-- 期望：200ms → 5ms
-- ============================================================
\echo '===== Q1 首页信息列表（推荐排序）====='
EXPLAIN ANALYZE
SELECT
    p.id, p.title, p.user_id, p.category_id, p.location_id,
    p.view_count, p.like_count, p.comment_count, p.credibility_score,
    p.created_at,
    u.nickname AS author_name,
    c.name AS category_name,
    l.name AS location_name
FROM posts p
LEFT JOIN users u ON u.id = p.user_id
LEFT JOIN categories c ON c.id = p.category_id
LEFT JOIN locations l ON l.id = p.location_id
WHERE p.is_deleted = FALSE
  AND p.status = 'published'
  AND p.school_id = 1
ORDER BY p.is_recommend DESC, p.created_at DESC
LIMIT 20;

-- ============================================================
-- Q2 信息详情（含验证统计）
-- 优化对象：MV01 mv_post_validation_stats 物化视图
-- 测试点：是否命中物化视图，避免 5 次 GROUP BY
-- 期望：150ms → 10ms
-- ============================================================
\echo '===== Q2 信息详情（含验证统计，物化视图）====='
EXPLAIN ANALYZE
SELECT
    p.id, p.title, p.content, p.user_id, p.status,
    p.view_count, p.like_count, p.comment_count,
    p.credibility_score, p.created_at,
    mv.confirm_cnt, mv.refute_cnt, mv.total_cnt,
    u.nickname AS author_name,
    u.reputation_score AS author_reputation
FROM posts p
LEFT JOIN mv_post_validation_stats mv ON mv.post_id = p.id
LEFT JOIN users u ON u.id = p.user_id
WHERE p.id = 1
  AND p.is_deleted = FALSE;

-- ============================================================
-- Q3 用户信誉排行（TOP 50）
-- 优化对象：MV02 mv_user_reputation_ranking 物化视图
-- 测试点：是否命中物化视图，避免全表 JOIN
-- 期望：800ms → 20ms
-- ============================================================
\echo '===== Q3 用户信誉排行（TOP 50，物化视图）====='
EXPLAIN ANALYZE
SELECT
    user_id, nickname, avatar_url, school_name,
    reputation_score, reputation_rank,
    post_count, published_count, confirmed_count, comment_count
FROM mv_user_reputation_ranking
WHERE school_id = 1
ORDER BY reputation_rank
LIMIT 50;

-- ============================================================
-- Q4 管理员仪表盘（15+ 聚合子查询）
-- 优化对象：MV03 mv_admin_dashboard 物化视图
-- 测试点：是否命中物化视图，避免 15+ 子查询
-- 期望：1500ms → 30ms
-- ============================================================
\echo '===== Q4 管理员仪表盘（物化视图）====='
EXPLAIN ANALYZE
SELECT
    total_users, active_users, admin_users, normal_users,
    total_posts, published_posts, pending_posts, draft_posts,
    archived_posts, expired_posts, conflict_posts,
    total_comments, total_likes,
    total_validations, pending_reports, resolved_reports,
    total_notifications, unread_notifications, total_admin_logs,
    avg_reputation, max_reputation, avg_credibility,
    refreshed_at
FROM mv_admin_dashboard
WHERE id = 1;

-- ============================================================
-- Q5 标题模糊搜索（LIKE '%关键词%'）
-- 优化索引：idx_posts_title_trgm（GIN + pg_trgm）
-- 测试点：是否使用 GIN 索引，避免全表扫描
-- 期望：500ms → 30ms
-- ============================================================
\echo '===== Q5 标题模糊搜索（GIN trigram 索引）====='
EXPLAIN ANALYZE
SELECT
    p.id, p.title, p.user_id, p.status,
    p.view_count, p.like_count, p.credibility_score,
    p.created_at,
    u.nickname AS author_name
FROM posts p
LEFT JOIN users u ON u.id = p.user_id
WHERE p.is_deleted = FALSE
  AND p.status = 'published'
  AND p.title LIKE '%食堂%'
ORDER BY p.created_at DESC
LIMIT 20;

-- 同样测试内容模糊搜索
\echo '===== Q5b 内容模糊搜索（GIN trigram 索引）====='
EXPLAIN ANALYZE
SELECT
    p.id, p.title, p.status,
    p.view_count, p.created_at
FROM posts p
WHERE p.is_deleted = FALSE
  AND p.status = 'published'
  AND p.content LIKE '%食堂%'
ORDER BY p.created_at DESC
LIMIT 20;

-- ============================================================
-- Q6 过期信息扫描（sp_mark_expired_posts 内部查询）
-- 优化索引：idx_post_expire_active（部分索引）
-- 测试点：是否使用部分索引，仅扫描活跃信息
-- 期望：100ms → 5ms
-- ============================================================
\echo '===== Q6 过期信息扫描（部分索引）====='
EXPLAIN ANALYZE
SELECT id, title, status, expire_at
FROM posts
WHERE is_deleted = FALSE
  AND status = 'published'
  AND expire_at IS NOT NULL
  AND expire_at < CURRENT_TIMESTAMP;

-- ============================================================
-- Q7 未读消息计数（首页红点）
-- 优化索引：idx_notification_unread（部分索引）
-- 测试点：是否使用部分索引，仅扫描未读
-- 期望：80ms → 3ms
-- ============================================================
\echo '===== Q7 未读消息计数（部分索引）====='
EXPLAIN ANALYZE
SELECT
    user_id,
    COUNT(*) AS unread_count,
    MAX(created_at) AS latest_unread_at
FROM notifications
WHERE is_read = FALSE
  AND is_deleted = FALSE
  AND user_id = 1
GROUP BY user_id;

-- ============================================================
-- Q8 评论树查询（按信息+创建时间）
-- 优化索引：idx_comment_post_created（部分索引）
-- 测试点：是否使用部分索引，避免回表排序
-- 期望：120ms → 15ms
-- ============================================================
\echo '===== Q8 评论树查询（部分索引）====='
EXPLAIN ANALYZE
SELECT
    c.id, c.post_id, c.user_id, c.parent_id,
    c.content, c.like_count, c.status, c.created_at,
    u.nickname AS author_name,
    parent.content AS parent_content
FROM comments c
LEFT JOIN users u ON u.id = c.user_id
LEFT JOIN comments parent ON parent.id = c.parent_id
WHERE c.post_id = 1
  AND c.is_deleted = FALSE
ORDER BY c.created_at ASC
LIMIT 50;

-- ============================================================
-- 附加测试：分区表剪枝（partition pruning）
-- 测试点：查询带时间条件时是否仅扫描对应分区
-- ============================================================
\echo '===== 附加测试：分区表剪枝 ====='
EXPLAIN ANALYZE
SELECT id, title, status, created_at
FROM posts
WHERE created_at >= '2026-06-01'
  AND created_at < '2026-07-01'
  AND is_deleted = FALSE
  AND status = 'published'
ORDER BY created_at DESC
LIMIT 20;

-- ============================================================
-- 附加测试：索引使用情况统计
-- ============================================================
\echo '===== 索引使用情况统计 ====='
SELECT
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS 扫描次数,
    idx_tup_read AS 读取行数,
    idx_tup_fetch AS 命中行数
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND idx_scan > 0
ORDER BY idx_scan DESC
LIMIT 20;

-- ============================================================
-- 性能测试汇总
-- ============================================================
\echo '===== 性能测试完成 ====='
\echo '请对照 doc 27 第 10.2 节的期望性能指标：'
\echo '  Q1 首页信息列表：     200ms → 5ms'
\echo '  Q2 信息详情含统计：   150ms → 10ms'
\echo '  Q3 用户信誉排行：     800ms → 20ms'
\echo '  Q4 管理员仪表盘：     1500ms → 30ms'
\echo '  Q5 标题模糊搜索：     500ms → 30ms'
\echo '  Q6 过期信息扫描：     100ms → 5ms'
\echo '  Q7 未读消息计数：     80ms → 3ms'
\echo '  Q8 评论树查询：       120ms → 15ms'
