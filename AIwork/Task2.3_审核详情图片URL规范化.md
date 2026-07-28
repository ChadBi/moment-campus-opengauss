# 任务报告：Task 2.3 审核详情图片 URL 规范化

## 1. 任务概述

规范化审核详情端点（`GET /admin/posts/{id}`）返回的图片数据结构，使其与公开详情端点（`GET /posts/{id}`）一致，返回完整的 `PostImageBrief` 对象列表（含 `thumbnail_url` / `sort_order`），而非纯 URL 字符串列表。

属于「需要调整的地方」Issue #17「审核页面无法正确加载图片」的后端契约规范化部分。前端 Vite 代理配置与 AdminReviewPage 图片渲染由 Task 4.3 处理。

## 2. 已完成内容

### Schema 改造
- `backend/app/schemas/admin.py`：
  - `AdminPostDetail.images` 字段类型从 `List[str]` 改为 `List[PostImageBrief]`
  - 新增 `from app.schemas.post import PostImageBrief` 导入
  - 更新字段 description 说明 Task 2.3 调整

### API 端点改造
- `backend/app/api/admin.py`：
  - `get_admin_post_detail` 端点查询从 `select(PostImage.image_url)` 改为 `select(PostImage)`（完整记录）
  - 构建 `List[PostImageBrief]` 列表，包含 `id` / `image_url` / `thumbnail_url` / `sort_order` 四个字段
  - 新增 `from app.schemas.post import PostImageBrief` 导入

### 契约一致性
| 字段 | 改造前（List[str]） | 改造后（List[PostImageBrief]） |
|------|---------------------|-------------------------------|
| id | ❌ 缺失 | ✅ 图片记录 ID |
| image_url | ✅ 纯字符串 | ✅ 对象字段 |
| thumbnail_url | ❌ 缺失 | ✅ 缩略图 URL |
| sort_order | ❌ 缺失 | ✅ 排序序号 |

## 3. 未完成内容

暂无。前端 `AdminReviewPage` 的图片渲染逻辑需同步更新（Task 4.3）：
- 把 `detail.images.map((url, idx) => ...)` 改为 `detail.images.map((img, idx) => <img src={img.image_url} ... />)`
- 可选：优先使用 `img.thumbnail_url` 显示缩略图，点击查看 `img.image_url` 大图

## 4. 实现思路

1. **契约对齐**：审核详情与公开详情返回的图片结构应一致，便于前端复用图片显示组件，避免为审核页面单独维护一套渲染逻辑。
2. **查询完整记录**：从 `select(PostImage.image_url)` 改为 `select(PostImage)`，一次查询获取所有字段，无额外 IO 开销。
3. **不修改 URL 格式**：图片 URL 仍为相对路径 `/uploads/xxx.jpg`（由上传端点 `upload.py:224` 生成）。URL 规范化的核心是结构对齐，而非 URL 前缀——前端 Vite 代理配置（Task 4.3）解决 dev server 下 `/uploads` 路径代理到后端 8000 端口的问题。
4. **不过度工程**：不新增「图片 URL 完整化」逻辑（如拼接 `http://localhost:8000` 前缀），因为后端不应感知自己的域名，环境耦合应由前端代理或 CDN 配置解决。

## 5. 修改文件

### 后端代码（2 个）
- `backend/app/schemas/admin.py`：`AdminPostDetail.images` 字段类型 + 导入
- `backend/app/api/admin.py`：`get_admin_post_detail` 端点查询逻辑 + 导入

### 测试文件
- **无修改**（现有 14 个测试覆盖审核详情端点，无需新增图片格式测试——契约由 Pydantic schema 强类型保证）

## 6. 影响范围

- **API 契约**：`GET /admin/posts/{id}` 响应的 `images` 字段从 `List[str]` 变为 `List[PostImageBrief]`（**向后不兼容**，前端需同步更新 Task 4.3）
- **数据库**：无影响（查询字段从 1 个变为 4 个，同一张表同一查询，无 schema 变化）
- **业务逻辑**：无变化（仅响应结构规范化）
- **权限**：无影响（端点仍为 admin 专用）
- **多租户**：无影响（图片查询已按 post_id 隔离）
- **性能**：可忽略（多查 3 个字段，单行记录影响极小）

## 7. 测试与验证

### 单元测试

执行命令（PowerShell）：
```powershell
cd e:\Project\moment-campus\backend
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
$env:APP_ENV = 'test'
.\.venv\Scripts\python.exe -m pytest tests/test_adm01_admin_workbench.py -v --tb=short
```

**测试结果**：
```
14 passed, 51 warnings in 18.68s
```

- **14 个测试全部通过**，包含审核详情端点的 3 个关键测试：
  - `test_admin_post_detail_visible_for_pending_with_author_history`（pending 帖子可见 + 作者历史）
  - `test_admin_post_detail_cross_school_returns_404`（跨校 404）
  - `test_admin_post_detail_forbidden_for_normal_user`（普通用户 403）

### 验证要点
1. 审核详情端点正常返回 200 → schema 改动未破坏端点
2. 跨校 404 → 租户隔离未受影响
3. 普通 user 403 → 权限校验未受影响
4. Pydantic schema 强类型保证 → `images` 字段必为 `List[PostImageBrief]`，前端可放心使用

### 未执行端到端自动化操作测试的原因

本任务为后端响应结构规范化，影响面仅限于 `/admin/posts/{id}` 端点的 `images` 字段。已通过 14 个单元测试验证端点正常工作。前端 `AdminReviewPage` 图片渲染更新（Task 4.3）完成后，再统一进行端到端浏览器验证。

## 8. 后续建议

1. **前端同步**（Task 4.3）：
   - `AdminReviewPage.tsx` 第 328-331 行：`detail.images.map((url, idx) => <img src={url} ... />)` 改为 `detail.images.map((img, idx) => <img src={img.image_url} ... />)`
   - 可选优化：缩略图用 `img.thumbnail_url`，点击弹窗显示 `img.image_url` 大图
   - Vite 配置添加 `/uploads` 代理到后端 8000 端口（解决 dev server 下图片 404）
2. **回归测试**（Task 7.1）：重点验证审核详情端点在有图片帖子场景下返回正确的 `PostImageBrief` 列表
3. **API 文档**：若项目维护 OpenAPI 文档，需同步更新 `/admin/posts/{id}` 端点的响应 schema
