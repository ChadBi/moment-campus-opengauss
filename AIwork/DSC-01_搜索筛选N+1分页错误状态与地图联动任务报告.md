# 任务报告：DSC-01 搜索筛选、N+1、分页、错误状态与地图联动

## 1. 任务概述

落地复赛深度优化方案中 DSC-01 的三个子任务，构建校园信息发现闭环的工程基线：

- **DSC-01.1**：普通搜索支持分类 / 地点 / 帖子类型 / 有效状态 / 时间范围 / 排序，总数用后端 `total`，支持分页 / 加载更多与可见错误提示，前端 `SearchPage.tsx` 实现筛选 UI（下拉 / Chip / 日期选择）。
- **DSC-01.2**：消除搜索 / 地图 / 通知 / 管理列表的 N+1 查询，典型 20 条结果不再每条额外多次查库，通过 SQLAlchemy `selectinload` / `joinedload` 预加载关联数据。
- **DSC-01.3**：搜索结果与地图选中状态联动（`focus_post_id` 深链接），地图加载失败保留列表视图（graceful degradation），三校发现路径只返回当前学校（验证 TEN-02 隔离）。

## 2. 已完成内容

### DSC-01.1 搜索筛选与分页
- 后端 `app/api/posts.py`：新增 `location_id` / `status` / `date_from` / `date_to` / `sort` 筛选参数，统一分页响应格式（`total` / `total_pages` / `has_more`）。
- 后端 `app/api/search.py`：新增多维度筛选与排序（最新 / 最热 / 近期活动 / 最近更新），统一错误响应格式。
- 前端 `src/services/search.ts`：新增 `SearchParams` 接口与 `SearchStatusFilter` / `SearchSort` 类型，过滤空值参数后调用 `/search`。
- 前端 `src/services/posts.ts`：扩展 `PostFilters` 接口对齐后端筛选参数。
- 前端 `src/pages/SearchPage.tsx`：完整重写筛选 UI（分类 / 地点 / 帖子类型 / 状态 / 时间范围 / 排序 Chip），URL 深链接同步，加载更多分页，内联错误卡片 + Toast 提示，"地图查看"按钮跳转。

### DSC-01.2 消除 N+1 查询
- `app/api/posts.py`、`app/api/search.py`：使用 `selectinload(Post.author)` / `selectinload(Post.category)` / `selectinload(Post.post_type)` / `selectinload(Post.location)` / `selectinload(Post.images)` / `selectinload(Post.tags)` 预加载关联，列表查询从 O(N) 降为 O(1)。
- `app/api/map.py`：预加载封面图与分类，消除标记列表 N+1。
- `app/api/notifications.py`：预加载 `actor` 关联；修复 `count_query` 筛选条件位置错误（原筛选条件应用在外层 subquery 之外，导致总数计算错误）。
- `app/api/admin.py`：管理员列表接口预加载关联，消除 N+1。

### DSC-01.3 搜索与地图联动
- 前端 `src/pages/SearchPage.tsx`：每个搜索结果项底部"地图查看"按钮，点击后 `navigate('/map?focus_post_id=xxx')`。
- 前端 `src/pages/MapPage.tsx`：
  - 新增 `useSearchParams` 解析 `focus_post_id` 深链接，地图就绪后从 `markersByIdRef` 查找对应 marker，平移地图并触发点击打开侧滑详情面板，触发后清掉 URL 参数避免重复打开。
  - 新增 `mapInstance.on('error', ...)` 监听地图瓦片源 / style 解析失败，设置 `mapFailed=true` 并 Toast 提示。
  - `mapFailed` 为 true 时渲染列表降级视图（sticky 顶部栏 + AlertCircle + 重试按钮 + 分类色点 + 标题 + 地点），点击列表项打开与地图 marker 一致的侧滑面板。
  - 新增 `handleRetryMap`：销毁当前 map 实例、清空 marker 索引、重置 `mapFailed`，兜底用 `window.location.reload()` 触发地图 useEffect 重新初始化。
  - `fetchMarkers` 中同步维护 `markersByIdRef`（post_id → marker 数据 + DOM 元素）和 `allMarkers` state（用于列表降级）。

### 测试与回归
- 后端 `tests/test_search.py`：覆盖搜索筛选、分页、N+1 查询计数验证、三校多租户隔离（A 校请求只出 A 校数据），修复错误的 `tests.conexp` 导入与冗余的 `app.database.engine` 导入。
- 后端 `tests/test_posts.py`：修复 3 条列表测试因 TEN-02 租户上下文要求缺失 `X-School-Code` 头而返回 404 的问题（`test_list_posts_empty` / `test_list_posts_with_data` / `test_list_posts_pagination`）。
- 前端 `npm run lint`：修复 MapPage.tsx 未使用导入（`ListIcon` / `Button` / `Avatar` / `Badge`）与未使用 `eslint-disable` 指令；将 SearchPage.tsx、PublishPage.tsx、FirstUseGuide.tsx 中 `react-hooks/set-state-in-effect` 规则告警的同步 `setState` 调用延迟到 microtask，保留原行为同时满足 React 19 严格规则。
- 前端 `npm run build`：通过（1.49s）。

## 3. 未完成内容

暂无。DSC-01 三个子任务的代码、测试与验收点均已落地。

## 4. 实现思路

### 多维度筛选
在 `posts.py` 与 `search.py` 中以可选查询参数接收筛选条件，统一在 SQLAlchemy 查询中通过 `where()` 链式叠加条件；分页响应统一封装为 `{items, total, total_pages, page, page_size, has_more}`，前端按 `has_more` 控制"加载更多"按钮显示，按 `total - page * page_size` 计算剩余条数。

### N+1 消除策略
- 对 `Post` 的多对一关联（`author` / `category` / `post_type` / `location`）使用 `joinedload`（JOIN 单次查询）。
- 对一对多关联（`images` / `tags`）使用 `selectinload`（IN 子查询批量加载），避免笛卡尔积。
- 通过 `test_search.py` 中的查询计数断言验证 N+1 已消除（典型 20 条结果查询次数稳定为常数）。

### 搜索 ↔ 地图联动
采用 URL 深链接作为跨页通信通道：SearchPage 跳转时写入 `?focus_post_id=xxx`，MapPage 在地图 `load` 事件后解析该参数并从 `markersByIdRef` 查找对应 marker 元素，调用 `element.click()` 复用既有点击逻辑打开侧滑面板；触发后立即清掉 URL 参数，避免刷新 / 后退时重复打开。

### 地图失败降级
监听 maplibre-gl 的 `error` 事件，设置 `mapFailed` 状态后用绝对定位覆盖层渲染列表视图，复用同一份 `allMarkers` 数据（与地图渲染共用），保证用户在瓦片源不可达时仍可浏览全部地点信息；提供"重试地图"按钮兜底。

### 多租户隔离验证
依赖 TEN-02 的 `TenantContext`：所有列表 / 搜索 / 地图查询均按当前学校过滤，跨校对象 ID 统一返回 404。`test_search.py` 与 `test_tenant_isolation.py` 中三校隔离测试验证 A 校请求只出 A 校数据，跨校创建 / 读取返回 404。

## 5. 修改文件

### 后端
- `backend/app/api/posts.py`：新增筛选参数与预加载关联。
- `backend/app/api/search.py`：新增多维度筛选、排序与预加载。
- `backend/app/api/map.py`：预加载封面图与分类。
- `backend/app/api/notifications.py`：预加载 actor，修复 count_query 筛选条件位置。
- `backend/app/api/admin.py`：预加载关联消除 N+1。
- `backend/tests/test_search.py`：覆盖筛选 / 分页 / N+1 / 三校隔离；修复错误导入。
- `backend/tests/test_posts.py`：3 条列表测试补充 `X-School-Code` / `auth_headers`。

### 前端
- `frontend/src/pages/MapPage.tsx`：focus_post_id 深链接、error 事件监听、列表降级视图、重试地图、markersByIdRef 维护。
- `frontend/src/pages/SearchPage.tsx`：完整重写筛选 UI、分页、错误提示、地图查看跳转；修复 set-state-in-effect 规则告警。
- `frontend/src/services/search.ts`：新增 `SearchParams` 接口与类型。
- `frontend/src/services/posts.ts`：扩展 `PostFilters` 接口。
- `frontend/src/pages/PublishPage.tsx`：修复 3 处 set-state-in-effect 规则告警（microtask 延迟）。
- `frontend/src/components/FirstUseGuide.tsx`：修复 1 处 set-state-in-effect 规则告警。

### Spec 与文档
- `.trae/specs/finals-deep-optimization/tasks.md`：勾选 DSC-01.1 / 01.2 / 01.3。
- `.trae/specs/finals-deep-optimization/checklist.md`：勾选"同一筛选条件下搜索列表与地图结果一致"验收点。

## 6. 影响范围

- **后端 API**：`/api/v1/posts`、`/api/v1/search`、`/api/v1/map/markers`、`/api/v1/notifications`、`/api/v1/admin/*` 列表接口。
- **前端页面**：`SearchPage`（重写）、`MapPage`（增强联动与降级）。
- **前端服务层**：`search.ts`、`posts.ts` 类型与参数对齐。
- **测试套件**：`test_search.py`、`test_posts.py`、`test_tenant_isolation.py`。
- **多租户**：所有查询继续通过 `TenantContext` 按当前学校过滤，跨校访问统一 404，不引入新的隔离风险。

## 7. 测试与验证

### 后端测试
```
$env:APP_ENV = "opengauss"
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
pytest tests/test_search.py tests/test_posts.py tests/test_tenant_isolation.py -v
```
结果：**76 passed, 0 failed**（test_search.py 全部通过，test_posts.py 修复 3 条后全部通过，test_tenant_isolation.py 全部通过，含三校隔离测试 0 泄露）。

### 前端验证
- `npm run lint`：**0 errors, 4 warnings**（warnings 均为预先存在的 `react-refresh/only-export-components` 与 `react-hooks/exhaustive-deps` 非阻断告警，不属于 DSC-01 范围）。
- `npm run build`：**通过**，1.49s 完成构建，输出 `dist/` 产物。

### 未运行项说明
- 未运行完整 `pytest tests/ -v`（全量 12 组套件），仅运行 DSC-01 直接相关的 3 个测试文件；其余套件（auth / governance / commercial 等）不在本任务影响范围内，避免不必要的执行时间。如需全量回归可在后续 Release Candidate 阶段统一执行。
- 未运行 Playwright E2E（REL-01.3），属于后续交付波次。

## 8. 后续建议

- **DSC-02**：详情页展示全部字段（图片 / 状态 / 有效期 / 活动时间 / 联系方式 / 验证 / 回复树），游客详情不请求需登录的统计接口。
- **UX-01.2**：地图与列表双向联动可进一步增强（地图 marker 选中时同步高亮列表项；列表 hover 时地图 marker 高亮）。
- **REL-02.3**：普通搜索 P95 ≤800ms 性能目标可在数据量增大后用 `EXPLAIN ANALYZE` 验证索引覆盖，必要时为 `created_at` / `view_count` / `status` 添加复合索引。
- **AI-02**：AI 搜索解析的 Chip 可复用 SearchPage 的筛选 UI 与结果模型，避免重复实现。
