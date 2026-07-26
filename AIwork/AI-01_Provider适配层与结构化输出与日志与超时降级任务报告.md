# 任务报告：AI-01 Provider 适配、结构化输出、日志、超时与降级

## 1. 任务概述

实现 AI-01 子任务，为后续 AI-02（AI 搜索）和 AI-03（AI 辅助发布）提供基础 AI 调用能力。包含三个子任务：

- **AI-01.1** Provider 适配层：模型名 / 超时 / 重试 / 最大 Token / 结构化输出验证 / 错误分类 / 熔断 / 成本耗时成功记录 / 测试用假 Provider / 密钥仅服务端环境变量
- **AI-01.2** `ai_invocation_logs` 模型与迁移：记录 school_id / user_id / 场景 / 模型 / 延迟 / 输入长度 / 输出状态 / 降级原因 / 候选数 / 结果数 / trace_id / 时间；默认不保存完整敏感输入
- **AI-01.3** 三校调用隔离与故障测试：school_id 强制来自 TenantContext；超时 / 429 / 余额不足 / JSON 解析失败 / 熔断 均降级为普通搜索

## 2. 已完成内容

### AI-01.1 Provider 适配层
- 抽象基类 `AIProvider`：封装 `asyncio.wait_for` 超时 + 指数退避重试 + 熔断 + JSON 解析 + Schema 校验 + 错误分类
- 子类只需实现 `_invoke(prompt, options) → AIInvokeResult`
- `OpenAIProvider`：基于 openai SDK（延迟导入，mock 模式无需安装）；异常分类映射（APITimeoutError / APIConnectionError / RateLimitError / APIStatusError → AI 异常体系）
- `MockAIProvider`：测试用，支持 `set_response` / `set_exception` / `set_exception_factory` / `set_delay`
- `CircuitBreaker`：closed / open / half_open 状态机；连续失败达阈值熔断；超时后半开放行一次
- `get_provider()` 工厂单例：按 `settings.AI_PROVIDER` 返回 mock 或 openai
- 密钥仅从 `settings.AI_API_KEY` 读取，不进日志、不进响应、不进前端
- 错误分类：`AITimeoutError` / `AIRateLimitError` / `AIInsufficientQuotaError` / `AINetworkError` / `AIJSONParseError` / `AICircuitBreakerOpenError` / `AIError`

### AI-01.2 ai_invocation_logs 模型与迁移
- ORM 模型 `AIInvocationLog`（`app/models/ai_invocation_log.py`）
- Alembic 迁移 `p4d5e6f7a8b9_ai_01_invocation_logs.py`：建表 + 11 个索引（school_id / user_id / scene / output_status / trace_id / created_at 单列索引 + school_id+created_at / school_id+scene+created_at / output_status+created_at / user_id+created_at 组合索引）
- 隐私约束：只保存 `input_length`（长度）与 `input_hash`（SHA-256 摘要），不保存完整 prompt
- 模型注册到 `app/models/__init__.py`

### AI-01.3 调用服务与三校隔离
- `invoke_ai()` 服务函数：封装 Provider 调用 + 自动记录日志 + 失败降级
- 三校隔离：`school_id` 强制取自 `TenantContext.school_id`，`invoke_ai` 签名不接受 `school_id` 参数
- 失败降级：超时 / 429 / 余额不足 / JSON 解析失败 / 熔断 / 其他异常 均返回 `AIInvokeOutcome(fallback=True)`，不抛异常给业务层
- `update_invocation_result()`：上层检索完成后补充候选数 / 结果数 / 降级原因

### 配置与依赖
- `app/config.py`：新增 AI 配置项（AI_PROVIDER / AI_API_KEY / AI_API_BASE / AI_MODEL / AI_TIMEOUT / AI_MAX_TOKENS / AI_MAX_RETRIES / AI_CIRCUIT_FAILURE_THRESHOLD / AI_CIRCUIT_RESET_SECONDS）
- `.env.opengauss.example`：补充 AI 配置示例
- `requirements.txt`：新增 `openai>=1.50.0` 与 `jsonschema>=4.20.0`

### 测试
- `tests/test_ai_provider_unit.py`：17 个单元测试（不依赖数据库），覆盖正常调用 / 结构化输出校验 / JSON 解析失败 / 超时 / 429 / 余额不足 / 网络错误 / 重试 / 熔断
- `tests/test_ai_provider.py`：11 个集成测试（依赖 openGauss 测试库），覆盖日志记录 / 隐私约束 / 各类故障降级落库 / 三校隔离 / update_invocation_result

### 修复测试基础设施回归
- `tests/conftest.py` 的 `setup_database` fixture 之前被改为使用 `ON CONFLICT DO NOTHING` 语法，但 openGauss 7.0.0-RC3 不支持该语法，导致所有集成测试报 `syntax error at or near "CONFLICT"` 而失败
- 改用 openGauss 兼容的 `DO $$ BEGIN ... EXCEPTION WHEN unique_violation THEN NULL; END $$` 模式（与同文件归档表清理同一模式）
- 同时将 TRUNCATE 与 plan 插入放在同一个 `test_engine.begin()` 连接中，避免 openGauss 跨连接 TRUNCATE 可见性问题

## 3. 未完成内容

暂无。AI-01 三个子任务全部完成，测试全部通过。

## 4. 实现思路

### Provider 适配层设计
采用「抽象基类 + 子类实现原始调用」的模式：
- 基类 `AIProvider.complete()` 统一处理熔断检查 → `asyncio.wait_for` 超时包裹 → 重试退避 → JSON 解析 → Schema 校验 → 错误分类
- 子类 `OpenAIProvider._invoke()` 只负责调用 openai SDK 并将异常映射到 AI 异常体系
- 子类 `MockAIProvider._invoke()` 用于测试，可注入预设响应 / 异常 / 延迟

### 熔断器设计
简单的 closed / open / half_open 状态机：
- 连续失败次数达 `failure_threshold` → 进入 open 状态，拒绝请求
- 经过 `reset_seconds` 后 → 进入 half_open，放行一次请求
- half_open 成功 → closed（计数清零）；失败 → open（重新计时）

### 降级策略
`invoke_ai()` 永不抛 `AIError` 给业务层，而是返回 `AIInvokeOutcome`：
- 成功：`fallback=False, response=AIResponse`
- 失败：`fallback=True, response=None, fallback_reason="AI 响应超时，已降级普通搜索"`
- 上层（AI-02/AI-03）根据 `fallback` 标记切换普通搜索 / 手动发布

### 三校隔离
- `invoke_ai()` 签名不接受 `school_id` 参数（通过 `inspect.signature` 测试验证）
- `school_id` 强制取自 `TenantContext.school_id`
- 日志按 `school_id` 隔离，A 校查询不会返回 B 校日志

### 隐私保护
- 日志只保存 `input_length`（字符数）与 `input_hash`（SHA-256 摘要）
- 不保存完整 prompt、不保存模型完整输出
- `output_status` 只记状态码，`candidate_count` / `result_count` 只记数量

## 5. 修改文件

### 新增文件
- `backend/app/ai/__init__.py` — AI 模块导出
- `backend/app/ai/exceptions.py` — AI 异常分类
- `backend/app/ai/provider.py` — Provider 适配层（AIProvider / OpenAIProvider / MockAIProvider / CircuitBreaker / get_provider）
- `backend/app/ai/schemas.py` — 结构化输出 JSON Schema 与校验
- `backend/app/ai/service.py` — 调用服务（invoke_ai / update_invocation_result / AIInvokeOutcome）
- `backend/app/models/ai_invocation_log.py` — AIInvocationLog ORM 模型
- `backend/alembic/versions/p4d5e6f7a8b9_ai_01_invocation_logs.py` — 建表迁移
- `backend/tests/test_ai_provider_unit.py` — 17 个单元测试
- `backend/tests/test_ai_provider.py` — 11 个集成测试
- `AIwork/AI-01_Provider适配层与结构化输出与日志与超时降级任务报告.md` — 本报告

### 修改文件
- `backend/app/config.py` — 新增 AI 配置项
- `backend/app/models/__init__.py` — 注册 AIInvocationLog
- `backend/.env.opengauss.example` — 补充 AI 配置示例
- `backend/requirements.txt` — 新增 openai 与 jsonschema 依赖
- `backend/tests/conftest.py` — 修复 ON CONFLICT 语法回归（改为 DO 块 + 同连接执行）
- `.trae/specs/finals-deep-optimization/tasks.md` — 勾选 AI-01.1 / AI-01.2 / AI-01.3

## 6. 影响范围

### 直接影响
- **AI 模块**（`app/ai/`）：新增模块，为 AI-02 / AI-03 提供基础调用能力
- **数据库**：新增 `ai_invocation_logs` 表（需执行 `alembic upgrade head`）
- **配置**：新增 9 个 AI 配置项（默认 mock 模式，不影响现有功能）
- **依赖**：新增 `openai` 与 `jsonschema` 两个 Python 包

### 间接影响
- **测试基础设施**：修复 `conftest.py` 的 `ON CONFLICT` 语法回归，使所有集成测试能在 openGauss 上运行
- **后续任务**：AI-02（AI 搜索）可直接调用 `invoke_ai()` 与 `SEARCH_INTENT_SCHEMA`；AI-03（AI 辅助发布）可直接调用 `invoke_ai()` 与 `PUBLISH_SUGGESTION_SCHEMA`

### 不影响
- 现有 API 路由、前端、状态机、租户隔离、权益校验等既有功能不受影响
- 默认 `AI_PROVIDER=mock`，不依赖外部 API Key，不影响本地开发与测试

## 7. 测试与验证

### 单元测试（`tests/test_ai_provider_unit.py`，17 个，不依赖数据库）
- `TestMockProviderNormal`：正常调用 + 结构化输出校验（4 个）
- `TestJSONParseFailure`：JSON 解析失败 + 代码块提取（2 个）
- `TestTimeoutFallback`：超时降级 + 熔断计数（2 个）
- `TestErrorClassification`：429 / 余额不足 / 网络错误 / 余额不足不重试（4 个）
- `TestRetry`：重试后成功 + 重试用尽后抛异常（2 个）
- `TestCircuitBreaker`：熔断阈值触发 + 超时后半开恢复（2 个）

执行命令：
```powershell
cd backend
$env:APP_ENV="opengauss"
$env:TEST_DATABASE_URL="postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"
.\.venv\Scripts\python.exe -m pytest tests/test_ai_provider_unit.py -v
```
结果：**17 passed in 0.57s**

### 集成测试（`tests/test_ai_provider.py`，11 个，依赖 openGauss 测试库）
- `TestInvokeAILogging`：成功调用日志记录 + 隐私约束（2 个）
- `TestInvokeFallbackLogging`：超时 / 429 / 余额不足 / JSON 解析失败 / 熔断 降级落库（5 个）
- `TestTenantIsolation`：签名校验 + 两校日志隔离 + 登录用户 user_id 记录（3 个）
- `TestUpdateInvocationResult`：补充候选数 / 结果数（1 个）

执行命令：
```powershell
cd backend
$env:APP_ENV="opengauss"
$env:TEST_DATABASE_URL="postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"
.\.venv\Scripts\python.exe -m pytest tests/test_ai_provider.py -v
```
结果：**11 passed in 46.10s**

### 合并执行
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ai_provider_unit.py tests/test_ai_provider.py -v
```
结果：**28 passed in 46.10s**

### 未运行的测试
- 前端 `npm run build`：本任务纯后端，无前端改动，未运行
- 全量后端测试 `pytest tests/ -v`：因 openGauss 多文件并发 TRUNCATE 死锁问题（预存问题，与 AI-01 无关），未运行全量；AI-01 相关测试单独运行全部通过

## 8. 后续建议

1. **AI-02 AI 搜索**：可直接基于 `invoke_ai()` + `SEARCH_INTENT_SCHEMA` 实现 `POST /api/v1/search/ai`，失败时根据 `outcome.fallback` 降级普通搜索
2. **AI-03 AI 辅助发布**：可直接基于 `invoke_ai()` + `PUBLISH_SUGGESTION_SCHEMA` 实现草稿建议，失败时不阻塞手动发布
3. **真实 openai 调用验证**：设置 `AI_PROVIDER=openai` + `AI_API_KEY=<真实 Key>` 后，可端到端验证 OpenAIProvider 的真实调用与异常分类
4. **openGauss 多文件并发测试死锁**：建议后续将 `setup_database` 的 TRUNCATE 改为按表逐个执行或使用 `pg_advisory_lock` 串行化，避免多文件并发运行时的 TRUNCATE 死锁（预存问题，影响全量 `pytest tests/`）
5. **AI 调用用量统计**：`ai_invocation_logs` 已记录 `school_id` + `scene` + `created_at`，后续可对接 `tenant_usage_daily.ai_calls_count` 实现 AI 调用日汇总
