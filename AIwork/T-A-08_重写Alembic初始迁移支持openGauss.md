# 任务报告：T-A-08 重写 Alembic 初始迁移以支持 openGauss

## 1. 任务概述

重写 Alembic 初始迁移脚本，使其能在 openGauss 7.0.0-RC3 上正确创建 21 张业务表，所有主键与外键使用 BIGINT 类型。任务包含：备份旧迁移脚本、配置 env.py 支持 openGauss、生成并应用新迁移、验证表结构。

## 2. 已完成内容

1. 创建 `delete/` 目录，将旧的空迁移脚本 `82978de89068_initial_migration_create_all_21_tables.py` 移入备份。
2. 更新 `backend/alembic/env.py`：
   - 添加 openGauss 版本字符串解析兼容补丁（覆写 `PGDialect._get_server_version_info`）。
   - 设置 `sqlalchemy.url` 时对 `%` 进行转义（`%%`），避免 `configparser` 解析 `Gaussdb%40123` 报错。
   - 在 `run_migrations_offline` 与 `do_run_migrations` 中添加 `render_as_batch=False`、`compare_type=True`、`compare_server_default=True`。
   - 显式 `import app.models`，确保 21 个模型注册到 `Base.metadata`（否则 autogenerate 生成空迁移）。
3. 通过 `alembic revision --autogenerate` 生成新迁移脚本 `af3fef102173_opengauss_initial_migration.py`，包含：
   - 21 个 `op.create_table()` 调用
   - 107 个 `op.create_index()` 调用
   - 61 处 `sa.BigInteger()`（21 主键 + 40 外键）
   - 完整的 `downgrade()` 函数
4. 执行 `alembic upgrade head` 成功，迁移版本 `af3fef102173` 已写入 `alembic_version` 表。
5. 通过 `gsql` 验证：
   - 22 张表（21 业务表 + alembic_version）
   - `users.id` 为 `bigint`，`users.school_id` 为 `bigint`
   - `posts.id` 为 `bigint`，5 个外键列（user_id / school_id / category_id / post_type_id / location_id）均为 `bigint`
   - 计数列（view_count 等）保留为 `integer`
6. 更新 `TODO.md`，标记 T-A-08 完成。

## 3. 未完成内容

暂无。

## 4. 实现思路

### openGauss 兼容性问题及解决方案

在执行 autogenerate 时遇到两个 openGauss 兼容性问题，逐一解决：

**问题 1：版本字符串解析失败**
SQLAlchemy 的 PostgreSQL 方言 `_get_server_version_info` 使用正则 `.*(?:PostgreSQL|EnterpriseDB) (\d+)\.?(\d+)?...` 匹配 `version()` 返回值。openGauss 返回 `(openGauss 7.0.0-RC3 build ...)`，不包含 `PostgreSQL` 关键字，导致 `AssertionError`。

**解决方案**：在 env.py 中对 `PGDialect._get_server_version_info` 做猴子补丁，先尝试原逻辑，失败后用 `.*openGauss (\d+)\.(\d+)(?:\.(\d+))?` 解析。

**问题 2：configparser 插值错误**
DATABASE_URL 中的密码 `Gaussdb%40123` 含 `%`，`config.set_main_option` 经 configparser BasicInterpolation 处理时报 `invalid interpolation syntax`。

**解决方案**：设置 URL 前将 `%` 替换为 `%%`，读取时 configparser 会自动还原。

**问题 3：autogenerate 生成空迁移**
env.py 原本只导入 `Base`，未导入模型模块，导致 `Base.metadata` 为空。

**解决方案**：在 env.py 中添加 `import app.models`，触发 21 个模型类加载并注册到 metadata。

### 迁移生成策略

采用 autogenerate 而非手写，确保迁移脚本与模型定义完全一致。生成的脚本经计数验证：21 表、107 索引、61 个 BigInteger 列，符合预期。

## 5. 修改文件

- **新增** `backend/alembic/versions/af3fef102173_opengauss_initial_migration.py`：新初始迁移脚本（576 行）。
- **修改** `backend/alembic/env.py`：添加 openGauss 兼容补丁、URL 转义、render_as_batch/compare_type/compare_server_default 参数、模型导入。
- **移动** `backend/alembic/versions/82978de89068_initial_migration_create_all_21_tables.py` → `delete/`（备份旧空迁移）。
- **修改** `TODO.md`：标记 T-A-08 完成。

## 6. 影响范围

- **Alembic 迁移体系**：初始迁移已重写，后续迁移基于 `af3fef102173` 版本。
- **openGauss 数据库**：`moment_campus` 库已创建 21 张业务表 + alembic_version 表。
- **后端配置**：env.py 的兼容补丁仅影响 Alembic 运行时，不影响应用本身（应用使用 `app/database.py` 的引擎）。
- **后续任务**：T-A-09（seed_data.py）、T-A-11（启动后端验证）可基于已建表结构进行。

## 7. 测试与验证

### 执行的验证

1. **autogenerate 日志验证**：日志显示检测到 21 张表 + 全部索引，无报错。
2. **迁移脚本静态检查**：
   - `op.create_table` 计数 = 21 ✓
   - `op.create_index` 计数 = 107 ✓
   - `sa.BigInteger()` 计数 = 61（21 PK + 40 FK）✓
   - `sa.Integer()` 计数 = 22（计数列，正确保留为 Integer）✓
   - `downgrade()` 函数存在 ✓
3. **alembic upgrade head**：退出码 0，日志显示 `Running upgrade -> af3fef102173` ✓
4. **gsql `\dt` 验证**：返回 22 行（21 业务表 + alembic_version）✓
5. **gsql `\d users` 验证**：`id | bigint`，`school_id | bigint`，主键约束 `users_pkey` 存在 ✓
6. **gsql `\d posts` 验证**：`id | bigint`，5 个外键列均为 `bigint`，5 个 FK 约束存在 ✓

### 未运行的测试

- 未运行 `backend/tests/` 下的 pytest 测试套件：这些测试基于 SQLite（conftest 默认使用 dev.db），与 openGauss 环境无关，且本任务范围仅限迁移脚本生成与应用，不涉及业务逻辑测试。
- 未启动 FastAPI 后端验证应用层连接：应用层使用 `app/database.py`，其未应用 openGauss 版本解析补丁，会在 T-A-11 任务中处理。

## 8. 后续建议

1. **应用层 openGauss 兼容**：`app/database.py` 创建引擎时同样会触发 `_get_server_version_info` 错误。建议在 T-A-11（启动后端验证）中将 env.py 的兼容补丁抽取到独立模块（如 `app/db_compat.py`），供 env.py 和 database.py 共同导入。
2. **索引冗余优化**：部分列同时存在 `index=True` 自动索引与 `__table_args__` 显式命名索引（如 `posts.category_id` 同时有 `idx_post_category` 和 `ix_posts_category_id`），共 107 个索引。后续可考虑清理模型中的 `index=True` 重复声明（需修改模型文件，本任务约束不允许）。
3. **seed_data.py 适配**：T-A-09 需修改 seed_data.py 以适配 openGauss（如自增序列、布尔类型默认值等），可直接基于本次建表结果进行。
4. **Git 提交**：本次变更（env.py、新迁移脚本、TODO.md、delete/ 备份）建议尽快提交，提交信息建议：`feat(db): 重写 Alembic 初始迁移支持 openGauss (T-A-08)`。
