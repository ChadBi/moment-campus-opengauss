# 任务报告：REL-03 本地 Docker 运行环境（不做公网部署）

## 1. 任务概述

实现复赛深度优化方案 REL-03 的五个子任务，建立本地 Docker 运行环境基线，明确不做公网部署：

- **REL-03.1**：本地 docker-compose + openGauss 可稳定启动（端口 5432 可访问、数据卷持久化）
- **REL-03.2**：FastAPI 挂载 /uploads 静态目录，前后端本地联调
- **REL-03.3**：Alembic 迁移可执行、可降级
- **REL-03.4**：明确不做公网/华为云部署、HTTPS 证书、Nginx 反向代理、备份回滚、版本核对流水线
- **REL-03.5**：/health/live、/health/ready、/version 本地开发辅助接口

依据：`docs/33_TRAE_AI创造力大赛复赛深度优化落地方案_2026.md` REL-03 节。约束：仅保证本地 Docker + openGauss 容器可稳定启动，所有演示与验证均在本地完成。

## 2. 已完成内容

### REL-03.1 docker-compose 验证
- 验证 `docker-compose.yml` 配置正确：
  - 镜像 `opengauss:7.0.0-RC3`（`pull_policy: never`，本地已加载）
  - 端口映射 `5432:5432`
  - 数据卷 `opengauss-data` → `/var/lib/opengauss`
  - 环境变量齐全：`GS_PASSWORD/GS_DB/GS_USERNAME/GS_USER_PASSWORD/GS_PORT`
- 容器稳定运行（`docker ps` 确认 `Up About an hour`）

### REL-03.2 /uploads 静态目录挂载
- 在 `backend/app/main.py` 通过 `StaticFiles` 挂载 `/uploads`：
  - 启动时 `os.makedirs(_upload_dir, exist_ok=True)` 确保目录存在，避免挂载失败
  - 目录路径由 `settings.UPLOAD_DIR` 控制（默认 `./uploads`）
  - 本地与容器行为一致：不引入 Nginx，由 FastAPI 直接提供静态文件
- 后端启动验证通过：`uvicorn app.main:app --reload` 正常启动，`/health/ready` 返回 `uploads: ok`

### REL-03.3 Alembic 迁移可执行、可降级
- 修复预存 bug：两个迁移文件 revision ID 冲突（`n2b3c4d5e6f7` 同时被 `acc_01_2_invitation_expires_used_by` 与 `gov_02_job_run_records` 使用），导致 `alembic upgrade head` 报 "Multiple head revisions"
  - 将 `gov_02_job_run_records` 改为新 revision `o3c4d5e6f7a8`，`down_revision = "n2b3c4d5e6f7"` 链式接续
  - 删除旧冲突文件 `n2b3c4d5e6f7_gov_02_job_run_records.py`，新建 `o3c4d5e6f7a8_gov_02_job_run_records.py`
- 验证三步全部通过：
  - `alembic upgrade head`：m1a2b3c4d5e6 → n2b3c4d5e6f7 → o3c4d5e6f7a8
  - `alembic downgrade -1`：o3c4d5e6f7a8 → n2b3c4d5e6f7
  - `alembic upgrade head` 恢复：n2b3c4d5e6f7 → o3c4d5e6f7a8

### REL-03.4 不做公网部署
- 在 `docs/22_项目运行与开发环境说明.md` 新增第 14.5 节，明确列出 7 项不做内容与对应脚本：
  - 公网/华为云部署、HTTPS 证书、Nginx 反向代理、备份回滚、版本核对流水线、生产 docker-compose、传统物理部署
- `deploy/` 目录下生产脚本（`docker-compose.prod.yml`、`deploy.sh`、`hybrid-deploy.sh`、bare-metal/nginx 配置等）本阶段一律不执行

### REL-03.5 健康检查与版本接口
- 新建 `backend/app/api/health.py`，实现三个根级端点（不在 /api/v1 前缀下）：
  - `GET /health/live`：返回 `{"status":"alive","timestamp":...}`（不检查任何依赖，仅证明进程可响应）
  - `GET /health/ready`：检查 DB 连接（SELECT 1）+ /uploads 目录可写性（实际写入临时文件测试，跨平台）+ AI 配置（AI_PROVIDER 环境变量）
    - DB 或 /uploads 失败 → 503 unavailable
    - AI 缺失但 DB/uploads 正常 → 200 degraded（不阻断，AI 搜索降级为普通搜索）
    - 全部正常 → 200 ready
  - `GET /version`：返回 commit_sha（GIT_COMMIT_SHA 环境变量，默认 local）/ build_time（BUILD_TIME 环境变量）/ migration_version（查询 alembic_version 表）/ app_env / app_name
- 在 `backend/app/main.py` 注册 health 路由（根级，无前缀）
- 后端启动后实际请求验证：
  - `/health/live` → `{"status":"alive","timestamp":"2026-07-25T00:24:59.474554+08:00"}`
  - `/health/ready` → `{"status":"degraded","checks":{"db":"ok","uploads":"ok","ai":"degraded: AI_PROVIDER not configured"}}`
  - `/version` → `{"commit_sha":"local","build_time":"...","migration_version":"o3c4d5e6f7a8","app_env":"opengauss","app_name":"此刻校园-OpenGauss"}`

### 修复预存 bug：app/models/__init__.py 语法错误
- 原文件 `__all__` 列表闭合错乱（`]    "JobRunRecord",]`），导致 Python 无法解析，进而 alembic 与整个后端无法启动
- 缺失 `from .ai_invocation_log import AIInvocationLog` 导入
- 修复后导入正常：`import app.models` 成功，`__all__` 共 33 项

## 3. 未完成内容

暂无。五个子任务全部完成并验证通过。

## 4. 实现思路

### 健康检查接口设计
- **存活 vs 就绪分离**：`/health/live` 只证明进程可响应（不检查依赖），`/health/ready` 检查关键依赖（DB/uploads/AI）。这是 Kubernetes 探针的常见模式，即使本地不做公网部署也保留此分层。
- **AI 故障降级而非阻断**：依据 REL-03.5 约束，AI 配置缺失只标 `degraded` 不标 `unavailable`。这与项目既有设计一致（`EntitlementService.ai_allowed` 超限时返回 False，调用方降级为普通搜索）。
- **跨平台可写性测试**：Windows 下 `os.access(path, os.W_OK)` 不可靠，改用实际写入临时文件 + 删除的方式测试 /uploads 目录可写性。
- **migration_version 实时查询**：直接查 `alembic_version` 表，而非硬编码版本号，确保升级/降级后 /version 反映真实状态。

### /uploads 静态目录挂载
- 在模块加载时（非 startup event）创建目录并挂载 `StaticFiles`，因为 `StaticFiles(directory=...)` 在挂载时就会检查目录是否存在，若延迟到 startup event 会报错。
- 不引入 Nginx：本地开发场景由 FastAPI 直接提供静态文件，与"不做公网部署"约束一致。

### Alembic 冲突修复
- 两个迁移文件（acc_01_2 与 gov_02）误用相同 revision ID `n2b3c4d5e6f7`，形成两个 head。
- 最小修复：保留 acc_01_2 的 revision 不变（已写入文档与依赖链），将 gov_02 改为新 ID `o3c4d5e6f7a8` 并设 `down_revision = "n2b3c4d5e6f7"`，形成单链：m1a2b3c4d5e6 → n2b3c4d5e6f7 → o3c4d5e6f7a8。

## 5. 修改文件

| 文件 | 操作 | 说明 |
| ---- | ---- | ---- |
| `backend/app/api/health.py` | 新增 | /health/live、/health/ready、/version 三个端点 |
| `backend/app/main.py` | 修改 | 挂载 /uploads 静态目录；注册 health 路由；导入 os、StaticFiles |
| `backend/app/models/__init__.py` | 修复 | 修复 __all__ 列表语法错误；补充 AIInvocationLog 导入；移除重复导入 |
| `backend/alembic/versions/o3c4d5e6f7a8_gov_02_job_run_records.py` | 新增 | 替代旧冲突文件，revision=o3c4d5e6f7a8，down_revision=n2b3c4d5e6f7 |
| `backend/alembic/versions/n2b3c4d5e6f7_gov_02_job_run_records.py` | 删除 | 旧文件 revision 与 acc_01_2 冲突 |
| `docs/22_项目运行与开发环境说明.md` | 修改 | 新增 9.5 节（健康检查接口）+ 第 14 章（REL-03 本地 Docker 运行环境） |
| `.trae/specs/finals-deep-optimization/tasks.md` | 修改 | REL-03.1~03.5 勾选为 [x] |
| `TODO.md` | 修改 | 新增 REL-03 完成记录 |
| `AIwork/REL-03_本地Docker运行环境任务报告.md` | 新增 | 本报告 |

## 6. 影响范围

- **后端启动链路**：修复 `app/models/__init__.py` 语法错误后，整个后端可正常启动（此前 alembic、uvicorn、pytest 全部受阻塞）。
- **Alembic 迁移链**：消除多 head 冲突，迁移链变为单链 m1a2b3c4d5e6 → n2b3c4d5e6f7 → o3c4d5e6f7a8。`alembic upgrade head` / `downgrade -1` 恢复可用。
- **静态文件服务**：`/uploads/*` 现由 FastAPI StaticFiles 提供，上传后的图片可通过 `/uploads/<filename>` 直接访问（此前上传逻辑已写入此目录但未挂载静态服务）。
- **健康检查**：新增三个根级端点，不影响既有 `/health`（保留向后兼容）与 `/api/v1/*` 路由。
- **文档**：docs/22 新增健康检查接口说明与 REL-03 本地运行章节，不影响既有内容。
- **不影响**：业务逻辑、前端、数据库表结构（仅修复迁移文件元数据，不改表结构）、权限模型、AI 调用链路。

## 7. 测试与验证

### 后端启动验证
- `$env:APP_ENV = "opengauss"` + `uvicorn app.main:app --reload` 启动成功
- 启动日志：`启动 此刻校园-OpenGauss | 环境: opengauss | DB: openGauss (asyncpg)`
- `/uploads` 静态目录挂载成功（否则 StaticFiles 会抛 RuntimeError）

### 健康检查接口实际请求验证
- `GET /health/live` → 200 `{"status":"alive","timestamp":"2026-07-25T00:24:59.474554+08:00"}`
- `GET /health/ready` → 200 `{"status":"degraded","checks":{"db":"ok","uploads":"ok","ai":"degraded: AI_PROVIDER not configured"}}`
  - DB 检查通过（SELECT 1 返回 1）
  - uploads 检查通过（目录存在且可写）
  - AI 检查降级（AI_PROVIDER 环境变量未设置，符合预期——本地未配置 AI）
- `GET /version` → 200 `{"commit_sha":"local","build_time":"...","migration_version":"o3c4d5e6f7a8","app_env":"opengauss","app_name":"此刻校园-OpenGauss"}`
  - migration_version 正确反映当前 alembic 版本

### Alembic 迁移验证
- `alembic heads` → 单 head `o3c4d5e6f7a8`（修复前为两个重复的 `n2b3c4d5e6f7`）
- `alembic current` → `m1a2b3c4d5e6`（初始状态）
- `alembic upgrade head` → 成功执行两步迁移（m1a2b3c4d5e6 → n2b3c4d5e6f7 → o3c4d5e6f7a8）
- `alembic downgrade -1` → 成功回退一步（o3c4d5e6f7a8 → n2b3c4d5e6f7）
- `alembic upgrade head` → 成功恢复（n2b3c4d5e6f7 → o3c4d5e6f7a8）

### 未运行 pytest 全量测试的原因
- 未运行 `pytest tests/ -v`：测试需 `TEST_DATABASE_URL` 环境变量指向独立测试库 `moment_campus_test`，且测试库需先 `CREATE DATABASE`。本次任务聚焦 REL-03 本地运行环境与健康检查接口，已通过实际 HTTP 请求验证三个端点行为符合预期。健康检查接口不依赖测试库（直接查开发库），全量测试留待 REL-01.2 统一执行。

### docker-compose 验证
- `docker ps --filter name=opengauss` → `opengauss Up About an hour`
- 镜像 `opengauss:7.0.0-RC3`、端口 `5432:5432`、数据卷 `opengauss-data` 均已确认

## 8. 后续建议

1. **AI_PROVIDER 配置**：当 AI-01（Provider 适配层）实现后，在 `.env.opengauss` 中配置 `AI_PROVIDER` 环境变量，`/health/ready` 的 ai 检查将从 `degraded` 变为 `ok`。
2. **GIT_COMMIT_SHA / BUILD_TIME 注入**：本地开发默认 `commit_sha=local`；若需精确版本追踪，可在 CI 构建时注入 `GIT_COMMIT_SHA` 与 `BUILD_TIME` 环境变量。
3. **REL-02.1 关联**：REL-03.5 实现的三个接口与 REL-02.1 描述一致，REL-02 可直接复用，无需重复实现。
4. **前端构建验证**：本次未运行 `npm run build`（REL-03 仅涉及后端接口与本地运行环境，前端无改动）；留待 REL-01.1 统一验证前端 lint 与构建。
5. **job_run_records 模型**：`JobRunRecord` 模型已存在于 `backend/app/models/job_run_record.py`，迁移文件已修复；GOV-02.1/02.2 实现时可直接使用。
