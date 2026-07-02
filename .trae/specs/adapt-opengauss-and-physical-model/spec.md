# openGauss 适配与物理模型落地 Spec

## Why

此刻校园项目当前基于 SQLite（`sqlite+aiosqlite:///./dev.db`），需切换为 openGauss 7.0.0-RC3 轻量版以符合数据库课程设计要求，并依据 [doc 27 物理模型设计](../../../docs/27_数据库物理模型设计.md) 落地表空间、索引、存储过程、触发器、物化视图、分区表等高级物理对象，体现 openGauss 特性应用深度。同时按 [doc 23 江南大学决策](../../../docs/23_江南大学模拟核心决策说明.md) 将模拟核心切换为江南大学蠡湖校区。

## What Changes

### 阶段 A：openGauss 适配（基础切换）

- **BREAKING**：数据库从 SQLite 切换为 openGauss，连接串改为 `postgresql+asyncpg://gaussdb:Gaussdb@123@localhost:5432/momentcampus`
- **BREAKING**：21 个模型主键类型从 `Integer` 统一为 `BigInteger`（解决 [doc 20 H1](../../../docs/20_openGauss适配分析.md) 类型不一致问题）
- 新增后端依赖：`asyncpg`（openGauss 异步驱动）
- 新增 openGauss 环境配置文件 `.env.opengauss`
- 重写 Alembic 初始迁移脚本（openGauss 兼容）
- 修改 `seed_data.py`：学校数据替换为江南大学蠡湖校区，15 个地点按 [doc 23](../../../docs/23_江南大学模拟核心决策说明.md) 调整
- 前端地图默认中心点调整为江南大学坐标（120.271166, 31.483706）
- 文档与 README 同步更新

### 阶段 P：物理模型落地（深度增强）

- 新增 `backend/scripts/opengauss/` 目录，含 11 个 SQL 脚本（依据 [doc 27 第 11 节](../../../docs/27_数据库物理模型设计.md)）
- 创建 4 个表空间：ts_system / ts_core / ts_interaction / ts_log
- 汇总 50 个现有索引 + 新增 8 个部分索引（含 pg_trgm GIN 索引）
- 实现 8 个 PL/pgSQL 存储过程（SP01-SP08：可信度计算、过期标记、冲突检测、信誉分更新、日志归档、软删除清理、信息发布、协同验证提交）
- 实现 8 个触发器（TR01-TR08：验证记录后重算可信度、评论/点赞/收藏计数、状态变更日志）
- 创建 4 个物化视图（MV01-MV04：验证统计、信誉排行、管理员仪表盘、地点信息数）
- 将 7 张大表改造为 RANGE 分区表（按月分区）
- 配置 7 个定时任务（cron + psql）
- 创建归档表 `admin_operation_logs_archive`
- 安装 zhparser 扩展（中文全文搜索）

## Impact

### 受影响的文档

- [docs/20_openGauss适配分析.md](../../../docs/20_openGauss适配分析.md)：H1-H3 高风险项落地
- [docs/21_后续开发任务清单.md](../../../docs/21_后续开发任务清单.md)：T-A 与 P-P 任务执行
- [docs/27_数据库物理模型设计.md](../../../docs/27_数据库物理模型设计.md)：物理对象落地
- [docs/23_江南大学模拟核心决策说明.md](../../../docs/23_江南大学模拟核心决策说明.md)：J1-J4 待确认事项处理
- [TODO.md](../../../TODO.md)：任务状态更新

### 受影响的代码

- 后端配置：`backend/app/database.py`、`backend/app/config.py`、`.env`、`.env.opengauss`
- 后端模型：`backend/app/models/*.py`（21 个文件，主键类型修复）
- 后端迁移：`backend/alembic/versions/`（重写初始迁移）
- 后端种子数据：`backend/scripts/seed_data.py`（江南大学数据）
- 后端依赖：`backend/requirements.txt`（新增 asyncpg）
- 前端地图：`frontend/src/pages/MapPage.tsx` 或相关配置（默认中心点）
- 前端配置：`frontend/.env*`（API 地址若需调整）
- 新增脚本目录：`backend/scripts/opengauss/`（11 个 SQL 脚本）
- 新增定时任务配置：`backend/scripts/opengauss/crontab`

### 受影响的能力

- 数据持久化：从 SQLite 切换为 openGauss
- 数据完整性：触发器自动维护计数与可信度
- 查询性能：部分索引 + 物化视图 + 分区表优化
- 业务自动化：存储过程封装复杂业务逻辑
- 数据归档：分区表 + 定时任务实现历史数据归档

## ADDED Requirements

### Requirement: openGauss 容器环境就绪

系统必须提供可运行的 openGauss 7.0.0-RC3 轻量版容器，作为开发与演示环境。

#### Scenario: openGauss 镜像加载成功
- **WHEN** 执行 `docker load -i opengauss-7.0.0-RC3-lite.tar`
- **THEN** 镜像 `opengauss:7.0.0-RC3` 出现在 `docker images` 列表
- **AND** 镜像大小合理（约 500MB-1GB）

#### Scenario: openGauss 容器启动成功
- **WHEN** 执行 `docker run -d --name momentcampus-opengauss -p 5432:5432 -e GS_PASSWORD=Gaussdb@123 opengauss:7.0.0-RC3`
- **THEN** 容器状态为 running
- **AND** 端口 5432 可访问
- **AND** 数据库 `momentcampus` 自动创建（或通过初始化脚本创建）
- **AND** 用户 `gaussdb` 可用密码 `Gaussdb@123` 登录

#### Scenario: asyncpg 连接验证成功
- **WHEN** 执行最小连接测试脚本
- **THEN** asyncpg 能成功连接 openGauss
- **AND** 能执行 `SELECT 1` 查询
- **AND** 能执行 `CREATE TABLE` 与 `INSERT` 语句
- **AND** 能查询 `pg_catalog.pg_tables` 系统视图

### Requirement: 模型类型一致性修复

21 个数据模型的主键类型必须统一为 `BigInteger`，外键类型与主键一致。

#### Scenario: 主键类型修复完成
- **WHEN** 检查 `backend/app/models/*.py` 中所有 21 个模型
- **THEN** 所有 `id` 主键字段类型为 `BigInteger`
- **AND** 所有外键字段（如 `user_id`、`school_id`、`post_id` 等）类型为 `BigInteger`
- **AND** 无 `Integer` 主键与 `BigInteger` 外键混用情况
- **AND** 模型导入与关系定义不受影响

### Requirement: openGauss 环境配置切换

后端必须支持通过环境变量在 SQLite 与 openGauss 之间切换。

#### Scenario: openGauss 配置文件就绪
- **WHEN** 检查 `backend/.env.opengauss`
- **THEN** 文件包含 `DATABASE_URL=postgresql+asyncpg://gaussdb:Gaussdb@123@localhost:5432/momentcampus`
- **AND** 包含 JWT_SECRET、SCHOOL_CODE=jiangnan 等配置项
- **AND** 文件不被 Git 跟踪（在 .gitignore 中）

#### Scenario: 配置加载支持环境切换
- **WHEN** 设置 `APP_ENV=opengauss` 启动后端
- **THEN** 后端加载 `.env.opengauss` 配置
- **AND** 数据库连接指向 openGauss
- **AND** 启动日志显示 "Database: openGauss 7.0.0-RC3"

### Requirement: Alembic 迁移重写

Alembic 初始迁移脚本必须兼容 openGauss，能成功创建全部 21 张表。

#### Scenario: 迁移脚本生成成功
- **WHEN** 执行 `alembic revision --autogenerate -m "openGauss initial"`
- **THEN** 生成新的迁移脚本
- **AND** 脚本中所有主键为 BIGINT
- **AND** 脚本中所有外键为 BIGINT
- **AND** 脚本中索引定义完整（50 个索引）

#### Scenario: 迁移应用成功
- **WHEN** 执行 `alembic upgrade head`
- **THEN** openGauss 中创建 21 张表
- **AND** 所有索引创建成功
- **AND** 所有唯一约束生效
- **AND** 所有外键约束生效

### Requirement: 江南大学数据填充

种子数据必须以江南大学蠡湖校区为模拟核心，替换原有华东师大+复旦数据。

#### Scenario: 学校数据替换成功
- **WHEN** 执行 `seed_data.py`
- **THEN** `schools` 表仅 1 条记录：江南大学
- **AND** 学校 code 为 `jiangnan`
- **AND** 地址为江苏省无锡市滨湖区蠡湖大道1800号
- **AND** 中心坐标为 (120.271166, 31.483706)

#### Scenario: 地点数据替换成功
- **WHEN** 检查 `locations` 表
- **THEN** 15 个地点均位于江南大学蠡湖校区
- **AND** 地点名称符合 [doc 23](../../../docs/23_江南大学模拟核心决策说明.md) 建议（如图书馆、第二教学楼、蠡湖等）
- **AND** 所有地点的 school_id 指向江南大学记录

#### Scenario: 用户与信息数据适配
- **WHEN** 检查 `users` 与 `posts` 表
- **THEN** 所有用户的 school_id 指向江南大学
- **AND** 所有信息的 school_id 指向江南大学
- **AND** 信息地点均在江南大学 15 个地点内

### Requirement: 前端地图默认中心调整

前端地图默认中心点必须调整为江南大学蠡湖校区坐标。

#### Scenario: 地图中心点调整成功
- **WHEN** 用户访问地图页
- **THEN** 地图初始中心为 (120.271166, 31.483706)
- **AND** 默认缩放级别为 15
- **AND** 地图标记均位于江南大学校区范围内

### Requirement: openGauss 联调验证

前后端必须在 openGauss 环境下完成核心业务联调，确保功能正常。

#### Scenario: 后端启动成功
- **WHEN** 使用 `.env.opengauss` 启动后端
- **THEN** 后端无错误启动
- **AND** Swagger 文档可访问
- **AND** 数据库连接池正常

#### Scenario: 核心业务链路验证
- **WHEN** 执行核心业务流程（注册→登录→发布→浏览→互动→验证）
- **THEN** 所有操作成功执行
- **AND** 数据正确写入 openGauss
- **AND** 查询结果正确返回

### Requirement: 表空间与索引创建

依据 [doc 27 第 2-3 节](../../../docs/27_数据库物理模型设计.md)，创建表空间与索引。

#### Scenario: 表空间创建成功
- **WHEN** 执行 `01_create_tablespaces.sql`
- **THEN** 创建 4 个表空间：ts_system / ts_core / ts_interaction / ts_log
- **AND** 所有者均为 gaussdb
- **AND** 物理路径存在且可写

#### Scenario: 索引创建成功
- **WHEN** 执行 `04_create_indexes.sql`
- **THEN** 创建约 50 个现有索引（含主键、唯一、复合索引）
- **AND** 创建 8 个新增部分索引（含 pg_trgm GIN 索引）
- **AND** `pg_trgm` 扩展安装成功

### Requirement: 存储过程与触发器实现

依据 [doc 27 第 4-5 节](../../../docs/27_数据库物理模型设计.md)，实现 8 个存储过程与 8 个触发器。

#### Scenario: 存储过程创建成功
- **WHEN** 执行 `07_create_functions.sql`
- **THEN** 创建 SP01-SP08 共 8 个 PL/pgSQL 存储过程
- **AND** `sp_recalc_credibility(post_id)` 能正确计算可信度
- **AND** `sp_mark_expired_posts()` 能标记过期信息
- **AND** `sp_submit_validation(...)` 能原子化提交验证

#### Scenario: 触发器创建成功
- **WHEN** 执行 `08_create_triggers.sql`
- **THEN** 创建 TR01-TR08 共 8 个触发器
- **AND** 插入验证记录后自动重算信息可信度
- **AND** 插入评论/点赞/收藏后自动更新 posts 计数字段
- **AND** posts 状态变更自动记录日志

#### Scenario: 触发器业务联动验证
- **WHEN** 用户提交一条证实验证记录
- **THEN** validation_records 表新增记录
- **AND** posts.valid_count 自动 +1
- **AND** posts.credibility_score 自动重算
- **AND** users.reputation_score（验证者与作者）自动更新

### Requirement: 物化视图与分区表实现

依据 [doc 27 第 6-7 节](../../../docs/27_数据库物理模型设计.md)，实现物化视图与分区表。

#### Scenario: 物化视图创建成功
- **WHEN** 执行 `06_create_materialized_views.sql`
- **THEN** 创建 MV01-MV04 共 4 个物化视图
- **AND** 每个物化视图有唯一索引（用于 CONCURRENTLY 刷新）
- **AND** `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_admin_dashboard` 执行成功

#### Scenario: 分区表创建成功
- **WHEN** 执行 `09_create_partitions.sql`
- **THEN** 7 张大表（posts/comments/notifications/admin_operation_logs/browse_histories/search_histories/validation_records）改造为分区表
- **AND** 按月创建分区（至少当前月与下月）
- **AND** 插入数据自动路由到正确分区

### Requirement: 定时任务与归档配置

依据 [doc 27 第 8 节](../../../docs/27_数据库物理模型设计.md)，配置定时任务与归档表。

#### Scenario: 归档表创建成功
- **WHEN** 执行 `09_create_partitions.sql` 中归档表部分
- **THEN** 创建 `admin_operation_logs_archive` 表
- **AND** 表结构与 `admin_operation_logs` 一致

#### Scenario: 定时任务配置就绪
- **WHEN** 检查 `backend/scripts/opengauss/crontab`
- **THEN** 包含 7 个 JOB 配置
- **AND** 过期标记任务每小时执行
- **AND** 日志归档任务每日 04:00 执行
- **AND** 物化视图刷新每 10 分钟执行

### Requirement: 性能验证

依据 [doc 27 第 10 节](../../../docs/27_数据库物理模型设计.md)，验证关键查询性能。

#### Scenario: 关键查询性能达标
- **WHEN** 执行 EXPLAIN ANALYZE 验证 8 个关键查询场景
- **THEN** 首页信息列表查询 ≤ 10ms
- **AND** 信息详情查询（含统计）≤ 10ms
- **AND** 管理员仪表盘查询 ≤ 30ms
- **AND** 标题模糊搜索 ≤ 30ms

## MODIFIED Requirements

### Requirement: 数据库连接配置

原 SQLite 配置保留为开发备选，新增 openGauss 配置作为课程设计主环境。

**修改说明**：
- `backend/app/config.py` 增加 `APP_ENV` 环境变量读取逻辑
- 默认环境为 `development`（SQLite），设置为 `opengauss` 时加载 openGauss 配置
- 两种环境可切换，互不影响

## REMOVED Requirements

无（保留 SQLite 作为开发备选，不删除原配置）
