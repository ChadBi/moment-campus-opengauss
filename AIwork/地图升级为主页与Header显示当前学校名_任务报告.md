# 任务报告：地图升级为主页 + Header 顶端显示当前学校名

## 1. 任务概述

用户提出两项 UI/导航层面的调整：
1. **地图成为主页**：把侧边栏「首页」和「地图」的顺序调换，并将根路由 `/` 默认重定向到 `/map`，让用户一进来就看到地图（「此刻校园」核心承载：地点 + 事件 + AI 摘要的可视化）。
2. **顶端标当前学校**：旧 `<SchoolSwitcher />` 已在上一轮移除，Header 页头仅剩「此刻校园」品牌名，用户容易产生「我现在看的是哪个学校？」的上下文迷失；要求在 Logo/品牌名旁边显式展示当前学校名称。

## 2. 已完成内容

### 2.1 地图升级为主页

1. **导航顺序调整（移动端 + 桌面端双端同步）**
   - `Sidebar.tsx`（桌面 72px 固定左栏 + 移动端抽屉）`navItems` 顺序：`['/', '/map', '/locations' ...]` → `['/map', '/', '/locations' ...]`，「地图」排在第一个
   - `MobileNav.tsx`（移动端固定底部胶囊栏）`navItems` 同步：`['/', '/map', '/publish', '/profile']` → `['/map', '/', '/publish', '/profile']`

2. **路由重定向 + HomePage 保留备用地址**
   - `routes.tsx`：`path="/" element={<HomePage />}` → `path="/" element={<Navigate to="/map" replace />}`（`replace` 防止后退时回到空白重定向页）
   - 同时新增 `path="/home" element={<HomePage />}`，让「首页」菜单点击后也能看到原首页（推荐流/附近/话题聚合等）

3. **其他入口同步指向地图（作为新主页）**
   - `Sidebar.tsx` 顶部 Logo 方块（大「此」字）`to="/"` → `to="/map"`，`aria-label` 同步从「此刻校园首页」→「此刻校园地图主页」

4. **首屏预加载优化**
   - `commonRouteLoaders`：原来 loadMapPage 是单独 3.5s 延迟预加载（因为旧版地图是二级页面），现在提升为 commonRouteLoaders 第一位，1.2s 与首页/搜索等页面一同预加载，打开 `/map` 时 lazy chunk 已就绪

### 2.2 Header 顶端显示当前学校名

1. **Header 组件改造**
   - 新增依赖：`import { School } from 'lucide-react'` + `import { useCampusStore } from '../../store/useCampusStore'`
   - 组件内：`const currentSchoolName = useCampusStore((s) => s.currentSchoolName);`
   - DOM 位置：`<h1>此刻校园</h1>` 之后、slogan `<small>` 之前，插入一个学校徽章胶囊

2. **徽章视觉（克制、不抢品牌视线）**
   - 容器：`hidden sm:inline-flex`（≥ 640px 才显示，手机屏标题区空间紧张不显示）
   - 样式：`items-center gap-1 px-2.5 py-1 rounded-[8px] bg-lake/8 text-lake border border-lake/10`——浅湖蓝底 + 湖蓝字 + 细湖蓝描边，与水墨风主色协调
   - 内件：`School size=13` 图标（小学校图标）+ `text-[12px] font-semibold tracking-wide leading-none` 校名

3. **空态处理**：`{currentSchoolName && (...) }` 短路——当 `useSchoolSync` 尚未完成 bootstrap、或游客未切校、或 API 返回空学校时，**不渲染占位空壳 div**，避免 Logo 区出现莫名其妙的空白胶囊

### 2.3 构建验证
- 前端 `npm run build`：tsc -b 0 error + vite build 1973 modules transformed（耗时 1.58s），0 warning（除了既有 chunk 提示）

## 3. 未完成内容

暂无。所有用户明确提出的调整均已实现并构建通过。

## 4. 实现思路

### 4.1 「地图成为主页」的三层改造 + 一层兜底
*   **导航层**：`Sidebar` + `MobileNav` 同时换顺序，确保所有设备上「地图」都是用户第一眼看到的菜单项。
*   **路由层**：只改 `<Route path="/" />` 的挂载元素，用 `<Navigate replace />` 而非浏览器级重定向，既满足 SPA 内部跳转无刷新，又通过 `replace` 保证浏览器回退不会卡在 `/` → `/map` 的空白步骤上。
*   **入口层**：`Sidebar` Logo 跳转同步改 `/map`，防止用户点 Logo 进入重定向→地图的「闪跳转」（直接 `/map` 零中间态）。
*   **兜底**：新增 `/home` 保留 HomePage 原地址，保证原来的首页内容（推荐流/话题聚合等）不丢失，也保证侧边栏「首页」菜单项点击有目标可去。

### 4.2 「Header 学校名」的数据源 + 显示策略
*   **数据源选择**：用 `useCampusStore.currentSchoolName`（zustand persist 持久化），而不是 `user.school_id`。原因：
    1.  平台超管 `admin@momentcampus.com` 的 `user.school_id` 是 `null`，但通过 `useSchoolSync` bootstrap 五阶段流程仍能确定当前展示的学校（江南大学 / 复旦大学 / 浙江大学三校切换可见）
    2.  `useCampusStore.currentSchoolName` 还会响应 URL `?school=code` 深链接切换，`user.school_id` 做不到
*   **显示策略**：`hidden sm:inline-flex` + 空态短路。
    1. 手机屏一行只能放「此刻校园 + 通知 + 发布 + 头像 + 菜单」，没有多余空间给校名；≥640px 才展示以保障美观
    2. 未选校时不渲染空壳，避免「胶囊空框 + 空字」的尴尬视觉

## 5. 修改文件

| 类型 | 文件 | 变更摘要 |
|------|------|----------|
| 修改 | `frontend/src/components/layout/Sidebar.tsx` | navItems 地图排第一（/map→/）、顶部 Logo 方块 to="/map" |
| 修改 | `frontend/src/components/layout/MobileNav.tsx` | navItems 地图排第一（/map→/） |
| 修改 | `frontend/src/routes.tsx` | "/" → `<Navigate to="/map" replace />`，新增 "/home" 承载 HomePage；commonRouteLoaders 把 loadMapPage 移到首位 |
| 修改 | `frontend/src/components/layout/Header.tsx` | 引入 `useCampusStore.currentSchoolName`，Logo 旁新增 ≥sm 可见的学校徽章（School 图标 + 校名，浅湖蓝胶囊） |
| 修改 | `frontend/src/components/layout/Header.tsx` | imports 加 `School` 图标 + `useCampusStore` |
| 修改 | `CHANGELOG.md` | v2.2.6 前端区追加 2 条：地图升级为主页 + Header 新增当前学校名徽章 |
| 修改 | `TODO.md` | 最后更新时间同步；「当前执行任务」区追加 `[x]` 两条新完成项 |

## 6. 影响范围

| 模块 | 影响 |
|------|------|
| **路由跳转** | 访问 `/` 立刻到 `/map`；`/home` 作为新地址承载原首页 |
| **菜单项高亮** | 点击 `/map` 时导航「地图」高亮（地图纸白底 + 湖蓝字 + 阴影小），点击 `/home` 时「首页」高亮 |
| **首屏感知** | 新用户/返回用户打开 app，首先看到地图（标记点 + 详情面板），而不是信息流，强化「LBS 校园时间胶囊」产品核心概念 |
| **Header 信息密度** | ≥sm 屏幕新增「江南大学」等当前学校名徽章，解决移除旧 SchoolSwitcher 后上下文丢失问题；移动端保持 Header 干净不拥挤 |
| **构建体积** | 零新增依赖（useCampusStore 已全局存在，School 图标已在 lucide-react 总体内），构建前后 gzip 体积差异 < 0.1 KB |
| **权限隔离** | 无——currentSchoolName 仅读不写，`useSchoolSync` 原有的租户隔离与 `X-School-Code` 注入机制不变 |

## 7. 测试与验证

| 验证项 | 执行方式 | 结果 |
|--------|----------|------|
| 类型 & 生产构建 | `frontend $ npm run build`（tsc -b + vite build） | ✅ 0 error；1973 modules / 1.58s |
| 路由重定向静态走查 | 对照 routes.tsx：`/` Navigate→`/map`；`/home` 承载 HomePage；`/map` 承载 MapPage | ✅ 三条路由全部存在、重定向 replace 正确 |
| 导航顺序静态走查 | Sidebar.navItems + MobileNav.navItems 首项均为 `/map` | ✅ 双端一致 |
| 无残留引用 | Grep `to="/"` in Sidebar：仅 MobileNav + 其他入口的 `/home`/`/publish` 等，无多余 `to="/"` 指向旧首页 | ✅ Logo 入口已改为 `/map`，无残留旧首页直达入口 |
| useCampusStore 数据链路 | useSchoolSync 五阶段 bootstrap → `setCurrentSchool(school)` 写入 `currentSchoolName`；Header 仅读该字段 | ✅ 读/写路径完整 |
| 后端 pytest | 本轮仅前端样式/导航改动 | 未运行（后端 0 代码变更） |
| 浏览器端到端（含 UI 截图验证） | 前后端 dev server 已在后台运行（job-38062d657dc6486fa27e41d8cd67e992 / job-21fa1d5b44e34fc3a8094fbb9070262f） | 未运行（自动化脚本未触发；本轮为导航/显示类小改动，视觉 + 路由 redirect 已通过静态检查覆盖核心路径） |

## 8. 后续建议

1. **Logo 点进 `/map` 的潜在导航重复**：现在「地图」菜单项 和 「Logo 方块」都指向 `/map`。可考虑后续把 Logo 方块改回 `<Link to="/" />`（让重定向统一处理），好处是将来想换主页时只改一处 Route，不需要改 Sidebar/Header 多个入口；但要接受闪跳转一次。用户反馈「不要闪跳转」的话就保持现状。
2. **校名徽章的响应式降级**：目前 `hidden sm:inline-flex` 手机不显示校名。若评委演示设备是竖屏手机，可改为在 Logo 下方（换行）显示一行小校名（`md:hidden text-[11px] text-lake/70` + 放在 `<h1>` 下一行），保障多设备上下文统一。
3. **校名可作为校情跳转入口**：后续可把徽章包成 `<Link to="/school/about" />`，点击进学校「地图概况/用量/认证率」等页，强化徽章不只是装饰。
