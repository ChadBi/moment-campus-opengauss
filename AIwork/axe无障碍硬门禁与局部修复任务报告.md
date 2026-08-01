# 任务报告：axe 无障碍硬门禁与局部修复

## 1. 任务概述

将五条关键流程的 axe 检查升级为真实硬门禁，并针对 RED 阶段发现的颜色对比度与学校切换器触控尺寸问题进行局部修复。

## 2. 已完成内容

- 将 critical 与 serious axe 违规统一改为阻断测试，并输出具体规则与节点选择器。
- 将学校切换器触发按钮、禁用态按钮和菜单选项调整为至少 44px 高，测试同时强制校验宽高。
- 提高 muted、lamp、grass、sun、danger 设计令牌的对比度，并同步 CSS、Tailwind 和 TypeScript 令牌。
- 修正 warning 徽标与发布提示文本颜色，移除后台空待办卡片导致子节点对比度下降的整体透明度。
- 在 axe 注入前等待动态信息流稳定，避免扫描动画中间态造成不稳定结果。

## 3. 未完成内容

暂无。

## 4. 实现思路

先修改测试建立 critical / serious 与 44px 触控尺寸硬门禁，运行后确认五条流程全部 RED。随后根据 axe 返回的实际 DOM 节点和计算对比度调整对应设计令牌及局部样式，再重复运行专项用例直至 GREEN。修复范围不改变页面结构和业务逻辑。

## 5. 修改文件

- `frontend/e2e/accessibility.spec.ts`
- `frontend/tailwind.config.js`
- `frontend/src/index.css`
- `frontend/src/styles/tokens.ts`
- `frontend/src/components/layout/SchoolSwitcher.tsx`
- `frontend/src/components/ui/Badge.tsx`
- `frontend/src/components/PostForm.tsx`
- `frontend/src/pages/admin/AdminHomePage.tsx`
- `AIwork/axe无障碍硬门禁与局部修复任务报告.md`

## 6. 影响范围

影响登录、搜索、首页学校切换、发布页、后台五条关键前端流程的颜色呈现和无障碍回归门禁。学校切换器触控区域增大，业务数据、接口和交互逻辑不变。

## 7. 测试与验证

- RED：`npx playwright test e2e/accessibility.spec.ts --project=chromium`，5 FAIL；确认 serious color-contrast 节点与学校切换器实际高度 40px 被硬门禁拦截。
- GREEN：`npx playwright test e2e/accessibility.spec.ts --project=chromium --reporter=line`，5 PASS / 0 FAIL，耗时 18.8 秒。
- `npm run lint`：通过，0 error、0 warning。
- `npm run build`：通过，1969 个模块完成转换；保留 MapLibre 大分包既有体积提示。
- VS Code 诊断：0 条。
- 完成局部修复后再次运行全量 `npm run e2e`，结果 36 PASS / 0 FAIL / 0 SKIP。
- 实施代理曾错误更新 `TODO.md`；主执行流程已完整回退该变更，最终 `TODO.md` 与任务开始前一致，且未执行 Git 提交。

## 8. 后续建议

将同一 critical / serious axe 硬门禁复用于后续新增关键页面，并在新增交互组件时默认采用至少 44×44px 的触控目标。
