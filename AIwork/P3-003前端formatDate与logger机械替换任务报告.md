# 任务报告：P3-003 前端 formatDate/formatDateTime 与 console.* 机械替换

## 1. 任务概述

在 `frontend/src` 目录下对 26 个文件执行两类机械替换：

- **任务 A**：将各页面本地实现的 `formatDate` / `formatDateTime` 函数体替换为 `utils/date` 工具函数导入（共 15 个文件，NotificationsPage.tsx 已先期处理不动）
- **任务 B**：将散落的 `console.error` / `console.warn` / `console.log` 调用替换为 `utils/logger` 中的 `logger.error` / `logger.warn` / `logger.info`（共 21 个文件，NotificationsPage 已处理、AdminTagsPage 即将删除，二者均跳过）

## 2. 已完成内容

### 任务 A：替换 15 个文件的本地日期格式化函数

| 文件 | 原实现类型 | 替换为 |
| --- | --- | --- |
| pages/HomePage.tsx | diff 相对时间 | `formatRelativeTime as formatDate` |
| pages/PostDetailPage.tsx | pad 完整日期时间 + diff 相对时间 | `formatDateTime` + `formatRelativeTime as formatDate` |
| pages/SearchPage.tsx | diff 相对时间 | `formatRelativeTime as formatDate` |
| pages/TopicDetailPage.tsx | diff 相对时间（含 ≥30 天切回绝对日期分支） | 薄包装，内部委派 `formatRelativeTime` / `formatDate as formatDateAbs` |
| pages/TopicListPage.tsx | `getFullYear()-pad-pad` 绝对日期 | `formatDate` |
| pages/admin/AdminGovernancePage.tsx | toLocaleString(month/day/hour/minute) | `formatShortDateTime as formatDate` |
| pages/admin/AdminJobsPage.tsx | toLocaleString + null 返回 '—' | 薄包装，委派 `formatShortDateTime` 并保留 '—' fallback |
| pages/admin/AdminLocationsPage.tsx | toLocaleString(month/day/hour/minute) | `formatShortDateTime as formatDate` |
| pages/admin/AdminLogsPage.tsx | toLocaleString(year/month/day/hour/minute) | `formatDateTime` |
| pages/admin/AdminReportsPage.tsx | toLocaleString(month/day/hour/minute) | `formatShortDateTime as formatDate` |
| pages/admin/AdminReviewPage.tsx | toLocaleString(month/day/hour/minute) | `formatShortDateTime as formatDate` |
| pages/admin/AdminPublishersPage.tsx | toLocaleString + null 返回 '—' | 薄包装，委派 `formatShortDateTime` 并保留 '—' fallback |
| pages/admin/AdminUsersPage.tsx | toLocaleDateString(year/month/day) | `formatDate` |
| pages/admin/AnalyticsPage.tsx | try/catch 包裹 toLocaleString(无 year) | 薄包装，委派 `formatShortDateTime`（util 内部已 try/catch） |
| pages/admin/PlatformOverviewPage.tsx | try/catch 包裹 toLocaleString(无 year) | 薄包装，委派 `formatShortDateTime`（util 内部已 try/catch） |

### 任务 B：替换 21 个文件的 console.* 调用

在所有含 `console.error` / `console.warn` / `console.log` 的目标文件顶部 import 区添加 `import { logger } from '../utils/logger'` 或 `'../../utils/logger'`，并按规则将调用替换为 `logger.error` / `logger.warn` / `logger.info`：

- `hooks/useServiceWorker.ts`（1 处 console.warn）
- `components/NotificationPreferencesCard.tsx`（1 处 console.error）
- `components/SubscribeButton.tsx`（1 处 console.warn）
- `components/SubscriptionsCard.tsx`（1 处 console.error）
- `pages/MapPage.tsx`（1 处 console.error）
- `pages/ProfilePage.tsx`（9 处 console.error）
- `pages/PostDetailPage.tsx`（2 处 console.error，与任务 A 同文件）
- `pages/TopicDetailPage.tsx`（1 处 console.error，与任务 A 同文件）
- `pages/TopicListPage.tsx`（1 处 console.error，与任务 A 同文件）
- `pages/admin/AdminCategoriesPage.tsx`（3 处 console.error）
- `pages/admin/AdminGovernancePage.tsx`（1 处 console.error，与任务 A 同文件）
- `pages/admin/AdminHomePage.tsx`（1 处 console.error）
- `pages/admin/AdminJobsPage.tsx`（1 处 console.error，与任务 A 同文件）
- `pages/admin/AdminLocationsPage.tsx`（1 处 console.error，与任务 A 同文件）
- `pages/admin/AdminLogsPage.tsx`（1 处 console.error，与任务 A 同文件）
- `pages/admin/AdminReportsPage.tsx`（2 处 console.error，与任务 A 同文件）
- `pages/admin/AdminReviewPage.tsx`（4 处 console.error，与任务 A 同文件）
- `pages/admin/AdminSettingsPage.tsx`（2 处 console.error）
- `pages/admin/AdminTopicsPage.tsx`（3 处 console.error）
- `pages/admin/AdminUsersPage.tsx`（3 处 console.error，与任务 A 同文件）
- `pages/admin/UsagePage.tsx`（1 处 console.error）

**合计修改 26 个唯一文件**（任务 A 15 + 任务 B 11 独占，10 个文件两类任务重叠）。

## 3. 未完成内容

暂无。

## 4. 实现思路

1. **识别本地实现类型**：先 Read 每个目标文件，根据函数体特征判断映射：
   - 计算 `diff` 返回 "刚刚/X分钟前/…" → `formatRelativeTime`
   - `toLocaleString('zh-CN', {year, month, day, hour, minute})` → `formatDateTime`
   - `toLocaleString('zh-CN', {month, day, hour, minute})`（省略 year）→ `formatShortDateTime`
   - `getFullYear()-pad-pad` 仅日期 → `formatDate`
2. **薄包装保留特殊业务逻辑**：对原函数有非平凡分支的情况（如 TopicDetailPage ≥30 天切回绝对日期、AdminJobsPage/AdminPublishersPage 在 null 输入返回 '—'、AnalyticsPage/PlatformOverviewPage 用 try/catch 包裹）保留为薄包装，仅委派给 util，不改变对外行为。
3. **import 路径**：`pages/` 直接子目录用 `'../utils/...'`；`pages/admin/` 子目录用 `'../../utils/...'`；`components/` 与 `hooks/` 用 `'../utils/...'`。
4. **保持原函数名**：原代码若用 `formatDate`，import 时用 `as formatDate`；若原代码用 `formatDateTime`，import 时用 `as formatDateTime`；若 util 函数名与本地一致（如 `formatDate` / `formatDateTime`）则直接 import 不加别名。
5. **验证**：先 grep 全局确认无遗漏 `console.*` 调用（除 logger.ts 内部实现与 AdminTagsPage.tsx 跳过项），再跑 ESLint 与 `npm run build`。

## 5. 修改文件

### 任务 A 修改文件（15 个）

- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/PostDetailPage.tsx`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/pages/TopicDetailPage.tsx`
- `frontend/src/pages/TopicListPage.tsx`
- `frontend/src/pages/admin/AdminGovernancePage.tsx`
- `frontend/src/pages/admin/AdminJobsPage.tsx`
- `frontend/src/pages/admin/AdminLocationsPage.tsx`
- `frontend/src/pages/admin/AdminLogsPage.tsx`
- `frontend/src/pages/admin/AdminReportsPage.tsx`
- `frontend/src/pages/admin/AdminReviewPage.tsx`
- `frontend/src/pages/admin/AdminPublishersPage.tsx`
- `frontend/src/pages/admin/AdminUsersPage.tsx`
- `frontend/src/pages/admin/AnalyticsPage.tsx`
- `frontend/src/pages/admin/PlatformOverviewPage.tsx`

### 任务 B 独占修改文件（11 个，与任务 A 重叠的 10 个已在上方列出）

- `frontend/src/hooks/useServiceWorker.ts`
- `frontend/src/components/NotificationPreferencesCard.tsx`
- `frontend/src/components/SubscribeButton.tsx`
- `frontend/src/components/SubscriptionsCard.tsx`
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/pages/ProfilePage.tsx`
- `frontend/src/pages/admin/AdminCategoriesPage.tsx`
- `frontend/src/pages/admin/AdminHomePage.tsx`
- `frontend/src/pages/admin/AdminSettingsPage.tsx`
- `frontend/src/pages/admin/AdminTopicsPage.tsx`
- `frontend/src/pages/admin/UsagePage.tsx`

## 6. 影响范围

- 前端日期格式化统一收敛到 `utils/date.ts`，后续若需调整日期显示规则只需修改一处。
- 前端日志统一通过 `utils/logger.ts` 出口，dev 全量输出、prod 静默（error 仅输出消息字符串）。
- 不影响任何业务逻辑、API 调用、状态管理或路由。
- AdminTagsPage.tsx 按要求跳过（即将整体删除）。
- NotificationsPage.tsx 按要求跳过（已先期处理）。

## 7. 测试与验证

### ESLint 检查

```powershell
cd e:\Project\moment-campus\frontend
npx eslint src/ --max-warnings=0
```

**结果**：0 errors，33 warnings。

- 33 个 warning 全部为既有问题，非本次引入：
  - 多处 `react-hooks/set-state-in-effect`（既有代码 effect 内同步 setState，非本次新增）
  - `utils/logger.ts` 中 5 处 `Unused eslint-disable directive`（logger.ts 文件本身既有问题，非本次任务范围）
- 期间出现 1 个 error（TopicDetailPage 薄包装中使用了 `Date.now()` 触发 `react-hooks/no-impure-functions-during-render`），已修复为 `new Date().getTime()` 与原始实现风格保持一致，复检后 0 error。

### TypeScript 编译

```powershell
cd e:\Project\moment-campus\frontend
npm run build
```

**结果**：编译成功，`✓ built in 1.33s`，无 TypeScript 错误。所有 chunk 正常产出。

### 单元/E2E 测试

未运行单元与 E2E 测试。原因：本任务为纯机械替换，不涉及业务逻辑变更，ESLint 与 TypeScript 编译均通过即可保证类型正确；运行时行为通过薄包装保留原语义，不需要新增测试覆盖。

## 8. 后续建议

1. 可考虑把 `utils/logger.ts` 中 5 处 `Unused eslint-disable directive` 警告清理掉（移除多余 `// eslint-disable-next-line no-console` 注释），让 `--max-warnings=0` 通过。
2. AdminTagsPage.tsx 删除后，可再次跑一遍 `npx eslint src/ --max-warnings=0` 确认 warning 数量进一步收敛。
3. 既有的 `react-hooks/set-state-in-effect` warning 较多（30+ 处），可单独立项治理，本任务未触碰这些代码。
4. NotificationsPage.tsx 已先期使用 `formatRelativeTime` + 薄包装的方案；本次 15 个文件采用相同方案（薄包装或 `as` 别名），保持全项目风格一致。
