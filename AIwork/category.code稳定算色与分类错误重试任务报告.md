# 任务报告：category.code 稳定算色与分类错误重试

## 1. 任务概述

按批准计划完善 Web 端动态分类能力：分类颜色仅由 `category.code` 稳定计算，移除首页名称映射与地图固定分类 ID/名称/颜色 fallback；学校切换时清理旧分类、筛选和地图 marker；搜索与地图分类相关请求失败时提供可重试入口；补充对应 E2E。

## 2. 已完成内容

- 新增基于稳定字符串哈希的分类视觉工具，支持 text、background、border、marker 和未知 code neutral 样式。
- 首页帖子与推荐卡片改用 `category.code` 取色，删除中文名称颜色映射。
- 地图 marker API 增加 `category_code`，前端 marker、列表和侧滑面板按 code 取色。
- 删除地图固定分类 ID、名称和颜色 fallback，仅渲染当前学校 API 返回的分类。
- 学校切换时立即屏蔽旧校分类与搜索筛选值，清理地图 marker、marker 索引、列表和面板，并重新请求新学校数据。
- 搜索分类、地点和地图分类分别维护 loading/error 状态，分类及 marker 请求失败均提供重试。
- 新增 3 条 E2E，覆盖搜索分类重试、地图分类与 marker 重试、学校切换清旧数据及稳定颜色。

## 3. 未完成内容

后端既有地图测试仍按数组响应断言，与当前工作区已经存在的 `{ "markers": [...] }` 响应契约不一致，定向测试未通过；本次未修改既有测试文件。未执行全量后端测试。

## 4. 实现思路

使用 FNV-1a 风格的无符号字符串哈希，将规范化后的 `category.code` 映射到固定水墨色板。地图接口直接返回分类 code，避免前端通过数据库 ID 或中文名称推断视觉和名称。分类状态带有 `schoolId` 归属，渲染和请求构造仅接受当前学校状态，从首帧开始隔离旧校数据。Playwright 使用持续失败到用户点击重试的路由桩，验证错误状态不会被重复请求掩盖。

## 5. 修改文件

- `backend/app/api/map.py`
- `frontend/src/utils/categoryVisual.ts`
- `frontend/src/utils/mapMarker.ts`
- `frontend/src/services/map.ts`
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/MapPage.tsx`
- `frontend/src/pages/SearchPage.tsx`
- `frontend/e2e/validation-and-categories.spec.ts`
- `frontend/src/pages/PostDetailPage.tsx`：移除并发改动中已不再使用的 `Loading` 导入，恢复 build/lint 门禁。

## 6. 影响范围

影响 Web 首页、搜索页、地图页、地图 marker API 和 Web Playwright E2E。未修改 `miniprogram/`，未修改 `TODO.md`，未提交 Git。地图 API 消费方改为读取 `{ markers }` 响应并使用新增 `category_code` 字段。

## 7. 测试与验证

- `npm run build`：通过。
- `npm run lint`：退出码 0，0 error，保留项目既有 26 条 warning。
- `npx playwright test e2e/validation-and-categories.spec.ts --project=chromium`：3 passed。
- 后端定向地图测试使用 `TEST_DATABASE_URL=postgresql+asyncpg://.../moment_campus_test`：2 failed，原因是既有测试仍把地图响应当数组读取，且一条 N+1 样本数量断言与当前测试数据/契约不一致。
- `git diff --check`：目标修改文件通过。
- 未执行 MCP `integrated_code_mode` 端到端链路测试：当前可用工具中没有该 MCP 调用入口；已通过现有 Playwright 浏览器 E2E 完成本任务相关 UI 链路验证。

## 8. 后续建议

- 同步 `backend/tests/test_search.py` 与 `backend/tests/test_tenant_isolation.py` 到当前 `{ markers }` 响应契约后，再执行完整后端测试。
- 后续可将剩余 26 条既有 lint warning 分批治理，但不属于本次分类与重试范围。
- 若地图 API 未来改为分页或响应包装扩展，继续保持服务层统一解包，避免页面直接依赖后端响应形状。
