-- ============================================================
-- 脚本名称：10_init_data.sql
-- 用途：初始化江南大学核心数据（学校 + 地点 + 分类 + 信息类型 + 管理员）
-- 依据：
--   - docs/23_江南大学模拟核心决策说明.md 第 2、4 节
--   - docs/27_数据库物理模型设计.md 第 11 节
-- 数据库：moment_campus（openGauss 7.0.0-RC3 轻量版）
-- 创建时间：2026-06-29
-- 说明：
--   1. 江南大学为项目唯一模拟学校（蠡湖校区）
--   2. 15 个地点为建议清单，坐标为估算值，需通过地图工具核对
--   3. 12 个分类覆盖校园生活主要场景
--   4. 3 个信息类型对应不同业务流程
--   5. 默认管理员密码为 admin123（bcrypt 哈希），生产环境请修改
--   6. 使用 ON CONFLICT DO NOTHING 保证可重复执行
-- ============================================================

-- ============================================================
-- 第一部分：江南大学学校记录
-- ============================================================
INSERT INTO schools (
    name, code, logo_url, province, city, address,
    center_lat, center_lng, map_zoom, is_active,
    created_at, updated_at
) VALUES (
    '江南大学', 'jiangnan', NULL,
    '江苏省', '无锡市', '江苏省无锡市滨湖区蠡湖大道1800号',
    31.483706, 120.271166, 16, TRUE,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
)
ON CONFLICT (code) DO NOTHING;

-- 验证学校记录
SELECT id, name, code, address, center_lat, center_lng
FROM schools WHERE code = 'jiangnan';

-- ============================================================
-- 第二部分：15 个地点（依据 doc 23 第 4 节）
-- 坐标为江南大学蠡湖校区附近估算值，需通过地图工具核对
-- ============================================================
INSERT INTO locations (
    school_id, name, description, latitude, longitude,
    building, floor, post_count, is_verified,
    created_at, updated_at, is_deleted
) VALUES
    (1, '北门', '蠡湖大道主入口', 31.486000, 120.271166, '北门', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '南门', '校园南入口', 31.481000, 120.271166, '南门', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '第一食堂', '主食堂', 31.484000, 120.272000, '第一食堂', '1F', 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '第二食堂', '学生食堂', 31.484000, 120.270000, '第二食堂', '1F', 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '图书馆', '主图书馆', 31.485000, 120.273000, '图书馆', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '体育馆', '综合体育馆', 31.483000, 120.274000, '体育馆', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '田径场', '主田径场', 31.484000, 120.274000, '田径场', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '教学楼A区', '主要教学区', 31.485000, 120.272000, '教学楼A', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '学士公寓', '学生宿舍区', 31.482000, 120.269000, '学士公寓', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '校园超市', '综合超市', 31.483000, 120.271000, '校园超市', '1F', 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '文浩科学馆', '讲座演出场地', 31.486000, 120.273000, '文浩科学馆', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '大学生活动中心', '社团活动场地', 31.486000, 120.272000, '活动中心', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '蠡湖畔', '校园水域景观', 31.485000, 120.275000, '蠡湖', NULL, 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '快递服务中心', '校园快递点', 31.482000, 120.270000, '快递中心', '1F', 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE),
    (1, '打印文印店', '文印服务', 31.484000, 120.271000, '文印店', '1F', 0, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE)
ON CONFLICT DO NOTHING;

-- 验证地点记录
SELECT id, name, latitude, longitude FROM locations WHERE school_id = 1 ORDER BY id;

-- ============================================================
-- 第三部分：12 个分类（覆盖校园生活主要场景）
-- ============================================================
INSERT INTO categories (
    name, code, icon, description, default_validity_days, sort_order, is_active,
    created_at, updated_at
) VALUES
    ('校园活动', 'activity', '🎪', '社团活动、讲座、演出等', 30, 1, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('失物招领', 'lost_found', '🔍', '丢失与拾到物品信息', 30, 2, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('求助问答', 'help', '❓', '学习、生活求助', 60, 3, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('校园美食', 'food', '🍜', '食堂、周边美食推荐', 30, 4, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('学习资源', 'study', '📚', '资料共享、学习心得', 90, 5, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('校园设施', 'facility', '🏫', '教学楼、体育馆、图书馆等', 90, 6, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('生活服务', 'life', '🛒', '超市、快递、文印等', 60, 7, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('校园动物', 'animal', '🐱', '校园流浪动物、宠物', 60, 8, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('二手交易', 'trade', '💰', '二手物品买卖', 30, 9, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('兼职招聘', 'job', '💼', '兼职、招聘信息', 30, 10, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('打印服务', 'print', '🖨️', '打印、复印、扫描', 30, 11, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('其他', 'other', '📝', '其他类型信息', 30, 12, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO NOTHING;

-- 验证分类记录
SELECT id, name, code, sort_order FROM categories ORDER BY sort_order;

-- ============================================================
-- 第四部分：3 个信息类型
-- normal  - 普通信息（默认）
-- event   - 活动信息（带活动时间）
-- lost_found - 失物信息（带 lost_type）
-- ============================================================
INSERT INTO post_types (
    name, code, description, sort_order, is_active,
    created_at, updated_at
) VALUES
    ('普通信息', 'normal', '通用校园信息，无特殊字段', 1, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('活动信息', 'event', '校园活动，需填写活动起止时间', 2, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
    ('失物信息', 'lost_found', '失物招领，需填写 lost_type（lost/picked）', 3, TRUE,
     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO NOTHING;

-- 验证信息类型记录
SELECT id, name, code, sort_order FROM post_types ORDER BY sort_order;

-- ============================================================
-- 第五部分：默认管理员账号
-- 邮箱：admin@momentcampus.com
-- 密码：admin123（bcrypt 哈希，cost=12）
-- 角色：admin
-- 学校：江南大学（school_id=1）
-- 注：生产环境请通过应用层修改密码
-- ============================================================
INSERT INTO users (
    email, nickname, password_hash, avatar_url, school_id, role,
    bio, is_active, last_login_at,
    reputation_score,
    created_at, updated_at, is_deleted
) VALUES (
    'admin@momentcampus.com',
    '系统管理员',
    '$2b$12$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy',
    NULL,
    1,
    'admin',
    '此刻校园系统管理员',
    TRUE,
    NULL,
    100.00,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    FALSE
)
ON CONFLICT (email) DO NOTHING;

-- 验证管理员账号
SELECT id, email, nickname, role, school_id, reputation_score, is_active
FROM users WHERE role = 'admin';

-- ============================================================
-- 第六部分：数据初始化验证汇总
-- ============================================================
SELECT '=== 数据初始化验证 ===' AS report;

SELECT
    (SELECT COUNT(*) FROM schools)              AS school_count,
    (SELECT COUNT(*) FROM locations)            AS location_count,
    (SELECT COUNT(*) FROM categories)           AS category_count,
    (SELECT COUNT(*) FROM post_types)           AS post_type_count,
    (SELECT COUNT(*) FROM users WHERE role='admin') AS admin_count;

-- ============================================================
-- 第七部分：初始化信誉分与可信度（若有现有数据）
-- ============================================================
-- 为所有现有用户设置默认信誉分（60.00）
UPDATE users
SET reputation_score = 60.00
WHERE reputation_score IS NULL;

-- 为所有现有信息设置默认可信度（60.00）
UPDATE posts
SET credibility_score = 60.00
WHERE credibility_score IS NULL;
