-- ============================================================
-- 脚本名称：01_create_tablespaces.sql
-- 用途：创建 4 个表空间（ts_system / ts_core / ts_interaction / ts_log）
-- 依据：docs/27_数据库物理模型设计.md 第 2.1 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 所有者：omm（openGauss 轻量版默认用户）
-- 创建时间：2026-06-29
-- 说明：
--   1. 表空间将物理存储与逻辑 schema 解耦，按访问模式分离 I/O
--   2. 物理路径需事先在 openGauss 容器内由 omm 用户创建并具备读写权限
--   3. openGauss 禁止在数据目录($PGDATA)下创建表空间，故使用独立目录
--   4. 执行前请在容器中执行：
--        mkdir -p /var/lib/opengauss/tablespaces/{system,core,interaction,log}
--        chown -R omm:omm /var/lib/opengauss/tablespaces
-- ============================================================

-- ------------------------------------------------------------
-- 1.1 系统表空间（默认）
--     存放：schools / categories / tags / locations
--     访问特征：配置类，读写比 ≈ 100:1
-- ------------------------------------------------------------
CREATE TABLESPACE ts_system
    OWNER omm
    LOCATION '/var/lib/opengauss/tablespaces/system';

-- ------------------------------------------------------------
-- 1.2 业务核心表空间
--     存放：users / posts / post_tags / post_images / validation_records
--           reports / drafts / topic_collections / topic_collection_posts
--     访问特征：核心业务，读写均衡
-- ------------------------------------------------------------
CREATE TABLESPACE ts_core
    OWNER omm
    LOCATION '/var/lib/opengauss/tablespaces/core';

-- ------------------------------------------------------------
-- 1.3 互动表空间
--     存放：comments / likes / notifications
--     访问特征：高并发写入，热点数据
-- ------------------------------------------------------------
CREATE TABLESPACE ts_interaction
    OWNER omm
    LOCATION '/var/lib/opengauss/tablespaces/interaction';

-- ------------------------------------------------------------
-- 1.4 日志与历史表空间
--     存放：admin_operation_logs / browse_histories / search_histories
--     访问特征：仅追加，定期归档
-- ------------------------------------------------------------
CREATE TABLESPACE ts_log
    OWNER omm
    LOCATION '/var/lib/opengauss/tablespaces/log';

-- ------------------------------------------------------------
-- 1.5 验证查询
-- 注：openGauss 的 pg_tablespace 没有 spclocation 列，路径存储在 spcoptions 中
-- ------------------------------------------------------------
SELECT spcname, pg_get_userbyid(spcowner) AS owner, spcoptions
FROM pg_tablespace
WHERE spcname IN ('ts_system', 'ts_core', 'ts_interaction', 'ts_log')
ORDER BY spcname;
