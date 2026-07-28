# 任务报告：PostForm 重构 — 移除 tags/post_type/activity_time，新增地图选点

## 1. 任务概述

对前端统一发布表单组件 `PostForm.tsx` 进行重构，移除已被后端删除的 `tags` / `post_type` / `activity_start_at` / `activity_end_at` 字段及其相关状态、校验、UI，同时新增基于 MapLibre GL 的地图选点功能，并对表单布局做以下调整：
- 「有效期」重命名为「信息截止时间」
- 「失物类型」改为条件渲染（仅 `lost_found` 分类显示）
- 「地点」改为非必填
- 经纬度可由地图选点自动填充

附带清理 `SearchPage`、`PostDetailPage`、`services`、`types` 中残留的 post_type / tags / activity_* 引用以保证前端构建通过。

## 2. 已完成内容

1. **PostForm.tsx 重构**
   - 移除 `PublishFormState` 中的 `post_type_id` / `tags` / `activity_start_at` / `activity_end_at` 字段
   - 移除 `handlePostTypeSelect` / `handleAddTag` / `handleRemoveTag` / `handleTagKeyDown` / `adoptTags` 等函数
   - `handleAISuggest` 请求体移除已删除字段
   - `handleSubmit` 提交载荷移除已删除字段
   - `validate` 校验移除 post_type 必选、activity 时间顺序校验；地点改为非必填（仅当填写新地点三件套时校验完整性）
   - 编辑模式加载（`getPost`）移除已删除字段
   - 移除「信息类型」「标签」UI 区块
   - 移除「活动开始时间 / 活动结束时间」输入框
   - 「有效期」label 改为「信息截止时间」
   - 「失物类型」改为条件渲染：仅当 `selectedCategory?.code === 'lost_found'` 时显示
   - 「地点」label 移除必填星号，改为「（可选；不选则发布为无地点信息）」
   - 新增「在地图上选择位置」按钮 + Modal 弹窗（内嵌 MapLocationPicker）
   - AI 建议面板移除「建议标签」区块

2. **MapLocationPicker 组件（新增）**
   - 基于 `maplibre-gl` 实现
   - 支持点击地图设置 marker 并回调 `onPick(lat, lng)`
   - 支持只读模式（`readOnly=true`，仅展示坐标点）
   - 初始中心点优先级：`initialLat/Lng` → 当前学校中心点 → 兜底江南大学坐标
   - 切换学校时自动平移到新中心（未选点时）
   - 底部展示选中坐标（纬度/经度）

3. **SearchPage 最小化修复**（完整重构留待 Task 3.3）
   - 移除 `PostTypeListItem` 导入
   - 移除 `postTypes` state 与 `listPostTypes` 调用
   - 移除 `postTypeId` state 及其在 `buildParams` / `syncUrlParams` / `handleReset` / `activeFilterCount` / `SavedQueryEntry` 中的引用
   - 移除「信息类型」筛选下拉 UI

4. **PostDetailPage 最小化修复**（完整重构留待 Task 3.2）
   - 移除 `post.post_type` Badge
   - 移除 `post.activity_start_at / activity_end_at` 活动时间展示
   - 移除 `post.tags` 标签列表展示
   - 移除未使用的 `Calendar` 图标导入

5. **services / types 同步**
   - `services/categories.ts`：已在上次会话移除 `PostTypeListItem` 与 `listPostTypes`
   - `services/index.ts`：移除 `PostTypeListItem` 再导出
   - `services/posts.ts`：已在上次会话移除 `CreatePostRequest` 中的 `post_type_id` / `tags` / `activity_*`
   - `types/index.ts`：已在上次会话移除 `PostTypeBrief` / `TagBrief` 及 `Post` / `PostListItem` 中对应字段

## 3. 未完成内容

暂无（Task 3.1 范围内全部完成）。SearchPage 与 PostDetailPage 的完整重构分别由 Task 3.3 / Task 3.2 负责。

## 4. 实现思路

- **字段移除**：从表单 state → 校验 → 提交载荷 → 编辑模式加载 → UI 渲染，逐层清理已删除字段，避免残留引用导致的 TypeScript / 运行时错误。
- **地图选点**：复用项目已有的 `maplibre-gl` 依赖（MapPage 已使用），新建 `MapLocationPicker` 组件封装地图初始化、marker 管理、点击选点回调；在 PostForm 中通过 `Modal` 弹窗集成，选点后自动回填经纬度字段。
- **条件渲染**：失物类型仅当分类为 `lost_found` 时显示，通过 `selectedCategory?.code === 'lost_found'` 判断。
- **最小化修复**：SearchPage / PostDetailPage 中残留的 post_type / tags / activity_* 引用会阻塞前端构建，本次做最小化移除以保证 Task 3.1 不破坏整体构建；完整重构由后续任务负责。

## 5. 修改文件

新增：
- `frontend/src/components/MapLocationPicker.tsx`

修改：
- `frontend/src/components/PostForm.tsx`
- `frontend/src/pages/PostDetailPage.tsx`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/src/services/categories.ts`（上次会话已改，本次无新增改动）
- `frontend/src/services/index.ts`
- `frontend/src/services/posts.ts`（上次会话已改，本次无新增改动）
- `frontend/src/types/index.ts`（上次会话已改，本次无新增改动）

## 6. 影响范围

- **发布表单（PostForm）**：发布 / 编辑帖子的表单字段、校验、提交载荷变化
- **发布页（PublishPage）/ 地图页（MapPage 侧滑面板）**：均使用 PostForm，受其重构影响
- **搜索页（SearchPage）**：移除信息类型筛选（最小化修复，完整重构留待 Task 3.3）
- **帖子详情页（PostDetailPage）**：移除 post_type / tags / activity 时间展示（最小化修复，完整重构留待 Task 3.2）
- **AI 辅助发布建议**：请求体不再传 tags / post_type / activity_*；UI 移除「建议标签」采纳区块

## 7. 测试与验证

- **前端构建**：执行 `npm run build`（tsc -b + vite build），构建成功，无 TypeScript 错误，产物正常生成。
- **未运行后端测试**：本次改动仅涉及前端，未改动后端代码，故未运行 `pytest`。
- **未运行 MCP 浏览器端到端测试**：按计划由 Task 7.3 统一进行关键链路端到端验证。

## 8. 后续建议

1. **Task 3.2**：完整重构 PostDetailPage — 布局重排 + 返回按钮 + 移除问题报告区。
2. **Task 3.3**：完整重构 SearchPage — 移除保存查询、移除每日摘要 / 邮件、优化 AI 快捷问题。
3. **Task 7.3**：MCP 浏览器端到端测试发布表单全链路（含地图选点、失物类型条件渲染、地点非必填）。
4. 可考虑为 `MapLocationPicker` 增加搜索框（按地点名称定位），提升大范围选址体验。
