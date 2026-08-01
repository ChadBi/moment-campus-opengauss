# 任务报告：前端 Lint 警告清理

## 1. 任务概述

清理 `frontend` 执行 `npm run lint` 时的全部 22 条 warning，不禁用 ESLint 规则，不改变既有业务行为，重点处理 effect 同步 setState、Hook 依赖、Fast Refresh 导出边界和 logger 中无用的 eslint-disable。

## 2. 已完成内容

- 将 effect 中的同步状态写入改为事件派生、渲染派生、异步回调或 React 19 `useEffectEvent`，消除 `react-hooks/set-state-in-effect` warning。
- 补齐 Hook 依赖，并用 `useCallback`、`useEffectEvent` 保持依赖语义稳定。
- 将全局 Toast 从入口文件拆分为独立组件，移除首用引导中未使用的非组件导出，满足 Fast Refresh 文件边界要求。
- 删除 logger 中 5 处无用 `eslint-disable-next-line no-console`。
- 保持 ESLint 配置及现有规则级别不变。

## 3. 未完成内容

暂无。

## 4. 实现思路

遵循 React 19 的状态建模原则，优先在渲染阶段从 props 或外部环境派生展示值，避免使用 effect 同步复制状态；必须由外部系统触发的数据加载保留在 effect 中，并将状态更新放入 Promise 回调；需要读取最新函数或输入但不应触发 effect 重跑的场景使用 `useEffectEvent`。Fast Refresh warning 通过拆分组件模块和移除无效导出解决，没有降低或关闭规则。

## 5. 修改文件

- `frontend/src/components/FirstUseGuide.tsx`
- `frontend/src/components/GlobalToast.tsx`
- `frontend/src/components/NotificationPreferencesCard.tsx`
- `frontend/src/components/SubscribeButton.tsx`
- `frontend/src/components/SubscriptionsCard.tsx`
- `frontend/src/components/UpdatePrompt.tsx`
- `frontend/src/components/layout/MainLayout.tsx`
- `frontend/src/components/layout/SchoolSwitcher.tsx`
- `frontend/src/main.tsx`
- `frontend/src/pages/PostDetailPage.tsx`
- `frontend/src/pages/ProfilePage.tsx`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/pages/admin/AdminJobsPage.tsx`
- `frontend/src/pages/admin/AdminSettingsPage.tsx`
- `frontend/src/pages/admin/AdminTopicsPage.tsx`
- `frontend/src/pages/admin/AnalyticsPage.tsx`
- `frontend/src/utils/logger.ts`
- `AIwork/前端Lint警告清理任务报告.md`

## 6. 影响范围

影响 Web 前端的通知偏好、订阅、版本提示、主布局、学校切换、帖子详情、个人中心、搜索页、后台任务/设置/专题/分析页面及全局 Toast 的内部状态管理与开发热更新边界。未修改 API、业务规则、小程序、`TODO.md` 或 ESLint 配置。

## 7. 测试与验证

- 执行 `frontend/npm run lint`：通过，0 error、0 warning。
- 执行 `frontend/npm run build`：通过，TypeScript 编译和 Vite 生产构建成功，共转换 1969 个模块。
- 构建仍报告既有 MapLibre chunk 超过 600 kB 的产物体积提示，该提示来自 Vite 构建器，不属于 ESLint warning，也不影响构建成功。
- VS Code 项目诊断：无诊断问题。
- lint 清理与无障碍修复合并后重新执行全量 `npm run e2e`，结果 36 PASS / 0 FAIL / 0 SKIP，确认状态建模调整未破坏现有业务链路。

## 8. 后续建议

后续可单独评估 MapLibre 产物体积与按需加载策略；该项与本次 22 条 ESLint warning 清理无关，不建议混入本次修改范围。
