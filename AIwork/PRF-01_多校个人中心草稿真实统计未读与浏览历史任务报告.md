# 任务报告：PRF-01 多校个人中心、草稿、真实统计、未读与浏览历史

## 1. 任务概述

在 moment-campus 多租户校园信息平台中实现完整的个人中心功能，覆盖三个子任务：

- **PRF-01.1** 我的帖子按状态分组分页；支持编辑/提交/归档/删除；资料更新同步刷新全局 auth store
- **PRF-01.2** 已发布/草稿/待审核/贡献验证统计用真实后端值；未读数量接口接入页头角标；通知列表分页
- **PRF-01.3** 浏览历史按当前学校隔离，提供最近浏览与清除入口；个人中心展示加入学校/各校角色/默认学校/切换入口

任务对应 [docs/33_TRAE_AI创造力大赛复赛深度优化落地方案_2026.md](../docs/33_TRAE_AI创造力大赛复赛深度优化落地方案_2026.md) 第 1208 行 PRF-01 行项，依赖 TEN-03（学校目录与切换）与 PUB-02（草稿闭环）。

## 2. 已完成内容

### PRF-01.1 我的帖子按状态分组分页

- `GET /users/me/posts?status=` 已在 PUB-02 实现，本次补充跨校隔离校验：按当前学校 TenantContext 过滤，跨校帖子不计入
- 编辑/提交/归档/删除复用 PUB-02 既有草稿闭环与状态机服务
- 资料更新后通过 `useAuthStore.setUser` 同步刷新全局 auth store，所有 UI 组件即时反映昵称/头像变更

### PRF-01.2 真实统计与未读数

- 新增 `GET /users/me/stats` 真实统计接口：
  - 按状态分组聚合（published/draft/pending/expired/conflict/archived/total）
  - 贡献验证数（仅统计 `confirmation` 类型 ValidationRecord，排除 `refutation`）
  - 全部按当前学校 `tenant.school_id` 过滤，跨校帖子/验证不计入
- 新增 `GET /notifications/unread-count` 未读通知数接口：
  - 返回 `{unread_count, has_unread}` 响应结构
  - 按 `user_id` 隔离，排除软删除通知（`is_deleted=False`）
- 前端 Header 角标接入未读数 API，路由切换自动刷新

### PRF-01.3 浏览历史按学校隔离

- `BrowseHistory` 模型扩展：
  - 新增 `school_id`（外键→schools.id）字段实现按校隔离
  - 新增 `viewed_at` 字段记录最近浏览时间（同帖再次访问更新此字段）
  - 唯一索引 `(user_id, school_id, post_id)` 保证同校同帖 upsert
- 帖子详情访问写入浏览历史：`school_id` 取自 `TenantContext`（即 `X-School-Code` 头），而非 `Post.school_id`，确保跨校切换视角时历史归属正确
- 浏览历史接口：
  - `GET /users/me/view-history`：按当前学校过滤 + 分页 + `viewed_at DESC` 排序
  - `DELETE /users/me/view-history`：仅清除当前学校历史，不影响其他学校
  - `DELETE /users/me/view-history/{post_id}`：删除单条，跨校访问返回 404 不泄露存在性
- 个人中心展示加入学校列表：各校角色、默认学校标识、切换入口（集成既有 `useCampusStore` 与 `SchoolSwitcher`）

### 数据库迁移

- Alembic 迁移 `q5e6f7a8b9c0_prf_01_browse_history_school_id`：
  - `add_column` school_id（nullable）/ viewed_at（nullable）
  - 回填：`school_id` 从 `posts.school_id` 取，`viewed_at` 从 `created_at` 取
  - `alter_column` 设为 `nullable=False`
  - 建外键 `fk_browse_histories_school_id_schools` 与 4 个索引

### 测试

- 新增 `tests/test_prf01_personal_center.py` 24 个用例，覆盖统计/未读数/浏览历史写入/列表/清除/单条删除/跨校隔离/我的帖子跨校过滤
- 修复 openGauss 跨连接可见性问题：`two_schools_setup` fixture 与跨校帖子创建改用 `test_session_maker` 独立 session（commit 后立即关闭），避免长连接阻塞 API 侧查询

## 3. 未完成内容

暂无。所有三个子任务（PRF-01.1 / PRF-01.2 / PRF-01.3）均已完成并通过测试。

## 4. 实现思路

### 浏览历史学校隔离方案

最初 `BrowseHistory` 仅有 `(user_id, post_id)`，跨校切换视角时历史会混在一起。解决方案：

1. 模型层新增 `school_id` 外键，唯一索引改为 `(user_id, school_id, post_id)`
2. 写入层：帖子详情端点在写入历史时，`school_id` 取自 `TenantContext.school_id`（由 `X-School-Code` 头解析），而非 `Post.school_id`。这样同一用户在 A 校视角访问 A 校帖子，历史记 A 校；切换到 B 校视角访问 B 校帖子，历史记 B 校
3. 查询层：所有浏览历史查询都加 `BrowseHistory.school_id == tenant.school_id` 过滤
4. 删除层：清除/单条删除都限定 `school_id`，跨校删除返回 404 不泄露存在性

### 真实统计聚合方案

用单条 `SELECT status, COUNT(*) FROM posts WHERE user_id=? AND school_id=? AND is_deleted=False GROUP BY status` 一次拿到所有状态计数，避免 N 次查询。贡献验证数用 `JOIN` + `COUNT` 单独查询，过滤 `validation_type='confirmation'` 且 `post.status='published'`。

### 未读数独立端点方案

不复用通知列表接口，而是新建轻量级 `GET /notifications/unread-count` 端点，只做 `COUNT(*) WHERE user_id=? AND is_read=False AND is_deleted=False`，响应仅含 `unread_count` 与 `has_unread` 两个字段，适合页头角标高频轮询。

### openGauss 跨连接可见性问题修复

测试中遇到 401 Unauthorized 与测试 hang 问题，根因是 openGauss 跨连接可见性：`db_session` fixture 的长连接在 `commit()` 后未关闭，会阻塞 API 侧（使用另一个连接池连接）的查询。修复方式：测试数据预置改用 `test_session_maker` 独立 session，`commit()` 后立即 `close()` 释放连接，避免阻塞 API 侧查询。

## 5. 修改文件

### 后端

- `backend/app/models/browse_history.py` — 新增 `school_id`、`viewed_at` 字段与唯一索引
- `backend/alembic/versions/q5e6f7a8b9c0_prf_01_browse_history_school_id.py` — 新增迁移文件
- `backend/app/api/users.py` — 新增 `GET /me/stats`、`GET /me/view-history`、`DELETE /me/view-history`、`DELETE /me/view-history/{post_id}` 端点与 `UserStatsResponse`、`ViewHistoryItem` schema
- `backend/app/api/notifications.py` — 新增 `GET /notifications/unread-count` 端点与 `UnreadCountResponse` schema
- `backend/app/api/posts.py` — 帖子详情端点写入 BrowseHistory（带 school_id 隔离与 upsert）
- `backend/tests/test_prf01_personal_center.py` — 新增 24 个测试用例

### 前端

- `frontend/src/pages/ProfilePage.tsx` — 重写：学校成员关系卡片、真实统计卡片、浏览历史卡片（含清除按钮与分页）
- `frontend/src/components/layout/Header.tsx` — 接入未读数角标，路由切换自动刷新
- `frontend/src/services/users.ts` — 新增 `getMyStats`、`getMyViewHistory`、`clearMyViewHistory`、`deleteMyViewHistoryItem` 方法
- `frontend/src/services/notifications.ts` — 新增 `getUnreadCount` 方法
- `frontend/src/types/index.ts` — 新增 `UserStats`、`ViewHistoryItem`、`UnreadCountResponse` 类型
- `frontend/src/store/useAuthStore.ts` — 资料更新后 `setUser` 同步刷新

## 6. 影响范围

- **个人中心模块**：ProfilePage 完整重写，新增学校成员关系、真实统计、浏览历史三大卡片
- **通知模块**：新增未读数端点，Header 角标接入
- **帖子详情模块**：访问帖子详情会写入浏览历史（带 school_id 隔离）
- **认证模块**：资料更新同步刷新全局 auth store
- **数据库**：browse_histories 表新增 school_id、viewed_at 字段与索引（需执行 Alembic 迁移）
- **多租户隔离**：所有新增端点均通过 TenantContext 按校过滤，跨校数据不泄露

## 7. 测试与验证

### 后端测试

执行命令：
```powershell
$env:APP_ENV = "opengauss"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"
cd backend
.venv\Scripts\python.exe -m pytest tests/test_prf01_personal_center.py -v --tb=short
```

结果：**24 passed, 92 warnings in 127.45s**

测试覆盖：
- `TestMyStats`（4 个）：各状态真实计数、跨校过滤、confirmation 排除 refutation、未登录 401
- `TestUnreadCount`（5 个）：无通知返回 0、正确计数、用户隔离、排除软删除、未登录 401
- `TestBrowseHistoryTracking`（4 个）：详情访问写入历史、重复访问更新 viewed_at、游客不写入、学校隔离
- `TestViewHistoryList`（5 个）：仅返回当前学校、viewed_at DESC 排序、分页、排除软删除帖子、未登录 401
- `TestClearViewHistory`（2 个）：仅清除当前学校、空历史返回 0
- `TestDeleteViewHistoryItem`（3 个）：删除单条、跨校 404、不存在 404
- `TestMyPostsSchoolIsolation`（1 个）：跨校帖子不计入当前学校

### 前端构建

执行命令：
```powershell
cd frontend
npm run build
```

结果：**✓ built in 4.42s**，`ProfilePage-DHTtyaTK.js 21.06 kB`

### 测试环境问题与修复

测试过程中遇到两个 openGauss 相关问题：

1. **401 Unauthorized**：`test_my_posts_only_returns_current_school` 用例失败，根因是 `db_session` 长连接 `commit()` 后未关闭，阻塞 API 侧查询。修复：改用 `test_session_maker` 独立 session
2. **测试 hang**：连续运行测试时，前一次测试的 `setup_database` teardown TRUNCATE 未完成即启动新测试，导致 TRUNCATE 互相阻塞。修复：终止残留 Python 进程并清理 DB 连接

## 8. 后续建议

1. **通知列表分页**：PRF-01.2 要求通知列表分页，当前 NotificationsPage 已有基础分页，可进一步接入后端分页参数与未读筛选
2. **浏览历史冷启动优化**：当前浏览历史仅在登录用户访问帖子详情时写入，可考虑在列表页点击时也写入
3. **统计缓存**：`/users/me/stats` 每次都查库聚合，可在 Redis 或内存中做短时缓存（30s）降低高频访问压力
4. **未读数 WebSocket 推送**：当前未读数靠路由切换轮询，可接入 WebSocket 实时推送
5. **浏览历史批量清除**：当前仅支持清除当前学校全部历史，可增加按时间范围清除（如"清除 7 天前的"）
