# 任务报告：PUB-01.1 合并 MapPage 与 PublishPage 发布表单逻辑

## 1. 任务概述

修复 PUB-01.1：将 `MapPage` 的发帖面板与 `PublishPage` 的发布表单抽取为共享子组件 `PostForm`，保证两处入口的字段集、校验规则、草稿恢复逻辑完全一致。

具体目标：
- `MapPage` 侧滑发帖面板补全缺失字段（post_type_id、图片、标签、有效期、活动时间、联系方式、失物类型、草稿按钮）。
- 分类 / 信息类型 / 地点全部来自 API（按当前学校过滤，依赖 `X-School-Code` 头）。
- 保留 `PublishPage` 已有草稿恢复机制，`MapPage` 表单也支持草稿恢复（相同的 localStorage key 策略，按 用户+学校 分键）。
- 不破坏 TEN-02 多租户隔离、PUB-01.2（图片/标签/有效期等）、PUB-01.3（发布成功跳 `/profile`）。

## 2. 已完成内容

1. 新增共享子组件 `frontend/src/components/PostForm.tsx`：
   - 支持 `variant='page'`（`PublishPage` 用，Card + Input 组件 + 宽松间距）与 `variant='panel'`（`MapPage` 侧滑面板用，紧凑原生 input）两种 UI 风格，字段集完全一致。
   - 字段：标题、内容、信息类型（API）、分类（API）、图片（最多 9 张，≤5MB）、标签（最多 5 个）、地点（已核验 + 待核验分组 + 新增地点三件套）、有效期、活动开始/结束时间、联系方式、失物类型、匿名。
   - 草稿恢复：`localStorage` key = `publish_draft::u{userId}::s{schoolId}`；自动保存（防抖 1s）+ `beforeunload` 同步写入 + 横幅恢复/丢弃；提交成功后清除。
   - 校验：标题 5-100、内容 10-5000、必选分类/信息类型/地点、新增地点三件套互校验、经纬度范围、活动时间顺序。
   - 提交：填了新地点三件套时先调 `createLocation` 创建 `is_verified=false` 地点，再调 `createPost`，失败兜底走 `createPost` 的 `location_name+lat+lng` 自动创建。
2. 改造 `PublishPage.tsx`：移除内联表单，集成 `PostForm variant='page'`，保留页面级标题/说明/当前学校名，沿用 PUB-01.3 跳转策略。
3. 改造 `MapPage.tsx`：移除原内联发帖表单（line 80-86、543-710），集成 `PostForm variant='panel'`，地图点选坐标通过 `defaultLocationLat/Lng` 传入（只读预填），`key` 绑定坐标确保每次打开重新初始化，`onSuccess` 关闭面板 + 刷新地图标记 + 跳 `/profile`。
4. 修复 PUB-01.1 改造引入的 4 个 TypeScript 错误：
   - `PostForm.tsx`：移除未使用的 `currentSchoolName`。
   - `MapPage.tsx`：移除未使用的 `currentSchoolId` 与未导入的 `useCampusStore` 引用（原代码引用了未导入的 store，且变量未使用）。
5. 更新 `tasks.md`，将 PUB-01.1 勾选为 `[x]`。

## 3. 未完成内容

- 2 个**与 PUB-01.1 无关**的预存 ESLint 错误仍存在（属于 REL-01.1 范围）：
  - `frontend/src/components/FirstUseGuide.tsx:93` `react-hooks/set-state-in-effect`（effect 内同步 setState）。
  - `frontend/src/pages/RegisterPage.tsx:36` `react-hooks/set-state-in-effect`（effect 内同步 setState）。
- 本次未对上述两个文件做任何改动，避免越界修改无关模块。

## 4. 实现思路

- **共享组件 + variant 差异化**：表单核心逻辑（state、校验、提交、草稿、API 调用）全部收敛到 `PostForm`，通过 `variant` 切换样式表 `getVariantStyles(variant)`，避免重复维护两套表单。
- **地图点选坐标只读预填**：`MapPage` 通过 `defaultLocationLat/Lng` 传入坐标，`PostForm` 初始化 `new_location_lat/lng` 字段并标记 `locationCoordsReadOnly`，用户可改名称或改选已有地点；用 `key={lat,lng}` 保证每次打开面板重新初始化表单状态。
- **草稿恢复按 用户+学校 分键**：`buildDraftStorageKey(userId, schoolId)`，避免跨用户/跨学校串数据；首次挂载检测旧草稿，仅在当前表单为空时弹出恢复横幅；自动保存防抖 1s + `beforeunload` 同步写入兜底；提交成功后清除。
- **多租户隔离不破坏**：分类/类型/地点全部走 `categoriesApi`（Axios 拦截器注入 `X-School-Code`），切换学校时 `useEffect([currentSchoolId])` 重新拉取并清空已选地点。
- **PUB-01.3 跳转策略不破坏**：`PublishPage` 与 `MapPage` 都在 `onSuccess` 回调中 `setTimeout(() => navigate('/profile'), 800)`。

## 5. 修改文件

- 新增：`frontend/src/components/PostForm.tsx`（共享发布表单组件，约 1060 行）。
- 修改：`frontend/src/pages/PublishPage.tsx`（替换为 PostForm page variant，53 行）。
- 修改：`frontend/src/pages/MapPage.tsx`（替换为 PostForm panel variant，移除内联表单与未用导入，694 行）。
- 修改：`.trae/specs/finals-deep-optimization/tasks.md`（PUB-01.1 勾选 `[x]`）。
- 新增：`AIwork/PUB-01.1_合并发布表单逻辑任务报告.md`（本报告）。

## 6. 影响范围

- 发布入口：`PublishPage`（页面发帖）、`MapPage`（地图点选发帖面板）两处用户路径。
- 草稿恢复：覆盖所有登录用户 + 所有当前学校的发布场景。
- 多租户：未改动 `X-School-Code` 注入逻辑与 `useCampusStore` 持久化字段，TEN-02 隔离机制不受影响。
- 后端 API：未改动，沿用 `POST /posts`、`POST /locations`、`GET /categories|post-types|locations` 既有契约。
- 不影响：搜索、地图标记渲染、详情、审核、通知、个人中心等其他模块。

## 7. 测试与验证

执行的前端验证（在 `frontend/` 目录）：

1. `npm run build`：**通过**（exit code 0，`tsc -b && vite build` 成功，产物正常输出 `dist/assets/PostForm-*.js`、`MapPage-*.js`、`PublishPage` 内联在 index 中）。
2. `npm run lint`：**PUB-01.1 相关错误已清零**；仅剩 2 个与 PUB-01.1 无关的预存错误（`FirstUseGuide.tsx:93`、`RegisterPage.tsx:36`，均属 REL-01.1 范围）+ 4 个既有 warning。

未运行后端测试：本次改动仅涉及前端组件，未触碰后端代码与 API 契约，无需 `pytest tests/ -v`。

未运行端到端测试：PUB-01.1 为表单合并重构，未引入新业务流程；建议在 PUB-02.2（完整 E2E）任务中统一覆盖"保存草稿 → 编辑 → 提交 → 审核 → 通知 → 公开"全链路。

## 8. 后续建议

1. **REL-01.1**：修复 `FirstUseGuide.tsx:93` 与 `RegisterPage.tsx:36` 的 `react-hooks/set-state-in-effect` 错误，使 `npm run lint` 0 错误。两处均为 effect 内同步 `setState`，可改为派生 state 或在事件回调中设置。
2. **PUB-02.1 / PUB-02.2**：草稿列表、继续编辑、删除/归档、重新提交、完整 E2E。`PostForm` 已暴露 `onSuccess(status)` 回调，可直接对接草稿列表页的"继续编辑"入口（传入初始值 + 复用同一组件）。
3. **UX-01.4**：当前草稿自动保存间隔为 1s 防抖 + `beforeunload` 同步，已满足"每 5 秒/离开页前自动保存"；恢复横幅已显示保存时间。可补充"冲突选择"（本地草稿 vs 服务端草稿）UI。
4. **MapPage 体积优化**：`MapPage-*.js` 产物 1.04MB（gzip 277KB），主要来自 maplibre-gl。后续可在 REL-01.1 / REL-02 中考虑动态 import 切片。
5. **MapPage 既存 warning**：`useCallback` 多余 `navigate` 依赖、`popupRef.current` 在 cleanup 中可能漂移。不影响功能，可在 REL-01.1 一并清理。
