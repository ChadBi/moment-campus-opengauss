-- ============================================================
-- 脚本名称：11_grant_permissions.sql
-- 用途：授予 omm 用户对所有数据库对象的访问权限
-- 依据：docs/27_数据库物理模型设计.md 第 9.3 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. omm 为 openGauss 轻量版默认管理员用户
--   2. 授予全部表/视图/物化视图/序列/函数权限
--   3. 授予执行所有存储过程的权限
--   4. 授予表空间使用权限
--   5. 本脚本应在所有对象创建完成后执行
-- ============================================================

-- ============================================================
-- 第一部分：授予表空间使用权限
-- ============================================================
GRANT CREATE ON TABLESPACE ts_system TO omm;
GRANT CREATE ON TABLESPACE ts_core TO omm;
GRANT CREATE ON TABLESPACE ts_interaction TO omm;
GRANT CREATE ON TABLESPACE ts_log TO omm;

-- ============================================================
-- 第二部分：授予 schema 权限
-- ============================================================
GRANT ALL ON SCHEMA public TO omm;

-- ============================================================
-- 第三部分：授予所有表的全部权限
-- ============================================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO omm;

-- ============================================================
-- 第四部分：授予所有序列的权限
-- ============================================================
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO omm;

-- ============================================================
-- 第五部分：授予所有函数/存储过程的执行权限
-- ============================================================
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO omm;

-- ============================================================
-- 第六部分：授予所有物化视图的 SELECT 权限
-- 注：物化视图的刷新权限包含在表的 ALL PRIVILEGES 中
-- ============================================================
GRANT SELECT ON ALL TABLES IN SCHEMA public TO omm;

-- ============================================================
-- 第七部分：默认权限（未来创建的对象自动授权）
-- ============================================================
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON TABLES TO omm;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL PRIVILEGES ON SEQUENCES TO omm;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO omm;

-- ============================================================
-- 第八部分：权限验证
-- ============================================================

-- 8.1 验证表的权限
SELECT
    n.nspname AS schema,
    c.relname AS table_name,
    c.relkind AS object_type,
    pg_get_userbyid(c.relowner) AS owner
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind IN ('r', 'm', 'v')  -- 普通表、物化视图、视图
ORDER BY c.relkind, c.relname;

-- 8.2 验证函数/存储过程的权限
SELECT
    n.nspname AS schema,
    p.proname AS function_name,
    pg_get_userbyid(p.proowner) AS owner
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname LIKE 'sp_%'
ORDER BY p.proname;

-- 8.3 验证表空间权限
-- 注：openGauss 的 pg_tablespace 无 spclocation 列，改用 spcoptions
SELECT
    spcname AS tablespace_name,
    pg_get_userbyid(spcowner) AS owner,
    spcoptions AS options
FROM pg_tablespace
WHERE spcname LIKE 'ts_%'
ORDER BY spcname;

-- 8.4 汇总授权结果
SELECT '=== 权限授予完成 ===' AS report;
SELECT
    (SELECT COUNT(*) FROM pg_class c
     JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind = 'r') AS table_count,
    (SELECT COUNT(*) FROM pg_class c
     JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind = 'm') AS materialized_view_count,
    (SELECT COUNT(*) FROM pg_class c
     JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public' AND c.relkind = 'v') AS view_count,
    (SELECT COUNT(*) FROM pg_proc p
     JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname LIKE 'sp_%') AS stored_procedure_count;
