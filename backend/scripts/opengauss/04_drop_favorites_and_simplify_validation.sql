-- ============================================================
-- 脚本名称：04_drop_favorites_and_simplify_validation.sql
-- 用途：
--   1. 删除收藏功能（drop favorites 表 + posts.favorite_count 字段）
--   2. 精简协同验证为 2 类（confirmation/refutation 互斥可切换）
--      - 删除 update/expiration_report/conflict_report 类型记录
--      - 添加 (post_id, user_id) 唯一约束
--   3. 旧别名 valid/invalid 保留不动（向后兼容）
-- 依据：用户需求 2026-07-04
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-07-04
-- 说明：
--   1. 此脚本幂等（可重复执行），所有 DROP IF EXISTS 不会因对象不存在而报错
--   2. 执行前请备份数据库
--   3. 执行后需重启后端服务
-- ============================================================

BEGIN;

-- ============================================================
-- 1. 删除收藏功能
-- ============================================================

-- 1.1 删除 favorites 表
DROP TABLE IF EXISTS favorites CASCADE;

-- 1.2 删除 posts.favorite_count 字段
ALTER TABLE posts DROP COLUMN IF EXISTS favorite_count;

-- ============================================================
-- 2. 精简协同验证为 2 类
-- ============================================================

-- 2.1 删除 update / expiration_report / conflict_report 类型的验证记录
--     （仅保留 confirmation / refutation / 旧别名 valid / invalid）
DELETE FROM validation_records
WHERE validation_type IN ('update', 'expiration_report', 'conflict_report', 'uncertain');

-- 2.2 删除旧的非唯一索引（如果存在）
DROP INDEX IF EXISTS idx_validation_post_type;

-- 2.3 删除可能存在的重复记录（保留每个 user+post 最旧的一条）
--     在加唯一约束前必须先去重
DELETE FROM validation_records
WHERE id NOT IN (
    SELECT MIN(id) FROM validation_records
    GROUP BY post_id, user_id
);

-- 2.4 添加 (post_id, user_id) 唯一约束
--     openGauss 不支持 IF NOT EXISTS，使用 DO 块判断
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'validation_records'
        AND indexname = 'idx_validation_post_user_unique'
    ) THEN
        CREATE UNIQUE INDEX idx_validation_post_user_unique
        ON validation_records (post_id, user_id);
    END IF;
END $$;

-- ============================================================
-- 3. 重算 posts.valid_count / invalid_count
--    （删除 update 等记录后，统计可能不一致，重算保证准确）
-- ============================================================

UPDATE posts p SET
    valid_count = COALESCE((
        SELECT COUNT(*) FROM validation_records v
        WHERE v.post_id = p.id AND v.validation_type IN ('confirmation', 'valid')
    ), 0),
    invalid_count = COALESCE((
        SELECT COUNT(*) FROM validation_records v
        WHERE v.post_id = p.id AND v.validation_type IN ('refutation', 'invalid')
    ), 0);

COMMIT;

-- ============================================================
-- 验证查询（手动执行检查）
-- ============================================================
-- SELECT COUNT(*) FROM validation_records;
-- SELECT COUNT(DISTINCT (post_id, user_id)) FROM validation_records;
-- SELECT validation_type, COUNT(*) FROM validation_records GROUP BY validation_type;
-- SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'favorites';
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'posts' AND column_name = 'favorite_count';
