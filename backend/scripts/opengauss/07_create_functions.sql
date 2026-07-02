-- ============================================================
-- 脚本名称：07_create_functions.sql
-- 用途：创建 8 个 PL/pgSQL 存储过程（SP01-SP08）
-- 依据：docs/27_数据库物理模型设计.md 第 4 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. SP01-SP04 由触发器调用，自动维护可信度/信誉分
--   2. SP05-SP06 由定时任务调用，归档/清理历史数据
--   3. SP07-SP08 由应用层调用，封装复杂业务流程
--   4. 依赖 03_alter_tables.sql 中的 credibility_score / reputation_score 字段
--   5. SP05 依赖 09_create_partitions.sql 中的 admin_operation_logs_archive 表
--      （CREATE FUNCTION 时不校验表存在，调用时校验）
-- ============================================================

-- ============================================================
-- SP01 sp_recalc_credibility（重算信息可信度）
-- 调用方：触发器 trg_validation_after_insert/delete、SP08
-- 公式：
--   基础分 = 作者信誉 * 0.3 + 50 * 0.7
--   证实 +5/条，证伪 -8/条，更新 +2/条，过期报告 -10/条，冲突报告 -15/条
--   限制范围 [0, 100]
-- ============================================================
CREATE OR REPLACE FUNCTION sp_recalc_credibility(p_post_id BIGINT)
RETURNS NUMERIC(5,2) AS $$
DECLARE
    v_confirm_cnt   INTEGER;
    v_refute_cnt    INTEGER;
    v_update_cnt    INTEGER;
    v_expire_cnt    INTEGER;
    v_conflict_cnt  INTEGER;
    v_credibility   NUMERIC(5,2);
    v_author_rep    NUMERIC(5,2);
BEGIN
    -- 统计 5 类验证记录
    SELECT
        COUNT(*) FILTER (WHERE validation_type = 'confirmation'),
        COUNT(*) FILTER (WHERE validation_type = 'refutation'),
        COUNT(*) FILTER (WHERE validation_type = 'update'),
        COUNT(*) FILTER (WHERE validation_type = 'expiration_report'),
        COUNT(*) FILTER (WHERE validation_type = 'conflict_report')
    INTO v_confirm_cnt, v_refute_cnt, v_update_cnt, v_expire_cnt, v_conflict_cnt
    FROM validation_records
    WHERE post_id = p_post_id AND is_deleted = FALSE;

    -- 获取作者信誉分（加权），默认 60
    SELECT COALESCE(u.reputation_score, 60.00) INTO v_author_rep
    FROM users u
    JOIN posts p ON p.user_id = u.id
    WHERE p.id = p_post_id;

    -- 可信度计算公式（详见 doc 27 第 4.3.1 节）
    v_credibility := v_author_rep * 0.3 + 50.0 * 0.7
                   + v_confirm_cnt * 5.0
                   - v_refute_cnt * 8.0
                   + v_update_cnt * 2.0
                   - v_expire_cnt * 10.0
                   - v_conflict_cnt * 15.0;

    -- 限制在 [0, 100]
    v_credibility := GREATEST(0.0, LEAST(100.0, v_credibility));

    -- 更新信息可信度字段
    UPDATE posts
    SET credibility_score = v_credibility,
        valid_count = v_confirm_cnt,
        invalid_count = v_refute_cnt,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_post_id;

    RETURN v_credibility;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_recalc_credibility(BIGINT) IS 'SP01 重算信息可信度（0-100），由验证记录触发器调用';

-- ============================================================
-- SP02 sp_mark_expired_posts（标记过期信息）
-- 调用方：定时任务 JOB01（每小时）
-- 功能：将 expire_at 已过期但状态仍为 published 的信息标记为 expired
-- ============================================================
CREATE OR REPLACE FUNCTION sp_mark_expired_posts()
RETURNS INTEGER AS $$
DECLARE
    v_affected INTEGER;
BEGIN
    -- 将已过期但状态仍为 published 的信息标记为 expired
    UPDATE posts
    SET status = 'expired',
        updated_at = CURRENT_TIMESTAMP
    WHERE is_deleted = FALSE
      AND status = 'published'
      AND expire_at IS NOT NULL
      AND expire_at < CURRENT_TIMESTAMP;

    GET DIAGNOSTICS v_affected = ROW_COUNT;

    -- 记录日志（admin_id=0 表示系统自动操作）
    INSERT INTO admin_operation_logs (admin_id, action, target_type, target_id, detail, created_at)
    SELECT 0, 'system_expire', 'post', id,
           '自动过期标记：expire_at=' || expire_at::TEXT,
           CURRENT_TIMESTAMP
    FROM posts
    WHERE is_deleted = FALSE
      AND status = 'expired'
      AND updated_at = CURRENT_TIMESTAMP;

    RETURN v_affected;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_mark_expired_posts() IS 'SP02 标记过期信息（每小时执行）';

-- ============================================================
-- SP03 sp_detect_conflict（检测冲突信息）
-- 调用方：触发器 trg_validation_after_insert、SP08
-- 功能：同地点、时间重叠、状态为 published 的其他信息存在时标记为 conflict
-- ============================================================
CREATE OR REPLACE FUNCTION sp_detect_conflict(p_post_id BIGINT)
RETURNS INTEGER AS $$
DECLARE
    v_conflict_cnt  INTEGER;
    v_location_id   BIGINT;
    v_post_start    TIMESTAMP WITH TIME ZONE;
    v_post_end      TIMESTAMP WITH TIME ZONE;
BEGIN
    -- 获取当前信息的地点与时间范围
    SELECT location_id, activity_start_at, activity_end_at
    INTO v_location_id, v_post_start, v_post_end
    FROM posts WHERE id = p_post_id;

    -- 无地点或无活动时间，无法判定冲突
    IF v_location_id IS NULL OR v_post_start IS NULL OR v_post_end IS NULL THEN
        RETURN 0;
    END IF;

    -- 查找同地点、时间重叠、状态为 published 的其他信息
    SELECT COUNT(*) INTO v_conflict_cnt
    FROM posts
    WHERE id <> p_post_id
      AND location_id = v_location_id
      AND status = 'published'
      AND is_deleted = FALSE
      AND activity_start_at IS NOT NULL
      AND activity_end_at IS NOT NULL
      AND activity_start_at < v_post_end
      AND activity_end_at > v_post_start;

    -- 若存在冲突，将当前信息标记为 conflict
    IF v_conflict_cnt > 0 THEN
        UPDATE posts
        SET status = 'conflict', updated_at = CURRENT_TIMESTAMP
        WHERE id = p_post_id AND status = 'published';
    END IF;

    RETURN v_conflict_cnt;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_detect_conflict(BIGINT) IS 'SP03 检测同地点同时段矛盾信息';

-- ============================================================
-- SP04 sp_update_reputation（更新用户信誉分）
-- 调用方：触发器 trg_validation_after_insert、SP08、定时任务 JOB02
-- 公式：
--   基础分 60 + 证实 +3 + 发布 +0.5 - 证伪 -5 - 被举报 -2
--   限制范围 [0, 100]
-- ============================================================
CREATE OR REPLACE FUNCTION sp_update_reputation(p_user_id BIGINT)
RETURNS NUMERIC(5,2) AS $$
DECLARE
    v_published_cnt   INTEGER;
    v_confirmed_cnt   INTEGER;
    v_refuted_cnt     INTEGER;
    v_reported_cnt    INTEGER;
    v_reputation      NUMERIC(5,2);
BEGIN
    -- 统计用户发布信息数
    SELECT COUNT(*) INTO v_published_cnt
    FROM posts WHERE user_id = p_user_id AND is_deleted = FALSE;

    -- 统计被证实的信息数
    SELECT COUNT(DISTINCT v.post_id) INTO v_confirmed_cnt
    FROM validation_records v
    JOIN posts p ON p.id = v.post_id
    WHERE p.user_id = p_user_id
      AND v.validation_type = 'confirmation'
      AND v.is_deleted = FALSE
      AND p.is_deleted = FALSE;

    -- 统计被证伪的信息数
    SELECT COUNT(DISTINCT v.post_id) INTO v_refuted_cnt
    FROM validation_records v
    JOIN posts p ON p.id = v.post_id
    WHERE p.user_id = p_user_id
      AND v.validation_type = 'refutation'
      AND v.is_deleted = FALSE
      AND p.is_deleted = FALSE;

    -- 统计用户发布的信息被举报数
    SELECT COUNT(*) INTO v_reported_cnt
    FROM reports r
    JOIN posts p ON p.id = r.post_id
    WHERE p.user_id = p_user_id;

    -- 信誉分公式（详见 doc 27 第 4.3.4 节）
    v_reputation := 60.0
                  + v_confirmed_cnt * 3.0
                  + v_published_cnt * 0.5
                  - v_refuted_cnt * 5.0
                  - v_reported_cnt * 2.0;

    v_reputation := GREATEST(0.0, LEAST(100.0, v_reputation));

    UPDATE users
    SET reputation_score = v_reputation,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_user_id;

    RETURN v_reputation;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_update_reputation(BIGINT) IS 'SP04 更新用户信誉分（0-100）';

-- ============================================================
-- SP05 sp_archive_logs（归档历史日志）
-- 调用方：定时任务 JOB03（每日 04:00）
-- 功能：将 90 天前的管理员操作日志迁移到 admin_operation_logs_archive
-- 依赖：09_create_partitions.sql 中的 admin_operation_logs_archive 表
-- ============================================================
CREATE OR REPLACE FUNCTION sp_archive_logs()
RETURNS INTEGER AS $$
DECLARE
    v_affected INTEGER;
BEGIN
    -- 将 90 天前的管理员操作日志迁移到归档表
    -- 注：归档表由 09_create_partitions.sql 创建，结构同 admin_operation_logs
    INSERT INTO admin_operation_logs_archive
        (admin_id, action, target_type, target_id, detail,
         ip_address, user_agent, created_at)
    SELECT admin_id, action, target_type, target_id, detail,
           ip_address, user_agent, created_at
    FROM admin_operation_logs
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';

    GET DIAGNOSTICS v_affected = ROW_COUNT;

    -- 删除已归档的日志
    DELETE FROM admin_operation_logs
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';

    RETURN v_affected;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_archive_logs() IS 'SP05 归档 90 天前管理员操作日志（每日 04:00）';

-- ============================================================
-- SP06 sp_cleanup_soft_deleted（清理软删除数据）
-- 调用方：定时任务 JOB05（每周日 02:00）
-- 功能：物理删除 30 天前软删除的数据
-- ============================================================
CREATE OR REPLACE FUNCTION sp_cleanup_soft_deleted()
RETURNS INTEGER AS $$
DECLARE
    v_total_affected INTEGER := 0;
    v_affected INTEGER;
    v_cutoff TIMESTAMP WITH TIME ZONE := CURRENT_TIMESTAMP - INTERVAL '30 days';
BEGIN
    -- 清理 30 天前软删除的 post_images
    DELETE FROM post_images
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 清理 30 天前软删除的 comments
    DELETE FROM comments
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 清理 30 天前软删除的 notifications
    DELETE FROM notifications
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 清理 30 天前软删除的 tags
    DELETE FROM tags
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 清理 30 天前软删除的 locations
    DELETE FROM locations
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 清理 30 天前软删除的 drafts
    DELETE FROM drafts
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 清理 30 天前软删除的 topic_collections
    DELETE FROM topic_collections
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 清理 30 天前软删除的 posts（最后清理，避免外键约束）
    DELETE FROM posts
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 清理 30 天前软删除的 users
    DELETE FROM users
    WHERE is_deleted = TRUE AND deleted_at IS NOT NULL AND deleted_at < v_cutoff;
    GET DIAGNOSTICS v_affected = ROW_COUNT;
    v_total_affected := v_total_affected + v_affected;

    -- 记录清理日志
    INSERT INTO admin_operation_logs (admin_id, action, target_type, target_id, detail, created_at)
    VALUES (0, 'system_cleanup', 'system', 0,
            '软删除清理：共清理 ' || v_total_affected || ' 条记录',
            CURRENT_TIMESTAMP);

    RETURN v_total_affected;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_cleanup_soft_deleted() IS 'SP06 清理 30 天前软删除数据（每周日 02:00）';

-- ============================================================
-- SP07 sp_publish_post（信息发布流程）
-- 调用方：应用层
-- 功能：封装信息发布的完整流程
--   1. 校验用户状态（未删除、已激活）
--   2. 插入信息记录
--   3. 初始化可信度（基于作者信誉分）
--   4. 记录发布日志
-- 参数：
--   p_user_id       - 发布者ID
--   p_school_id     - 学校ID
--   p_category_id   - 分类ID
--   p_post_type_id  - 信息类型ID
--   p_location_id   - 地点ID（可空）
--   p_title         - 标题
--   p_content       - 内容
--   p_is_anonymous  - 是否匿名
--   p_expire_at     - 过期时间（可空）
--   p_activity_start_at - 活动开始时间（可空）
--   p_activity_end_at   - 活动结束时间（可空）
--   p_contact_info  - 联系方式（可空）
--   p_status        - 初始状态（默认 pending_review）
-- 返回：新信息ID
-- ============================================================
CREATE OR REPLACE FUNCTION sp_publish_post(
    p_user_id           BIGINT,
    p_school_id         BIGINT,
    p_category_id       BIGINT,
    p_post_type_id      BIGINT,
    p_location_id       BIGINT DEFAULT NULL,
    p_title             VARCHAR(200),
    p_content           TEXT,
    p_is_anonymous      BOOLEAN DEFAULT FALSE,
    p_expire_at         TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    p_activity_start_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    p_activity_end_at   TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    p_contact_info      VARCHAR(255) DEFAULT NULL,
    p_status            VARCHAR(20) DEFAULT 'pending_review'
)
RETURNS BIGINT AS $$
DECLARE
    v_post_id      BIGINT;
    v_author_rep   NUMERIC(5,2);
    v_credibility  NUMERIC(5,2);
BEGIN
    -- 校验：用户必须存在且未删除、已激活
    IF NOT EXISTS (
        SELECT 1 FROM users
        WHERE id = p_user_id AND is_deleted = FALSE AND is_active = TRUE
    ) THEN
        RAISE EXCEPTION '用户不存在或已被禁用：user_id=%', p_user_id;
    END IF;

    -- 校验：标题与内容非空
    IF p_title IS NULL OR LENGTH(TRIM(p_title)) = 0 THEN
        RAISE EXCEPTION '信息标题不能为空';
    END IF;
    IF p_content IS NULL OR LENGTH(TRIM(p_content)) = 0 THEN
        RAISE EXCEPTION '信息内容不能为空';
    END IF;

    -- 获取作者信誉分（默认 60）
    SELECT COALESCE(reputation_score, 60.00) INTO v_author_rep
    FROM users WHERE id = p_user_id;

    -- 初始可信度 = 作者信誉 * 0.3 + 50 * 0.7
    v_credibility := v_author_rep * 0.3 + 50.0 * 0.7;
    v_credibility := GREATEST(0.0, LEAST(100.0, v_credibility));

    -- 插入信息记录
    INSERT INTO posts (
        user_id, school_id, category_id, post_type_id, location_id,
        title, content, is_anonymous, status,
        view_count, like_count, comment_count, favorite_count,
        valid_count, invalid_count, credibility_score,
        expire_at, activity_start_at, activity_end_at,
        contact_info, is_top, is_recommend,
        created_at, updated_at, is_deleted
    ) VALUES (
        p_user_id, p_school_id, p_category_id, p_post_type_id, p_location_id,
        p_title, p_content, p_is_anonymous, p_status,
        0, 0, 0, 0,
        0, 0, v_credibility,
        p_expire_at, p_activity_start_at, p_activity_end_at,
        p_contact_info, FALSE, FALSE,
        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE
    )
    RETURNING id INTO v_post_id;

    -- 记录发布日志
    INSERT INTO admin_operation_logs (admin_id, action, target_type, target_id, detail, created_at)
    VALUES (p_user_id, 'publish_post', 'post', v_post_id,
            '发布信息：' || p_title, CURRENT_TIMESTAMP);

    -- 若已直接发布（status=published），触发冲突检测
    IF p_status = 'published' AND p_location_id IS NOT NULL
       AND p_activity_start_at IS NOT NULL AND p_activity_end_at IS NOT NULL THEN
        PERFORM sp_detect_conflict(v_post_id);
    END IF;

    RETURN v_post_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_publish_post(BIGINT, BIGINT, BIGINT, BIGINT, BIGINT, VARCHAR, TEXT, BOOLEAN,
                                    TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE,
                                    TIMESTAMP WITH TIME ZONE, VARCHAR, VARCHAR) IS 'SP07 信息发布流程（应用层调用）';

-- ============================================================
-- SP08 sp_submit_validation（提交协同验证）
-- 调用方：应用层
-- 功能：原子化提交验证记录 + 重算可信度 + 冲突检测 + 信誉分更新
-- 参数：
--   p_user_id         - 验证者ID
--   p_post_id         - 信息ID
--   p_validation_type - 验证类型（confirmation/refutation/update/expiration_report/conflict_report）
--   p_content         - 验证内容/评论
--   p_evidence_urls   - 证据图片URL数组（可空）
-- 返回：新验证记录ID
-- 校验：
--   1. 不能为自己的信息验证
--   2. 信息状态必须为 published
-- ============================================================
CREATE OR REPLACE FUNCTION sp_submit_validation(
    p_user_id         BIGINT,
    p_post_id         BIGINT,
    p_validation_type VARCHAR(30),
    p_content         TEXT,
    p_evidence_urls   TEXT[] DEFAULT NULL
)
RETURNS BIGINT AS $$
DECLARE
    v_record_id    BIGINT;
    v_post_author  BIGINT;
    v_post_status  VARCHAR(20);
BEGIN
    -- 校验：信息存在并获取作者与状态
    SELECT user_id, status INTO v_post_author, v_post_status
    FROM posts WHERE id = p_post_id AND is_deleted = FALSE;

    IF NOT FOUND THEN
        RAISE EXCEPTION '信息不存在或已删除：post_id=%', p_post_id;
    END IF;

    -- 校验：不能为自己的信息验证
    IF v_post_author = p_user_id THEN
        RAISE EXCEPTION '不能为自己的信息提交验证';
    END IF;

    -- 校验：信息状态必须为 published
    IF v_post_status <> 'published' THEN
        RAISE EXCEPTION '信息状态不允许验证（当前状态：%）', v_post_status;
    END IF;

    -- 校验：验证类型合法
    IF p_validation_type NOT IN ('confirmation', 'refutation', 'update',
                                  'expiration_report', 'conflict_report') THEN
        RAISE EXCEPTION '无效的验证类型：%', p_validation_type;
    END IF;

    -- 插入验证记录
    -- 注：validation_records.comment 字段对应 p_content
    --     evidence_urls 字段当前模型未实现，p_evidence_urls 参数预留
    INSERT INTO validation_records (post_id, user_id, validation_type, comment, created_at)
    VALUES (p_post_id, p_user_id, p_validation_type, p_content, CURRENT_TIMESTAMP)
    RETURNING id INTO v_record_id;

    -- 重算信息可信度
    PERFORM sp_recalc_credibility(p_post_id);

    -- 若为冲突报告，触发冲突检测
    IF p_validation_type = 'conflict_report' THEN
        PERFORM sp_detect_conflict(p_post_id);
    END IF;

    -- 更新验证者信誉分（参与验证 +0.1，由公式自动计算）
    PERFORM sp_update_reputation(p_user_id);

    -- 更新信息作者信誉分
    PERFORM sp_update_reputation(v_post_author);

    RETURN v_record_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION sp_submit_validation(BIGINT, BIGINT, VARCHAR, TEXT, TEXT[]) IS 'SP08 提交协同验证（原子操作）';

-- ============================================================
-- 存储过程验证
-- ============================================================
SELECT
    n.nspname AS schema,
    p.proname AS function_name,
    pg_get_function_result(p.oid) AS return_type,
    pg_get_function_arguments(p.oid) AS arguments
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname LIKE 'sp_%'
ORDER BY p.proname;
