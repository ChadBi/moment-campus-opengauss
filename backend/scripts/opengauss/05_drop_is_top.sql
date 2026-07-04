-- 05_drop_is_top.sql
-- 放弃置顶帖子设计，删除 posts.is_top 字段
-- 配合本次互动功能精简：列表排序改为纯 created_at/like_count/updated_at

BEGIN;

-- 删除 is_top 字段（openGauss 支持 IF EXISTS）
ALTER TABLE posts DROP COLUMN IF EXISTS is_top;

COMMIT;
