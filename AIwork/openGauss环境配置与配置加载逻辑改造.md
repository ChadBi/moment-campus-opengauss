# 任务报告：openGauss 环境配置与配置加载逻辑改造（T-A-06 ~ T-A-07）

## 1. 任务概述

为后端引入 openGauss 环境配置文件，并改造配置加载逻辑以支持 SQLite / openGauss 双环境切换。具体包含：

- T-A-06：创建 `.env.opengauss`（实际使用）与 `.env.opengauss.example`（模板），并更新 `.gitignore`。
- T-A-07：修改 `config.py`、`database.py`、`main.py`，使后端可根据 `APP_ENV` 环境变量加载对应配置，并为 PostgreSQL 连接池参数化、应用启动日志。

## 2. 已完成内容

### T-A-06 创建 openGauss 环境配置文件

1. 新建 `backend/.env.opengauss`：
   - `APP_ENV=opengauss`
   - `DATABASE_URL=postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus`（密码 `@` 已 URL 编码为 `%40`）
   - 连接池参数：`DB_POOL_SIZE=10`、`DB_MAX_OVERFLOW=20`、`DB_POOL_RECYCLE=3600`
   - `SCHOOL_CODE=jiangnan`（江南大学代号）
2. 新建 `backend/.env.opengauss.example`（模板）：
   - 与 `.env.opengauss` 结构相同，密码替换为 `Gaussdb%40PLACEHOLDER`，`SECRET_KEY` 替换为 `change-me-in-production`。
3. 更新 `backend/.gitignore`：
   - 新增 `.env.*`（忽略所有 env 配置）与 `!.env.*.example`（放行模板文件，确保 example 可被 git 跟踪）。

### T-A-07 修改后端配置加载逻辑

1. 修改 `backend/app/config.py`：
   - 新增 `APP_ENV: str = "development"` 字段。
   - 新增 `SCHOOL_CODE: str = "jiangnan"` 字段。
   - 新增 `DB_POOL_SIZE: int = 5`、`DB_MAX_OVERFLOW: int = 10`、`DB_POOL_RECYCLE: int = 3600` 字段。
   - 在类外通过 `os.environ.get("APP_ENV")` 判断环境，选择加载 `.env.opengauss` 或默认 `.env.development`。
   - **关键修复**：env_file 使用基于 `config.py` 模块位置的绝对路径（`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`），避免因运行时 CWD 不同导致 .env 文件加载失败。
   - Config 中新增 `extra = "ignore"`，忽略 .env 文件中未声明字段。
2. 修改 `backend/app/database.py`：
   - 根据 `settings.DATABASE_URL` 判断数据库类型。
   - PostgreSQL（含 `postgresql` 或 `asyncpg`）传入 `pool_size`、`max_overflow`、`pool_recycle` 连接池参数。
   - SQLite 保持原有逻辑（不传 pool 参数，避免 aiosqlite 警告）。
3. 修改 `backend/app/main.py`：
   - 新增 `logger = logging.getLogger(__name__)`。
   - 新增 `@app.on_event("startup")` 启动事件，日志输出 `APP_NAME`、`APP_ENV`、数据库类型（`DATABASE_URL` 的 scheme 部分）。

## 3. 未完成内容

暂无。

## 4. 实现思路

- **环境切换**：通过 `APP_ENV` 环境变量在 Settings 类实例化前决定加载哪个 .env 文件。该变量在类外读取，确保 pydantic-settings 的 `env_file` 配置在类定义时即确定。
- **路径解析**：pydantic-settings 的 `env_file` 默认按 CWD 解析相对路径。由于验证命令从项目根目录执行，而 .env 文件位于 `backend/`，故采用基于 `__file__` 的绝对路径拼接，使配置加载与运行目录解耦，无论从项目根还是 backend 目录启动均可用。
- **连接池适配**：SQLAlchemy 的 `create_async_engine` 对 SQLite（aiosqlite）传入 pool 参数会触发警告，故按 URL scheme 分支构造 engine_kwargs，仅 PostgreSQL 走连接池路径。
- **模板与密钥隔离**：`.env.opengauss` 含真实密码，被 `.env.*` 忽略；`.env.opengauss.example` 通过 `!.env.*.example` 例外放行，便于团队共享配置结构而不泄露凭据。

## 5. 修改文件

- 新增 `backend/.env.opengauss`
- 新增 `backend/.env.opengauss.example`
- 修改 `backend/.gitignore`
- 修改 `backend/app/config.py`
- 修改 `backend/app/database.py`
- 修改 `backend/app/main.py`
- 更新 `TODO.md`（标记 T-A-06、T-A-07 完成，更新阶段状态）

## 6. 影响范围

- **配置层**：`app.config.settings` 现可根据 `APP_ENV` 加载不同 .env，新增 APP_ENV、SCHOOL_CODE、DB_POOL_* 字段。
- **数据库层**：`app.database.engine` 构造方式变更，PostgreSQL 启用连接池参数；SQLite 行为不变。
- **应用入口**：`app.main` 新增启动日志，便于运维确认当前运行环境与数据库类型。
- **构建/部署**：开发者需通过 `APP_ENV=opengauss` 切换到 openGauss；默认仍为 SQLite 开发环境，向后兼容。

## 7. 测试与验证

执行 4 条验证命令（任务要求的 3 条 + 1 条 SQLite database.py 回归），全部通过：

1. **默认 SQLite（config）**：
   ```
   ENV: development DB: sqlite+aiosqlite:///./dev.db POOL: 5 10 3600 SCHOOL: jiangnan
   ```
   说明 `.env.development` 加载成功，默认字段值正确。

2. **openGauss（config）**：
   ```
   ENV: opengauss DB: postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus
   ```
   说明 `APP_ENV=opengauss` 时 `.env.opengauss` 加载成功，DATABASE_URL 正确。

3. **openGauss（database.py engine）**：
   ```
   engine: postgresql+asyncpg://gaussdb:***@localhost:5432/moment_campus
   ```
   说明 database.py 能基于 openGauss 配置构造 engine（密码被 SQLAlchemy 自动掩码）。

4. **SQLite（database.py engine，回归）**：
   ```
   engine: sqlite+aiosqlite:///./dev.db
   ```
   说明 SQLite 环境下 database.py 不报 pool 参数错误，向后兼容。

未运行完整 uvicorn 启动与 API 链路测试（属 T-A-11/T-A-12 范围）。

## 8. 后续建议

- T-A-08：基于 openGauss 重写 Alembic 初始迁移（注意 openGauss 与 PostgreSQL 在 DDL 上的差异，如 `SERIAL`/`IDENTITY`、`BOOLEAN` 等）。
- T-A-09/T-A-10：修改 seed_data.py 并填充演示数据到 openGauss。
- T-A-11：实际启动 uvicorn 验证启动日志输出与 openGauss 连接稳定性。
- 可考虑在 `.env.development` 中也补充 `APP_ENV=development`、`SCHOOL_CODE=jiangnan`、`DB_POOL_*` 字段，保持两套配置结构一致（当前 SQLite 环境使用默认值，不影响功能）。
- 生产部署时务必替换 `.env.opengauss` 中的 SECRET_KEY 与数据库密码。
