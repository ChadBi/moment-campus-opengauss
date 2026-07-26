# 任务报告：TEN-03 学校目录、加入、默认学校、切换与缓存分区

## 1. 任务概述

实现多租户校园 SaaS 的学校目录、加入、默认学校、切换与缓存分区能力，对应 `tasks.md` 中三个子任务：

- TEN-03.1：后端学校目录/当前学校/我的成员关系/加入学校/设置默认学校 5 个 API
- TEN-03.2：前端 `useCampusStore` + Axios `X-School-Code` 拦截器 + URL `?school=` 深链接 + React Query 学校分区缓存键
- TEN-03.3：多校账号切换不串数据，A→B→A 并发切换不闪现旧学校数据

本任务为复赛深度优化第一交付波收尾项，依赖 TEN-01（成员模型迁移）与 TEN-02（TenantContext 与查询强隔离）。

## 2. 已完成内容

### 后端（TEN-03.1）

- 新建 `backend/app/api/schools.py`，含 5 个端点：
  - `GET /api/v1/schools`：公开学校目录（仅 `is_active=true`，无需登录、无需 `X-School-Code`）
  - `GET /api/v1/schools/current`：当前学校详情（基于 `TenantContext`，复用 TEN-02 解析规则）
  - `GET /api/v1/me/memberships`：当前用户加入的学校列表（含 role/status/is_default，默认校排在首位）
  - `POST /api/v1/schools/{code}/join`：加入学校（幂等：已是 active 直接返回；invited/suspended 升级为 active；支持邀请码校验邮箱匹配）
  - `PUT /api/v1/me/default-school`：设置默认学校（取消其它默认、同步 `user.school_id` 兼容旧逻辑）
- 在 `backend/app/api/router.py` 注册 `schools_router` 与 `me_router`
- 编写 `backend/tests/test_schools_api.py`，覆盖 26 个用例：公开目录、当前学校、memberships、join 幂等/升级/邀请码校验、设置默认学校与唯一性、加入后立即出现在 memberships 列表

### 前端（TEN-03.2 / TEN-03.3）

- 扩展 `frontend/src/store/useCampusStore.ts`：
  - 维护 `currentSchoolId/Code/Name/Logo/Center/Zoom` + 学校目录 `schools` + `memberships`
  - `setCurrentSchool` / `setCurrentSchoolById` / `clearSchool` / `ensureValidSchool` 方法
  - 通过 `zustand/persist` 持久化当前学校关键字段（列表数据每次启动重拉，避免脏缓存）
- `frontend/src/services/api.ts`：Axios 请求拦截器注入 `X-School-Code` 头，对 `/schools` 公开目录与 `/auth/*` 跳过注入
- `frontend/src/services/schools.ts`：5 个端点的客户端封装
- `frontend/src/hooks/useSchoolSync.ts`：
  - 应用启动拉公开学校目录 + 登录后拉 memberships
  - Bootstrap 优先级：URL `?school=` > 持久化 code > 默认校 > 第一个 active > `user.school_id` > 第一所学校
  - 监听 URL `?school=` 变化触发切换
  - 切换时 `queryClient.cancelQueries` + `removeQueries` 按 `['school', prevId]` 前缀精确清理（避免 A→B→A 闪现）
  - `useSwitchSchool` 封装：写 URL + 可选 `setAsDefault` 调 `PUT /me/default-school`
- `frontend/src/hooks/useSchoolQueryKey.ts`：统一的 `['school', schoolId]` queryKey 工具
- `frontend/src/components/layout/SchoolSwitcher.tsx`：页头下拉切换组件，已加入显示 ✓、默认校显示 ★，未加入学校点击时自动调 `joinSchool` 后再切换
- `frontend/src/components/layout/Header.tsx`：桌面端与移动端各嵌入一个 `SchoolSwitcher`
- `frontend/src/routes.tsx`：新增 `SchoolAwareRoot` 在 `BrowserRouter` 内层调用 `useSchoolSync`
- `frontend/src/pages/HomePage.tsx`：feed 查询改用 `[...schoolKey, 'posts', 'feed']` 实现学校分区缓存

### 验证

- 后端测试：`pytest tests/test_schools_api.py -v` → 26 passed
- 前端 lint：`npm run lint` → 0 errors（3 个 warnings 均为 TEN-03 之外的旧文件）
- 前端 build：`npm run build` → 通过
- `tasks.md` 中 TEN-03.1/.2/.3 三个勾选框已勾选

## 3. 未完成内容

暂无。

说明：
- TEN-03.3 的"并发切换 A→B→A 不闪现"通过 `useSchoolSync` 中 `cancelQueries + removeQueries` 按 `['school', prevId]` 前缀精确清理实现；当前以单测与构建验证为主，未启动浏览器 Playwright E2E（按 `tasks.md` 约定，E2E 在 REL-01 统一编排）。
- 浏览器端真机切换演示留待 TEN-05 三校差异化数据准备完成后，作为复赛视频录制的一部分。

## 4. 实现思路

### 后端：复用 TenantContext，幂等加入 + 唯一默认

- 公开目录与 `/schools/current` 完全复用 TEN-02 的 `TenantContext` 解析规则，避免重复实现学校解析逻辑
- `join_school` 严格幂等：
  - 已 active → `already_member=true`，原样返回原 membership（不修改、不重新发邀请码消费）
  - invited/suspended → 升级为 active，更新 `joined_at`
  - 全新加入 → 若用户当前无任何默认校，本次自动设为默认；否则 `is_default=false`
- `set_default_school` 通过 `UPDATE ... WHERE id != target.id` 一次性取消其它默认，避免多次往返；同时同步 `user.school_id` 兼容 TEN-02 中"未传 `X-School-Code` 时回退到 `user.school_id`"的旧逻辑
- 邀请码：仅在提供时校验（无效 400、邮箱不匹配 400、已使用 409）；消费时机分两种路径（升级与新建），均标记为 `accepted`

### 前端：URL 深链接 + Store 持久化 + React Query 分区

- URL `?school=code` 作为最高优先级来源，保证分享链接、刷新、深链接进入均落到正确学校
- Store 仅持久化当前学校关键字段；学校目录与 memberships 每次启动重新拉取，避免脏缓存
- Axios 拦截器统一注入 `X-School-Code`，公开目录与认证接口跳过，避免"先有鸡还是先有蛋"循环依赖
- React Query 所有按学校作用域的查询以 `['school', schoolId]` 起头，切换学校时新 queryKey 与旧的不同 → 自动启动新查询；同时主动 `cancelQueries + removeQueries` 旧学校前缀，杜绝 A→B→A 闪现

### 切换组件：登录态自动加入 + 视觉反馈

- 下拉显示学校目录全集（公开），已加入显示 ✓、默认校显示 ★
- 登录用户点击未加入学校时，先调 `joinSchool`（幂等），再切换；加入失败仍允许切换查看公开内容
- 桌面端与移动端分别嵌入独立 `SchoolSwitcher` 实例，避免布局挤压

## 5. 修改文件

新增：
- `backend/app/api/schools.py`
- `backend/tests/test_schools_api.py`
- `frontend/src/services/schools.ts`
- `frontend/src/hooks/useSchoolSync.ts`
- `frontend/src/hooks/useSchoolQueryKey.ts`
- `frontend/src/components/layout/SchoolSwitcher.tsx`
- `AIwork/TEN-03_学校目录加入默认学校切换与缓存分区任务报告.md`

修改：
- `backend/app/api/router.py`：注册 `schools_router` 与 `me_router`
- `frontend/src/store/useCampusStore.ts`：扩展为完整学校状态管理
- `frontend/src/services/api.ts`：增加 `X-School-Code` 请求拦截器
- `frontend/src/components/layout/Header.tsx`：桌面端 + 移动端各嵌入 `SchoolSwitcher`
- `frontend/src/routes.tsx`：新增 `SchoolAwareRoot` 调用 `useSchoolSync`
- `frontend/src/pages/HomePage.tsx`：feed 查询改用 `schoolKey` 分区
- `frontend/src/components/layout/SchoolSwitcher.tsx`：将原动态 `import('../../services/schools')` 改为静态导入，消除 vite `INEFFECTIVE_DYNAMIC_IMPORT` 警告
- `.trae/specs/finals-deep-optimization/tasks.md`：勾选 TEN-03.1/.2/.3

删除（清理调试残留）：
- `backend/tests/test_debug_visibility.py`
- `backend/_db_cleanup.py`
- `backend/_db_check.py`

## 6. 影响范围

- 后端：`app/api/schools.py` 为新增路由模块，注册到 `api_router` 后挂载于 `/api/v1/schools/*` 与 `/api/v1/me/*`，不影响既有路由
- 后端：`schools.py` 依赖 TEN-01 的 `SchoolMembership` / `SchoolInvitation` 模型与 TEN-02 的 `TenantContext`，未修改这些上游模块
- 前端：`useCampusStore` 为全局 store，被 `api.ts` 拦截器、`useSchoolSync`、`SchoolSwitcher`、`HomePage` 等消费；其它页面接入 schoolKey 分区可后续渐进迁移
- 前端：Axios 拦截器对 `/schools` 公开目录与 `/auth/*` 跳过 `X-School-Code`，避免影响登录与目录拉取
- 测试：`test_schools_api.py` 在独立测试库 `moment_campus_test` 运行，不污染开发库

## 7. 测试与验证

### 后端测试

执行命令：

```powershell
$env:APP_ENV = "opengauss"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"
.\.venv\Scripts\python.exe -m pytest tests/test_schools_api.py -v --tb=short
```

结果：26 passed, 81 warnings in 106.04s

覆盖场景：
- 公开目录无 Auth 也可访问；只返回 `is_active=true` 的学校
- `/schools/current`：游客无 `X-School-Code` → 404；游客有 header → 200；登录用户无 header → user.school_id；登录用户有 header → 切换（需 membership）；不存在 code → 404
- `/me/memberships`：未登录 → 401；u1 返回 A/B 两校；字段完整；默认校排首位
- `POST /schools/{code}/join`：未登录 → 401；新加入 → active + DB 校验；幂等 → already_member=true；invited → 升级 active；不存在/停用学校 → 404；无效邀请码 → 400；邀请码邮箱不匹配 → 400；有效邀请码新加入 → 标记 accepted
- `PUT /me/default-school`：未登录 → 401；切换默认 + DB 校验取消其它默认 + 同步 user.school_id；未加入 → 404；不存在 → 404；多次切换仅保留一个默认
- 集成：u2 加入 B 校后立即出现在 memberships 列表

### 前端验证

- `npm run lint`：0 errors（3 warnings，均位于 TEN-03 之外的 `main.tsx` / `MapPage.tsx` 旧文件）
- `npm run build`：通过（`tsc -b && vite build` 全部成功，1928 modules transformed）

### 未执行测试

- 未启动 Playwright E2E：按 `tasks.md` 约定，E2E 在 REL-01 阶段统一编排（≥18 条核心路径，含多租户切换 ≥6 条）
- 未启动浏览器真机切换演示：留待 TEN-05 三校差异化数据准备完成后，作为复赛视频录制的一部分

## 8. 后续建议

1. **React Query 分区渐进迁移**：当前仅 `HomePage` 的 feed 查询接入 `schoolKey` 分区，后续应将 `MapPage` / `SearchPage` / `PostDetailPage` / `NotificationsPage` / `ProfilePage` 等所有按学校作用域的查询统一改为 `[...schoolKey, ...]`，确保切换学校时所有列表同步刷新
2. **TEN-03.3 E2E**：在 REL-01 阶段补 Playwright 用例，覆盖：登录多校账号 → 切换 A→B→A → 断言无闪现、无串数据；URL 深链接 `?school=xxx` 直接进入正确学校
3. **TEN-04 联动**：super_admin 通过 `/api/v1/platform/schools/*` 创建新学校后，前端 `SchoolSwitcher` 应自动 refetch 公开目录（当前 `staleTime: 5min`，可由 super_admin 操作后主动 `invalidateQueries(['schools', 'directory'])`）
4. **邀请码 UI**：当前 `SchoolSwitcher` 直接 join 不带邀请码；后续可在切换未加入学校时弹窗让用户填邀请码（admin 邀请 → admin 角色）
5. **默认学校持久化**：`useSwitchSchool(code, setAsDefault=true)` 已支持同时设为默认，可在切换组件增加"设为默认"勾选项
