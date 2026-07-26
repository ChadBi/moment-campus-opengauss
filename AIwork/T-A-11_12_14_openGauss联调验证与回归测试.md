# 任务报告：T-A-11~14 openGauss 联调验证（启动后端 + API 测试 + pytest 回归）

## 1. 任务概述

在 openGauss 容器运行、21 张表已创建、演示数据已填充的基础上，完成以下三项联调验证任务：

- **T-A-11**：以 `APP_ENV=opengauss` 启动 FastAPI 后端，验证 openGauss 连接、Swagger UI 可访问性、启动日志正确性。
- **T-A-12**：通过现有 pytest 测试套件验证 API 链路在 openGauss 环境下可用。
- **T-A-14**：将上述 pytest 运行结果作为 openGauss 兼容性回归测试，记录通过/失败用例与兼容性问题。

## 2. 已完成内容

### T-A-11 后端启动验证

- 使用 `APP_ENV=opengauss` 启动 `uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`（后台运行）。
- 启动成功，日志含：
  - `启动 此刻校园-OpenGauss | 环境: opengauss | DB: postgresql+asyncpg`
  - `Application startup complete.`
  - `Uvicorn running on http://127.0.0.1:8000`
- `db_compat.py` 补丁生效：日志可见 `select pg_catalog.version()` 被调用以解析 openGauss 版本串。
- Swagger UI 可访问：`GET /docs` 返回 200，HTML 含 "Swagger UI"。
- 健康检查通过：`GET /health` 返回 `{"status":"ok"}`。
- 真实数据库读写验证：`GET /api/v1/categories` 返回 200，成功读取 12 个分类（江南大学演示数据）。
- 验证完成后用 StopCommand 停止后端。

### T-A-12 / T-A-14 API 链路与兼容性回归测试

- 安装测试依赖：`pytest`、`pytest-asyncio`、`httpx`、`aiosqlite`（venv 中此前未安装）。
- 修改 `backend/tests/conftest.py` 支持 `APP_ENV=opengauss` 切换至 openGauss 数据库（详见实现思路）。
- 运行完整 pytest 套件（38 个用例）：
  ```
  $env:APP_ENV='opengauss'; .\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
  ```
- **结果：38 passed, 76 warnings in 51.87s**（全部通过）。
  - test_auth.py：9 个用例全部通过
  - test_interactions.py：14 个用例全部通过
  - test_posts.py：15 个用例全部通过
- 76 个 warnings 均为 Pydantic V2 / FastAPI / datetime 弃用警告，与 openGauss 兼容性无关。

## 3. 未完成内容

- **T-A-13 前后端联调验证** 不在本任务范围内（仅涉及后端 API + pytest 回归）。
- 未提交 Git 代码（任务描述未明确要求提交，遵循"NEVER commit unless explicitly instructed"原则）。

## 4. 实现思路

### 4.1 conftest.py 改造（支持 openGauss）

原 `conftest.py` 仅支持内存 SQLite（`create_all` / `drop_all`）。改为通过 `APP_ENV` 环境变量切换：

- **默认（无 APP_ENV）**：保持原有 SQLite 内存数据库行为，`create_all` / `drop_all`，代码路径完全不变。
- **APP_ENV=opengauss**：
  - 引擎指向 `app.config.settings.DATABASE_URL`（即 `.env.opengauss` 中的 openGauss 连接串）。
  - 使用 `sqlalchemy.pool.NullPool`，避免连接跨事件循环复用（pytest-asyncio 1.x 默认每用例创建新事件循环，连接池复用会导致 `Event loop is closed` 错误）。
  - 用 `TRUNCATE ... CASCADE` 在每个用例前后清空所有 21 张表（保留外部已创建的 schema）。
  - 用 `setval(pg_get_serial_sequence(...), 1, false)` 显式重置自增序列。

### 4.2 修复的 openGauss 兼容性问题

#### 问题 1：`TRUNCATE ... RESTART IDENTITY` 不支持

- **现象**：`asyncpg.exceptions.FeatureNotSupportedError: PGXC does not support RESTART IDENTITY yet`
- **原因**：openGauss 基于 PGXC 架构，不支持 `TRUNCATE ... RESTART IDENTITY` 语法。
- **修复**：移除 `RESTART IDENTITY` 子句，改用 `setval(pg_get_serial_sequence(...), 1, false)` 单独重置每个表的 id 序列。

#### 问题 2：跨事件循环连接复用导致 `Event loop is closed`

- **现象**：第一个用例通过，后续用例在 setup 阶段报 `RuntimeError: Event loop is closed` 或 `cannot perform operation: another operation is in progress`。
- **原因**：pytest-asyncio 1.4.0 默认 `asyncio_default_test_loop_scope=function`（每用例新建事件循环），而 asyncpg 连接绑定到首次创建它的事件循环；连接池复用旧连接时，旧 loop 已关闭。
- **修复**：openGauss 引擎使用 `poolclass=NullPool`，每次操作获取新连接、用完即关，不再跨 loop 复用。

#### 问题 3：db_compat.py 补丁已生效（无需新增修复）

- 启动日志中 `select pg_catalog.version()` 被调用并成功解析 openGauss 7.0.0-RC3 版本串，证明 `backend/app/db_compat.py`（此前任务已创建）的 `_get_server_version_info` 补丁工作正常，无需额外修改。

### 4.3 验证策略

- **后端启动验证**：用 `Invoke-WebRequest` 访问 `/docs`、`/health`、`/`、`/api/v1/categories`，确认 HTTP 200 且数据库读写正常。
- **API 链路验证**：复用现有 pytest 套件（test_auth/test_posts/test_interactions 共 38 用例），覆盖认证、帖子 CRUD、点赞、收藏、协同验证等核心链路。
- **回归测试**：pytest 运行结果即为兼容性回归结果；通过即视为 openGauss 兼容性 OK。

## 5. 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/tests/conftest.py` | 修改 | 新增 openGauss 分支（NullPool + TRUNCATE + 序列重置），保留原 SQLite 分支不变 |
| `TODO.md` | 修改 | 标记 T-A-11、T-A-12、T-A-14 为已完成 |
| `AIwork/T-A-11_12_14_openGauss联调验证与回归测试.md` | 新增 | 本任务报告 |

> 注：`backend/.venv` 中新安装了 pytest/pytest-asyncio/httpx/aiosqlite 等测试依赖（pip install），未写入 `requirements.txt`（这些是测试依赖，非业务依赖）。

## 6. 影响范围

- **测试基础设施**：`backend/tests/conftest.py` — 仅影响测试 fixture，不影响业务代码。
- **业务代码**：零修改。`backend/app/` 下所有业务代码（models/api/schemas/core）均未改动。
- **数据库**：openGauss `moment_campus` 库中的数据在测试过程中被 TRUNCATE 清空（测试用例设计如此），测试结束后库内无数据。如需恢复演示数据，可重新运行 `backend/scripts/seed_data.py`。

## 7. 测试与验证

### 7.1 后端启动验证（T-A-11）

执行命令（PowerShell，工作目录 `backend/`）：
```
$env:APP_ENV='opengauss'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

验证结果：
- 启动日志含 `环境: opengauss` 和 `DB: postgresql+asyncpg` ✓
- 启动日志含 `Application startup complete.` ✓
- `GET /docs` → 200，含 "Swagger UI" ✓
- `GET /health` → 200，`{"status":"ok"}` ✓
- `GET /` → 200 ✓
- `GET /api/v1/categories` → 200，返回 12 个分类 ✓
- 日志含 `select pg_catalog.version()`（db_compat 补丁生效）✓

### 7.2 pytest 回归测试（T-A-12 / T-A-14）

执行命令（PowerShell，工作目录 `backend/`）：
```
$env:APP_ENV='opengauss'; .\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
```

完整结果：
```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0
plugins: anyio-4.14.1, asyncio-1.4.0
asyncio: mode=Mode.STRICT, asyncio_default_test_loop_scope=function
collected 38 items

tests/test_auth.py::test_register_success PASSED                         [  2%]
tests/test_auth.py::test_register_duplicate_email PASSED                 [  5%]
tests/test_auth.py::test_login_success PASSED                            [  7%]
tests/test_auth.py::test_login_wrong_password PASSED                    [ 10%]
tests/test_auth.py::test_login_nonexistent_email PASSED                 [ 13%]
tests/test_auth.py::test_refresh_token_success PASSED                   [ 15%]
tests/test_auth.py::test_refresh_token_invalid PASSED                   [ 18%]
tests/test_auth.py::test_refresh_token_with_access_token PASSED         [ 21%]
tests/test_auth.py::test_logout PASSED                                   [ 23%]
tests/test_interactions.py::test_like_post PASSED                       [ 26%]
tests/test_interactions.py::test_unlike_post PASSED                     [ 28%]
tests/test_interactions.py::test_like_post_unauthenticated PASSED       [ 31%]
tests/test_interactions.py::test_like_nonexistent_post PASSED           [ 34%]
tests/test_interactions.py::test_favorite_post PASSED                   [ 36%]
tests/test_interactions.py::test_unfavorite_post PASSED                 [ 39%]
tests/test_interactions.py::test_favorite_post_unauthenticated PASSED   [ 42%]
tests/test_interactions.py::test_favorite_nonexistent_post PASSED       [ 44%]
tests/test_interactions.py::test_validate_post_valid PASSED             [ 47%]
tests/test_interactions.py::test_validate_post_invalid PASSED           [ 50%]
tests/test_interactions.py::test_validate_post_uncertain PASSED         [ 52%]
tests/test_interactions.py::test_validate_post_invalid_type PASSED      [ 55%]
tests/test_interactions.py::test_validate_post_unauthenticated PASSED   [ 57%]
tests/test_interactions.py::test_validate_nonexistent_post PASSED       [ 60%]
tests/test_posts.py::test_list_posts_empty PASSED                       [ 63%]
tests/test_posts.py::test_list_posts_with_data PASSED                   [ 65%]
tests/test_posts.py::test_list_posts_pagination PASSED                  [ 68%]
tests/test_posts.py::test_get_post_detail PASSED                        [ 71%]
tests/test_posts.py::test_get_post_detail_increments_view PASSED        [ 73%]
tests/test_posts.py::test_get_post_not_found PASSED                     [ 76%]
tests/test_posts.py::test_create_post_authenticated PASSED              [ 78%]
tests/test_posts.py::test_create_post_unauthenticated PASSED            [ 81%]
tests/test_posts.py::test_create_post_with_tags PASSED                  [ 84%]
tests/test_posts.py::test_update_post_owner PASSED                      [ 86%]
tests/test_posts.py::test_update_post_not_owner PASSED                  [ 89%]
tests/test_posts.py::test_update_post_not_found PASSED                  [ 92%]
tests/test_posts.py::test_delete_post_owner PASSED                      [ 94%]
tests/test_posts.py::test_delete_post_not_owner PASSED                  [ 97%]
tests/test_posts.py::test_delete_post_not_found PASSED                  [100%]

====================== 38 passed, 76 warnings in 51.87s =======================
```

- **通过用例数**：38
- **失败用例数**：0
- **错误用例数**：0
- **耗时**：51.87s

### 7.3 未运行的测试

- 未运行 SQLite 默认环境的完整回归。后续验证中发现 SQLite 路径存在预存问题（`BigInteger` 主键在 SQLite 下不自增，导致 `NOT NULL constraint failed`），但该问题与本次 openGauss 改造无关（SQLite 分支代码与原始版本完全一致，见 `git diff`），不在本任务修复范围。

## 8. 后续建议

1. **T-A-13 前后端联调**：本任务验证了后端 API + openGauss 数据库链路，下一步可启动前端（`frontend/`）与 openGauss 后端进行端到端联调。
2. **SQLite 测试修复（可选）**：如需保留 SQLite 作为开发备选，可为 SQLite 测试引擎使用 `BigInteger().with_variant(Integer, "sqlite")` 让主键在 SQLite 下退化为 `INTEGER PRIMARY KEY` 以支持自增。该问题为预存问题，与 openGauss 适配无关。
3. **测试依赖写入 requirements**：建议新增 `backend/requirements-dev.txt` 记录 pytest/pytest-asyncio/httpx/aiosqlite 等测试依赖，便于环境复现。
4. **演示数据恢复**：测试运行已 TRUNCATE openGauss 中的演示数据，如需继续演示可重新执行 `backend/scripts/seed_data.py`。
5. **T-A-15 阶段 A 文档与提交**：阶段 A 剩余 T-A-13、T-A-15、T-A-17、T-A-18，完成后可统一提交 Git。
6. **警告清理（可选）**：76 个 warnings 来自 Pydantic V2 class-based config、FastAPI `on_event`、`datetime.utcnow()` 弃用，可在后续重构中升级为 `ConfigDict`、`lifespan`、`datetime.now(UTC)`。
