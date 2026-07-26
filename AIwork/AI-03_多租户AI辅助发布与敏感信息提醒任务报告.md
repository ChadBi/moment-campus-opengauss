# 任务报告：AI-03 多租户 AI 辅助发布与敏感信息提醒

## 1. 任务概述

在 moment-campus 项目中实现 AI 辅助发布与敏感信息提醒，包含两个子任务：

- **AI-03.1** `POST /api/v1/posts/ai-suggest` 后端：在草稿基础上建议标题/摘要/分类/标签/默认有效期/遗漏信息/敏感提醒；只返回结构化建议，不修改原文；用户在前端逐项确认采纳；不改坐标/状态；不自动过审；失败不阻塞手动发布（fallback=true 时仍返回敏感检测 + 缺失提示）；记录 `ai_invocation_logs`（成功/失败均记录）。
- **AI-03.2** 三校隔离：分类/标签/有效期来自当前租户配置，不引用其他学校地点或词表。提示词只含当前学校的分类/标签白名单；模型若返回其他学校的分类/标签 → 白名单校验直接丢弃。

## 2. 已完成内容

### AI-03.1 后端 AI 辅助发布建议

- **schemas** (`backend/app/schemas/ai.py`)：新增 `AIPublishSuggestRequest`（草稿字段，全部可选）+ `AIPublishSuggestions`（建议标题/摘要/分类/标签/默认有效期）+ `AIPublishSuggestionResponse`（建议 + 遗漏信息 + 敏感提醒 + 命中明细 + 降级标记 + ai_log_id）
- **service** (`backend/app/services/ai_publish.py`)：实现 `execute_publish_suggestion` 主入口
  - **确定性敏感信息检测** `detect_sensitive_info`：5 类正则（手机/座机/400/邮箱/身份证 15+18 位/银行卡 16-19 位/QQ 5-12 位）+ 掩码（保留前 3 位 + 末 2 位）
  - **缺失字段检测** `_detect_missing_info`：标题/正文是否为空或过短、分类是否已选、地点是否已选、有效期是否已设置、活动时间是否完整、失物招领类是否补充联系方式
  - **白名单加载** `_load_whitelists`：当前学校分类（按 sort_order/id 排序）+ 标签（按 usage_count 降序取前 50，避免提示词过长）
  - **提示词构造** `_build_prompt`：任务说明 + 返回 JSON 字段约束 + 重要约束（不修改原文 / category 必须从白名单选取 / tags 必须从白名单选取 / 不引用其他学校数据 / summary 基于草稿概括）+ 当前学校可用分类白名单 + 当前学校已有标签白名单 + 当前草稿已选字段 + 用户草稿原文
  - **白名单校验** `_validate_suggestions`：title 截断 200 字符；summary 截断 200 字符；category 按 name 或 code 匹配（非法值丢弃，category_id 置空）；tags 按 name 不区分大小写匹配（非法标签丢弃，最多 5 个，去重）；default_validity_days 限定 1-365（超出范围回退到当前已选分类的默认有效期）
  - **降级机制**：白名单加载失败 / 输入过短（标题<3 且正文<5）/ Provider 网络错误 / 超时 / JSON 解析失败 / 白名单校验失败 均降级返回 `fallback=true`，仍返回确定性的敏感检测与缺失字段提示（不依赖模型）；降级时仍记录 `ai_invocation_logs`
  - **结果合并**：missing_info 合并确定性检测与模型输出（去重保序，最多 8 条）；sensitive_warnings 合并确定性检测与模型输出（去重保序，最多 10 条）；更新 ai_invocation_logs 的 result_count（建议项数）
- **API** (`backend/app/api/posts.py`)：新增 `POST /posts/ai-suggest` 端点
  - 集成 TenantContext（三校隔离，school_id 强制取自上下文）+ get_current_user（必须登录，游客返回 401）
  - trace_id 来自 `request.state.request_id`
- **AI schema** (`backend/app/ai/schemas.py`)：新增 `PUBLISH_SUGGESTION_SCHEMA`
  - required: `suggestions` / `missing_info` / `sensitive_warnings`
  - suggestions 内 required: `title` / `summary` / `category` / `tags` / `default_validity_days`
  - 所有字段允许 null（模型可对某项无建议时填 null）
- **限流** (`backend/app/middleware.py`)：`/api/v1/posts/ai-suggest` 在 `RATE_LIMIT_RULES` 中独立配置 10 次/分钟（与 AI 搜索一致），且放在通用 `/api/v1/posts` 规则之前（startswith 匹配按声明顺序）
- **安全约束**：
  - **不修改原文**：仅返回"建议"，由前端逐项确认采纳
  - **不改坐标/状态**：本接口不修改 Post 任何字段
  - **不自动过审**：不调用状态机，不影响审核流程
  - **失败不阻塞**：fallback=true 时仍返回敏感检测 + 缺失提示，前端可继续手动发布
  - school_id 强制取自 TenantContext，不信任外部传入
  - 提示词只含当前学校分类/标签白名单，不泄露其他学校数据
  - 密钥仅从 settings 读取，不进日志/响应/前端
  - 隐私约束：ai_invocation_logs 只保存 input_length 与 input_hash

### AI-03.2 三校隔离

- **租户隔离**：所有查询（categories/tags）均按 `tenant.school_id` 过滤，不引用其他学校数据
- **提示词隔离**：A 校调用时提示词只含 A 校分类与标签，不含 B 校数据（测试 `test_prompt_does_not_leak_other_school_categories` 验证）
- **白名单校验隔离**：A 校调用，模型若返回 B 校分类名 → category_id 置空（测试 `test_b_school_category_dropped_in_a_school` 验证）；A 校调用，模型若返回 B 校标签 → 该标签丢弃（测试 `test_b_school_tag_dropped_in_a_school` 验证）
- **默认有效期隔离**：default_validity_days 超出 1-365 范围 → 回退到当前已选分类的默认有效期（来自当前学校分类配置，测试 `test_validity_days_out_of_range_falls_back` 验证）

### 前端 PostForm 集成

- **类型定义** (`frontend/src/types/index.ts`)：新增 `AIPublishSuggestRequest` / `AIPublishSuggestions` / `AIPublishSuggestionResponse`
- **服务层** (`frontend/src/services/posts.ts`)：新增 `aiSuggest` 方法调用 `POST /posts/ai-suggest`，含完整安全保证注释（不修改原文 / 失败不阻塞 / 三校隔离）
- **PostForm** (`frontend/src/components/PostForm.tsx`)：
  - 状态管理：`aiSuggesting` / `aiSuggestion` / `aiSuggestionError` / `adoptedFields`（已采纳字段集合）
  - "AI 建议"按钮：Sparkles 图标 + 加载态 + 重新生成态
  - 建议面板：
    - 建议标题（含"采纳"按钮，采纳后显示"已采纳"标记）
    - 建议摘要（含"采纳"按钮）
    - 建议分类（显示分类名，含"采纳"按钮，采纳后同步 category_id）
    - 建议标签（标签列表，含"全部采纳"按钮）
    - 建议默认有效期（显示天数，含"采纳"按钮，采纳后同步 expire_at）
  - 遗漏信息列表（圆点引导 + 文案）
  - 敏感信息提醒列表（含命中类型聚合展示，如"phone / email"）
  - 降级横幅：fallback=true 时橙色横幅"AI 服务暂时不可用：{原因}"
  - 关闭按钮：清除 AI 建议状态
  - 失败错误提示：API 失败时显示 toast 与错误信息，但不阻塞用户继续填写

### 测试

- **后端测试** (`backend/tests/test_ai_publish.py`)：25 个用例（单类运行全部通过）
  - 成功场景 3：返回结构化建议 / 默认有效期回退到分类默认值 / 成功记录日志
  - 降级场景 5：Provider 网络错误 / 超时 / JSON 解析失败 / 输入过短（不调用模型）/ 降级仍记录失败状态日志
  - 敏感检测 4：手机号 / 邮箱 / 身份证 / 输入过短降级时敏感检测仍生效
  - 白名单 3：非法分类丢弃 / 非法标签丢弃 / 有效期超出范围回退
  - 租户隔离 3：提示词不含 B 校分类 / B 校分类在 A 校被丢弃 / B 校标签在 A 校被丢弃
  - 鉴权校验 4：未登录 401 / 缺 X-School-Code 使用默认学校 / 超长 title 422 / 超长 content 422
  - 缺失字段 3：标题缺失提示 / 分类缺失提示 / 有效期缺失提示

### 修复预存 Bug

- **`backend/app/models/__init__.py`**：补充 `ProductEvent` 模型导入与 `__all__` 注册。此前缺失导致 `Base.metadata.create_all()` 不创建 `product_events` 表，测试报 `relation 'product_events' does not exist`。

## 3. 未完成内容

- **`npm run build` 整体构建未通过**：因 `frontend/src/pages/SearchPage.tsx` 与 `frontend/src/pages/TopicListPage.tsx` 存在 pre-existing TypeScript 错误（重复声明 `categoryId`/`setCategoryId`、未使用变量 `total` 等），导致 `tsc` 阶段失败。这些错误**与 AI-03 修改无关**（AI-03 修改的 `PostForm.tsx` / `posts.ts` / `types/index.ts` 经 `npx tsc --noEmit` 验证无任何 TypeScript 错误）。需后续单独修复 SearchPage.tsx 与 TopicListPage.tsx。
- **后端测试套件全量运行存在 openGauss 跨连接可见性问题**：在连续运行 12-18 个测试后，部分测试因 openGauss 的 TRUNCATE 在连接 A 提交后、连接 B 的快照仍看到旧数据导致 `duplicate key value violates unique constraint "ix_post_types_code"` 错误失败。该问题在 `conftest.py` 注释中已记录（"TRUNCATE 在连接 A 提交后，连接 B 的快照可能仍看到旧数据 → INSERT 报 duplicate key"），是 pre-existing 的环境问题，**非 AI-03 代码缺陷**。单类运行或单测试运行均全部通过。

## 4. 实现思路

### 后端架构

采用「确定性优先 + 模型补充 + 白名单兜底」三层架构，确保即使模型失败也能返回有价值的建议：

1. **确定性敏感信息检测**（不依赖模型）：使用正则表达式检测手机号/邮箱/身份证/银行卡/QQ 号，命中后做掩码处理（保留前 3 位 + 末 2 位）。始终执行，即使后续 AI 调用失败也返回该结果。
2. **确定性缺失字段检测**（不依赖模型）：根据草稿字段空缺情况生成提示（标题/正文/分类/地点/有效期/活动时间/联系方式），始终执行。
3. **白名单加载**：从当前学校加载分类与标签白名单（按 sort_order/usage_count 排序），用于提示词注入与解析后校验。失败则降级。
4. **输入过短检查**：标题<3 且正文<5 时不调用模型，降级为仅敏感检测 + 缺失提示（节省 API 成本）。
5. **模型调用**：复用 AI-01 的 `invoke_ai` 服务（Provider 适配层 + 熔断 + 重试 + 日志），通过 `PUBLISH_SUGGESTION_SCHEMA` 严格约束模型输出为 JSON。提示词注入当前学校分类/标签白名单，防止模型编造不存在的分类。
6. **白名单校验**：模型返回的 category 按 name/code 匹配白名单（非法值丢弃，category_id 置空）；tags 按 name 不区分大小写匹配白名单（非法标签丢弃，最多 5 个，去重）；default_validity_days 限定 1-365（超出范围回退到当前已选分类的默认有效期）。
7. **结果合并**：将模型输出与确定性检测结果合并（去重保序），missing_info 最多 8 条，sensitive_warnings 最多 10 条。
8. **日志记录**：通过 `invoke_ai` 自动记录 ai_invocation_logs（成功/失败均记录），上层补充 result_count。

### 安全设计

- **不修改原文**：本服务只生成"建议"，不返回修改后的内容；采纳由前端用户逐项确认
- **不改坐标/状态**：本服务不修改 Post 任何字段（不调用状态机、不修改 location_id/status）
- **不自动过审**：本服务不参与审核流程
- **失败不阻塞**：fallback=true 时仍返回敏感检测 + 缺失提示，前端可继续手动发布
- **三校隔离**：school_id 强制取自 TenantContext；提示词只含当前学校白名单
- **隐私约束**：ai_invocation_logs 只保存 input_length 与 input_hash，不保存完整 prompt
- **限流**：独立配置 10 次/分钟，防止滥用

### 前端设计

- **逐项采纳**：每条建议都有独立的"采纳"按钮，用户可选择性地采纳某些建议
- **状态可视化**：采纳后显示"已采纳"标记，便于用户区分
- **降级友好**：fallback=true 时显示橙色横幅与原因，但用户仍可继续填写表单
- **敏感信息聚合**：sensitive_findings 中的 type（phone/email/id_card/bank_card/qq）聚合展示，便于用户定位
- **失败容错**：API 调用失败时显示 toast 提示，但不阻塞用户继续填写表单

## 5. 修改文件

### 新增文件

- `backend/app/schemas/ai.py`：AI 发布建议请求/响应 Pydantic 模型
- `backend/app/services/ai_publish.py`：AI 发布建议核心服务（敏感检测 + 缺失检测 + 白名单加载 + 提示词构造 + 白名单校验 + 降级）
- `backend/tests/test_ai_publish.py`：AI 发布建议测试用例（25 个）
- `AIwork/AI-03_多租户AI辅助发布与敏感信息提醒任务报告.md`：本任务报告

### 修改文件

- `backend/app/api/posts.py`：新增 `POST /posts/ai-suggest` 端点（导入 `AIPublishSuggestRequest` / `AIPublishSuggestionResponse` 与 `execute_publish_suggestion` 服务）
- `backend/app/ai/schemas.py`：新增 `PUBLISH_SUGGESTION_SCHEMA` JSON Schema 定义
- `backend/app/middleware.py`：`RATE_LIMIT_RULES` 新增 `/api/v1/posts/ai-suggest` 10 次/分钟规则（放在通用 `/api/v1/posts` 规则之前）
- `backend/app/models/__init__.py`：补充 `ProductEvent` 模型导入与 `__all__` 注册（修复 pre-existing bug）
- `frontend/src/types/index.ts`：新增 `AIPublishSuggestRequest` / `AIPublishSuggestions` / `AIPublishSuggestionResponse` 类型
- `frontend/src/services/posts.ts`：新增 `aiSuggest` 方法
- `frontend/src/components/PostForm.tsx`：新增 AI 建议按钮 + 建议面板 + 状态管理 + 采纳函数
- `TODO.md`：新增 AI-03 完成条目

## 6. 影响范围

- **后端 AI 能力**：新增 AI-03 辅助发布建议能力，复用 AI-01 Provider 适配层与 `invoke_ai` 服务，与 AI-02 AI 搜索共用日志模型 `ai_invocation_logs`
- **后端 Post API**：新增 `POST /posts/ai-suggest` 端点，不影响现有 Post CRUD 与状态机
- **后端中间件**：新增限流规则，不影响现有规则
- **后端模型**：修复 `__init__.py` 中 `ProductEvent` 缺失导入，影响 `Base.metadata.create_all()` 创建 `product_events` 表（修复后测试库可正常建表）
- **前端 PostForm**：新增 AI 建议按钮与面板，不影响现有发布表单逻辑（AI 建议失败不阻塞手动发布）
- **前端类型与服务**：新增类型定义与服务方法，不影响现有类型与服务

## 7. 测试与验证

### 后端测试

- **执行命令**：`cd backend && pytest tests/test_ai_publish.py -v`
- **环境变量**：`APP_ENV=opengauss`、`TEST_DATABASE_URL=postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test`
- **结果**：
  - **单类运行全部通过**：25 个用例全部通过（成功场景 3 + 降级场景 5 + 敏感检测 4 + 白名单 3 + 租户隔离 3 + 鉴权校验 4 + 缺失字段 3）
  - **全量套件运行**：18 个用例通过 / 7 个用例 ERROR（fixture 阶段失败），原因是 openGauss 跨连接可见性问题（TRUNCATE 在连接 A 提交后、连接 B 的快照仍看到旧数据导致 `duplicate key value violates unique constraint "ix_post_types_code"`），该问题在 `conftest.py` 注释中已记录，非 AI-03 代码缺陷。同问题也影响 `test_ai_search.py`（12 通过 / 9 ERROR）等其他测试文件。
- **未运行全量后端测试套件**：因 openGauss 跨连接可见性问题在连续运行多个测试后会触发 ERROR，无法在单次运行中验证所有测试。已通过单类运行验证 AI-03 所有测试逻辑正确。

### 前端构建

- **执行命令**：`cd frontend && npm run build`
- **结果**：**未通过**（pre-existing TypeScript 错误）
- **失败原因**：`frontend/src/pages/SearchPage.tsx` 存在重复声明（`const [categoryId, setCategoryId]` 在第 175 行与第 336 行重复声明）、`frontend/src/pages/TopicListPage.tsx` 存在未使用变量（`total`）。这些错误**与 AI-03 修改无关**。
- **AI-03 文件验证**：通过 `npx tsc --noEmit` 过滤 `PostForm|posts\.ts|types/index` 返回空结果，证明 AI-03 修改的三个前端文件无任何 TypeScript 错误。

### 手动验证

- 后端 API 端点签名正确：`POST /api/v1/posts/ai-suggest` 已注册，response_model 为 `AIPublishSuggestionResponse`
- 限流规则正确：`/api/v1/posts/ai-suggest` 10 次/分钟，放在 `/api/v1/posts` 通用规则之前
- AI schema 正确：`PUBLISH_SUGGESTION_SCHEMA` 包含 required 字段与 properties
- 前端类型与服务方法正确：`aiSuggest` 方法签名与后端契约一致
- 前端 PostForm 集成完整：状态管理 / 处理函数 / UI 组件齐全

## 8. 后续建议

1. **修复 pre-existing 前端 TypeScript 错误**：`SearchPage.tsx` 重复声明 `categoryId`/`setCategoryId`（第 175 行与第 336 行），`TopicListPage.tsx` 未使用变量 `total`。修复后 `npm run build` 可恢复正常。
2. **修复 openGauss 跨连接可见性问题**：`conftest.py` 的 `setup_database` fixture 使用 `test_engine.begin()` 在连接 A 执行 TRUNCATE，但测试用 `db_session` 在连接 B 执行 INSERT，openGauss 在某些情况下连接 B 的快照仍看到旧数据。建议改为在同一连接中执行 TRUNCATE + INSERT，或使用 `READ COMMITTED` 隔离级别 + 显式 `COMMIT` 后重新连接。
3. **扩展敏感信息检测**：当前仅检测 5 类（手机/邮箱/身份证/银行卡/QQ），可考虑增加宿舍精确房间号（如"XX 栋 XXX 室"）、个人二维码（图片 OCR）、私人聊天截图等。
4. **AI 建议采纳率统计**：可在前端采纳按钮点击时上报 `product_events`（ai_suggestion_adopted），用于后续分析 AI 建议的实际采纳率与质量。
5. **多语言支持**：当前提示词与降级原因均为中文，若需支持多语言可抽取为 i18n 资源。
6. **缓存白名单**：当前每次调用都重新加载分类/标签白名单，可考虑添加短时缓存（如 60 秒 TTL）减少 DB 查询。
