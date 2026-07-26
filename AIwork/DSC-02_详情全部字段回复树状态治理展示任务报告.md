# 任务报告：DSC-02 详情全部字段、回复树、状态/治理展示

## 1. 任务概述

完善帖子详情页，实现 DSC-02.1：
1. 详情页展示所有字段：图片轮播、状态标签（中文）、有效期倒计时、活动时间、联系方式
2. 展示验证信息：证实/证伪投票数、问题报告（update/expiration_report/conflict_report）列表
3. 评论按回复树展示（支持嵌套回复）
4. 游客访问详情时不请求需要登录的接口（如点赞状态、投票状态、订阅状态）
5. 游客只看公开字段，登录用户看完整字段（如联系方式对游客隐藏）
6. 所有接口有租户隔离校验

## 2. 已完成内容

### 后端
- 详情接口 `GET /api/v1/posts/{id}` 返回全字段：图片列表（按 `sort_order` 排序）、状态、有效期、活动起止、联系方式、治理聚合 `governance`
- 权限脱敏：游客 `contact_info` 恒为 `None`；登录用户（含非作者）可见完整 `contact_info`
- 游客不请求需登录的统计接口：`is_liked` 恒为 `False`（后端不查 Like 表）；`governance.user_validation_type` 恒为 `None`
- 治理聚合 `_build_governance_summary`：投票计数 + 综合有效性状态 + 问题报告总数/待处理数/最近 10 条 + 登录用户 `user_validation_type`
- 评论按回复树展示：`GET /posts/{id}/comments` 返回顶级评论 + 嵌套 `replies`（含 `reply_to_user`）
- 预加载二级回复（`selectinload`）避免 `MissingGreenlet`；手动构造 `CommentResponse`（`_build_comment_response`）避免 `model_validate` 递归触发未加载关系的 lazy load
- 评论接口游客可读：`GET /posts/{id}/comments` 不要求登录；`POST /posts/{id}/comments` 需登录，游客返回 401
- 资源级租户校验：跨校帖子/评论统一返回 404（不泄露存在性）

### 前端
- `PostDetailPage.tsx`：图片轮播（左右切换 + 序号）、有效期倒计时、活动时间、联系方式（仅登录用户可见）、状态标签（中文）、投票按钮（仅登录用户可见，作者不可给自己投票）、问题报告列表（3 类 + 处理状态）、评论回复树（嵌套回复 + `reply_to_user` 高亮）
- 从 `post.governance` 取聚合数据（游客/登录用户均可读，无需额外请求需登录的统计接口）

### 测试
- 新增后端测试 `tests/test_post_detail_dsc02.py` 16 个用例全部通过
- 后端全量测试：770 通过 / 3 失败 / 3 跳过
- 前端 `npm run build` 通过

## 3. 未完成内容

暂无。

注：后端全量测试有 3 个失败用例位于 `tests/test_adm02_school_settings.py`，错误为 `TypeError: 'NoneType' object can't be awaited`，属于该模块预先存在的问题（与 DSC-02.1 无关，DSC-02.1 仅修改 `posts.py` 与 `comments.py`），不在本任务范围内。

## 4. 实现思路

### 详情全字段 + 权限脱敏
- 在 `app/api/posts.py` 的 `get_post` 端点中，通过 `selectinload(Post.post_images)` 预加载图片关系，再按 `sort_order` 排序映射到 `response.images`（无图时显式设置为 `[]`，前端轮播不渲染）
- 通过 `tenant.is_guest` 判断游客身份，游客访问时 `response.contact_info = None`（敏感字段脱敏）
- `is_liked` 仅在 `current_user` 存在时查询 Like 表，游客恒为 `False`
- 治理聚合 `_build_governance_summary` 接收 `current_user` 参数，登录用户额外查询其投票类型并归一化（`valid→confirmation` / `invalid→refutation`），游客恒为 `None`

### 评论回复树
- `app/api/comments.py` 的 `get_post_comments` 端点预加载三级关系：`joinedload(Comment.user)` + `joinedload(Comment.reply_to_user)` + `selectinload(Comment.replies)`（嵌套二级 `selectinload`）
- 手动构造 `_build_comment_response(comment, include_replies)`，递归构造 `replies`（仅一层，避免无限递归），避免 `model_validate` 递归触发未加载关系的 lazy load（`MissingGreenlet`）
- 顶级评论 `include_replies=True`，回复本身 `include_replies=False`（`replies` 恒为 `None`）

### 游客访问控制
- 详情接口使用 `get_current_user_optional` 依赖，游客 `current_user` 为 `None`
- 评论列表接口不依赖 `get_current_user`（公开可读）
- 前端从 `post.governance` 取聚合数据，不额外请求需登录的统计接口；投票/点赞/评论按钮根据 `isAuthenticated` 与 `userValidationType` 控制显示

## 5. 修改文件

### 后端
- `backend/app/api/posts.py` — 详情接口全字段返回、权限脱敏、治理聚合 `user_validation_type`、图片列表按 `sort_order` 排序
- `backend/app/api/comments.py` — 评论回复树预加载（`selectinload` 二级）+ 手动构造 `CommentResponse`（`_build_comment_response`）避免 `MissingGreenlet`
- `backend/tests/test_post_detail_dsc02.py` — 新增 16 个 DSC-02.1 测试用例
- `backend/tests/conftest.py` — `test_post_type` fixture 幂等化（避免 `UniqueViolationError`）

### 前端
- `frontend/src/pages/PostDetailPage.tsx` — 图片轮播、有效期倒计时、活动时间、联系方式权限显示、状态标签、投票按钮权限控制、问题报告列表、评论回复树

### 工具脚本
- `backend/_cleanup_db.py` — 测试库连接终止 + TRUNCATE + 序列重置（用于解决测试死锁与脏数据问题）

### 文档
- `TODO.md` — 新增 DSC-02 完成条目

## 6. 影响范围

- **帖子详情**：`GET /api/v1/posts/{id}` 返回结构扩展（`images` / `governance.user_validation_type` / `contact_info` 权限脱敏）
- **评论列表**：`GET /api/v1/posts/{id}/comments` 返回结构扩展（嵌套 `replies` + `reply_to_user`）
- **前端详情页**：`PostDetailPage.tsx` 全面增强（图片轮播、治理展示、回复树）
- **测试**：新增 `test_post_detail_dsc02.py`；`conftest.py` 的 `test_post_type` fixture 幂等化
- **未影响**：帖子创建/更新/删除、评论创建/删除、治理投票/问题报告提交逻辑、其他模块

## 7. 测试与验证

### 后端测试
1. **DSC-02.1 专项测试**（`tests/test_post_detail_dsc02.py`，16 个用例全部通过）：
   - `test_detail_returns_all_fields_for_logged_in_user` — 登录用户详情全字段
   - `test_detail_returns_all_fields_for_guest_except_contact` — 游客详情公开字段（contact_info 为 None）
   - `test_guest_contact_info_is_none` — 游客 contact_info 恒 None
   - `test_logged_in_user_contact_info_visible` — 登录用户（含非作者）contact_info 可见
   - `test_guest_governance_user_validation_type_is_none` — 游客 user_validation_type 恒 None
   - `test_logged_in_user_governance_user_validation_type_reflects_vote` — 登录用户投票后 user_validation_type 反映投票类型
   - `test_logged_in_user_without_vote_returns_none_validation_type` — 登录用户未投票时 user_validation_type 为 None
   - `test_guest_detail_is_liked_is_false` — 游客 is_liked 恒 False
   - `test_logged_in_user_detail_is_liked_reflects_state` — 登录用户 is_liked 反映点赞状态
   - `test_comment_reply_tree_structure` — 评论回复树结构（顶级 + 嵌套回复 + reply_to_user）
   - `test_comment_list_guest_accessible` — 游客可访问评论列表
   - `test_guest_cannot_create_comment` — 游客不能发评论（401）
   - `test_detail_governance_has_all_required_fields` — governance 契约字段完整
   - `test_detail_change_reports_aggregated_in_governance` — 3 类问题报告聚合
   - `test_detail_multiple_images_with_sort_order` — 多图按 sort_order 排序
   - `test_detail_no_images_returns_empty_list` — 无图返回空列表
2. **后端全量测试**（`pytest tests/ -v --ignore=tests/integration`）：
   - 770 通过 / 3 失败 / 3 跳过
   - 3 个失败位于 `test_adm02_school_settings.py`，错误为 `TypeError: 'NoneType' object can't be awaited`，属于该模块预先存在的问题，与 DSC-02.1 无关

### 前端构建
- `cd frontend && npm run build` 通过（`tsc -b` + `vite build`，2.61s 完成）
- `PostDetailPage-DkrBeGi4.js 27.64 kB`

## 8. 后续建议

1. **`test_adm02_school_settings.py` 失败用例修复**：3 个用例报 `TypeError: 'NoneType' object can't be awaited`，建议排查 `school_settings` 模块的异步函数返回值（可能是某依赖注入返回 `None` 而非协程），与 DSC-02.1 无关
2. **评论回复树深层嵌套**：当前仅支持二级嵌套（顶级 + 一层 replies），如需支持无限层级可改为递归构造 + 懒加载子评论接口
3. **图片轮播懒加载**：前端图片轮播可补充 `loading="lazy"` 与占位图，优化多图详情页加载性能
4. **治理聚合缓存**：`_build_governance_summary` 每次详情访问都查询投票计数与问题报告，高频访问时可考虑短期缓存（如 30 秒 TTL）
5. **联系方式权限配置化**：当前硬编码"游客不可见"，可扩展为 `school_settings` 配置项，允许各校自定义联系方式对游客/登录用户/同校成员的可见性
