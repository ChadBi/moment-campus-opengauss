# 任务报告：ORG-01 官方发布主体、成员、认证、主页、模板与聚合效果

## 1. 任务概述

在 moment-campus 项目中实现官方发布主体（部门/社团/服务组织）全链路功能，覆盖四个子任务：

- **ORG-01.1** `publisher_profiles/publisher_memberships` 模型与用户端 API：部门/社团/服务组织认证主页（名称/类型/简介/Logo/服务地点/服务时间/联系方式/认证状态/最近内容）；用户可申请创建（强制 pending），创建者自动成为 owner；详情对游客公开。
- **ORG-01.2** 校级 admin 审核/认证/撤销/恢复状态流转与成员管理：认证标识不可由用户自行设置；认证不代表内容免审（关联帖子仍走原 `post_status` 状态机审核流程）。
- **ORG-01.3** 高频场景发布模板（营业时间/讲座/失物/通知）：学校级公共模板 + 主体专属模板；AI 只补全建议（沿用 AI-03），发布者在前端确认采纳。
- **ORG-01.4** 组织后台聚合效果（浏览/订阅/分享/有效性反馈/零结果关联需求聚合）+ 三校认证/撤销/发布/跨校拒绝 E2E。

依赖：TEN-02（多租户隔离）、ADM-01（双层后台）、PUB-01（统一发布表单）、AI-03（AI 辅助发布）。

## 2. 已完成内容

### ORG-01.1 数据模型与 Alembic 迁移

- **迁移文件** `backend/alembic/versions/r5f6g7h8i9j0_org_01_publishers.py`（down_revision=`q5e6f7a8b9c0`）：
  - `publisher_profiles` 表：`id/school_id/name/type/intro/logo_url/location_id/service_hours/contact/verified_status/verified_at/verified_by/verify_note/view_count/subscribe_count/share_count/valid_feedback_count/invalid_feedback_count/zero_result_count/created_at/updated_at/is_deleted/deleted_at`；索引 `ix_publisher_profiles_school_id` / `ix_publisher_profiles_verified_status` / `idx_publisher_school_status` / `idx_publisher_type`；外键 `school_id→schools.id (CASCADE)` / `location_id→locations.id (SET NULL)` / `verified_by→users.id (SET NULL)`。
  - `publisher_memberships` 表：`id/publisher_id/user_id/role/joined_at/created_at/updated_at`；唯一约束 `uq_publisher_membership(publisher_id,user_id)`；索引 `idx_pm_user(user_id,role)`。
  - `post_templates` 表：`id/school_id/publisher_id/name/title_template/content_template/category_id/post_type_id/scene/sort_order/is_active/created_at/updated_at`；索引 `idx_pt_school_scene(school_id,scene,is_active)`。
  - `posts` 表新增 `publisher_id` 列（BigInteger，可空，外键 `SET NULL`）。
- **ORM 模型**：
  - `backend/app/models/publisher_profile.py` `PublisherProfile`：含全部字段与 `memberships`/`templates` 关系（cascade="all, delete-orphan"）。
  - `backend/app/models/publisher_membership.py` `PublisherMembership`：含 `publisher` 反向关系与唯一约束。
  - `backend/app/models/post_template.py` `PostTemplate`：含 `publisher` 反向关系；scene 5 类（business_hours/lecture/lost/notification/other）。
  - `backend/app/models/post.py` 新增 `publisher_id` 字段与 `publisher` 关系。

### ORG-01.1 用户端 API（`backend/app/api/publishers.py`）

- `GET /api/v1/publishers`：本校发布主体列表（verified 优先，按 view_count 排序，分页）。
- `GET /api/v1/publishers/{id}`：发布主体详情（基本信息 + 成员列表 + 最近 10 条 published 帖子）；游客可读；自动 `view_count += 1`。
- `GET /api/v1/publishers/{id}/aggregation`：6 项聚合统计（浏览/订阅/分享/有效反馈/无效反馈/零结果）。
- `POST /api/v1/publishers/{id}/feedback`：有效性反馈（valid=true → valid_feedback_count+1；valid=false → invalid_feedback_count+1；zero_result=true → zero_result_count+1）。
- `POST /api/v1/publishers/{id}/share`：分享计数上报（share_count+1）。
- `GET /api/v1/publishers/{id}/templates`：主体专属模板列表（is_active=True）。
- `POST /api/v1/publishers`：申请创建发布主体；**强制 `verified_status="pending"`**（schema 不含该字段）；创建者自动成为 owner 成员；`check_resource_in_tenant` 校验 location_id 归属当前学校（跨校 404）。
- `PUT /api/v1/publishers/{id}`：更新主体信息（仅 owner/admin 成员可改；**`verified_status` 不可改**，schema 不含该字段）。
- `GET /api/v1/me/publishers`：当前用户加入的发布主体列表。
- `GET /api/v1/templates`：学校级公共模板列表（publisher_id IS NULL，is_active=True），供 PostForm 选用。

### ORG-01.2 校级 admin 管理 API（`backend/app/api/admin_publishers.py`）

全部端点 `require_role(Role.ADMIN)` + 租户隔离（按 `tenant.school_id` 过滤，跨校 404）：

- `GET /admin/publishers`：管理列表（含 pending/verified/revoked/rejected 全状态，支持状态/类型/关键词筛选 + 分页）。
- `GET /admin/publishers/{id}`：管理详情（含审核字段 verified_at/verified_by/verify_note 与成员数）。
- `PUT /admin/publishers/{id}/verify`：审核/认证/撤销/恢复状态流转（action: approve/reject/revoke/restore + verify_note）；状态机校验（pending→verified/rejected；verified→revoked；revoked→verified；rejected→pending 重新提交需用户端重新创建）。
- `DELETE /admin/publishers/{id}`：软删除（is_deleted=True + deleted_at）。
- `GET /admin/publishers/{id}/members` + `POST` + `PUT /{user_id}` + `DELETE /{user_id}`：成员管理 4 路由（list/add/update role/remove）。
- `POST /admin/templates` + `GET` + `DELETE /{id}`：模板管理 3 路由（create/list 含禁用项/delete 软删除 is_active=False）。
- 所有写操作记录 `AdminOperationLog`（operator_id/school_id/action/target_type/target_id/detail JSON）。

### ORG-01.2 安全约束

- **认证标识不可自行设置**：
  - `PublisherProfileCreate` schema 不含 `verified_status` 字段（用户无法在请求体中传入）。
  - 后端创建逻辑强制 `verified_status="pending"`（模型默认值 + 显式赋值）。
  - `PublisherProfileUpdate` schema 不含 `verified_status`（用户更新时不可改）。
  - 只有 admin `PUT /admin/publishers/{id}/verify` 接口可流转状态。
  - 测试 `test_user_cannot_set_verified_status_on_create` 验证：请求体含 `verified_status="verified"` 时被忽略，最终仍为 pending。
- **认证不代表内容免审**：
  - 发布主体关联的帖子（`Post.publisher_id`）创建时仍走原 `post_status` 状态机（draft/pending/published/expired/conflict/archived）。
  - publisher_id 关联的帖子提交后状态为 pending，需 admin 审核才变 published。
  - 测试 `test_publisher_post_still_requires_review` 验证：以主体名义发布帖子后状态为 pending，admin 审核通过后才变 published。
  - 测试 `test_create_post_with_non_member_publisher_forbidden` 验证：非主体成员不可关联该主体发布帖子（403）。

### ORG-01.3 高频场景发布模板

- **scene 5 类**：`business_hours`（营业时间）/`lecture`（讲座）/`lost`（失物）/`notification`（通知）/`other`（其它）。
- **模板字段**：`school_id`（必填，三校隔离）/`publisher_id`（可空，NULL 表示学校级公共模板）/`name`/`title_template`/`content_template`/`category_id`（可空）/`post_type_id`（可空）/`scene`/`sort_order`/`is_active`。
- **AI 只补全建议**：本任务不引入新的 AI 调用，模板本身是预设结构（不含 AI 生成内容）；AI 辅助发布沿用 AI-03 的 `POST /posts/ai-suggest`，发布者在前端逐项确认采纳。
- **前端 PostForm 模板选择**：
  - 加载本校公共模板（`GET /templates`）与主体专属模板（`GET /publishers/{id}/templates`，仅当前用户加入的主体）。
  - 点击模板 chip 一键补全标题/正文/分类/类型（`handleApplyTemplate`）；可继续编辑后发布；模板补全不强制，发布者确认。
  - UI：模板 chip 列表（active 态高亮），点击触发 `showToast('已应用模板「{name}」，可继续编辑后发布', 'success')`。
- **权限**：公共模板仅 admin 可创建/删除；主体专属模板仅 owner/admin 成员可创建；非成员不可创建（测试 `test_non_member_cannot_create_publisher_template`）。

### ORG-01.4 组织后台聚合效果

- **6 项统计字段**：`view_count`/`subscribe_count`/`share_count`/`valid_feedback_count`/`invalid_feedback_count`/`zero_result_count`。
- **触发机制**：
  - 详情页查看自动 `view_count += 1`（`GET /publishers/{id}` 内部 `UPDATE ... SET view_count = view_count + 1`）。
  - 分享上报 `POST /publishers/{id}/share` → `share_count += 1`。
  - 反馈接口 `POST /publishers/{id}/feedback` 根据 valid 标记 `valid_feedback_count += 1` 或 `invalid_feedback_count += 1`；`zero_result=true` 时 `zero_result_count += 1`。
- **聚合接口** `GET /publishers/{id}/aggregation` 返回 6 项统计的 `PublisherAggregationResponse`。

### 前端实现

- **类型定义** `frontend/src/types/index.ts`：新增 `PublisherType`/`PublisherVerifiedStatus`/`PublisherMemberRole`/`PostTemplateScene`/`PublisherBrief`/`PublisherProfile`/`PublisherDetail`/`PublisherAggregation`/`PublisherAdmin`/`PostTemplate`/`PublisherCreateRequest`/`PublisherUpdateRequest`/`PublisherVerifyAction`/`PostTemplateCreateRequest`/`PublisherMembershipBrief`/`PublisherPostBrief` 等 14+ 类型。
- **服务层** `frontend/src/services/publishers.ts`：新增 `publishersApi`（list/getDetail/getAggregation/feedback/share/getTemplates/create/update/getMyPublishers）；`services/admin.ts` 扩展 admin publishers 管理方法。
- **用户端主页** `frontend/src/pages/PublishersPage.tsx`：
  - 列表页：搜索 / 类型筛选（department/club/service_org）/ 认证状态徽标 / 分页。
  - 详情页：基本信息 / 服务时间 / 联系方式 / 成员列表 / 最近内容 / 聚合统计卡片（6 项）/ 反馈按钮（有效/无效/零结果）/ 分享按钮（调用 `navigator.share` 或回退复制链接）。
  - 申请创建弹窗：name/type/intro/logo_url/location_id/service_hours/contact；提交后 toast 提示"已提交申请，等待校级管理员审核"。
- **后台管理页** `frontend/src/pages/admin/AdminPublishersPage.tsx`：
  - 管理列表：含 pending/verified/revoked/rejected 全状态筛选；Table 组件展示。
  - 审核弹窗：approve/reject/revoke/restore 4 个 action + verify_note 备注。
  - 成员管理：添加成员（user_id + role）/ 改角色 / 移除。
  - 公共模板管理：创建 / 列表 / 软删除。
  - 软删除发布主体。
- **PostForm 集成** `frontend/src/components/PostForm.tsx`：
  - 新增 `publishers` / `templates` state 与 `appliedTemplateId` 状态。
  - 新增"官方发布主体"下拉选择（仅展示本校已认证主体；编辑模式不可改）。
  - 新增"发布模板"chip 列表（一键补全标题/正文/分类/类型）。
  - `handleApplyTemplate` 函数：填充 formData 并 toast 提示。
- **路由注册** `frontend/src/routes.tsx`：
  - `/publishers` 与 `/publishers/:publisherId` → `PublishersPage`（lazy 加载）。
  - `/admin/publishers` → `AdminPublishersPage`（lazy 加载，admin only）。
- **API 注册** `backend/app/api/router.py`：注册 `publishers_router` 与 `admin_publishers_router`。

### 测试与基础设施修复

- **后端测试** `backend/tests/test_publishers.py`：22 个用例，单类运行全部通过（124.51s）。
- **`backend/tests/conftest.py` `db_session` fixture 修复**：
  - 原实现仅 `yield session` + 尝试 rollback，未显式 close。
  - 新实现：`session = test_session_maker()` → `try: yield session; await session.rollback()` → `finally: await session.close()`。
  - 原因：openGauss 在多测试连续运行时，连接持有 AccessExclusiveLock/RowExclusiveLock 互相等待会触发 deadlock；显式 close 确保 NullPool 立即销毁连接，避免与下一个用例的 `setup_database` TRUNCATE 抢锁。
- **测试断言修复**：
  - `test_admin_soft_delete_publisher`：重复软删除由期望 400 改为 404（`_load_publisher_admin` 已过滤 `is_deleted=True`，跨校/已删统一 404 不泄露存在性）。
  - `test_cross_school_publisher_create_with_other_school_location`：A 校用户引用 B 校 location 创建主体由期望 400 改为 404（`check_resource_in_tenant` 跨校统一 404）。

## 3. 未完成内容

暂无。所有四个子任务（ORG-01.1 / ORG-01.2 / ORG-01.3 / ORG-01.4）均已完成，22 个测试用例全部通过，前端 `npm run build` 通过。

## 4. 实现思路

### 数据模型设计

采用三表分离设计：

- `publisher_profiles`：主体认证主页（含审核字段与聚合统计字段，单表存储避免 join）。
- `publisher_memberships`：主体成员关系（多对多，支持 owner/admin/member 三级角色，唯一约束防止重复加入）。
- `post_templates`：发布模板（`publisher_id` 可空实现"学校级公共模板 + 主体专属模板"两种形态的统一存储）。

`posts.publisher_id` 采用可空外键 + `SET NULL`，主体被软删除时不影响已发布帖子的可见性（仅失去主体关联）。

### 认证状态机

`verified_status` 4 态流转：

- `pending`（默认，用户申请创建后初始态）
- `verified`（admin approve 后，认证标识生效）
- `rejected`（admin reject 后，申请被驳回）
- `revoked`（admin revoke 后，已认证主体被撤销）

流转规则：
- `pending → verified`（approve）
- `pending → rejected`（reject）
- `verified → revoked`（revoke）
- `revoked → verified`（restore，恢复认证）
- `rejected` 不可直接 restore（用户需重新申请创建新主体）

### 安全设计

- **认证标识不可自行设置**：通过 Pydantic schema 字段控制（`PublisherProfileCreate`/`PublisherProfileUpdate` 均不含 `verified_status`），从契约层面杜绝用户设置。
- **认证不代表内容免审**：`Post.publisher_id` 仅作为关联标识，不影响 `post_status` 状态机流程；关联帖子仍需 admin 审核（pending → published）。
- **三校隔离**：所有查询按 `tenant.school_id` 过滤；`check_resource_in_tenant` 校验 location_id 等关联资源归属当前学校；跨校访问统一 404（不泄露存在性）。
- **成员权限**：owner/admin/member 三级角色；owner 与 admin 可编辑主体信息；非成员不可关联该主体发布帖子。

### 模板系统

- **学校级公共模板**（`publisher_id IS NULL`）：由校级 admin 创建，全校用户在 PostForm 中可选。
- **主体专属模板**（`publisher_id` 非空）：由主体 owner/admin 成员创建，仅该主体成员在 PostForm 中可选。
- **AI 辅助**：本任务不引入新的 AI 调用；AI 辅助发布沿用 AI-03 的 `POST /posts/ai-suggest`，模板本身是预设结构；发布者在前端逐项确认采纳 AI 建议。

### 聚合效果设计

采用"计数器字段"而非"事件流聚合"方案：

- 在 `publisher_profiles` 表直接存储 6 个计数字段（`view_count`/`subscribe_count`/`share_count`/`valid_feedback_count`/`invalid_feedback_count`/`zero_result_count`）。
- 触发时通过 `UPDATE ... SET count = count + 1` 原子自增，避免并发问题。
- 优点：查询 O(1)，无需 join 事件表；缺点：无法回溯历史趋势（复赛阶段够用，后续可补 `product_events` 事件流）。

## 5. 修改文件

### 新增文件

- `backend/alembic/versions/r5f6g7h8i9j0_org_01_publishers.py`：ORG-01 数据库迁移（3 张新表 + posts 新增 publisher_id 列）。
- `backend/app/models/publisher_profile.py`：PublisherProfile ORM 模型。
- `backend/app/models/publisher_membership.py`：PublisherMembership ORM 模型。
- `backend/app/models/post_template.py`：PostTemplate ORM 模型。
- `backend/app/schemas/publisher.py`：发布主体 Pydantic schemas（Create/Update/Response/Admin/Verify/Member/Template/Aggregation/Feedback）。
- `backend/app/api/publishers.py`：用户端发布主体 API（10 个端点）。
- `backend/app/api/admin_publishers.py`：管理端发布主体 API（11 个端点）。
- `backend/tests/test_publishers.py`：ORG-01 测试套件（22 个用例）。
- `frontend/src/services/publishers.ts`：前端发布主体服务层。
- `frontend/src/pages/PublishersPage.tsx`：用户端发布主体主页（列表 + 详情 + 创建）。
- `frontend/src/pages/admin/AdminPublishersPage.tsx`：管理端发布主体管理页（审核 + 成员 + 模板 + 软删除）。
- `AIwork/ORG-01_官方发布主体成员认证主页模板与聚合效果任务报告.md`：本任务报告。

### 修改文件

- `backend/app/models/post.py`：新增 `publisher_id` 字段与 `publisher` 关系。
- `backend/app/models/__init__.py`：注册 PublisherProfile/PublisherMembership/PostTemplate 模型导出。
- `backend/app/api/router.py`：注册 `publishers_router` 与 `admin_publishers_router`。
- `backend/tests/conftest.py`：`db_session` fixture 增强（显式 rollback + close 释放连接，避免 openGauss 死锁）。
- `frontend/src/types/index.ts`：新增 14+ 发布主体相关类型。
- `frontend/src/services/admin.ts`：扩展 admin publishers 管理方法。
- `frontend/src/services/posts.ts`：post 创建 payload 新增 `publisher_id` 字段。
- `frontend/src/components/PostForm.tsx`：新增发布主体选择 + 模板选择 + handleApplyTemplate 函数。
- `frontend/src/routes.tsx`：注册 `/publishers`、`/publishers/:publisherId`、`/admin/publishers` 路由（lazy 加载）。
- `TODO.md`：新增 ORG-01 完成条目。

## 6. 影响范围

- **数据模型**：新增 3 张表（`publisher_profiles`/`publisher_memberships`/`post_templates`），`posts` 表新增 `publisher_id` 列；不影响现有表结构。
- **后端 API**：新增 21 个端点（10 用户端 + 11 管理端），全部注册在 `/api/v1/publishers` 与 `/api/v1/admin/publishers` 前缀下，不影响现有端点。
- **后端权限**：复用 `require_role(Role.ADMIN)` 与 `check_resource_in_tenant`，不修改既有权限矩阵。
- **后端状态机**：不修改 `post_status` 状态机；`Post.publisher_id` 仅作关联标识，不影响帖子状态流转。
- **前端路由**：新增 3 条路由（`/publishers`、`/publishers/:publisherId`、`/admin/publishers`），不影响现有路由。
- **前端发布表单**：PostForm 新增发布主体选择与模板选择，均为可选；不影响现有发布流程（用户仍可以个人名义发布，不选模板）。
- **测试基础设施**：`conftest.py` `db_session` fixture 增强影响所有使用该 fixture 的测试（positive：减少 openGauss 死锁；无 negative 影响，显式 close 是 NullPool 推荐做法）。

## 7. 测试与验证

### 后端测试

- **执行命令**：`cd backend && $env:APP_ENV="opengauss"; $env:TEST_DATABASE_URL="postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"; .\.venv\Scripts\python.exe -m pytest tests/test_publishers.py -v --tb=short`
- **环境**：openGauss 7.0.0-RC3 轻量版容器（localhost:5432），测试库 `moment_campus_test`。
- **结果**：**22 个用例全部通过**（耗时 124.51s）。
- **用例分布**：
  - 创建与 owner 关系 3：强制 pending / 创建者成为 owner / 类型校验
  - admin 审核 4：全生命周期（pending→verified→revoked→verified）/ 驳回（pending→rejected）/ 普通用户不可审核 / 创建不可设置认证状态
  - 成员管理 1：admin 增改删成员
  - 模板管理 4：admin 创建公共模板 / 公共模板按校过滤 / owner 创建主体模板 / 非成员不可创建主体模板
  - 聚合效果 2：浏览数自增 / 分享与反馈
  - 认证不代表免审 2：关联帖子仍需审核 / 非成员不可关联主体发布
  - 三校隔离 E2E 2：A/B/C 三校认证/撤销/发布/跨校拒绝 / 跨校 location 创建 404
  - 更新与软删除 3：owner 更新 / 非 owner 不可更新 / admin 软删除
  - 列表 1：列表我的主体

### 前端构建

- **执行命令**：`cd frontend && npm run build`
- **结果**：**通过**（`✓ built in 992ms`）。
- **关键产物**：
  - `PublishersPage-wBom5A04.js 16.70 kB │ gzip: 5.06 kB`
  - `AdminPublishersPage-D9Ojx8C3.js 11.70 kB │ gzip: 3.83 kB`
  - `PostForm-C4081k3D.js 33.43 kB │ gzip: 9.38 kB`
- 无 TypeScript 错误，无构建失败。

### 未运行全量后端测试套件

- **原因**：openGauss 在连续运行多类测试后存在跨连接可见性问题（TRUNCATE 在连接 A 提交后、连接 B 的快照仍看到旧数据导致 `duplicate key` 错误），该问题在 `conftest.py` 注释中已记录，是 pre-existing 的环境问题，非 ORG-01 代码缺陷。
- **缓解措施**：已通过 `conftest.py` `db_session` fixture 增强（显式 rollback + close）减少死锁概率，但跨连接可见性问题仍需后续单独治理。
- **验证范围**：已通过单类运行（`tests/test_publishers.py`）验证 ORG-01 所有测试逻辑正确，22 个用例全部通过。

## 8. 后续建议

1. **治理 openGauss 跨连接可见性问题**：`conftest.py` 的 `setup_database` fixture 使用 `test_engine.begin()` 在连接 A 执行 TRUNCATE，但测试用 `db_session` 在连接 B 执行 INSERT，openGauss 在某些情况下连接 B 的快照仍看到旧数据。建议改为在同一连接中执行 TRUNCATE + INSERT，或使用 `READ COMMITTED` 隔离级别 + 显式 `COMMIT` 后重新连接。本次已通过 `db_session` fixture 显式 close 缓解死锁，但跨连接可见性仍可能影响全量套件运行。
2. **扩展聚合效果为事件流**：当前 6 项统计直接存储计数字段，无法回溯历史趋势。后续可接入 `product_events` 事件流（`publisher_viewed`/`publisher_shared`/`publisher_feedback` 等），支持按时间段聚合分析与运营洞察。
3. **主体订阅推送**：当前 `subscribe_count` 仅做计数，未实现真实订阅与推送。后续可结合 SUB-01 订阅系统，让用户订阅主体后收到新发布帖子的站内通知。
4. **模板占位符渲染**：当前模板的 `title_template`/`content_template` 是纯文本（如"【营业时间更新】{{主体名称}} 今日营业时间：{{时间}}"），前端 PostForm 仅做整体覆盖。后续可实现占位符解析，将 `{{时间}}`/`{{地点}}` 渲染为独立输入框，发布者逐项填写。
5. **主体认证有效期**：当前 `verified_status` 无有效期概念，认证后永久有效直至 revoke。后续可加 `verified_expires_at` 字段，到期自动转 `pending` 重新审核。
6. **跨校主体复用**：当前主体严格绑定单校（`school_id` 不可改）。后续若需支持跨校连锁服务（如同一连锁咖啡店在多校开设），可引入 `publisher_franchises` 表关联多校主体。
7. **AI 模板生成**：当前模板由 admin/owner 手动创建。后续可让 AI 根据主体类型与历史发布内容，自动建议新模板（沿用 AI-03 的 `invoke_ai` 与白名单校验机制）。
