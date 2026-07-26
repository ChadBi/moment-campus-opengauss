# openGauss 适配分析文档

> 文档版本：1.0
> 编写日期：2026-06-29
> 适用范围：将"此刻校园"Base 项目（SQLite）切换为 openGauss 数据库
> 重要说明：本文档所有结论均标注【已确认】【推测】【待验证】三种状态。未标注【已确认】的内容不得作为最终实施依据。

---

## 1. Docker Compose 中的实际数据库配置【已确认】

### 1.1 配置文件

[docker-compose.yml](docker-compose.yml)（仓库根目录）

### 1.2 实际配置内容

```yaml
services:
  opengauss:
    image: opengauss:7.0.0-RC3
    container_name: opengauss
    privileged: true
    restart: unless-stopped
    pull_policy: never

    environment:
      GS_PASSWORD: "Gaussdb@123"          # 初始密码
      GS_DB: "moment_campus"              # 自动创建的数据库
      GS_USERNAME: "gaussdb"              # 数据库用户名
      GS_USER_PASSWORD: "Gaussdb@123"     # 用户密码
      GS_PORT: "5432"                     # 监听端口

    ports:
      - "5432:5432"                       # 主机 5432 → 容器 5432

    volumes:
      - opengauss-data:/var/lib/opengauss # 数据持久化

volumes:
  opengauss-data:
```

### 1.3 关键配置值汇总

| 项 | 值 |
| -- | -- |
| 镜像 | `opengauss:7.0.0-RC3`（openGauss 7.0.0-RC3 轻量版，依据官方 release_notes） |
| 容器名 | `opengauss` |
| 数据库类型 | openGauss（轻量版） |
| 数据库名 | `moment_campus` |
| 用户名 | `gaussdb` |
| 密码 | `Gaussdb@123` |
| 端口（容器内） | 5432 |
| 端口（主机映射） | 5432 |
| 数据卷 | `opengauss-data`（Docker managed volume） |
| 数据卷容器路径 | `/var/lib/opengauss` |
| 启动策略 | `unless-stopped`（除非显式停止，否则自动重启） |
| 镜像拉取策略 | `never`（不主动拉取，使用本地镜像，**意味着必须先本地导入 opengauss:7.0.0-RC3 镜像**） |
| 特权模式 | `privileged: true`（容器以特权运行，openGauss 官方镜像建议） |

### 1.4 配置文件与文档冲突记录

| 冲突点 | docker-compose 实际值 | README/Spec 声称值 | 处理建议 |
| ------ | --------------------- | ------------------ | -------- |
| 数据库类型 | openGauss 7.0.0-RC3 | README 宣称 PostgreSQL（生产） | **以 docker-compose 为准**，README 需更新 |
| 数据库连接 | `gaussdb:Gaussdb@123@localhost:5432/moment_campus` | `.env.development` 仍为 `sqlite+aiosqlite:///./dev.db` | **以 docker-compose 为目标**，需新建 `.env.opengauss` 或修改 `.env.development` |
| 镜像拉取 | `pull_policy: never` | 无说明 | 需要先在本地导入 openGauss 镜像，否则 `docker compose up` 会失败 |

### 1.5 启动前置条件【待验证】

由于 `pull_policy: never`，启动前必须确保本地已存在 `opengauss:7.0.0-RC3` 镜像。验证命令：

```bash
docker images | findstr opengauss
```

若不存在，需从 openGauss 官方下载离线镜像包并 `docker load` 导入。具体导入方式 **【待确认】**——需查阅 openGauss 官方镜像发布页（https://opengauss.org/zh/download/）确认轻量版镜像获取方式。

---

## 2. 项目当前数据库配置【已确认】

### 2.1 配置位置

| 文件 | 行号 | 内容 |
| ---- | ---- | ---- |
| [backend/app/config.py](backend/app/config.py) | 12 | `DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"` |
| [backend/.env.development](backend/.env.development) | 7 | `DATABASE_URL=sqlite+aiosqlite:///./dev.db` |
| [backend/.env.example](backend/.env.example) | 7 | `DATABASE_URL=sqlite+aiosqlite:///./dev.db` |
| [backend/alembic.ini](backend/alembic.ini) | 30 | `sqlalchemy.url = sqlite+aiosqlite:///./dev.db`（实际被 `env.py` 覆盖） |

### 2.2 连接信息的读取方式【已确认】

- `backend/app/config.py` 的 `Settings` 类继承 `pydantic_settings.BaseSettings`
- `class Config: env_file = ".env"` —— 从 `.env` 文件读取
- `backend/alembic/env.py` 第 24 行 `config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)` —— Alembic 从 Settings 覆盖 `alembic.ini` 中的 URL
- 实际生效的 URL 来自 `settings.DATABASE_URL`，**而非 `alembic.ini`**

### 2.3 数据库连接代码【已确认】

[backend/app/database.py](backend/app/database.py)：

```python
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

- 使用 SQLAlchemy 2.0 async API
- `expire_on_commit=False` 是 async 常见配置，避免 commit 后访问属性触发同步 IO
- 切换数据库**只需修改 `DATABASE_URL`**，引擎代码无需改动

---

## 3. 数据库连接改造点

### 3.1 DATABASE_URL 切换【已确认】

| 项 | 当前 | 目标（推荐） |
| -- | ---- | ------------ |
| URL 格式 | `sqlite+aiosqlite:///./dev.db` | `postgresql+asyncpg://gaussdb:Gaussdb@123@localhost:5432/moment_campus` |
| 驱动 dialect | `sqlite+aiosqlite` | `postgresql+asyncpg`（**待验证**，详见第 4 节） |

**注意**：openGauss 兼容 PostgreSQL 协议，SQLAlchemy 通过 PostgreSQL dialect 即可访问。但需在连接参数中处理 openGauss 特定行为（如 `prepareThreshold` 等），**【待验证】asyncpg 是否需要特殊参数**。

### 3.2 密码中的 `@` 转义【已确认 - 风险点】

目标密码为 `Gaussdb@123`，其中包含 `@` 字符。在标准 URL 中 `@` 是用户名/密码与主机的分隔符，**直接拼接会导致 URL 解析错误**。

解决方案（任选其一）：

1. **URL 编码**（推荐）：将 `@` 编码为 `%40`，最终 URL 为：
   ```
   postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus
   ```

2. **使用 SQLAlchemy URL 对象**：
   ```python
   from sqlalchemy.engine import URL
   db_url = URL.create(
       drivername="postgresql+asyncpg",
       username="gaussdb",
       password="Gaussdb@123",  # 无需转义
       host="localhost",
       port=5432,
       database="moment_campus",
   )
   ```

3. **修改密码**：将密码改为不含特殊字符的字符串（不推荐，需要重建数据库）

### 3.3 推荐的配置组织方式【推测 - 建议方案】

为同时支持本地 SQLite（保留为开发备选）与 openGauss（课设主用），建议拆分环境变量文件：

```
backend/
├── .env.sqlite           # SQLite 配置（保留为开发备选）
├── .env.opengauss        # openGauss 配置（课设主用）
├── .env.development      # 当前默认（可软链接到上述之一）
└── .env.example          # 示例
```

`config.py` 可增加显式 DBMS 标识字段，便于条件分支：

```python
class Settings(BaseSettings):
    DBMS: str = "sqlite"  # sqlite | opengauss
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"
    # openGauss 专用字段（便于排查）
    OPENGAUSS_HOST: str = "localhost"
    OPENGAUSS_PORT: int = 5432
    OPENGAUSS_USER: str = "gaussdb"
    OPENGAUSS_PASSWORD: str = ""
    OPENGAUSS_DATABASE: str = "moment_campus"
```

---

## 4. 驱动和依赖改造点

### 4.1 当前驱动【已确认】

- `aiosqlite>=0.20.0`（在 [requirements.txt](backend/requirements.txt) 第 10 行）
- 仅支持 SQLite 异步访问

### 4.2 候选驱动对比【部分待验证】

| 驱动 | 同步/异步 | openGauss 兼容性 | SQLAlchemy 2.0 async 支持 | 备注 |
| ---- | --------- | ---------------- | ------------------------- | ---- |
| `asyncpg` | 异步 | **【待验证】** | ✅ `postgresql+asyncpg://` | 性能最佳，纯异步；社区报告称与 openGauss 兼容，但需验证 prepared statement 行为 |
| `psycopg2`（或 psycopg2-binary） | 同步 | **【推测】兼容 | ✅ `postgresql+psycopg2://` | 老牌驱动，稳定性高；与 async SQLAlchemy 不兼容，需改为同步引擎 |
| `psycopg`（v3，即 psycopg3） | 异步（asyncio 模式） | **【待验证】** | ✅ `postgresql+psycopg://` | 新一代驱动，支持 async；与 openGauss 兼容性需验证 |
| `py-opengauss`（openGauss 官方 Python 驱动） | 同步 | ✅ 原生 | ❌ 非 SQLAlchemy dialect | 不直接兼容 SQLAlchemy，需要自写适配层 |

### 4.3 推荐方案【推测，待实测验证】

**首选：`asyncpg`**

理由：
1. 与现有 `AsyncSession`、`async_sessionmaker`、`create_async_engine` 代码完全兼容
2. openGauss 兼容 PostgreSQL 协议，asyncpg 通过 PostgreSQL 协议通信
3. 性能优于 psycopg2
4. 无需改动 `database.py` 中任何代码

**备选：`psycopg2-binary` + 同步引擎**

若 asyncpg 不兼容 openGauss，需将 `database.py` 改造为同步引擎，并将所有 `async def` 改为 `def`、`await db.execute()` 改为 `db.execute()`，影响面大（**应避免**）。

### 4.4 requirements.txt 改造【已确认 - 待执行】

需新增：

```
asyncpg>=0.29.0
# 备选：psycopg2-binary>=2.9.9
```

建议保留 `aiosqlite` 以支持本地快速开发与测试（测试用例使用内存 SQLite 仍方便）。

### 4.5 asyncpg 与 openGauss 已知潜在问题【待验证】

| 问题 | 说明 | 验证方式 |
| ---- | ---- | -------- |
| prepared statement 缓存 | asyncpg 默认使用 prepared statement，openGauss 在某些模式下可能与 PostgreSQL 行为不一致 | 连接后执行简单查询验证 |
| `prepareThreshold` 参数 | asyncpg 0.29+ 暴露此参数，openGauss 可能需设为 0 | 查阅 openGauss + asyncpg 兼容性资料 |
| SSL/TLS | openGauss 默认开启 SSL，asyncpg 需配置 `ssl` 参数 | 连接时观察是否报 SSL 错误 |
| 类型映射 | openGauss 部分类型（如 `LARGEINT`、`BLOB`）在 PostgreSQL 中无对应 | 本项目未使用这些类型，预期无影响 |
| schema 搜索路径 | openGauss 默认 schema 与 PostgreSQL 不同 | 显式指定 `search_path` |

---

## 5. ORM 兼容性分析

### 5.1 SQLAlchemy 2.0 与 openGauss【推测 - 兼容性高】

- SQLAlchemy 2.0 通过 dialect+driver 形式支持 PostgreSQL
- openGauss 兼容 PostgreSQL 协议，使用 `postgresql+asyncpg://` 即可让 SQLAlchemy 视其为 PostgreSQL
- 现有代码使用的所有 SQLAlchemy API 均为标准 API，不依赖 SQLite 专有特性

### 5.2 现有代码使用的 SQLAlchemy 特性扫描【已确认】

| 特性 | 使用位置 | openGauss 兼容性 |
| ---- | -------- | ---------------- |
| `create_async_engine` | database.py | ✅ |
| `async_sessionmaker` | database.py | ✅ |
| `AsyncSession` | database.py、dependencies.py | ✅ |
| `DeclarativeBase` | database.py | ✅ |
| `Mapped` + `mapped_column` | 所有 models | ✅ |
| `relationship(back_populates=...)` | 所有 models | ✅ |
| `ForeignKey` | 所有外键字段 | ✅ |
| `Index`（含复合索引） | 所有 models 的 `__table_args__` | ✅ |
| `select` + `where` + `order_by` + `offset` + `limit` | api/*.py | ✅ |
| `func.count()` | posts.py、search.py | ✅ |
| `or_` | search.py | ✅ |
| `ilike` | search.py | ✅（openGauss 原生支持 ILIKE） |
| `joinedload` / `selectinload` | posts.py | ✅ |
| `subquery()` | posts.py、search.py | ✅ |
| `IntegrityError` 异常捕获 | interactions.py | ✅ |
| `db.refresh(post, attribute_names=[...])` | posts.py | ✅ |

### 5.3 未使用但目标项目可能引入的 SQLAlchemy 特性【推测】

| 特性 | 用途 | 兼容性 |
| ---- | ---- | ------ |
| `text()` 原生 SQL | 复杂查询、视图查询 | ✅ |
| `JSON` / `JSONB` 类型 | 存储结构化数据（如版本 diff） | ✅（openGauss 支持 JSON） |
| `Enum` 类型 | 状态机字段 | ✅（建议用 String + Python 枚举，避免 DB 端 ENUM 修改困难） |
| `Index(..., postgresql_using='gist')` | 地理空间索引 | **【待验证】** openGauss 是否支持 GIST 索引 |
| 事件监听 `@event.listens_for` | 自动可信度计算 | ✅ |
| `with_for_update()` | 乐观锁/悲观锁 | ✅ |

---

## 6. SQL 方言兼容性分析

### 6.1 代码中实际使用的 SQL 模式【已确认 - 全部兼容】

通过 `Grep` 扫描 `backend/` 下所有 `.py` 文件，**未发现任何**：
- 原生 SQL 字符串（`text()`、`raw()`）
- 数据库专有函数（`NOW()`、`CURRENT_TIMESTAMP`、`JSONB_AGG`、`ARRAY_AGG`、`TO_CHAR`、`TO_TIMESTAMP`）
- 存储过程调用
- 视图查询
- 自定义类型

所有数据访问均通过 SQLAlchemy ORM 完成。这是适配 openGauss 的**最大有利因素**。

### 6.2 关键 SQL 行为差异分析【部分待验证】

| SQL 行为 | SQLite | openGauss | 影响 |
| -------- | ------ | --------- | ---- |
| 主键自增 | `INTEGER PRIMARY KEY` 隐式自增 | `SERIAL` 或 `GENERATED ALWAYS AS IDENTITY` | SQLAlchemy 自动处理 dialect 差异 |
| `ILIKE` 大小写不敏感匹配 | SQLite 无 ILIKE，SQLAlchemy 通过 `lower()` 模拟 | openGauss 原生支持 ILIKE | **【已确认兼容】** search.py 中的 `ilike` 调用可直接工作 |
| Boolean 字面量 | 0/1 | true/false | SQLAlchemy 自动转换 |
| 事务隔离 | 隐式 SERIALIZABLE | 默认 READ COMMITTED | 业务代码无显式隔离级别，预期无影响 |
| 外键约束 | 默认不强制（需 `PRAGMA foreign_keys=ON`） | 默认强制 | **【风险】** 之前 SQLite 不强制外键，可能导致数据不一致；切到 openGauss 后外键约束会生效，需排查历史数据 |
| 空字符串 vs NULL | SQLite 区分 | openGauss 区分 | 一致 |
| `LIMIT offset, count` | SQLite 支持 | openGauss 仅支持 `LIMIT count OFFSET offset` | SQLAlchemy 使用 `offset().limit()` 生成正确语法 |
| 字符串拼接 `||` | 支持 | 支持 | 一致 |
| `AUTOINCREMENT` 关键字 | SQLite 专有 | 不支持 | SQLAlchemy 不会生成此关键字 |
| 自动提交 DDL | 隐式 | 需显式事务 | Alembic 自动处理 |

### 6.3 时间函数兼容性【已确认 - 无问题】

- 当前代码**未使用任何 SQL 端时间函数**
- 所有时间默认值在 Python 端生成：`default=datetime.now`、`onupdate=datetime.now`
- `datetime.utcnow()` 仅在 `core/security.py` 中用于 JWT 过期计算（不涉及数据库）
- 切换 openGauss 后**无需修改任何时间相关代码**

### 6.4 字符串函数兼容性【已确认 - 无问题】

- 代码中未使用 SQL 字符串函数（如 `SUBSTRING`、`LENGTH`、`LOWER`、`UPPER`）
- 字符串操作均在 Python 端完成
- 切换 openGauss 后**无需修改任何字符串相关代码**

### 6.5 分页兼容性【已确认 - 无问题】

[backend/app/api/posts.py](backend/app/api/posts.py) 第 69-70 行：

```python
offset = (page - 1) * page_size
query = query.offset(offset).limit(page_size)
```

SQLAlchemy 会根据 dialect 生成正确语法，openGauss 兼容。

---

## 7. 表结构兼容性分析

### 7.1 主键 / 外键类型不一致【已确认 - 严重风险】

**问题**：

- 所有模型的主键 `id` 类型为 `Integer`（INT4）
- 所有模型的外键字段（`user_id`、`school_id`、`post_id` 等）类型为 `BigInteger`（INT8）
- 历史原因：[`AIwork/SQLite主键类型修改.md`](AIwork/SQLite主键类型修改.md) 记录了主键从 BigInteger 改为 Integer 的过程，但外键未同步修改

**在 SQLite 中的表现**：SQLite 忽略整型尺寸（INT4 和 INT8 都映射为 `INTEGER`），无问题。

**在 openGauss 中的表现**：openGauss 严格区分 `INTEGER`（4 字节）与 `BIGINT`（8 字节），**外键列类型必须与被引用列类型完全一致**，否则外键约束创建失败。

**改造方案**：将所有主键改为 `BigInteger`，与外键统一。

**影响范围**：21 个模型文件，每个文件的主键字段需要从：

```python
id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
```

改为：

```python
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
```

**SQLite 兼容性**：SQLite 仍然忽略 BigInteger 的尺寸，不会破坏本地开发环境。

### 7.2 字段类型兼容性逐项检查【已确认 - 全部兼容】

| SQLAlchemy 类型 | openGauss 实际类型 | 兼容性 | 使用位置 |
| --------------- | ------------------ | ------ | -------- |
| `Integer` | `INTEGER` | ✅ | 计数字段（view_count 等） |
| `BigInteger` | `BIGINT` | ✅ | 外键、主键（改造后） |
| `String(n)` | `VARCHAR(n)` | ✅ | 标题、邮箱、状态等 |
| `Text` | `TEXT` | ✅ | 长文本 |
| `Boolean` | `BOOLEAN` | ✅ | is_deleted、is_active 等 |
| `DateTime` | `TIMESTAMP WITHOUT TIME ZONE` | ✅ | created_at、updated_at 等 |
| `Numeric(10, 7)` | `NUMERIC(10, 7)` | ✅ | Location.latitude / longitude |
| `Float`（隐式，School.center_lat） | `DOUBLE PRECISION` | ✅ | 学校中心坐标 |

### 7.3 索引兼容性【已确认 - 全部兼容】

扫描所有模型的 `__table_args__`，使用的索引类型：

- 单列索引：`Index("idx_xxx", "column")` ✅
- 复合索引：`Index("idx_xxx", "col1", "col2")` ✅
- 唯一索引：`Index("idx_xxx", "col", unique=True)` ✅
- 字段级 `index=True`、`unique=True` ✅

所有索引语法 openGauss 完全兼容，无需修改。

### 7.4 约束兼容性【已确认 - 全部兼容】

- `unique=True`（字段级） ✅
- `nullable=False` ✅
- `ForeignKey("table.column")` ✅
- 复合唯一约束（通过 `UniqueConstraint`）—— **未使用**，但 openGauss 兼容

### 7.5 默认值兼容性【已确认 - 全部兼容】

- 字符串默认值：`default="user"`、`default="pending"` ✅
- 整数默认值：`default=0`、`default=30` ✅
- 布尔默认值：`default=True`、`default=False` ✅
- Python 函数默认值：`default=datetime.now` ✅（Python 端执行，不涉及 SQL）

---

## 8. 数据迁移方案

### 8.1 是否需要迁移现有 SQLite 数据【推测 - 不需要】

理由：
1. 当前 SQLite 中只有演示数据（`seed_data.py` 填充）
2. 演示数据可在 openGauss 中通过修改后的 `seed_data.py` 重新生成
3. 没有真实业务数据需要保留

**结论**：跳过数据迁移，直接在 openGauss 中重建演示数据。

### 8.2 若需要迁移的备选方案【推测】

若未来确需迁移：

| 方案 | 工具 | 步骤 |
| ---- | ---- | ---- |
| 简单导出导入 | sqlite3 `.dump` + psql `\i` | 导出 SQL → 修改语法（如 `AUTOINCREMENT`）→ 在 openGauss 执行 |
| 中间格式 | CSV | 每张表导出 CSV → openGauss `COPY` 导入 |
| ETL 工具 | openGauss DataKit 或自写 Python 脚本 | 字段映射 + 类型转换 + 数据校验 |

### 8.3 演示数据脚本改造【已确认 - 需小改】

[backend/scripts/seed_data.py](backend/scripts/seed_data.py) 当前：

```python
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

**改造建议**：

1. 保留 `Base.metadata.create_all` 作为快速建表方式（开发/测试场景）
2. 正式环境使用 `alembic upgrade head`（见第 9 节）
3. `seed_data.py` 不需修改数据填充逻辑，只需确保连接 URL 指向 openGauss

---

## 9. 初始化方案

### 9.1 当前问题【已确认】

[backend/alembic/versions/82978de89068_initial_migration_create_all_21_tables.py](backend/alembic/versions/82978de89068_initial_migration_create_all_21_tables.py) 是空迁移：

```python
def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
```

**实际不创建任何表**。建表依赖 `seed_data.py` 中的 `Base.metadata.create_all`。

### 9.2 改造目标

让 `alembic upgrade head` 能够在 openGauss 中正确创建全部 21 张表（含索引、约束、外键）。

### 9.3 改造方案

#### 方案 A：重写初始迁移（推荐）

1. 删除空的 `82978de89068_initial_migration_create_all_21_tables.py`
2. 在 openGauss 已启动、DATABASE_URL 指向 openGauss 的环境下，执行：
   ```bash
   cd backend
   alembic revision --autogenerate -m "initial migration for opengauss"
   ```
3. 检查生成的迁移脚本，确保所有 21 张表的 `op.create_table(...)` 调用完整
4. 验证外键、索引、约束均正确生成
5. 执行 `alembic upgrade head` 验证

#### 方案 B：保留 `Base.metadata.create_all`

仅作为开发场景备选，不作为正式初始化方式。

### 9.4 openGauss 特有的初始化注意事项【待验证】

| 项 | 说明 | 验证方式 |
| -- | ---- | -------- |
| Schema | openGauss 默认 schema 为 `public` 还是 `$user`？ | 连接后查询 `current_schema()` |
| 数据库大小写敏感 | openGauss 默认大小写敏感，与 PostgreSQL 一致 | 创建测试表验证 |
| 字符集 | 默认 UTF-8 | 查询 `server_encoding` |
| 时区 | 默认时区 | 查询 `current_setting('timezone')` |
| `search_path` | 默认 `$user, public` | 查询 `current_setting('search_path')` |

---

## 10. 验证方案

### 10.1 连接验证

```bash
# 1. 启动 openGauss
docker compose up -d opengauss

# 2. 验证容器运行
docker ps | findstr opengauss

# 3. 验证端口监听
docker exec opengauss sh -c "ss -tlnp | grep 5432"

# 4. 用 gsql 验证连接（容器内）
docker exec -it opengauss gsql -d moment_campus -U gaussdb -W Gaussdb@123 -c "SELECT version();"
```

### 10.2 应用层连接验证

```bash
# 1. 安装 asyncpg
cd backend
.venv\Scripts\activate
pip install asyncpg

# 2. 修改 .env.development
# DATABASE_URL=postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus

# 3. 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 验证健康检查
curl http://localhost:8000/health
# 期望返回 {"status":"ok"}

# 5. 验证 Swagger
# 浏览器打开 http://localhost:8000/docs
```

### 10.3 建表验证

```bash
# 1. 执行迁移
cd backend
alembic upgrade head

# 2. 验证表创建
docker exec opengauss gsql -d moment_campus -U gaussdb -W Gaussdb@123 -c "\dt"

# 期望输出 21 张表
```

### 10.4 演示数据验证

```bash
cd backend
python scripts/seed_data.py
# 期望看到 "✅ 所有演示数据填充完成！"

# 验证数据
docker exec opengauss gsql -d moment_campus -U gaussdb -W Gaussdb@123 -c "SELECT COUNT(*) FROM users;"
# 期望 11
docker exec opengauss gsql -d moment_campus -U gaussdb -W Gaussdb@123 -c "SELECT COUNT(*) FROM posts;"
# 期望 30
```

### 10.5 API 链路验证

```bash
# 1. 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@momentcampus.com","password":"pass123"}'
# 期望返回 access_token

# 2. 获取信息列表
curl http://localhost:8000/api/v1/posts
# 期望返回 30 条信息

# 3. 获取分类列表
curl http://localhost:8000/api/v1/categories
# 期望返回 12 个分类
```

### 10.6 测试套件验证

**注意**：测试目前使用内存 SQLite（`conftest.py` 第 15 行 `TEST_DATABASE_URL = "sqlite+aiosqlite://"`），切换 openGauss 后**测试套件保持 SQLite** 即可，无需改造。理由：

1. 测试关注业务逻辑正确性，不关注底层数据库
2. 内存 SQLite 测试速度快
3. 若需测试 openGauss 兼容性，单独编写集成测试

---

## 11. 风险点

### 11.1 高风险

| # | 风险 | 影响 | 缓解措施 |
| -- | ---- | ---- | -------- |
| H1 | 主键/外键类型不一致 | openGauss 中外键约束创建失败，整个迁移失败 | **必须修复**：21 个模型主键改为 BigInteger |
| H2 | asyncpg 与 openGauss 兼容性未验证 | 应用无法连接数据库 | **必须验证**：先做最小连接测试，再投入业务改造 |
| H3 | 密码中 `@` 字符未转义 | URL 解析失败 | 使用 `%40` 转义或 URL.create() |
| H4 | Alembic 初始迁移为空 | `alembic upgrade head` 不建表 | 重写初始迁移 |

### 11.2 中风险

| # | 风险 | 影响 | 缓解措施 |
| -- | ---- | ---- | -------- |
| M1 | openGauss 镜像未本地导入 | `docker compose up` 失败（`pull_policy: never`） | 提前导入镜像 |
| M2 | 外键约束在 openGauss 中严格强制 | 历史不一致数据导致写入失败 | 切换前清理或重建数据 |
| M3 | asyncpg prepared statement 行为差异 | 部分查询报错 | 设置 `prepareThreshold=0` 或改用 psycopg |
| M4 | openGauss SSL 配置 | 连接失败 | 在 URL 中添加 `?sslmode=disable` 或配置证书 |
| M5 | 时区差异 | 时间字段显示不一致 | 统一应用层时区为 `Asia/Shanghai` |

### 11.3 低风险

| # | 风险 | 影响 | 缓解措施 |
| -- | ---- | ---- | -------- |
| L1 | `ilike` 性能 | 大表搜索慢 | 后续添加全文索引 |
| L2 | Boolean 字面量差异 | SQLAlchemy 自动转换 | 无需处理 |
| L3 | 事务隔离级别变化 | 业务行为微妙变化 | 显式声明隔离级别 |

---

## 12. 待确认事项

| # | 事项 | 当前状态 | 确认方式 |
| -- | ---- | -------- | -------- |
| C1 | asyncpg 是否能稳定连接 openGauss 7.0.0-RC3 轻量版 | 待验证 | 编写最小连接测试脚本 |
| C2 | asyncpg 是否需要特殊连接参数（`prepareThreshold`、`ssl`） | 待验证 | 连接测试时观察报错 |
| C3 | openGauss 轻量版是否支持所有 PostgreSQL dialect 特性 | 推测兼容 | 查阅官方文档 + 实测 |
| C4 | openGauss 镜像是否已本地导入 | 待验证 | 执行 `docker images \| findstr opengauss` |
| C5 | openGauss 默认 schema 与 search_path | 待验证 | `current_schema()`、`current_setting('search_path')` |
| C6 | openGauss 时区配置 | 待验证 | `current_setting('timezone')` |
| C7 | 课程设计是否要求使用 openGauss 特有功能（触发器/存储过程/视图） | 待确认 | 与指导老师沟通 |
| C8 | 是否需要保留 SQLite 作为开发备选 | 推测保留 | 通过环境变量切换 |
| C9 | asyncpg 在 openGauss 上的 JSON/JSONB 类型支持 | 待验证（目标项目可能用到） | 写测试用例验证 |
| C10 | openGauss 单机模式下并发写入性能 | 待验证 | 压测 |

---

## 13. 后续实施步骤

### 13.1 阶段 0：准备与验证（不修改业务代码）

1. **导入 openGauss 镜像**（若未导入）
2. **启动 openGauss 容器**：`docker compose up -d opengauss`
3. **验证容器与端口**：`docker ps`、`docker exec opengauss gsql -d moment_campus -U gaussdb -W Gaussdb@123 -c "SELECT version();"`
4. **编写最小连接测试脚本**（Python，使用 asyncpg 直连，绕过 SQLAlchemy）：
   ```python
   import asyncio
   import asyncpg

   async def test():
       conn = await asyncpg.connect(
           host="localhost", port=5432,
           user="gaussdb", password="Gaussdb@123",
           database="moment_campus",
       )
       print(await conn.fetch("SELECT version();"))
       await conn.close()

   asyncio.run(test())
   ```
5. **确认 asyncpg 兼容性**（C1、C2）。若不兼容，切换 psycopg 方案
6. **记录验证结果到 `AIwork/`**

### 13.2 阶段 1：模型修复（最小代码改动）

1. **修改 21 个模型主键类型**：`Integer` → `BigInteger`
2. **验证 SQLite 仍可运行**：执行 `pytest tests/ -v`
3. **提交 git**：`fix: 统一主键与外键类型为 BigInteger，为 openGauss 适配做准备`

### 13.3 阶段 2：驱动与配置切换

1. **更新 requirements.txt**：新增 `asyncpg>=0.29.0`
2. **安装依赖**：`pip install asyncpg`
3. **新建 `.env.opengauss`**：
   ```
   DATABASE_URL=postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus
   ```
4. **修改 `.env.development`** 或通过环境变量切换到 openGauss
5. **启动后端验证连接**：`uvicorn app.main:app --reload`
6. **验证 `/health` 与 `/docs`**

### 13.4 阶段 3：初始化脚本重写

1. **删除空的初始迁移**
2. **重新生成初始迁移**：`alembic revision --autogenerate -m "initial migration for opengauss"`
3. **检查迁移脚本**：确认 21 张表的 `op.create_table` 完整
4. **执行迁移**：`alembic upgrade head`
5. **验证表创建**：`gsql -c "\dt"`

### 13.5 阶段 4：演示数据填充

1. **修改 `seed_data.py` 的 `init_db`**：可选改为 `alembic upgrade head` 而非 `create_all`
2. **执行**：`python scripts/seed_data.py`
3. **验证数据**：通过 SQL 查询每张表的记录数

### 13.6 阶段 5：API 联调验证

1. **启动后端**
2. **执行第 10.5 节 API 链路验证**
3. **执行 pytest**：`pytest tests/ -v`（测试仍使用 SQLite，验证业务逻辑无回归）
4. **启动前端**：`npm run dev`
5. **浏览器验证**：登录、浏览、发布、搜索

### 13.7 阶段 6：兼容性回归

1. 验证所有 11 个 API 模块功能正常
2. 验证 `ilike` 搜索在 openGauss 上工作
3. 验证事务（`db.commit`、`db.rollback`）正常
4. 验证软删除（`is_deleted`）正常
5. 验证外键约束生效（尝试插入孤儿记录应失败）

### 13.8 阶段 7：文档与提交

1. 更新 README.md（修正数据库说明）
2. 更新 `.trae/specs/implement-full-project/spec.md`
3. 在 `AIwork/` 新增任务报告
4. Git 提交

---

## 14. 速查清单

### 14.1 必改清单（P0）

- [ ] 21 个模型主键 `Integer` → `BigInteger`
- [ ] `requirements.txt` 新增 `asyncpg`
- [ ] 新建 `.env.opengauss` 配置文件
- [ ] 密码 `@` 字符 URL 编码
- [ ] 重写 Alembic 初始迁移
- [ ] 修正 README 中关于 PostgreSQL 的描述

### 14.2 必验证清单（P0）

- [ ] openGauss 镜像本地存在
- [ ] `docker compose up -d opengauss` 成功
- [ ] asyncpg 能直连 openGauss
- [ ] `alembic upgrade head` 建表成功
- [ ] `seed_data.py` 填充成功
- [ ] API 链路全通

### 14.3 可选改进（P1）

- [ ] 拆分 `.env.sqlite` / `.env.opengauss`
- [ ] 引入 openGauss 视图（用于状态统计）
- [ ] 引入 openGauss 触发器（用于可信度自动更新，体现课设要点）
- [ ] Docker Compose 增加后端、前端服务
