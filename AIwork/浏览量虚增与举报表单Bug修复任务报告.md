# 任务报告：浏览量虚增与举报表单Bug修复

## 1. 任务概述

修复帖子详情页的三个功能缺陷：
1. 点赞/取消点赞导致浏览量异常上升
2. 举报提交后表单不关闭
3. 帖子详情页与列表预览页的浏览量/点赞数显示不一致

## 2. 已完成内容

- 后端：为 `GET /posts/{id}` 接口添加 `increment_view` 查询参数，允许调用方控制是否增加浏览次数
- 前端：修复 `handleLike` 函数，不再调用 `loadPost()`，改为使用 API 返回的 `LikeResponse` 本地更新状态
- 前端：修复 `handleComment` 函数，不再调用 `loadPost()`，改为本地更新 `comment_count`
- 前端：修复 `handleReply` 函数，不再调用 `loadPost()`，改为本地更新 `comment_count`
- 前端：修复 `handleValidate` 函数，改为使用 `loadPost(true)` 跳过浏览量自增
- 前端：修复举报表单，添加 `if (reporting) return;` 防重复提交守卫

## 3. 未完成内容

暂无

## 4. 实现思路

### 问题1：点赞导致浏览量上升
- **根因**：`handleLike` 调用 `interactionsApi.likePost()` 后调用 `loadPost()` 刷新页面数据，而 `loadPost()` 默认通过 `GET /posts/{id}` 带 `increment_view=true` 自增浏览量
- **方案**：后端为 `get_post` 添加 `increment_view` 参数（默认 `true`），前端点赞/评论/回复等操作不再调用 `loadPost()`，直接使用 API 响应数据本地更新状态

### 问题2：举报表单不关闭
- **根因**：用户快速双击提交按钮导致重复请求，第二次请求因"已举报"返回 400 错误，触发 catch 块但未关闭表单
- **方案**：添加 `if (reporting) return;` 守卫，防止重复提交

### 问题3：数据不一致
- **根因**：详情页每次操作都调用 `loadPost()` 刷新，导致浏览量反复自增，与列表页（不调用 `loadPost`）数据不一致
- **方案**：所有操作类函数（点赞、评论、回复、验证）不再调用 `loadPost()`，改为本地更新状态

## 5. 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/api/posts.py` | `get_post` 端点添加 `increment_view` 查询参数 |
| `frontend/src/services/posts.ts` | `getPost` 方法添加 `incrementView` 参数支持 |
| `frontend/src/pages/PostDetailPage.tsx` | 修复 `loadPost`、`handleLike`、`handleComment`、`handleReply`、`handleValidate`、`handleReport` 函数 |

## 6. 影响范围

- 帖子详情页的点赞、取消点赞、评论、回复、验证、举报功能
- 帖子浏览量统计逻辑
- 帖子详情页与列表页数据一致性

## 7. 测试与验证

### 前端构建
- `npm run build` 构建成功 ✅

### MCP E2E 测试
- **点赞不增加浏览量**：取消点赞后浏览量保持 1296 → 重新点赞后浏览量仍为 1296 ✅
- **点赞数正确更新**：取消点赞 100→99，重新点赞 99→100 ✅
- **举报表单关闭**：提交举报成功后表单正确关闭 ✅
- **列表/详情数据一致**：列表页显示 1296 浏览、100 赞；详情页操作后数据保持一致 ✅

## 8. 后续建议

1. 考虑为评论/回复操作也添加 `increment_view` 参数控制，进一步优化
2. 可以在列表页也增加点击详情时不修改浏览量的逻辑，通过单独接口获取详情
3. 考虑添加乐观更新（optimistic update）机制，提升点赞/评论等操作的响应速度
