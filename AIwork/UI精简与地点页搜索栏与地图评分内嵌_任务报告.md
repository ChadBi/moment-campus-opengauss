# 任务报告：UI 精简与地点页搜索栏与地图评分内嵌

## 1. 任务概述

根据用户在浏览器端对三个 UI 元素（学校切换 button、地图地点 aside 面板、个人中心订阅卡 div）的逐个点选反馈，完成四项 UI/交互调整：

1. 删除页头 `Header` 中的学校切换按钮（桌面 + 移动两处），避免与「用户-学校严格一对一绑定」设计冲突。
2. 地图页 `MapPage` 的地点侧滑面板（`<aside>`）升级：评价区域改为可点击展开/收起查看完整评价列表；面板内嵌与 `LocationPage` 一致的评分表单（5 星 + 可选正文 + 提交/撤回 + 校园认证门禁）。
3. 在 `LocationPage` 校园地点页面的地点列表容器之前新增独立搜索框卡片（bg-paper rounded-[16px]），按名称/描述/楼栋/楼层四字段前端过滤。
4. 移除个人中心 `ProfilePage` 中已废弃的「我的订阅」模块卡片 `<SubscriptionsCard />`，避免展示已下线功能误导用户。

## 2. 已完成内容

- [x] 移除 `Header.tsx` 的 `SchoolSwitcher` import 与桌面端 + 移动端两处 `<SchoolSwitcher />` 渲染
- [x] `MapPage.tsx` 升级：评价区域改为可点击展开/收起评价列表（含时间、头像、认证徽标、评分星级、正文、分页/列表）
- [x] `MapPage.tsx` 内嵌评分表单：5 星点击选择、500 字可选正文、提交/撤回双按钮、`VerifyGate compact` 未认证拦截、未登录去登录引导
- [x] `MapPage.tsx` 打开面板时并行拉取 reviews + my_review + detail；提交/撤回后自动回写 avg_score / rating_count / review_count
- [x] `LocationPage.tsx` 在页头下方、地点列表之前新增 bg-paper 卡片包裹的搜索框：Search 图标占位、清除按钮、前端按 4 字段 `useMemo` 过滤、空匹配 EmptyState 提示
- [x] `ProfilePage.tsx` 移除 `<SubscriptionsCard />` 及其 import；撤销中间过程错误放入浏览历史的搜索栏
- [x] 前端 `npm run build`（tsc -b + vite build）通过，0 error，chunk 42 项正常产出
- [x] 提交 Git 代码并同步更新 TODO.md（当前执行任务 6 条勾选项，首条为「评分表单常态防误触」）与 CHANGELOG 2.2.6「前端」分类条目（追加两条 MapPage/LocationPage 常态防误触说明）
- [x] **评分表单常态防误触**：在已有 myReview 时，`LocationPage` 详情页 + `MapPage` 地点弹窗的评分区默认只展示「我已提交的只读摘要卡片 + 「更新评价」按钮」，需点击按钮才展开星星选择器 + 文本框 + 撤回/取消编辑/更新按钮；提交/撤回/取消编辑/切换面板 后，自动复位 `editingReview` 为 false 保证常态不展开
- [x] **常态「我的评价」卡片布局紧凑化**：去掉双层嵌套（外层 border + 内层 bg-mist/40 border 嵌套卡片），改为单层 border 卡片；标题「我的评价」与「更新评价」按钮同排左右对齐；我/认证/星级/评分 横向用 1px 竖线分隔合并为一行；正文直接平铺；MapPage padding p-3 → p-2.5，LocationPage padding p-4 → p-3.5；编辑态/未登录态排版保持不变
- [x] 三次 Git 提交：commit `3dbd0ae`（UI 精简与 4 项主改动）+ commit `d56511e`（fix: 评分表单常态防误触）+ commit `a9d02d3`（style: 常态我的评价卡片紧凑化，去双层嵌套 + 标题按钮同排 + 横排合并）
- [x] 在 `AIwork/` 目录生成本任务报告（中文 8 节模板）

## 3. 未完成内容

暂无。（后端 pytest 未作为本轮强制验证，因修改仅涉及前端且未触及 API 合同；后端 pytest 的 TEST_DATABASE_URL 配置问题是项目既有状态，与本轮修改无关，作为后续回归任务。）

## 4. 实现思路

### 4.1 删除学校切换按钮

从 [Header.tsx](file:///E:/Project/moment-campus/frontend/src/components/layout/Header.tsx) 移除 `SchoolSwitcher` import，并在 flex layout 中删除「标题同行桌面端」与「右侧操作区移动端」两处渲染节点——学校切换改由个人中心的「我的学校」卡片与 `SwitchSchoolModal` 承载，入口更集中、更符合「一对一绑定」场景（由认证后主动切换，而非浏览时随意改校）。

### 4.2 地图弹窗评价展开 + 内嵌评分

参照 `LocationPage` 的评价面板与评分表单实现，在 [MapPage.tsx](file:///E:/Project/moment-campus/frontend/src/pages/MapPage.tsx) 的 `<aside>` 中：

- 将原静态 `{review_count} 条评价` 改为 `<button>`，`onClick` 切换 `locationReviewsOpen`，`aria-expanded` 同步反馈，`ChevronRight` 旋转动画指示展开方向。
- 状态扩展：新增 `locationReviews / locationReviewsLoading / locationMyReview / locationScore / locationReviewContent / locationReviewSubmitting` 六个状态变量。
- 打开面板时并行请求 `postsApi.getPosts(location_id)`、`locationsApi.getReviews(id, 1, 20)`、`locationsApi.getDetail(id)`；后两者用 detail 的 `my_review` 回填当前评分星位与内容。
- 评分提交 `handleLocationSubmitReview` 与撤回 `handleLocationWithdrawReview` 成功后重新拉取列表与详情，用 spread 同步更新 `locationPanel` 的汇总字段，使 UI 无需关闭面板即可看到评分变化。
- 内嵌评分表单位于评价列表与相关帖子之间，最外层用 `<VerifyGate compact message="完成校园身份认证后即可评分评价">` 包裹，未登录态显示「登录后即可评分评价」+ `去登录` 跳转按钮，与 `LocationPage` 心智一致。
- **常态防误触（本轮用户第二次检查时追加修正）**：已有 `locationMyReview` 时默认只读展示我的那条评价（bg-mist/40 背景卡片 + 星级 + 时间 + 认证徽标 + 正文 line-clamp-4）+ 右下角「更新评价」按钮；点击按钮时先回填 `locationScore/locationReviewContent` 并把 `locationEditingReview=true`，才进入星星/文本框编辑器 + 撤回/取消编辑/更新三按钮；提交 `handleLocationSubmitReview` 与撤回 `handleLocationWithdrawReview` 成功后均 `setLocationEditingReview(false)` 回到常态；切换地点面板（`locationPanel` 变化）时也在 cleanup 中一并清掉，避免从 A 点打开编辑态未保存再切到 B 点时状态残留。

### 4.2.1 地点详情页评分表单常态防误触（与地图弹窗同步）

在 [LocationPage.tsx](file:///E:/Project/moment-campus/frontend/src/pages/LocationPage.tsx) 详情 Modal 中与 MapPage 做同步修改：

- 新增 `editingReview` boolean state（默认 false）。
- 条件分支新增一层 `myReview && !editingReview`：该分支渲染只读我的评价摘要卡片（结构与 MapPage 同尺寸调整：字号稍大、圆角 rounded-[10px]、正文不加 line-clamp）+ 「更新评价」按钮。
- 点击更新评价时先执行 `setScore(myReview.score)` + `setContent(myReview.content ?? '')` 回填旧值，再 `setEditingReview(true)` 进入编辑态。
- 编辑态分支额外在左侧显示「取消编辑」按钮（仅 `myReview && editingReview` 时显示），让用户可随时放弃改动回到只读态；提交/撤回成功后同样 reset `editingReview=false`。
- `Edit3` lucide 图标加入 import，用于「更新评价」按钮图标，让语义与 Header 编辑图标保持一致。

### 4.3 地点页面新增搜索框

在 [LocationPage.tsx](file:///E:/Project/moment-campus/frontend/src/pages/LocationPage.tsx) 的 `header` 下方新增独立 `bg-paper rounded-[16px] p-4 shadow-sm` 卡片容器（与用户选中的「div bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4」结构一致），内部放置带 Search 图标前缀、X 清除按钮后缀的 `<input type="search">`：

- 过滤使用 `useMemo`，按「名称 → 描述 → 楼栋 → 楼层」四字段大小写不敏感 `includes`，避免重渲染抖动。
- 渲染分支 `locations.length===0` 改为 `filteredLocations.length===0`，无匹配时 EmptyState 区分「搜索词无匹配」与「真的没地点」两种文案。
- 列表改用 `filteredLocations.map` 渲染。

### 4.4 移除「我的订阅」模块

在 [ProfilePage.tsx](file:///E:/Project/moment-campus/frontend/src/pages/ProfilePage.tsx) 顶部移除 `import { SubscriptionsCard }`，在 JSX 中删除 `<SubscriptionsCard />` 整段调用（位于通知偏好卡后、推荐隐私卡前）。中间过程曾错误把搜索栏放入浏览历史卡片，已全部撤销（移除 `searchKeyword` state、三个 `useMemo` 过滤计算、搜索框 UI div、列表里 keyword 分支与 filteredXXX 映射），彻底回归个人中心无搜索（搜索入口统一在 `/locations` 与 `/search`）。

## 5. 修改文件

新增 0 个，修改 6 个；两次 Git 提交共 10 个文件变更：

| 文件 | 说明 |
|------|------|
| [TODO.md](file:///E:/Project/moment-campus/TODO.md) | 新增「UI 体验精简调整」任务块，6 条 x 勾选项（首条为评分表单常态防误触），更新最后更新日期与当前执行任务标题 |
| [CHANGELOG.md](file:///E:/Project/moment-campus/CHANGELOG.md) | v2.2.6 新增「前端」分类，原 4 条基础 UI 调整 + 2 条追加常态防误触（MapPage + LocationPage 各一条） |
| [frontend/src/components/layout/Header.tsx](file:///E:/Project/moment-campus/frontend/src/components/layout/Header.tsx) | 删除学校切换组件 import + 桌面端/移动端两处渲染 |
| [frontend/src/pages/MapPage.tsx](file:///E:/Project/moment-campus/frontend/src/pages/MapPage.tsx) | 评价展开/收起、评分内嵌、ScoreStars 与 VerifyGate 引入、提交/撤回与汇总回写；**追加修正**：新增 `locationEditingReview` state + 常态只读摘要卡片 + 「更新评价」按钮展开编辑 + 取消编辑/撤回/更新三按钮；关闭面板与切换地点时清理 `locationEditingReview=false` |
| [frontend/src/pages/LocationPage.tsx](file:///E:/Project/moment-campus/frontend/src/pages/LocationPage.tsx) | 新增搜索框、useMemo 过滤、EmptyState 双分支、清除按钮；lucide-react 追加 Edit3 图标 import；**追加修正**：评分区新增 `editingReview` state + 常态只读我的评价卡片 + 「更新评价」按钮展开编辑态 + 提交/撤回/取消编辑后自动复位为 false |
| [frontend/src/pages/ProfilePage.tsx](file:///E:/Project/moment-campus/frontend/src/pages/ProfilePage.tsx) | 移除 SubscriptionsCard import 与渲染；撤销中间过程误加入的搜索栏状态、3 个 useMemo 过滤、搜索框 UI、keyword 分支与 filteredXXX 映射 |

## 6. 影响范围

仅影响前端 Web，不涉及后端/数据库/小程序/API 合同：

- 页头：视觉简化（去掉学校切换器）；学校切换入口仍保留在个人中心「我的学校 → 切换学校」。
- 地图页：地点侧滑面板交互升级，评价与评分入口触达更深但入口更集中，相关帖子展示、地图缩放、发布入口等其他面板行为保持不变。
- 地点页：新增搜索能力纯前端过滤，不发额外请求；空搜索时仍展示全部，性能与原列表一致。
- 个人中心：页面缩短一块卡片高度，滚动与下方通知偏好/推荐隐私/浏览历史/我的发布的顺序与交互均不变。

## 7. 测试与验证

- **构建测试（×2 轮）**：第 1 轮 `npm run build` 42 chunks 通过（0 error）；第 2 轮追加常态防误触后再次 `npm run build` 通过（chunk 仍 42，`LocationPage` 从 16.54kB → 17.93kB，`MapPage` 从 21.03kB → 22.43kB，体积变化符合新增只读卡片 + 状态分支的预期）。
- **静态走查（×2 轮）**：第 1 轮检查四处 diff；第 2 轮追加验证：常态只读卡片无可点击交互元素（除「更新评价」按钮）、编辑态出现的星星点击区域 `<Star size={18/24}>` 与父级 `<button className="p-0.5">` 点击热区不重合导致漏点、取消编辑只改变 `editingReview` 不触发请求、`editingReview/locationEditingReview` 在 4 条路径（提交成功/撤回成功/切换地点面板 cleanup/用户点取消编辑）均会被重置为 false。
- **后端 pytest**：未作为本轮门禁（本轮改动纯前端且不改变 API 合同）；且项目既有 conftest 要求 `TEST_DATABASE_URL` 独立测试库（防止误删开发数据），该环境变量未设置，故跳过并如实记录，后续回归时再补齐不影响本轮 UI 改动的正确性。
- **浏览器 E2E（MCP）**：未运行，因服务虽在运行，但本轮改动是用户在浏览器实时点选检查的交互反馈，已通过用户在页面中实时视觉检查作为主要验证路径，后续若需可再使用 `integrated_browser` 做登录→地点搜索→地图评分的完整链路补测。

## 8. 后续建议

1. 在小程序 `pages/locations/locations`（地点列表页）加入与 Web 同款搜索框，保证两端体验一致。
2. 地图弹窗当前评分只支持一次性撤回/更新，与地点详情页相同；后续可考虑在面板中也显示管理员审核后的 location_summary「此刻摘要」卡片（与 LocationPage 底部同步），避免用户仍需跳到详情看摘要。
3. 个人中心的浏览历史如果需要搜索，可以考虑在将来单独加一个「搜索浏览历史」入口（不要与地点页搜索框混用概念）。
4. 下一次回归执行后端 pytest 时，先设置 `$env:TEST_DATABASE_URL='postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'`（独立测试库），保证清理时不误删开发库数据。
5. 目前常态只读卡片中只显示最近一次提交的评价正文，若用户在取消编辑时希望保留「草稿内容」（未提交但输入到服务器的修改），可以后续给 `score/content/locationScore/locationReviewContent` 做「已保存值 vs 草稿值」分层存储，避免取消编辑后本地输入丢失。
