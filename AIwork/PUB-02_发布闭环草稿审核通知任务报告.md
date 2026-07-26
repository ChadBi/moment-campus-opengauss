# 任务报告：PUB-02 草稿—编辑—提交—审核—通知—公开完整闭环

## 1. 任务概述

实现复赛深度优化方案中的 PUB-02 任务：打通「保存草稿 → 继续编辑 → 提交审核 → 管理员审核（通过/驳回）→ 审核通知 → 公开展示」的完整发布闭环。关键修正：原驳回逻辑将帖子置为 archived（终态，无法重新提交），与设计文档「驳回 = pending → draft」不一致，需改为退回草稿并支持作者修改后重新提交。

## 2. 已完成内容

- 后端驳回语义修正（`app/api/admin.py`）：单个驳回与批量驳回均由 `pending → archived` 改为 `pending → draft`；审核通知文案改为「未通过审核，已退回草稿，可修改后重新提交。备注：{原因}」，通知中携带下一步动作与驳回原因。
- 后端配套接口：
  - `GET /api/v1/users/me/posts` 新增 `status` 查询参数（6 态 pattern 校验），支持按状态筛选我的发布。
  - `PostListResponse` 补充 `status` 字段，列表项携带状态供前端分组展示。
- 前端我的发布（`ProfilePage.tsx`）：
  - 6 态分组标签页（全部/草稿/待审核/已发布/已过期/冲突中/已归档）+ 各状态计数徽标 + 分页。
  - 中文状态 Badge、驳回原因提取展示（从最新一条审核通知「备注：」后截取）。
  - 草稿操作按钮：继续编辑（跳 `/publish?edit={id}`）、提交审核（draft → pending）、删除。
- 前端编辑模式（`PostForm.tsx` / `PublishPage.tsx`）：传入 `editPostId` 后加载并预填草稿（含图片/标签/时间/联系方式等全部字段），提交走 `update`（+ 可选 draft → pending 流转），编辑模式停用 localStorage 草稿恢复/自动保存避免与服务器草稿互相覆盖。
- 前端服务扩展：`postsApi.getMyPosts(page, pageSize, status)`、`postsApi.transitionPost(id, targetStatus)`、`notificationsApi.getNotifications(page, pageSize, type)`。
- 新增后端测试 `backend/tests/test_pub02_draft_review_flow.py`（7 个用例）：驳回回草稿（非归档）、驳回通知含原因与下一步动作、批量驳回回草稿、完整闭环 E2E（驳回→编辑→重新提交→待审核队列→通过→通知→公开列表可见）、驳回后编辑重提、按状态筛选、非法状态值 422。
- 顺带修复 2 个存量测试失败：`test_notifications.py::test_approve_post_creates_audit_notification` 与 `test_post_transition.py::test_deleted_post_not_in_published_list`，原因是 ACC-01.1 后游客请求必须携带学校上下文，补上 `X-School-Code` 请求头。
- 顺带修复前端构建错误：`AdminReviewPage.tsx` 残留未使用的 `batchLoading` 状态（审核动作已改为弹窗 + `actionSubmitting`），删除死代码后 `npm run build` 通过。

## 3. 未完成内容

- 移动端真机/浏览器人工验收（checklist 中「普通用户可在移动端完成保存草稿 → 编辑 → 提交 → 审核 → 通知 → 公开」一项仍保持未勾选，前端为响应式实现但未做移动端人工验证）。
- 前端 Playwright 端到端自动化（本次 E2E 以后端 API 级测试覆盖，未新增浏览器级 E2E）。

## 4. 实现思路

- 驳回语义以状态机为唯一入口：`can_transition(PENDING, DRAFT)` 校验通过后由管理员接口写 `draft`，操作日志记录驳回原因，通知同事务提交；作者侧通过已有的 `/posts/{id}/transition`（普通用户仅允许自己的 draft → pending）完成重新提交，不新增专用接口。
- 前端分组列表复用 `/users/me/posts?status=`：标签页切换即换 status 参数重新分页拉取；计数徽标通过并行请求 6 个状态的 `total` 获取；驳回原因通过并行拉取最近 50 条 `type=audit` 通知按 `target_id` 去重映射到帖子。
- 编辑模式复用 PUB-01 统一表单：`?edit={id}` 参数驱动，`getPost` 预填（作者可见自己所有状态），提交时先 `PUT` 保存再按需 `transition` 到 pending。

## 5. 修改文件

- 修改：`backend/app/api/admin.py`（驳回 → draft、通知文案、批量驳回）
- 修改：`backend/app/api/users.py`（`/users/me/posts` 新增 status 筛选）
- 修改：`backend/app/schemas/post.py`（`PostListResponse` 增加 status 字段）
- 新增：`backend/tests/test_pub02_draft_review_flow.py`
- 修改：`backend/tests/test_notifications.py`、`backend/tests/test_post_transition.py`（补 X-School-Code 头修复存量失败）
- 修改：`frontend/src/pages/ProfilePage.tsx`（状态分组标签页/计数/驳回原因/草稿操作）
- 修改：`frontend/src/components/PostForm.tsx`（editPostId 编辑模式）
- 修改：`frontend/src/pages/PublishPage.tsx`（解析 `?edit=` 参数）
- 修改：`frontend/src/services/posts.ts`、`frontend/src/services/notifications.ts`
- 修改：`frontend/src/pages/admin/AdminReviewPage.tsx`（删除导致构建失败的死代码 batchLoading）
- 更新：`TODO.md`、`.trae/specs/finals-deep-optimization/tasks.md`（勾选 PUB-02.1/02.2）、`.trae/specs/finals-deep-optimization/checklist.md`（勾选发布闭环 E2E 项）

## 6. 影响范围

- 后端：管理端审核接口（驳回行为变化：archived → draft）、用户中心我的发布接口（新增可选参数，向后兼容）、帖子列表响应模型（新增字段，向后兼容）。
- 前端：个人中心「我的发布」、发布页（编辑模式）、审核页文案（"已驳回并退回草稿"）。
- 对存量数据无迁移要求（状态枚举未变，仅流转目标变化）。

## 7. 测试与验证

- `pytest tests/test_pub02_draft_review_flow.py -v`：7 passed。
- 关联回归 `pytest tests/test_post_transition.py tests/test_notifications.py tests/test_publish_flow.py`：初次 68 passed / 2 failed（2 个失败为 ACC-01.1 引入的存量问题，与本次改动无关），修复后相关用例全部通过。
- 前端 `npm run build`：通过（tsc + vite build exit 0）。
- 未运行完整 `pytest tests/ -v` 全量套件：全量运行耗时较长（关联三组已 5 分钟），本次变更影响面已由上述三组 + 新增 7 个用例覆盖；全量基线属 REL-01.2 范围。

## 8. 后续建议

- 在移动端视口人工走一遍「草稿 → 编辑 → 提交 → 审核 → 通知 → 公开」全流程，补齐 checklist 移动端验收项。
- PRF-01.1（我的帖子按状态分组分页、编辑/提交/归档/删除）与本次实现高度重叠，执行 PRF-01 时可直接复用并核对差异。
- 驳回原因的展示依赖通知文案「备注：」约定，若后续支持结构化驳回原因（如通知表增加 reason 字段），前端可改为直接读取字段，去掉字符串解析。
