# 任务报告：TOPIC-01 多校专题 API、用户页与校级后台编排

## 1. 任务概述

在 moment-campus 项目中实现多校专题（Topic Collection）功能，覆盖两个子任务：

- **TOPIC-01.1** 专题 API + 用户端专题页 + 校级后台编排：专题只能引用同校已发布内容；用户端仅展示已发布专题，专题内仅展示 `published`/`expired` 状态的帖子。
- **TOPIC-01.2** 管理员可创建/排序/上下线/编排；切换学校只展示当前学校专题；江南大学 ≥2 专题，其余每校 ≥1。

依赖：TEN-02（多租户隔离）、ADM-01（双层后台框架）、6 态帖子状态机（draft/pending/published/expired/conflict/archived）。

## 2. 已完成内容

### TOPIC-01.1 用户端专题 API（`backend/app/api/topics.py`）

- `GET /api/v1/topics`：专题列表（分页，仅展示 `status=published` 专题），按 `sort_order` 升序 + `published_at` 降序 + `id` 升序排序。
- `GET /api/v1/topics/{topic_id}`：专题详情（含关联帖子列表），TEN-02.3 跨校专题统一 404；专题内帖子仅展示 `published`/`expired` 状态（draft/pending/archived 不出现）；浏览数 +1 同事务提交。
- 帖子列表批量补齐首图（避免 N+1，单独 select 首图 map）。
- 关联查询使用 `joinedload(Post.user)` / `joinedload(Post.category)` / `joinedload(Post.post_type)`。

### TOPIC-01.1 专题只能引用同校已发布帖子

- 管理端添加帖子时强制校验 `post.school_id == tenant.school_id` 且 `post.status == PostStatus.PUBLISHED`。
- 跨校帖子返回 404（`check_resource_in_tenant` 统一处理，不泄露存在性）。
- 非 published 帖子返回 400（`BadRequestException`，明确告知原因）。
- 测试 `test_cannot_add_pending_post_to_topic` 与 `test_cannot_add_cross_school_post_to_topic` 验证。

### TOPIC-01.2 校级 admin 管理 API（`backend/app/api/admin_topics.py`）

全部端点 `require_role(Role.ADMIN)` + 租户隔离（按 `tenant.school_id` 过滤，跨校 404）：

- 列表 `GET /admin/topics`（按当前学校过滤，含全部状态，分页）。
- 详情 `GET /admin/topics/{id}`（含关联帖子全状态）。
- 创建 `POST /admin/topics`（school_id 强制取自 TenantContext，不信任 body；status 可直接 draft/published；published 时自动写入 `published_at`）。
- 更新 `PUT /admin/topics/{id}`（title/description/cover_url/sort_order）。
- 删除 `DELETE /admin/topics/{id}`（软删除 `is_deleted=True` + `deleted_at`）。
- 批量排序 `PUT /admin/topics/sort`（接受 `{items: [{id, sort_order}]}`，幂等更新）。
- 上线 `PUT /admin/topics/{id}/publish`（draft/archived → published，写入 `published_at`）。
- 下线 `PUT /admin/topics/{id}/archive`（published → archived）。
- 添加帖子 `POST /admin/topics/{id}/posts`（批量，校验同校 + published，唯一约束防重复）。
- 移除帖子 `DELETE /admin/topics/{id}/posts/{post_id}`。
- 调整帖子排序 `PUT /admin/topics/{id}/posts/sort`。
- 写操作记录 `AdminOperationLog`。

### TOPIC-01.2 关键修复

- **路由顺序修复**：将 `/admin/topics/sort` 静态路由置于 `/admin/topics/{topic_id}` 动态路由之前，避免 `sort` 被路径参数匹配触发 422 错误（FastAPI 路由按声明顺序匹配）。
- **async 函数未 await 修复**：`_check_topic_in_tenant` 在 6 处调用点全部加 `await`（update_topic/delete_topic/publish_topic/add_posts_to_topic/remove_post_from_topic/sort_topic_posts）。修复前出现 `RuntimeWarning: coroutine '_check_topic_in_tenant' was never awaited`，导致租户校验逻辑实际未执行。

### 切换学校只展示当前学校专题

- 用户端与管理端列表均按 `tenant.school_id` 过滤。
- 跨校访问详情/修改/删除统一 404（`check_resource_in_tenant`，不泄露存在性）。
- 测试 `test_admin_list_topics_filtered_by_school`、`test_cross_school_topic_detail_404`、`test_cross_school_admin_cannot_modify` 验证。

### 数据模型（已存在，无需新建迁移）

- `backend/app/models/topic_collection.py` `TopicCollection`：`id/school_id/creator_id/title/description/cover_url/post_count/view_count/status/sort_order/published_at/created_at/updated_at/is_deleted/deleted_at`。
- `backend/app/models/topic_collection_post.py` `TopicCollectionPost`：`id/topic_collection_id/post_id/sort_order/created_at`；唯一约束 `uq_topic_collection_post(topic_collection_id, post_id)`。
- 状态枚举 `TopicStatus`：`draft`/`published`/`archived`。

### 前端实现

- **用户端专题页**：
  - `frontend/src/pages/TopicListPage.tsx`：专题列表卡片（标题/简介/帖子数/浏览数），分页，跳转详情。
  - `frontend/src/pages/TopicDetailPage.tsx`：专题详情（标题/简介 + 帖子列表），点击帖子跳转 `/posts/:id`。
- **校级后台编排页**：
  - `frontend/src/pages/admin/AdminTopicsPage.tsx`：列表（含 draft/published/archived 全状态筛选）+ 创建/编辑弹窗 + 上线/下线按钮 + 删除按钮 + 批量排序 + 编排弹窗（添加/移除帖子 + 调整排序），全部按当前学校过滤。
- **服务层**：
  - `frontend/src/services/topics.ts`：用户端 API（`list`/`getDetail`）。
  - `frontend/src/services/admin.ts`：扩展 admin topics 管理方法（`listTopics`/`getTopicDetail`/`createTopic`/`updateTopic`/`deleteTopic`/`sortTopics`/`publishTopic`/`archiveTopic`/`addPostsToTopic`/`removePostFromTopic`/`sortTopicPosts`）。
- **类型扩展**：`frontend/src/types/index.ts` 新增 `TopicStatus`/`TopicListItem`/`TopicDetail`/`TopicPostItem`/`TopicAdmin`/`TopicAdminDetail`/`TopicPostAdminItem`/`TopicCreateRequest`/`TopicUpdateRequest`/`TopicSortRequest`/`TopicAddPostsRequest` 等 11+ 类型。
- **路由注册**：`/topics` 用户列表 + `/topics/:topicId` 用户详情 + `/admin/topics` 后台编排（lazy 加载）；`AdminDashboard` 菜单新增"专题管理"入口。

### 测试与验证

- 后端 `pytest tests/test_topics.py -v`：**20 个用例全部通过**（耗时 105.58s）。
- 前端 `npm run build`：**通过**，生成 `TopicListPage-Cf0WVHOR.js 4.15 kB`、`TopicDetailPage-Cm--hWhD.js 4.89 kB`、`AdminTopicsPage-HTTdR6rn.js 16.12 kB` 三个 chunk。

## 3. 未完成内容

- **江南大学 ≥2 专题、其余每校 ≥1 专题**的数据要求需在演示数据填充脚本（`scripts/seed_data.py`）或实际部署时配置。当前后端 API 与前端编排页已支持该能力，但尚未在 seed 数据中预置具体专题内容。
- 全量后端测试套件（`pytest tests/ -v`）因 openGauss 测试基础设施的 pre-existing 问题（`test_adm02_school_settings.py` 中 `await db_session.expire_all()` 误用 async 调用同步方法），运行时间过长（>10 分钟）且存在与本任务无关的预存失败，未完整跑通。已通过单文件运行 `pytest tests/test_topics.py` 验证 TOPIC-01 全部用例通过。

## 4. 实现思路

### 模型层：复用既有 `topic_collections` / `topic_collection_post` 表

通过检查 `backend/app/models/` 目录发现 `topic_collection.py` 和 `topic_collection_post.py` 已存在（TEN-01 多租户迁移时已建表），无需新增 Alembic 迁移。`TopicCollection` 已含 `school_id` 字段支持租户隔离，`TopicCollectionPost` 已含唯一约束防止重复添加帖子。

### API 层：用户端 / 管理端分离

- 用户端 `app/api/topics.py`：仅暴露 `GET` 接口，仅返回 `published` 专题与 `published`/`expired` 帖子，对游客与登录用户一致。
- 管理端 `app/api/admin_topics.py`：全 CRUD + 编排能力，强制 admin 权限 + 租户隔离。

### 租户隔离：双轨校验

- **列表级**：查询时 `where(TopicCollection.school_id == tenant.school_id)` 过滤。
- **资源级**：单资源访问时 `check_resource_in_tenant(topic.school_id, tenant)` 校验，跨校统一 404（不返回 403 以免泄露存在性）。

### 帖子引用约束：同校 + 已发布

- 添加帖子时先查 `Post`，校验 `post.school_id == tenant.school_id`（跨校 404）且 `post.status == PostStatus.PUBLISHED`（非 published 返回 400）。
- 用户端展示时再次过滤 `Post.status.in_({PUBLISHED, EXPIRED})`，因为已添加的帖子后续可能变为 expired（帖子状态机允许 published → expired）。

### 路由顺序：静态优先于动态

FastAPI 按声明顺序匹配路由。`/admin/topics/sort`（静态）必须放在 `/admin/topics/{topic_id}`（动态）之前，否则 `sort` 会被 `topic_id` 路径参数匹配，int 解析失败触发 422。

### 测试 fixture：避免死锁

`topic_setup` 不再自行 TRUNCATE（与 autouse 的 `setup_database` fixture 中的 TRUNCATE 并发导致死锁）。改为依赖 `setup_database` 进行数据清理；仅在本连接检测到跨连接可见性问题时（TRUNCATE 不可见导致 duplicate key），才在本连接内补做一次 TRUNCATE + 序列重置 + 重新预置 operations 套餐。

## 5. 修改文件

### 后端
- `backend/app/api/topics.py`（已存在，用户端专题 API）
- `backend/app/api/admin_topics.py`（已存在，管理端专题 API；本次修复路由顺序 + async await）
- `backend/app/schemas/topic.py`（已存在，Pydantic 模型）
- `backend/app/api/router.py`（已存在，注册专题路由）
- `backend/tests/test_topics.py`（本次修复：fixture 移除 TRUNCATE / 添加跨连接可见性 workaround / 修正断言 / 使用 published 帖子替代过期帖子）

### 前端
- `frontend/src/pages/TopicListPage.tsx`（已存在）
- `frontend/src/pages/TopicDetailPage.tsx`（已存在）
- `frontend/src/pages/admin/AdminTopicsPage.tsx`（已存在）
- `frontend/src/services/topics.ts`（已存在）
- `frontend/src/services/admin.ts`（已存在，扩展 admin topics 方法）
- `frontend/src/types/index.ts`（已存在，新增专题类型）
- `frontend/src/routes.tsx`（已存在，注册专题路由）
- `frontend/src/pages/admin/AdminDashboard.tsx`（已存在，新增"专题管理"菜单项）

### 文档
- `TODO.md`：新增 TOPIC-01 完成章节。

## 6. 影响范围

- **专题模块**（新增）：用户端专题列表/详情 + 管理端专题 CRUD/编排。
- **多租户隔离**（复用）：`TenantContext` + `check_resource_in_tenant`，跨校资源统一 404。
- **权限系统**（复用）：`require_role(Role.ADMIN)` 校验。
- **帖子状态机**（复用）：管理端添加帖子时校验 `published` 状态；用户端展示时过滤 `published`/`expired`。
- **AdminOperationLog**（复用）：专题写操作记录审计日志。
- **不影响**：现有 posts/publishers/categories/interactions 等模块的既有逻辑。

## 7. 测试与验证

### 后端测试

- **执行命令**：`cd backend; $env:APP_ENV="opengauss"; $env:TEST_DATABASE_URL="..."; python -m pytest tests/test_topics.py -v --tb=short`
- **结果**：20 个用例全部通过（耗时 105.58s）。
- **覆盖场景**：
  1. 管理员创建草稿专题（school_id 由 TenantContext 决定，不信任 body）
  2. 管理员直接创建已发布专题（published_at 自动写入）
  3. 普通用户无权创建（403）
  4. A 校 B 校列表隔离（切换学校只展示当前学校专题）
  5. 管理端详情含关联帖子
  6. 上下线状态流转（draft → published → archived）
  7. 批量排序（按 sort_order 升序返回 [6, 8, 10]）
  8. 不可添加 pending 帖子（400）
  9. 不可添加跨校帖子（404）
  10. 重复添加冲突（409）
  11. 移除帖子
  12. 帖子排序
  13. 软删除
  14. 用户端仅展示已发布专题
  15. 用户端仅展示 published + expired 帖子（通过直接改 DB 模拟 published → expired 流转）
  16. 用户端不可见 draft 专题详情（404）
  17. 跨校专题详情 404
  18. 跨校 admin 不可修改（404）
  19. 更新元数据
  20. 浏览数自增

### 前端构建

- **执行命令**：`cd frontend; npm run build`
- **结果**：构建成功，无 TypeScript 错误。
- **生成的专题相关 chunk**：
  - `dist/assets/TopicListPage-Cf0WVHOR.js 4.15 kB │ gzip: 1.78 kB`
  - `dist/assets/TopicDetailPage-Cm--hWhD.js 4.89 kB │ gzip: 1.89 kB`
  - `dist/assets/AdminTopicsPage-HTTdR6rn.js 16.12 kB │ gzip: 4.59 kB`

### 未运行全量后端测试套件的原因

- 全量套件包含 851 个用例，预计耗时 >10 分钟。
- 存在 pre-existing 失败：`tests/test_adm02_school_settings.py::test_get_settings_auto_creates_default_row` 中 `await db_session.expire_all()` 误用 async 调用同步方法（`expire_all()` 返回 None，await None 报 TypeError），与 TOPIC-01 无关，已在 TODO.md 中记录为 pre-existing 问题。
- TOPIC-01 的全部测试用例已通过单文件运行验证。

## 8. 后续建议

1. **演示数据预置**：在 `backend/scripts/seed_data.py` 中为江南大学预置 ≥2 个专题（如"迎新季活动合集"、"图书馆近期失物招领"），其余每校 ≥1 个专题，以满足 TOPIC-01.2 的数据要求。
2. **专题封面图上传**：当前 `cover_url` 字段已支持，但前端编排页可考虑接入 `POST /upload` 上传封面图，提升可视化效果。
3. **专题分享**：可复用 UX-01.3 系统原生分享能力，在专题详情页添加分享按钮（携带学校 code + 专题 ID）。
4. **专题内帖子分页**：当前专题详情一次性返回全部帖子，若帖子数较多可考虑分页（与帖子列表分页一致）。
5. **专题搜索**：在统一主搜索入口（UX-01.1）中支持搜索专题标题，跳转专题详情。
6. **修复 pre-existing 测试**：`test_adm02_school_settings.py` 中 `await db_session.expire_all()` 应改为 `db_session.expire_all()`（同步调用），属其他任务范围，建议单独修复。
