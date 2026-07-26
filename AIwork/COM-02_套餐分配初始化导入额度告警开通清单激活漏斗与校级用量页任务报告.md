# 任务报告：COM-02 套餐分配、初始化导入、额度告警、开通清单、激活漏斗与校级用量页

## 1. 任务概述

实现 COM-02 商业运营模块的四个子任务，为 super_admin 提供平台套餐管理、学校开通向导批量导入、校级用量页与激活漏斗可视化能力，覆盖从套餐分配到学校激活全链路。

依据：`.trae/specs/finals-deep-optimization/tasks.md` COM-02 节，依赖 COM-01（套餐/权益模型）与 TEN-04（学校开通）。

## 2. 已完成内容

### COM-02.1 平台后台套餐管理 UI
- 平台套餐管理页（PlatformPlansPage）：套餐列表、订阅管理、套餐分配弹窗
- 学校管理页（PlatformSchoolsPage）：学校列表、详情、开通清单（5 项）、状态管理
- 后端：`GET /platform/schools/{id}/subscription-history` 套餐历史变更
- 后端：`GET /platform/schools/{id}/alerts` 单校额度告警
- 后端：`GET /platform/alerts` 全平台告警汇总

### COM-02.2 学校开通向导批量导入
- 开通向导页（SchoolImportPage）：CSV 模板下载、预览（dry_run）、提交（commit）
- 后端：`GET /platform/import-template` 下载 CSV 模板
- 后端：`POST /platform/schools/{id}/import?dry_run=true` 预览
- 后端：`POST /platform/schools/{id}/import` 提交（事务保护，任一行失败整批不提交，记录批次 ID 到 PlatformAuditLog）
- `_to_str` 辅助方法兼容 JSON 入参（float/int/bool）与 CSV 入参（str）

### COM-02.3 校级用量页
- 校级用量页（UsagePage）：当前套餐、额度余量、阈值告警、配额可视化
- 后端：`GET /admin/usage` 校级用量端点（admin 可访问）

### COM-02.4 激活漏斗 + 演示校配置
- 激活漏斗页（ActivationFunnelPage）：漏斗指标、学校激活状态追踪、关键词过滤
- 后端：`GET /platform/activation-funnel` 激活漏斗数据
- 漏斗 5 阶段：品牌设置 → 管理员接受 → 地点导入 → 首批内容 → 首批成员

### 测试
- 新建 `backend/tests/test_commercial_import.py`，16 个测试用例覆盖全部 COM-02 端点与权限校验

## 3. 未完成内容

- 前端 `npm run lint` 仍有 4 个 error（`react-hooks/set-state-in-effect`），位于 `FirstUseGuide.tsx`（ACC-01.4）与 `PublishPage.tsx`（PUB-01），属于其他任务文件所有权范围，非 COM-02 引入，按文件所有权约束未修改。COM-02 自身新建文件 lint 0 错误。
- COM-02.4 中"三所演示校全部运营档"的实际数据填充属于 TEN-05 任务范围，COM-02 仅提供激活漏斗端点与 UI 支持。

## 4. 实现思路

### 后端
- 扩展 `app/api/platform.py`：新增套餐历史、告警、导入模板、批量导入、激活漏斗端点，全部 `require_role('super_admin')` 守卫
- 扩展 `app/services/school_provisioning.py`：新增 `ImportRowError`/`ImportPreviewResult`/`ImportCommitResult` 数据类与 `preview_import`/`commit_import`/`build_activation_funnel` 方法
- 批量导入采用 savepoint 事务保护：预览阶段全量校验，提交阶段任一行失败整批回滚并记录批次 ID
- `app/api/admin.py` 仅新增 `/admin/usage` 端点，不动其他逻辑

### 前端
- 5 个新页面：PlatformPlansPage、PlatformSchoolsPage、SchoolImportPage、UsagePage、ActivationFunnelPage
- `services/platform.ts`：API 客户端封装
- `types/index.ts`：追加商业运营相关 TS 类型
- `routes.tsx`：注册新路由并用 `ProtectedRoute requireSuperAdmin` 守卫
- `AdminDashboard.tsx`：super_admin 专属"平台运营"菜单组

## 5. 修改文件

### 新建
- `backend/tests/test_commercial_import.py`（16 个测试）
- `frontend/src/pages/admin/PlatformPlansPage.tsx`
- `frontend/src/pages/admin/PlatformSchoolsPage.tsx`
- `frontend/src/pages/admin/SchoolImportPage.tsx`
- `frontend/src/pages/admin/UsagePage.tsx`
- `frontend/src/pages/admin/ActivationFunnelPage.tsx`
- `frontend/src/services/platform.ts`

### 修改
- `backend/app/api/platform.py`（套餐历史/导入/告警/激活漏斗端点）
- `backend/app/services/school_provisioning.py`（批量导入逻辑、`_to_str`、`selectinload` 导入）
- `backend/app/api/admin.py`（仅新增 `/admin/usage` 端点）
- `frontend/src/types/index.ts`（追加商业类型）
- `frontend/src/routes.tsx`（注册路由 + super_admin 守卫）
- `frontend/src/pages/admin/AdminDashboard.tsx`（平台运营菜单组）
- `.trae/specs/finals-deep-optimization/tasks.md`（COM-02 四个子任务勾选）

## 6. 影响范围

- 平台运营模块（super_admin 专属）：套餐管理、学校管理、开通向导、激活漏斗
- 校级后台：新增用量页入口
- 后端 platform 路由：新增 6 个端点
- 后端 admin 路由：新增 1 个端点（usage）
- 不影响普通用户与 admin 现有功能链路

## 7. 测试与验证

### 后端测试
- 命令：`$env:APP_ENV="opengauss"; $env:TEST_DATABASE_URL="postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"; pytest tests/test_commercial_import.py -v`
- 结果：**16 passed, 35 warnings in 66.56s**（全部通过）
- 覆盖：套餐历史、单校告警、全平台告警、模板下载、预览（成功/含错误）、提交成功写库、提交回滚、权限 403、校级用量、激活漏斗（含关键词过滤）

### 前端构建
- 命令：`npm run build`
- 结果：**构建成功**，5 个 COM-02 页面全部打包（ActivationFunnelPage 8.41 kB、UsagePage 8.87 kB、PlatformPlansPage 10.82 kB、SchoolImportPage 13.95 kB、PlatformSchoolsPage 14.52 kB）

### 前端 lint
- 命令：`npm run lint`
- 结果：COM-02 新建文件 0 错误；剩 4 个 error 位于 `FirstUseGuide.tsx`/`PublishPage.tsx`（非 COM-02 文件，属 ACC-01/PUB-01 任务范围，未修改）

## 8. 后续建议

- 由 ACC-01/PUB-01 任务负责人修复 `FirstUseGuide.tsx`、`PublishPage.tsx` 的 `react-hooks/set-state-in-effect` lint 错误（添加 `// eslint-disable-next-line` 或重构 effect 逻辑），使全前端 lint 达到 0 错误
- TEN-05 任务填充三所演示校数据时，使用 COM-02.4 激活漏斗端点验证各校激活阶段完成度
- 可扩展批量导入支持更多行类型（如官方主体、专题），当前仅支持 location/post
- 激活漏斗可增加时间维度趋势图，展示各校激活进度变化
