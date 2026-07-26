# 任务报告：openGauss 物理模型 SQL 脚本编写

## 1. 任务概述

为此刻校园项目编写 openGauss 物理模型的 SQL 脚本，依据 doc 27 数据库物理模型设计文档。共需编写 12 个文件（10 个 SQL 脚本 + 1 个 crontab + 1 个 shell 安装脚本），覆盖表空间、扩展、字段变更、索引、物化视图、存储过程、触发器、分区表、初始化数据、权限、定时任务与性能测试。

## 2. 已完成内容

共创建 12 个文件，全部位于 `backend/scripts/opengauss/` 目录下：

| 序号 | 文件名 | 内容 |
| ---- | ------ | ---- |
| 1 | 01_create_tablespaces.sql | 4 个表空间（ts_system/ts_core/ts_interaction/ts_log），所有者 omm |
| 2 | 02_create_extensions.sql | pg_trgm 必装扩展 + zhparser 可选扩展（注释说明） |
| 3 | 03_alter_tables.sql | posts.credibility_score + users.reputation_score 两个 NUMERIC(5,2) 字段 |
| 4 | 04_create_indexes.sql | 21 张表约 50 个现有索引 + 8 个新增部分索引/GIN 索引 |
| 5 | 06_create_materialized_views.sql | 4 个物化视图（MV01-MV04），每个含唯一索引支持 CONCURRENTLY 刷新 |
| 6 | 07_create_functions.sql | 8 个 PL/pgSQL 存储过程（SP01-SP08） |
| 7 | 08_create_triggers.sql | 8 个触发器函数 + 触发器（TR01-TR08） |
| 8 | 09_create_partitions.sql | 7 张大表按月 RANGE 分区 + 归档表 admin_operation_logs_archive |
| 9 | 10_init_data.sql | 江南大学 + 15 地点 + 12 分类 + 3 信息类型 + 默认管理员账号 |
| 10 | 11_grant_permissions.sql | omm 用户对所有对象的全部权限 |
| 11 | crontab | 7 个定时任务（JOB01-JOB07） |
| 12 | install_crontab.sh | crontab 安装脚本，含环境变量配置与备份 |
| 13 | performance_test.sql | 8 个关键查询的 EXPLAIN ANALYZE |

## 3. 未完成内容

- **zhparser 中文分词扩展**：openGauss 轻量版默认未携带，仅在 02_create_extensions.sql 中以注释形式给出安装步骤，需用户在容器内手动编译安装后启用。
- **真实环境执行验证**：本任务仅编写 SQL 脚本，未在 openGauss 容器中实际执行验证。需用户在部署环境中按顺序执行脚本并验证。
- **管理员密码哈希**：10_init_data.sql 中使用占位 bcrypt 哈希值，对应密码 "admin123"，生产环境建议通过应用层修改密码。

## 4. 实现思路

### 4.1 设计依据
- 主要依据 `docs/27_数据库物理模型设计.md` 第 2-10 节
- 索引清单参考 `backend/app/models/` 中各模型的 `__table_args__`
- 初始化数据参考 `docs/23_江南大学模拟核心决策说明.md` 第 2、4 节

### 4.2 关键设计决策
1. **用户名 omm**：openGauss 轻量版默认用户为 omm（非 gaussdb），所有表空间、权限均授予 omm
2. **数据库 moment_campus**：使用下划线命名（非 momentcampus）
3. **字段新增独立脚本**：将 credibility_score/reputation_score 字段添加独立为 03_alter_tables.sql，便于在 04 索引脚本之前执行
4. **分区表主键**：openGauss 分区表主键必须包含分区键，故使用 (id, created_at) 复合主键
5. **MV03 单行视图唯一索引**：使用常量列 id=1 作为唯一索引，支持 CONCURRENTLY 刷新
6. **部分索引命名**：为避免与现有索引同名，新增带 WHERE 的部分索引使用 _active 后缀（如 idx_validation_post_type_active）
7. **分区表迁移**：使用临时表 _backup_xxx 过渡数据，DROP 原表后重建分区表，再导入数据
8. **可重复执行**：所有 CREATE 语句使用 IF NOT EXISTS，INSERT 使用 ON CONFLICT DO NOTHING

### 4.3 脚本执行顺序
```
01_create_tablespaces.sql      → 创建表空间
02_create_extensions.sql       → 安装 pg_trgm
03_alter_tables.sql            → 新增 credibility_score / reputation_score 字段
04_create_indexes.sql          → 创建所有索引
06_create_materialized_views.sql → 创建物化视图
07_create_functions.sql        → 创建存储过程
08_create_triggers.sql         → 创建触发器
09_create_partitions.sql       → 分区表改造（破坏性，需备份）
10_init_data.sql               → 初始化江南大学核心数据
11_grant_permissions.sql       → 授予 omm 权限
```

## 5. 修改文件

### 5.1 新增文件（13 个）
- `backend/scripts/opengauss/01_create_tablespaces.sql`
- `backend/scripts/opengauss/02_create_extensions.sql`
- `backend/scripts/opengauss/03_alter_tables.sql`
- `backend/scripts/opengauss/04_create_indexes.sql`
- `backend/scripts/opengauss/06_create_materialized_views.sql`
- `backend/scripts/opengauss/07_create_functions.sql`
- `backend/scripts/opengauss/08_create_triggers.sql`
- `backend/scripts/opengauss/09_create_partitions.sql`
- `backend/scripts/opengauss/10_init_data.sql`
- `backend/scripts/opengauss/11_grant_permissions.sql`
- `backend/scripts/opengauss/crontab`
- `backend/scripts/opengauss/install_crontab.sh`
- `backend/scripts/opengauss/performance_test.sql`

### 5.2 修改文件
- 无（本任务仅新增脚本，未修改现有代码）

## 6. 影响范围

- **数据库物理层**：表空间、索引、物化视图、存储过程、触发器、分区表、归档表
- **数据库初始化**：江南大学核心数据（学校、地点、分类、信息类型、管理员）
- **运维调度**：7 个 cron 定时任务
- **性能验证**：8 个关键查询的 EXPLAIN ANALYZE
- **不影响**：应用层代码（backend/app/）、前端代码（frontend/）、API 接口

## 7. 测试与验证

**未运行测试**。原因：
1. 本任务仅编写 SQL 脚本，未在 openGauss 容器中实际执行
2. 任务要求是"编写 SQL 脚本"，未要求在数据库中执行验证
3. openGauss 容器需用户自行启动，脚本中包含的环境路径（如 /var/lib/opengauss/data/）需用户确认

**建议验证步骤**：
1. 启动 openGauss 容器，创建 moment_campus 数据库
2. 在容器内创建表空间目录：`mkdir -p /var/lib/opengauss/data/{system,core,interaction,log}`
3. 按顺序执行 01-11 脚本
4. 执行 performance_test.sql 验证性能
5. 安装 crontab 并观察定时任务执行情况

## 8. 后续建议

1. **环境验证**：在 openGauss 容器中实际执行所有脚本，修复可能的兼容性问题
2. **zhparser 安装**：若需中文全文搜索，在容器内编译安装 zhparser 扩展
3. **管理员密码**：执行 10_init_data.sql 后，通过应用层修改管理员密码为强密码
4. **地点坐标核对**：15 个地点的坐标为估算值，需通过百度/高德地图拾取器核对
5. **分区表性能测试**：在数据量较大时验证分区裁剪（partition pruning）效果
6. **物化视图刷新策略**：根据实际数据更新频率调整 crontab 中的刷新周期
7. **03_create_tables.sql 缺失**：doc 27 第 11 节列出 03_create_tables.sql（21 张表），但本任务未要求编写（假设表已存在）。若需要在 openGauss 上从零创建表结构，需补充此脚本
8. **05_create_views.sql 缺失**：doc 27 第 11 节列出 05_create_views.sql（15 个普通视图），本任务未要求编写，需后续补充
