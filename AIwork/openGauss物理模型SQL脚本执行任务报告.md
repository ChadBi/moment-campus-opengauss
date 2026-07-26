# 任务报告：openGauss 物理模型 SQL 脚本执行（P-P-01~09）

## 1. 任务概述

在 openGauss 7.0.0-RC3 轻量版容器中执行 P-P-01~09 物理模型 SQL 脚本，将数据库物理模型设计（docs/27_数据库物理模型设计.md）落地为实际数据库对象，包括：表空间、扩展、字段补全、索引、物化视图、存储过程、触发器、分区表、归档表与权限授予。

- 数据库：`moment_campus`，用户 `omm`
- 脚本目录：`backend/scripts/opengauss/`
- 执行环境：Docker 容器 `opengauss`（运行中，已含 21 张业务表与江南大学演示数据）

## 2. 已完成内容

### 2.1 脚本执行清单（按顺序）

| 顺序 | 脚本 | 内容 | 结果 |
|------|------|------|------|
| 01 | 01_create_tablespaces.sql | 4 个表空间（ts_system/ts_core/ts_interaction/ts_log） | ✅ 成功 |
| 02 | 02_create_extensions.sql | pg_trgm 扩展安装（轻量版不可用，已优雅跳过） | ✅ 成功 |
| 03 | 03_alter_tables.sql | users 增加 credibility_score/reputation_score；validation_records 增加 is_deleted/deleted_at | ✅ 成功 |
| 04 | 04_create_indexes.sql | 50+ 索引 + 6 个部分索引（trgm 索引条件创建） | ✅ 成功 |
| 06 | 06_create_materialized_views.sql | 4 个物化视图（MV01-MV04） | ✅ 成功 |
| 07 | 07_create_functions.sql | 8 个存储过程（SP01-SP08） | ✅ 成功 |
| 08 | 08_create_triggers.sql | 8 个触发器函数 + 11 个触发器（TR01-TR08） | ✅ 成功 |
| 09 | 09_create_partitions.sql | 7 张分区表（每表 13 分区）+ 归档表 | ✅ 成功 |
| 11 | 11_grant_permissions.sql | 全对象权限授予 omm | ✅ 成功 |

> 注：10_init_data.sql 未执行（演示数据已通过 seed_data.py 填充）；crontab/install_crontab.sh 未处理（属 P-P-07 定时任务，后续单独处理）。

### 2.2 分区改造后重建

脚本 09 使用 `DROP TABLE CASCADE` 迁移 7 张表为分区表，导致这些表上的触发器（6 个）与全部物化视图（4 个）丢失。已重新执行脚本 06 与 08 完成重建：
- 物化视图：0 → 4（全部重建成功）
- 触发器：5 → 11（丢失的 6 个全部重建成功）

### 2.3 最终验证结果（汇总）

| 对象类型 | 预期 | 实际 | 状态 |
|----------|------|------|------|
| 表空间 | 4 | 4 | ✅ |
| pg_trgm 扩展 | 0（轻量版不可用） | 0 | ✅ |
| 物化视图 | 4 | 4 | ✅ |
| 存储过程（sp_*） | 8 | 8 | ✅ |
| 触发器函数（trg_func_*） | 8 | 8 | ✅ |
| 触发器 | 11 | 11 | ✅ |
| 分区父表 | 7 | 7 | ✅ |
| 分区子表 | 91（7×13） | 91 | ✅ |
| 归档表 | 1 | 1 | ✅ |
| posts 索引 | 12（11 业务 + pkey） | 12 | ✅ |

### 2.4 功能联动验证

- `REFRESH MATERIALIZED VIEW` 4 个物化视图全部刷新成功（非 CONCURRENTLY）
- `sp_mark_expired_posts()` 调用成功（返回 0，符合演示数据预期）
- 触发器联动正常：post id=27 的 credibility_score=60.00、valid_count=3（由 TR01 → sp_recalc_credibility 自动计算）

### 2.5 数据完整性抽样

| 表 | 行数 |
|----|------|
| schools | 1（江南大学） |
| users | 11 |
| locations | 15 |
| posts | 30 |
| comments | 68 |
| validation_records | 37 |
| notifications | 19 |

## 3. 未完成内容

- **P-P-07 定时任务安装**：`crontab` 与 `install_crontab.sh` 未在容器中安装执行（属独立任务，需配置容器内 cron 服务）
- **P-P-08 性能测试**：`performance_test.sql` 未执行（EXPLAIN ANALYZE 性能基准测试，属独立任务）
- **P-P-10 zhparser 中文分词**：未安装（轻量版可能不携带，待确认）
- **物化视图 CONCURRENTLY 刷新**：openGauss 轻量版是否支持 `REFRESH MATERIALIZED VIEW CONCURRENTLY` 未测试（需物化视图有唯一索引，已具备，但语法兼容性待验证）
- **分区表部分索引**：openGauss 分区表不支持部分索引（WHERE 子句），脚本 09 中已移除 WHERE 改为普通索引，原脚本 04 的部分索引在分区表上未重建（非分区表上的部分索引仍保留）

## 4. 实现思路

### 4.1 整体策略

1. **顺序执行**：严格按 01→02→03→04→06→07→08→09→11 顺序，确保依赖关系正确
2. **错误驱动修改**：遇到 openGauss 兼容性错误时，修改宿主机 .sql 文件 → 重新 docker cp → 重新执行
3. **幂等设计**：所有脚本使用 `IF NOT EXISTS` / `DROP IF EXISTS` / `CREATE OR REPLACE`，支持重复执行
4. **分区迁移后重建**：脚本 09 的 `DROP TABLE CASCADE` 会清除触发器和物化视图，执行后重新跑 06 与 08

### 4.2 openGauss 兼容性适配要点

| 问题 | PostgreSQL 语法 | openGauss 适配方案 |
|------|-----------------|-------------------|
| 表空间路径 | 可在 $PGDATA 下创建 | 改用 `/var/lib/opengauss/tablespaces/` |
| pg_tablespace 系统表 | 有 spclocation 列 | 改用 spcoptions 列 |
| pg_trgm 扩展 | 默认携带 | 轻量版不携带，DO 块捕获异常优雅跳过 |
| IDENTITY 列 | `GENERATED ALWAYS AS IDENTITY` | 改用 `BIGSERIAL` |
| 分区表语法 | `PARTITION OF parent ...` | 改用内联 `PARTITION ... VALUES LESS THAN (...)` |
| 分区系统表 | pg_partitioned_table | 改用 pg_partition（parttype='r' 父表，'p' 子分区） |
| 分区表部分索引 | 支持 WHERE 子句 | 不支持，移除 WHERE 改普通索引 |
| 字段缺失 | validation_records 无 is_deleted | 脚本 03 补充 is_deleted/deleted_at 字段 |
| reports 表无 is_deleted | MV03 原 SQL 过滤 is_deleted | MV03 移除 reports 的 is_deleted 过滤 |

### 4.3 PowerShell 引号转义

内联 SQL 在 PowerShell 中易被引号转义破坏，采用 here-string `@' ... '@` + 管道 `| docker exec -i` 方式传输 SQL，避免转义问题。

## 5. 修改文件

### 5.1 宿主机 SQL 脚本（已修改以适配 openGauss）

| 文件 | 修改内容 |
|------|---------|
| `backend/scripts/opengauss/01_create_tablespaces.sql` | 表空间路径从 `/var/lib/opengauss/data/` 改为 `/var/lib/opengauss/tablespaces/`；验证查询 spclocation 改为 spcoptions |
| `backend/scripts/opengauss/02_create_extensions.sql` | pg_trgm 创建改用 DO 块 + EXCEPTION 捕获 |
| `backend/scripts/opengauss/03_alter_tables.sql` | 新增 validation_records 的 is_deleted/deleted_at 字段补全 |
| `backend/scripts/opengauss/04_create_indexes.sql` | trgm 索引与部分索引改用 DO 块条件创建 |
| `backend/scripts/opengauss/06_create_materialized_views.sql` | MV03 移除 reports 表的 is_deleted 过滤 |
| `backend/scripts/opengauss/09_create_partitions.sql` | fn_is_partitioned 改用 pg_partition；IDENTITY 改 BIGSERIAL；7 张表改用 openGauss 内联分区语法；分区表部分索引移除 WHERE |
| `backend/scripts/opengauss/11_grant_permissions.sql` | 验证查询 spclocation 改为 spcoptions |

### 5.2 新增文件

| 文件 | 说明 |
|------|------|
| `AIwork/openGauss物理模型SQL脚本执行任务报告.md` | 本任务报告 |

## 6. 影响范围

- **数据库层**：moment_campus 数据库新增表空间、物化视图、存储过程、触发器、分区表、归档表；7 张大表结构重建为分区表（数据已迁移保留）
- **脚本目录**：`backend/scripts/opengauss/` 下 7 个 SQL 脚本经 openGauss 兼容性修改
- **业务代码**：未修改（本次仅数据库对象创建，不涉及后端 Python 代码）
- **数据**：江南大学演示数据完整保留（posts 30、comments 68、users 11 等）

## 7. 测试与验证

### 7.1 已执行测试

1. **对象创建验证**：通过 `_verify_all.sql` 综合 SQL 验证 12 类对象，全部符合预期（见 2.3 节）
2. **物化视图刷新测试**：4 个物化视图 `REFRESH MATERIALIZED VIEW` 全部成功
3. **存储过程调用测试**：`sp_mark_expired_posts()` 调用成功
4. **触发器联动测试**：posts.credibility_score 由触发器链自动计算（post id=27 = 60.00）
5. **数据完整性验证**：7 张核心表行数抽样正常

### 7.2 未执行测试及原因

- **单元测试（pytest）**：未执行，本次任务聚焦数据库对象创建，业务代码未改动，现有测试基于 SQLite 环境，与本次 openGauss 对象创建无直接关联
- **性能测试（performance_test.sql）**：未执行，属 P-P-08 独立任务
- **CONCURRENTLY 刷新测试**：未执行，需单独验证 openGauss 兼容性

## 8. 后续建议

1. **P-P-07 定时任务安装**：在 openGauss 容器内安装 cron 服务并加载 `crontab` 配置，启用 7 个定时作业（过期标记、信誉更新、日志归档、物化视图刷新、软删除清理、统计更新、索引维护）
2. **P-P-08 性能测试**：执行 `performance_test.sql`，记录 8 个关键查询的 EXPLAIN ANALYZE 数据，对比 docs/27 第 10.2 节预期值
3. **CONCURRENTLY 刷新验证**：测试 `REFRESH MATERIALIZED VIEW CONCURRENTLY` 是否被 openGauss 轻量版支持（物化视图已具备唯一索引）
4. **P-P-10 zhparser**：确认 openGauss 轻量版是否可安装 zhparser 中文分词扩展，若不可则保留 pg_trgm 备选方案
5. **分区表索引补全评估**：评估分区迁移后 posts 表索引从 21 降至 12 是否影响关键查询性能，必要时在分区表上补充非部分索引
6. **Git 提交**：将本次 openGauss 兼容性修改的 7 个 SQL 脚本提交到版本库
