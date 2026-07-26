# 任务报告：REL-02 性能、安全、ready/version、结构化日志与 AI 监控（本地）

## 1. 任务概述

按 `docs/33_TRAE_AI创造力大赛复赛深度优化落地方案_2026.md` 的 REL-02 要求，在本地开发环境（FastAPI + React + openGauss 7.0.0-RC3 容器）实现三大子任务：

- **REL-02.1**：实现 `/health/live`（进程存活探针）、`/health/ready`（DB/必要目录/AI 配置三段就绪检查，AI 失败标 degraded）、`/version`（commit SHA / build time / migration version / app_env）三个本地开发辅助接口，不作为生产发布门禁。
- **REL-02.2**：每请求生成或接受 `X-Request-ID`，贯穿日志 / AI 调用 / 行政审计；记录状态码 / 延时 / 异常类型，不记录密码 / Token / 密钥等敏感参数。
- **REL-02.3**：普通搜索 P95 ≤800ms（生产目标）、AI 搜索 P95 ≤3.5s（含超时降级，生产目标）；进行安全 / 限流 / 故障注入测试；管理首页展示最近任务失败与 AI 降级率（本地环境采样）。

## 2. 已完成内容

### REL-02.1 健康检查与版本接口
- `app/api/health.py` 实现 `GET /health/live`：返回 `{"status":"alive","timestamp":...}`，无外部依赖。
- `GET /health/ready`：依次检查 DB（`SELECT 1`）+ `/uploads` 目录可写性（写 `.health_check_<pid>.tmp` 临时文件后删除）+ AI 配置（`AI_PROVIDER` 缺失标 degraded）。DB/uploads 失败返回 503 unavailable，AI 缺失返回 200 degraded，全部 OK 返回 200 ready。
- `GET /version`：返回 commit_sha（`GIT_COMMIT_SHA` 环境变量，默认 local）/ build_time / migration_version（查询 alembic_version 表）/ app_env。
- 测试覆盖：DB 故障 503、AI degraded、版本信息完整、`/health/live` 不依赖外部资源。

### REL-02.2 请求追踪与结构化日志
- `RequestIDMiddleware`：生成或接受 `X-Request-ID`（uuid4 / 透传客户端请求头），写入 `request.state.request_id`，响应头回写。
- `RequestLoggingMiddleware`：记录 `method / 脱敏 path / 状态码 / 耗时 / request_id`；`_sanitize_path` 对 `password/token/api_key/secret/access_token/refresh_token` 等敏感参数值替换为 `***REDACTED***`；不记录请求体（含密码 / Token / 密钥）。
- 异常兜底：`call_next` 抛错时返回 500 JSON（不泄露堆栈），仅记录异常类型 + request_id 便于追踪；解决 BaseHTTPMiddleware 中 `call_next` 异常绕过 FastAPI 全局 handler 的已知 Starlette 问题。
- AI 调用透传：`invoke_ai` 将 `request_id` 写入 `AIInvocationLog.trace_id`，行政审计同样关联。

### REL-02.3 性能 / 安全 / 故障注入测试 + AI 降级率监控
- 性能基线（本地测试阈值，生产目标见括号）：
  - 普通搜索 P95 ≤2500ms（生产目标 800ms）
  - AI 搜索 P95 ≤5000ms（生产目标 3.5s，含超时降级）
  - 健康端点 `/health/live` P95 <200ms、`/health/ready` P95 <500ms
- 限流：`RateLimitMiddleware` 覆盖 login / register / publish / AI 搜索 / AI 建议等关键端点（基于 in-memory token bucket，按 IP + path 规则匹配）。
- 安全测试：SQL 注入（搜索 / 标题按字面量处理，无 `OR '1'='1` 命中）、XSS（响应不执行脚本，原文存储）、CSRF（Bearer Token 校验）、日志脱敏（password / token / api_key 替换为 REDACTED）。
- 故障注入：DB 故障返回 500 + X-Request-ID（不泄露堆栈）；AI 超时 / 网络错误 / 限流 / 余额不足 全部 fallback 到普通搜索 + 记录对应 `output_status`（timeout / network_error / rate_limit / insufficient_quota）。
- AI 降级率监控：
  - 后端 `GET /admin/todos` 返回 `ai_calls_24h` / `ai_fallback_24h` / `ai_fallback_rate`（本校最近 24h 采样）。
  - 前端 `AdminHomePage.tsx` 新增 AI 监控卡片：三色徽标（≥50% danger / ≥20% warning / <20% success），降级率 ≥50% 且调用 ≥5 次高亮告警，并给出"建议检查 AI 配置 / 网络连通性"提示。

### 测试基础设施修复
- `tests/conftest.py` 预置套餐 + 权益项改用 Python 层 SELECT-then-INSERT + savepoint 容错；并将 `created_at/updated_at` 由字符串改为 `datetime` 对象（asyncpg 类型要求，否则报 `invalid input for query argument ... expected a datetime.date or datetime.datetime instance, got 'str'`）；权益项 INSERT 全部改用绑定参数（避免 SQL 注入 + 类型由 driver 处理）。

## 3. 未完成内容

暂无。

> 说明：生产目标阈值（普通搜索 800ms / AI 搜索 3.5s）因本地开发环境硬件与容器资源受限，测试采用宽松阈值（2500ms / 5000ms）作为基线，生产环境上线后需在目标硬件上重新采样校验。本地环境采样监控已满足 REL-02.3 的"本地环境采样"要求。

## 4. 实现思路

### 健康检查分级
- `/health/live` 仅校验进程存活，无任何外部依赖，适合 kubelet 风格的高频探针。
- `/health/ready` 区分 critical（DB / uploads 目录）与 non-critical（AI 配置）：critical 失败直接 503 unavailable，non-critical 失败仅标 degraded 仍返回 200，避免 AI 配置缺失导致整个服务被踢出。
- `/version` 查询 alembic_version 表获得真实迁移版本，便于本地排查"迁移未执行"类问题。

### 请求追踪三层中间件
- 中间件注册顺序（`app/main.py`）：CORSMiddleware → RequestIDMiddleware → RateLimitMiddleware → RequestLoggingMiddleware。RequestID 必须先于 Logging，确保日志能拿到 request_id；RateLimit 在两者之间，限流命中时也能记录到 request_id。
- 敏感参数脱敏在 `_sanitize_path` 中完成，覆盖 password / token / api_key / secret / access_token / refresh_token 等常见命名，值统一替换为 `***REDACTED***`。
- 异常兜底：BaseHTTPMiddleware 中 `call_next` 抛出的异常可能绕过 FastAPI 的全局 Exception handler（已知 Starlette 问题），在 `dispatch` 内 try/except 兜底返回 500 JSON，不泄露堆栈，仅记录异常类型 + request_id。

### AI 故障降级链路
- `app/ai/provider.py` 的 `MockAIProvider` 与 `OpenAIProvider` 统一抛出 `AITimeoutError` / `AINetworkError` / `AIRateLimitError` / `AIInsufficientQuotaError` 四类异常。
- `app/ai/service.py` 的 `invoke_ai` 捕获后写入 `AIInvocationLog.output_status`（对应 timeout / network_error / rate_limit / insufficient_quota）与 `fallback_reason`，并将 `request_id` 写入 `trace_id`。
- `app/api/search.py` 的 AI 搜索端点在 fallback 后返回普通搜索结果 + `fallback=true` + `fallback_reason` + `ai_log_id`，前端据此显示降级提示。

### AI 降级率监控
- `app/api/admin.py` 的 `get_admin_todos` 在原有 7 类待办基础上，额外查询 `AIInvocationLog` 最近 24h 本校调用总数与 `fallback_reason IS NOT NULL` 数，计算降级率。
- 前端 `AdminHomePage.tsx` 三色徽标 + 告警提示，降级率 ≥50% 且调用 ≥5 次时高亮，避免低调用基数下的误报。

### 测试基础设施修复
- openGauss 不支持 PostgreSQL 的 `ON CONFLICT`，原 DO 块在并发 / 锁场景下可能静默失败（INSERT 未生效但未抛异常），改用 Python 层 SELECT-then-INSERT + savepoint 容错。
- asyncpg 期望 `datetime` 对象而非字符串，原代码传 `now.strftime('%Y-%m-%d %H:%M:%S')` 导致 `DataError`，改为直接传 `datetime` 对象。
- 权益项 INSERT 原用字符串拼接（`f"VALUES ({plan_id}, '{key}', {lv_sql}, {hard_sql}, ...)"`），存在 SQL 注入风险与类型不匹配，改为全绑定参数。

## 5. 修改文件

### 后端
- `backend/app/api/health.py`：健康检查与版本接口实现（已存在，本任务确认并通过测试）。
- `backend/app/middleware.py`：`RequestIDMiddleware` / `RateLimitMiddleware` / `RequestLoggingMiddleware` 三层中间件，含异常兜底与敏感参数脱敏。
- `backend/app/api/admin.py`：`get_admin_todos` 新增 AI 降级率统计（`ai_calls_24h` / `ai_fallback_24h` / `ai_fallback_rate`）。
- `backend/app/schemas/admin.py`：`TodoStats` schema 新增 AI 降级率三字段。
- `backend/tests/conftest.py`：预置套餐 + 权益项改用 Python 层 SELECT-then-INSERT + savepoint；`created_at/updated_at` 由字符串改为 `datetime` 对象；权益项 INSERT 全绑定参数。
- `backend/tests/test_rel02_health.py`：新增，健康 / 版本探针测试（含 DB 故障 503、AI degraded、版本信息）。
- `backend/tests/test_rel02_security.py`：新增，SQL 注入 / XSS / CSRF / 限流规则 / 日志脱敏测试。
- `backend/tests/test_rel02_fault_injection.py`：新增，DB 故障 500 + X-Request-ID、AI 超时 / 网络 / 限流 / 余额不足降级 + ai_invocation_logs 状态记录 + /admin/todos AI 降级率统计 + 故障链路 X-Request-ID 透传测试。
- `backend/tests/test_rel02_performance.py`：新增，普通搜索 / AI 搜索 / 健康端点 P95 阈值校验测试。

### 前端
- `frontend/src/pages/admin/AdminHomePage.tsx`：新增 AI 监控卡片（三色徽标 + 调用次数 / 降级次数 / 降级率 + 告警提示）。

### 文档
- `TODO.md`：在"已完成"顶部新增 REL-02 节，记录三个子任务、测试结果与报告链接。

## 6. 影响范围

- **后端中间件链路**：所有 HTTP 请求经过三层中间件，`X-Request-ID` 响应头全局生效；异常响应统一为 500 JSON（不泄露堆栈）。
- **管理后台首页**：`/admin/todos` 响应体新增 3 个字段（向后兼容，默认 0），前端展示 AI 监控卡片。
- **AI 搜索链路**：故障时 fallback 到普通搜索，`ai_invocation_logs` 记录详细故障状态与 trace_id。
- **测试基础设施**：`conftest.py` 预置套餐 / 权益项逻辑修复，影响所有依赖 `test_school` 夹具的测试（全量 972 个用例验证通过，无回归）。
- **本地开发辅助**：`/health/live` / `/health/ready` / `/version` 三个端点供本地排查与演示使用，不作为生产发布门禁。

## 7. 测试与验证

### 后端测试
- 命令：`cd backend; $env:TEST_DATABASE_URL = "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"; $env:APP_ENV = "opengauss"; .\.venv\Scripts\python.exe -m pytest tests/ -q`
- 结果：**972 passed, 66 skipped**（无失败，无错误），耗时 786.49s。
- REL-02 新增 55 个用例全部通过：
  - `test_rel02_health.py`：健康 / 版本探针，含 DB 故障 503、AI degraded、版本信息。
  - `test_rel02_security.py`：SQL 注入 / XSS / CSRF / 限流规则 / 日志脱敏。
  - `test_rel02_fault_injection.py`：DB 故障 500 + X-Request-ID、AI 超时 / 网络 / 限流 / 余额不足降级 + ai_invocation_logs 状态记录 + /admin/todos AI 降级率统计 + 故障链路 X-Request-ID 透传。
  - `test_rel02_performance.py`：普通搜索 / AI 搜索 / 健康端点 P95 阈值校验。

### 前端构建
- 命令：`cd frontend; npm run build`
- 结果：**build 通过**（1.04s），AdminHomePage AI 监控卡片正确打包（`AdminHomePage-CK29EWwT.js 10.94 kB`）。

### 测试基础设施修复验证
- 修复前：`conftest.py` 预置套餐时报 `invalid input for query argument $5: '2026-07-26 04:06:19' (expected a datetime.date or datetime.datetime instance, got 'str')`，55 个 REL-02 用例全部 ERROR。
- 修复后：将 `created_at/updated_at` 由 `now.strftime('%Y-%m-%d %H:%M:%S')` 改为直接传 `datetime` 对象 `now`，权益项 INSERT 改为全绑定参数，55 个用例全部通过，全量 972 个用例无回归。

## 8. 后续建议

1. **生产性能阈值校验**：本地测试采用宽松阈值（普通搜索 2500ms / AI 搜索 5000ms），生产环境上线后需在目标硬件上重新采样，校验是否达到生产目标（800ms / 3.5s）。若不达标，可考虑为 `posts` 表 `(school_id, status, created_at)` 添加复合索引、AI provider 增加连接池与缓存。
2. **限流持久化**：当前 `RateLimitMiddleware` 基于 in-memory token bucket，单进程内有效；多进程部署后需改为 Redis 共享计数。
3. **日志聚合**：当前日志输出到 stdout，本地开发够用；生产环境建议接入 ELK / Loki + Grafana，按 `request_id` 串联全链路。
4. **AI 降级率告警通道**：当前仅在前端管理首页展示，后续可扩展为飞书 / 邮件告警（降级率 ≥50% 持续 5 分钟触发）。
5. **健康检查扩展**：`/health/ready` 当前检查 DB / uploads / AI 三项，后续可扩展检查 Redis（若引入）、对象存储（若引入）、关键定时任务最近运行状态。
6. **测试用例优化**：`test_rel02_security.py` 中部分非异步测试被 `pytestmark = pytest.mark.asyncio` 误标记，触发 PytestWarning，可后续拆分为同步 / 异步两份 mark 文件清理告警。
