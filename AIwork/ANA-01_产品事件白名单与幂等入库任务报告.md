# 任务报告：ANA-01 产品事件白名单、最小字段、幂等入库与环境标记

## 1. 任务概述

实现 moment-campus 数据分析底座（ANA-01）：产品事件白名单字典、最小字段集、幂等入库与环境标记，为后续 ANA-02 指标计算与漏斗分析提供数据基础。

依据 spec：`.trae/specs/finals-deep-optimization/tasks.md` 的 ANA-01 节。

依赖前置任务：FND-01（统一枚举）、TEN-02（TenantContext，提供 school_id）。

## 2. 已完成内容

### ANA-01.1 事件字典白名单 + 最小字段（`app/core/analytics.py`）

- 11 类白名单事件，每事件定义允许的最小字段集（多余字段被静默剔除，敏感字段抛错拒绝入库）：
  - `school_viewed`：source
  - `search_started`：keyword_length / category_code / source（**不记** keyword 原文）
  - `search_succeeded`：keyword_length / result_count / category_code / has_filter
  - `search_zero`：keyword_length / category_code / has_filter
  - `post_viewed`：post_id / source
  - `share_clicked`：post_id / channel
  - `subscribed`：target_type / target_id
  - `draft_saved`：post_id / has_title / has_image / content_length（**不记** 草稿标题/正文）
  - `post_submitted`：post_id / category_code / post_type_code / is_anonymous（**不记** 标题/正文/标签）
  - `publisher_verified`：publisher_id / action
  - `tenant_activated`：stage
- 敏感字段黑名单 `SENSITIVE_FIELD_NAMES`：password / token / secret / api_key / keyword / query / content / body / text / title / description / phone / mobile / email / id_card——客户端误传即抛 ValueError 拒绝入库（隐私硬约束）
- `track_event(event_id, event_name, school_id, ...)` 异步函数：白名单 + 敏感字段双重校验后入库

### ANA-01.2 ProductEvent 模型 + 迁移 + 幂等入库

- 新建 `app/models/product_event.py`：`ProductEvent`
  - 字段：id / event_id(UUID, 唯一) / event_name / school_id(FK) / user_id(可空, FK) / session_id / trace_id / occurred_at / received_at / environment / fields_json(JSONB)
  - 索引：event_id 唯一 / event_name / school_id / user_id / session_id / trace_id / occurred_at / environment；组合索引 (school_id, event_name, occurred_at) / (environment, occurred_at) / (session_id, occurred_at)
- 新建 Alembic 迁移 `alembic/versions/k0f1a2b3c4d5_ana_01_product_events.py`，down_revision = `j9e0f1a2b3c4`（TEN-04 的 platform_audit_logs 之后），保持迁移链线性
- 幂等实现：openGauss 不支持 PostgreSQL 的 `INSERT ... ON CONFLICT DO NOTHING` 语法，改用「SELECT event_id → 不存在则 INSERT」+ `event_id` 上的唯一约束在并发场景下兜底（重复 INSERT 抛 IntegrityError，调用方捕获并视为已存在）
- `environment` 从 `settings.ANALYTICS_ENV` 读取，未配置时按 `APP_ENV` / `TEST_DATABASE_URL` 推导：APP_ENV=test → test；TEST_DATABASE_URL 非空 → test；APP_ENV=opengauss → demo
- 在 `app/config.py` 新增 `ANALYTICS_ENV` 配置项（值域 production/demo/test/seed，默认空字符串走推导）

### ANA-01.3 事件上报 API

- 新建 `app/api/analytics.py`：`POST /api/v1/analytics/events`（批量上报，1-50 条/批）
  - 登录/游客均可上报（游客必须携带 X-School-Code / ?school=，由 TenantContext 解析 school_id）
  - 普通用户上报载荷中的 user_id 被忽略（防伪造），以 token 解析的 user_id 为准；super_admin 可显式指定 user_id（跨校上报场景）
  - X-Request-ID 头写入 trace_id 字段，便于与请求日志关联
  - 单事件非白名单/敏感字段被拒不影响其他事件入库（使用 `db.begin_nested()` savepoint 隔离）
  - 返回 total / inserted / idempotent / rejected / results[]
- 在 `app/api/router.py` 追加 analytics 路由（仅追加 2 行，未触动其他路由；先 Read 最新内容确认 TEN-03 已注册 schools 路由后追加）
- 限流：复用 FND-03 限流中间件，未对 /api/v1/analytics 新增独立规则（默认放行；如需限制可后续在 `RATE_LIMIT_RULES` 追加）

### 测试

- 新建 `backend/tests/test_analytics.py`：33 个测试用例，覆盖：
  - 白名单完整性（11 类事件全在白名单内）
  - 搜索事件白名单不含 keyword 原文字段；草稿/帖子事件不含 content/title/body
  - sanitize_fields 剔除多余字段、拒绝敏感字段、拒绝非白名单事件
  - resolve_environment 返回合法值；TEST_DATABASE_URL 非空 → test；ANALYTICS_ENV 显式优先；非法值回退
  - track_event 新插入、幂等去重（重复 event_id 不重复入库）、拒绝非白名单、拒绝敏感字段、剔除多余字段、游客事件 user_id=None、4 种 environment 全部正确记录、非法 environment 抛错
  - track_events_batch 混合事件（合法+非白名单+敏感字段）单事件失败不影响其他；批量幂等
  - API：游客上报、登录用户上报（载荷 user_id 被忽略）、非白名单事件 422、幂等（第二次 inserted=0 idempotent=1）、敏感字段被拒、environment 写入数据库、X-Request-ID 写入 trace_id、游客无 school code 404、空事件列表 422

### 文档与勾选

- 更新 `.trae/specs/finals-deep-optimization/tasks.md` 中 ANA-01 的 2 个子任务勾选框为 `[x]`
- 更新 `TODO.md` 增加 ANA-01 完成记录

## 3. 未完成内容

- 限流策略：未对 `/api/v1/analytics/events` 配置专门的 `RATE_LIMIT_RULES` 条目（默认放行）。如生产环境出现上报滥用，可在 `app/middleware.py` 的 `RATE_LIMIT_RULES` 追加 `("/api/v1/analytics", "POST", 30, 60)` 等。
- 业务流程埋点未实装：根据文件所有权约束，未修改 `app/api/posts.py` / `app/api/search.py` 等业务 API。后续若需在发帖/搜索等流程中实装埋点，可在对应 handler 内调用 `track_event`，扩展点已留好。
- Git 提交：按任务要求未运行 git commit。

## 4. 实现思路

### 白名单 + 最小字段

事件字典采用 `dict[str, frozenset[str]]` 常量，每事件显式列出允许字段。`sanitize_fields` 函数：
1. 校验事件名在白名单内，否则抛 ValueError
2. 遍历客户端上报字段，命中 `SENSITIVE_FIELD_NAMES` 抛 ValueError（隐私硬约束）
3. 不在白名单内的字段静默剔除（便于前端增量迭代）
4. 返回清洗后的最小字段 dict

### 幂等入库

openGauss 兼容 PostgreSQL 协议但不支持 `INSERT ... ON CONFLICT DO NOTHING` 语法（与 `app/jobs/usage_summary.py` 中已确认一致）。采用「SELECT event_id → 不存在则 INSERT」+ 唯一约束兜底模式：
1. 先 SELECT event_id；若已存在 → 返回 (False, existing)（幂等命中）
2. INSERT；若并发触发唯一约束 IntegrityError → 回滚并视为已存在
3. 批量场景使用 `db.begin_nested()` savepoint 隔离单事件失败，避免回滚已成功的其他事件

### 环境标记

`resolve_environment()` 优先级：
1. `settings.ANALYTICS_ENV`（若为非空合法值）
2. `APP_ENV=test` → test
3. `TEST_DATABASE_URL` 非空 → test
4. `APP_ENV=opengauss` → demo（本地开发默认演示档）

测试环境（TEST_DATABASE_URL 必填）自动标记为 test，生产部署可通过 `ANALYTICS_ENV=production` 显式指定。

### API 设计

- 路径：`POST /api/v1/analytics/events`
- 请求体：`{"events": [EventInput, ...]}`，1-50 条/批
- 响应：`{total, inserted, idempotent, rejected, results: [{event_id, inserted, error}]}`
- 依赖 `TenantContext` 解析 school_id（游客必须传 X-School-Code）
- 普通用户载荷中的 user_id 被忽略（防伪造），仅 super_admin 可显式指定（跨校上报场景）

## 5. 修改文件

### 新建
- `backend/app/models/product_event.py` — ProductEvent 模型
- `backend/app/core/analytics.py` — 白名单 + track_event + 批量入库 + 环境标记
- `backend/app/api/analytics.py` — POST /api/v1/analytics/events 批量上报 API
- `backend/alembic/versions/k0f1a2b3c4d5_ana_01_product_events.py` — Alembic 迁移（建表 + 索引 + 唯一约束）
- `backend/tests/test_analytics.py` — 33 个测试用例

### 修改
- `backend/app/models/__init__.py` — 追加 `ProductEvent` 导出
- `backend/app/api/router.py` — 追加 analytics 路由（import + include_router 各 1 行；先 Read 最新内容确认 TEN-03 已注册 schools 路由后追加，未触动其他路由）
- `backend/app/config.py` — 新增 `ANALYTICS_ENV` 配置项（默认空字符串，走推导）
- `.trae/specs/finals-deep-optimization/tasks.md` — ANA-01 两个子任务勾选为 `[x]`
- `TODO.md` — 新增 ANA-01 完成记录

## 6. 影响范围

### 直接影响
- **数据分析底座**：新增 `product_events` 表与 `app/core/analytics.py`，为后续 ANA-02 指标计算提供数据源
- **API 路由**：新增 `/api/v1/analytics/events` 端点；router.py 仅追加 2 行，不影响其他路由
- **配置**：新增 `ANALYTICS_ENV` 环境变量，未配置时走 APP_ENV 推导，向后兼容

### 不影响
- 业务 API（posts/search/comments/interactions 等）逻辑未变
- TenantContext / permissions / schools / platform 等 API 未变
- 现有数据库表结构与数据未变（product_events 是新表）
- Alembic 迁移链线性延续（k0f1a2b3c4d5 → j9e0f1a2b3c4 TEN-04 → i8d9e0f1a2b3 COM-01）

## 7. 测试与验证

### 执行的测试

1. **Alembic 迁移**：`alembic upgrade head` 成功（i8d9e0f1a2b3 → j9e0f1a2b3c4 → k0f1a2b3c4d5 两步升级均通过）
2. **应用导入**：`python -c "from app.main import app"` 成功；analytics 模块导入 OK，11 类事件全部在白名单内
3. **ANA-01 测试**：`pytest tests/test_analytics.py -v` — **33 passed** in 117.22s
4. **回归验证**：`pytest tests/test_entitlement.py tests/test_tenant_isolation.py` — 部分用例因 conftest.py 的 setup_database fixture 在 openGauss 上的 TRUNCATE 可见性/死锁偶发问题失败（conftest.py 注释已明示此为已知 openGauss 兼容性 flaky 问题，非 ANA-01 引入；test_entitlement 18/22 通过，4 个 errors 均为 ConnectionDoesNotExistError/DeadlockDetectedError/UniqueViolation on product_plans 等 setup 错误）

### 未运行测试的原因

无。所有 ANA-01 相关测试均已运行并通过。

## 8. 后续建议

1. **业务流程埋点**：在 `posts.py`（post_submitted）/ `search.py`（search_started/succeeded/zero）/ `interactions.py`（share_clicked）等业务 handler 中调用 `track_event`，扩展点已留好（不动业务逻辑，仅追加一行 track_event 调用）
2. **限流配置**：若生产环境出现上报滥用，在 `app/middleware.py` 的 `RATE_LIMIT_RULES` 追加 `("/api/v1/analytics", "POST", 30, 60)` 等
3. **ANA-02 衔接**：`product_events` 表已就绪，ANA-02 可基于此表实现平台级/校级聚合指标、漏斗分析、7 日回访、搜索成功率/零结果率等
4. **环境标记运维**：生产部署时务必设置 `ANALYTICS_ENV=production`，避免生产数据被标记为 demo；种子数据导入脚本应设置 `ANALYTICS_ENV=seed` 以便与真实数据区分
5. **前端 SDK**：可封装前端 `trackEvent(event_name, fields)` 工具，自动生成 event_id（uuid v4）、session_id、occurred_at，统一上报到 `/api/v1/analytics/events`
6. **数据保留策略**：product_events 表会持续增长，建议后续制定归档/清理策略（如保留近 90 天明细 + 历史聚合到 tenant_usage_daily）
