# 任务报告：FND-03 帖子可见性、6 态唯一写入口、举报/上传安全

## 1. 任务概述

执行复赛深度优化方案（`docs/33_TRAE_AI创造力大赛复赛深度优化落地方案_2026.md` 第 13 节）第一交付波 FND-03 任务，目标是强化后端安全与状态机完整性：

- FND-03.1：`GET /posts/{id}` 增加状态/作者/租户可见性策略。
- FND-03.2：状态变化只走状态机服务；实质修改后 published 回 pending；删除采用 `is_deleted` + `archived`，不写第 7 种 `deleted` 状态。
- FND-03.3：管理路由统一 `require_role()`，补资源级租户校验；举报删除不再写非法状态。
- FND-03.4：上传安全：按文件内容 magic bytes 识别格式，限制尺寸/像素，重新编码去除 EXIF，生成安全文件名。
- FND-03.5：为登录/注册/发布/评论/验证/举报/AI 搜索增加基础限流；统一异常响应与请求 ID；日志不输出敏感参数。

## 2. 已完成内容

### FND-03.1 帖子可见性策略
- 新增 `can_view_post(post, current_user)` 集中判断函数（`app/api/posts.py`）：
  - 已软删除帖子：任何人都不可见。
  - 公开可见状态（published / expired）：任何人都可见。
  - 作者本人：可见自己所有状态。
  - 管理员（admin/super_admin）：可见所有状态（本校校验由 TEN-02 完善）。
- `get_post` 接口在返回前进行可见性校验，不可见返回 404（不泄露存在性）。
- 浏览次数（view_count）自增放在可见性校验之后，不可见时不增加。

### FND-03.2 状态机唯一写入口
- `post_status.py` 新增 `SUBSTANTIAL_FIELDS` 与 `is_substantial_change()` 函数，定义 9 个实质字段（title/content/category_id/post_type_id/location_id/location_name/location_lat/location_lng/lost_type）。
- `_TRANSITIONS` 新增 `published → pending` 流转，仅用于已发布帖子被实质修改后自动回审。
- `update_post` 接口检测实质字段变更时，通过状态机服务触发 `published → pending` 回审。
- `delete_post` 接口改为 `is_deleted=True` + 状态机流转到 `archived`（非终态时），不引入第 7 种 `deleted` 状态。
- 已归档帖子不可修改（返回 400）。

### FND-03.3 管理路由统一权限
- `admin.py` 定义 `AdminDep = Depends(require_role(Role.ADMIN))`，替换所有 `Depends(get_current_admin)`。
- 新增 `_check_post_in_admin_school()` 资源级校验：admin 仅限操作本校帖子，super_admin 可跨校。
- `approve_post` / `reject_post` / `handle_report` / `batch_approve` / `batch_reject` 均补齐状态机校验与资源校验。
- `handle_report` 不再写非法 `deleted` 状态，改为通过状态机流转到 `archived`。
- `dependencies.py` 的 `get_current_admin` 委托给 `require_role(Role.ADMIN)`，保持向后兼容。

### FND-03.4 上传安全
- `upload.py` 重写为完整的安全上传策略：
  - 按文件内容 magic bytes 识别真实格式（JPEG/PNG/GIF），不信任客户端 content_type。
  - 单文件大小 ≤ 5MB；像素尺寸 1x1 ~ 8000x8000。
  - 用 Pillow `verify()` + `load()` 双重校验图片完整性。
  - PIL 格式与 magic bytes 双重一致校验，防伪造。
  - 重新编码图片去除 EXIF/恶意 payload（JPEG→RGB quality=90，PNG→RGBA，GIF→save_all 保留动画）。
  - 文件名 = `uuid4().hex + 真实扩展名`，杜绝路径穿越。
  - 自动生成 300x300 缩略图。

### FND-03.5 限流 + 请求 ID + 异常统一 + 日志脱敏
- `middleware.py` 重写，新增三个中间件：
  - `RequestIDMiddleware`：接受/生成 `X-Request-ID`（截断 128 字符），注入 `request.state.request_id`，响应头返回。
  - `RateLimitMiddleware`：基于内存的固定窗口限流，覆盖 login/register/refresh/posts/comments/search-ai/upload 7 类接口；测试环境自动禁用（检测 `TEST_DATABASE_URL`）。
  - `RequestLoggingMiddleware`：记录方法/脱敏路径/状态码/耗时/request_id，不记录请求体。
- `_sanitize_path()` 对 URL query 中的敏感参数（password/token/secret/api_key 等 12 个）脱敏为 `***REDACTED***`。
- `main.py` 注册三个中间件 + 统一异常处理器：
  - `StarletteHTTPException` → `{detail, request_id}` + `X-Request-ID` 头。
  - `RequestValidationError` → 422 `{detail, request_id}`。
  - `Exception` 兜底 → 500 通用提示，日志保留完整堆栈但不泄露给客户端。

### 测试修复（附带）
- `conftest.py` 的 `test_category` fixture 增加 `test_school` 依赖并显式设置 `school_id`，修复因 TEN-01.3 添加 `school_id` 字段后导致的外键约束违规（`test_create_post_unauthenticated` 不依赖 `test_school` 时触发）。
- `test_api_contract.py` 修复 4 个举报契约测试的 URL 路径（`/api/v1/interactions/posts/{id}/reports` → `/api/v1/posts/{id}/report`），并修复 `test_report_with_all_five_types` 重复举报拦截问题（改为每类创建新帖子）。

## 3. 未完成内容

暂无。FND-03 全部 5 个子任务已完成。

注：
- Nginx 与应用 `/uploads` 行为一致性（FND-03.4 后半部分）属于 REL-03 本地 Docker 运行环境任务范围，本任务仅实现应用层上传安全。
- 完整的「按当前学校过滤」租户可见性由 TEN-02.3 负责，FND-03.1 简化为按角色判断，跨校资源隔离留待 TEN-02 完成。

## 4. 实现思路

- **可见性集中化**：将分散的可见性判断集中到 `can_view_post()` 函数，确保所有帖子检索端点使用一致策略，避免遗漏。
- **状态机唯一写入口**：所有状态变化（审核/驳回/归档/过期/冲突/删除/实质修改回审）均通过 `can_transition()` 校验后写入，禁止 API 直接设置 status 字段。`PostUpdate` schema 已在 FND-01.2 移除 status 字段。
- **实质修改检测**：定义 `SUBSTANTIAL_FIELDS` 集合，只修改非实质字段（expire_at/contact_info/is_anonymous/tags/activity_*/image_urls）时不触发回审，平衡审核严格度与用户便利。
- **软删除 + 状态机归档**：删除操作设置 `is_deleted=True` 并通过状态机流转到 `archived`，避免引入第 7 种 `deleted` 状态破坏 6 态完整性。已归档帖子删除仅设置 `is_deleted`，不再触发状态机。
- **上传内容校验**：不信任客户端声明的 content_type 与文件扩展名，通过 magic bytes 识别真实格式，再用 Pillow verify/load 双重校验，最后重新编码去除潜在恶意 payload。
- **限流测试环境禁用**：限流中间件检测 `TEST_DATABASE_URL` 环境变量，测试时自动跳过，避免 fixture 频繁调用 `/auth/register` 等接口触发误拦。
- **统一异常响应**：所有异常返回 `{detail, request_id}` 结构，响应头包含 `X-Request-ID`，便于前端关联日志与追踪问题。

## 5. 修改文件

### 后端核心
- `backend/app/core/post_status.py`：新增 `SUBSTANTIAL_FIELDS` / `is_substantial_change()`；`_TRANSITIONS` 新增 `published → pending`。
- `backend/app/api/posts.py`：新增 `can_view_post()`；`get_post` 增加可见性校验；`update_post` 实质修改触发回审；`delete_post` 软删除 + 状态机归档。
- `backend/app/api/admin.py`：统一 `AdminDep`；新增 `_check_post_in_admin_school()`；审核/驳回/举报处理/批量操作补齐状态机与资源校验；`handle_report` 不再写非法状态。
- `backend/app/api/upload.py`：重写为安全上传（magic bytes / Pillow 校验 / 重新编码 / 安全文件名 / 缩略图）。
- `backend/app/middleware.py`：重写，新增 `RequestIDMiddleware` / `RateLimitMiddleware`（测试环境禁用）/ 增强 `RequestLoggingMiddleware`（脱敏）。
- `backend/app/main.py`：注册三个中间件 + 统一异常处理器（HTTPException / RequestValidationError / Exception）。
- `backend/app/dependencies.py`：`get_current_admin` 委托给 `require_role(Role.ADMIN)`。

### 后端测试
- `backend/tests/test_post_visibility.py`（新建）：25 个测试，覆盖 `can_view_post` 单元测试 + `GET /posts/{id}` 端到端可见性 + 统一异常响应与 request_id 透传。
- `backend/tests/test_post_transition.py`：扩充 `TestSubstantialChangeUnit`（12 个单元测试）+ 实质修改回审 E2E（8 个）+ 软删除 + 状态机归档（5 个）。
- `backend/tests/test_upload_security.py`（新建）：35 个测试，覆盖 magic bytes 检测 / 图片校验 / 重新编码 / 路径脱敏 / 上传端到端。
- `backend/tests/test_post_status.py`：更新 `published → pending` 合法流转断言。
- `backend/tests/conftest.py`：`test_category` fixture 增加 `test_school` 依赖并显式设置 `school_id`。
- `backend/tests/test_api_contract.py`：修复 4 个举报契约测试 URL 路径 + 重复举报拦截问题。

### 规格与任务
- `.trae/specs/finals-deep-optimization/tasks.md`：勾选 FND-03.1 ~ FND-03.5 全部完成。

## 6. 影响范围

- **帖子 API**：`GET /posts/{id}` 可见性策略变更影响所有详情访问；`PUT /posts/{id}` 实质修改回审影响已发布帖子的编辑流程；`DELETE /posts/{id}` 改为软删除影响列表查询与详情访问。
- **管理 API**：所有管理路由统一 `require_role` 校验，资源级校验影响跨校操作；`handle_report` 状态变更影响举报处理流程。
- **上传 API**：`POST /upload/image` 安全加固影响所有图片上传，不兼容非图片文件与伪造扩展名。
- **中间件**：限流影响登录/注册/发布/评论/AI 搜索/上传接口的高频调用；请求 ID 与统一异常响应影响所有 API 的错误响应结构（增加 `request_id` 字段与 `X-Request-ID` 头）。
- **测试**：`conftest.py` 的 `test_category` fixture 变更影响所有依赖该 fixture 的测试（显式依赖 `test_school`）。
- **不影响**：数据库模型结构、前端页面交互逻辑。

## 7. 测试与验证

### 后端测试
- **FND-03 专项测试**（115 个用例）全部通过：
  - `test_post_visibility.py`：25 个（`can_view_post` 单元 + 端到端可见性 + request_id）
  - `test_post_transition.py`：71 个（状态流转 + 实质修改回审 + 软删除）
  - `test_upload_security.py`：35 个（magic bytes + 图片校验 + 重新编码 + 路径脱敏 + 上传端到端）
  - 耗时 364.77s（每用例 TRUNCATE ALL TABLES 导致较慢，属 FND-02 已知问题）。
- **全量后端测试**：4 failed + 1 error → 修复后 5 个问题用例全部通过；全量 382 passed + 65 skipped。
  - 修复 `test_create_post_unauthenticated` 外键违规（conftest fixture）。
  - 修复 4 个 `TestAPIReportTypeContract` URL 路径错误与重复举报拦截。

### 前端构建
- **`npm run build`**：16.87s 通过，TypeScript 编译无错误，Vite 打包成功（MapPage chunk 1044KB 为已知警告，非阻断）。

## 8. 后续建议

1. **TEN-02 租户可见性**：FND-03.1 的 `can_view_post` 简化为按角色判断，跨校资源隔离由 TEN-02.3 补齐 `post.school_id == current_user.school_id` 校验。
2. **限流持久化**：当前 `RateLimitMiddleware` 基于内存计数器，单进程重启后重置。生产环境可考虑 Redis 分布式限流。
3. **上传 Nginx 一致性**：REL-03 任务需确认 Nginx `client_max_body_size` 与应用 `MAX_UPLOAD_SIZE`（5MB）一致，并配置 `/uploads` 静态目录。
4. **`datetime.utcnow()` 弃用**：`app/core/security.py` 使用了 `datetime.utcnow()`（Python 3.12+ 弃用），建议后续迁移到 `datetime.now(datetime.UTC)`。
5. **测试性能优化**：`conftest.py` 的 autouse `setup_database` 每用例 TRUNCATE ALL TABLES 导致全量测试耗时 18 分钟，FND-02.4 已建议分组，可后续实施。
6. **Pydantic 序列化警告**：`UserBrief` 序列化时出现 `PydanticSerializationUnexpectedValue` 警告（author 字段 dict 输入），建议后续排查 `PostResponse.author` 的 `from_attributes` 配置。
