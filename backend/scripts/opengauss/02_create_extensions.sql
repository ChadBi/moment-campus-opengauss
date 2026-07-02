-- ============================================================
-- 脚本名称：02_create_extensions.sql
-- 用途：安装数据库扩展（pg_trgm 必装 / zhparser 可选）
-- 依据：docs/27_数据库物理模型设计.md 第 3.3.1 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. pg_trgm 用于 LIKE '%关键词%' 模糊搜索优化（GIN 索引）
--   2. zhparser 为中文分词扩展，openGauss 轻量版默认未携带，按需安装
--   3. 04_create_indexes.sql 中的 idx_posts_title_trgm / idx_posts_content_trgm
--      依赖 pg_trgm，必须先执行本脚本
-- ============================================================

-- ------------------------------------------------------------
-- 2.1 pg_trgm：trigram 模糊匹配（必装）
--     用途：加速 LIKE '%xxx%' 与相似度比较
--     依赖索引：idx_posts_title_trgm / idx_posts_content_trgm（GIN）
-- 注意：openGauss 轻量版默认未携带 pg_trgm，需手动编译安装。
--       若未安装，下方 DO 块会捕获异常并以 NOTICE 提示，
--       后续 04 脚本会跳过 trgm 索引创建。
-- ------------------------------------------------------------
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    RAISE NOTICE 'pg_trgm 扩展已安装';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'pg_trgm 扩展不可用（%），将跳过 trgm 索引创建', SQLERRM;
END $$;

-- 验证安装
SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_trgm';

-- ------------------------------------------------------------
-- 2.2 zhparser：中文分词（可选）
--     用途：full-text search 全文检索中文分词
--     注意：
--       (1) openGauss 轻量版默认不携带 zhparser，需手动编译安装
--       (2) 安装步骤：
--           a. 在容器内编译 zhparser.so 并放到 $GAUSSHOME/lib/
--           b. 将 zhparser.sql 控制脚本放到 $GAUSSHOME/share/postgresql/extension/
--           c. 重启 openGauss 后再执行下方 CREATE EXTENSION
--       (3) 若未安装，下方语句会报错，可注释掉跳过
-- ------------------------------------------------------------
-- CREATE EXTENSION IF NOT EXISTS zhparser;
-- CREATE TEXT SEARCH CONFIGURATION chinese_zh (PARSER = zhparser);
-- ALTER TEXT SEARCH CONFIGURATION chinese_zh ADD MAPPING FOR n,v,a,i,e,l WITH simple;

-- 可选：zhparser 安装后可创建 GIN 全文索引
-- CREATE INDEX idx_posts_title_gin ON posts USING gin(to_tsvector('chinese_zh', title));
-- CREATE INDEX idx_posts_content_gin ON posts USING gin(to_tsvector('chinese_zh', content));

-- ------------------------------------------------------------
-- 2.3 验证已安装扩展
-- ------------------------------------------------------------
SELECT extname, extversion, obj_description(oid, 'pg_extension') AS comment
FROM pg_extension
ORDER BY extname;
