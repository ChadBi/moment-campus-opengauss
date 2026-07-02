-- ============================================================
-- 脚本名称：03_alter_tables.sql
-- 用途：为 posts / users 表新增可信度、信誉分字段
-- 依据：docs/27_数据库物理模型设计.md 第 4.3 节、第 6.2 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. posts.credibility_score NUMERIC(5,2) - 信息可信度（0-100）
--      被 SP01 sp_recalc_credibility 更新
--      被 MV01 mv_post_validation_stats 引用
--   2. users.reputation_score NUMERIC(5,2) - 用户信誉分（0-100）
--      被 SP04 sp_update_reputation 更新
--      被 MV02 mv_user_reputation_ranking 引用
--   3. 新增字段均允许 NULL，便于现有数据平滑过渡
--   4. 后续可通过 UPDATE 设置默认值（60.00）
-- ============================================================

-- ------------------------------------------------------------
-- 3.1 posts 表新增 credibility_score 字段
-- ------------------------------------------------------------
ALTER TABLE posts
    ADD COLUMN IF NOT EXISTS credibility_score NUMERIC(5,2);

COMMENT ON COLUMN posts.credibility_score IS '信息可信度评分（0-100），由 sp_recalc_credibility 计算';

-- 为现有信息设置默认可信度（仅在字段为 NULL 时填充）
UPDATE posts
SET credibility_score = 60.00
WHERE credibility_score IS NULL;

-- ------------------------------------------------------------
-- 3.2 users 表新增 reputation_score 字段
-- ------------------------------------------------------------
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS reputation_score NUMERIC(5,2);

COMMENT ON COLUMN users.reputation_score IS '用户信誉分（0-100），由 sp_update_reputation 计算';

-- 为现有用户设置默认信誉分（仅在字段为 NULL 时填充）
UPDATE users
SET reputation_score = 60.00
WHERE reputation_score IS NULL;

-- ------------------------------------------------------------
-- 3.2.1 validation_records 表新增软删除字段
--   说明：原模型未包含 is_deleted/deleted_at，但物化视图（06）、
--         存储过程（07）、触发器（08）均需按 is_deleted 过滤。
--         09_create_partitions.sql 分区改造时也会保留这两个字段。
-- ------------------------------------------------------------
ALTER TABLE validation_records
    ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;

ALTER TABLE validation_records
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN validation_records.is_deleted IS '软删除标记';
COMMENT ON COLUMN validation_records.deleted_at IS '软删除时间';

-- ------------------------------------------------------------
-- 3.3 验证字段添加结果
-- ------------------------------------------------------------
SELECT
    c.relname AS table_name,
    a.attname AS column_name,
    format_type(a.atttypid, a.atttypmod) AS data_type
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('posts', 'users')
  AND a.attname IN ('credibility_score', 'reputation_score')
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY c.relname, a.attname;
