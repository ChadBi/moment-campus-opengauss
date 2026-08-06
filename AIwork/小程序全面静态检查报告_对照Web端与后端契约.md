# 小程序全面静态检查报告（对照 Web 端与后端契约）

## 1. 任务概述

对微信小程序进行全量静态检查，重点核对：

- 代码逻辑正确性（页面、服务层、核心层）。
- 与 Web 端相同功能的一致性。
- 与后端实际接口契约（`app/api` + `app/schemas`）的匹配度。

本次为静态代码审查，未启动 MCP / 浏览器连接测试，未修改任何代码。

## 2. 检查范围

| 层次 | 覆盖内容 |
| --- | --- |
| 主页面 | home、map、search、publish、profile、post-detail、notifications、subscriptions、login |
| 分包页面 | edit-post、locations、school-select、feedback、notification-preferences、forgot-password、bind-account、about 等 |
| 服务层 | auth、posts、interactions、locations、map、notifications、schools、search、upload、feedback、notification-preferences |
| 核心层 | request、auth-guard、store/auth、store/campus、cache、format |
| 对照基准 | web 端 `routes.tsx` + `services/*`；后端 `app/api/*` + `app/schemas/*` |

## 3. 严重问题（功能失效 / 直接报错）

### 3.1 发布页字段名与后端不匹配 —— 图片、有效期、地点全部失效

- 小程序 `pages/publish/publish.ts` 提交：`images` / `expires_at` / `latitude` / `longitude`。
- 后端 `schemas/post.py` 的 `PostCreate` 只认：`image_urls` / `expire_at` / `location_name` + `location_lat` + `location_lng`。
- Pydantic 默认忽略未知字段 → 发布时**图片、截止时间、地点坐标全部不生效**（地点不会创建）。
- 对比同目录 `subpackages/pages/edit-post/edit-post.ts` 提交的是正确的 `image_urls` / `expire_at` / `location_id`，两页契约不一致。

### 3.2 帖子列表 / 详情计数与图片字段名整体不匹配（影响所有卡片）

- 后端 `PostListResponse` / `PostResponse` 返回：`like_count` / `comment_count` / `view_count` / `valid_count` / `invalid_count` / `expire_at`；列表图片为 `cover_image`，详情图片为 `images[]`（`{image_url}` 对象数组）。
- 小程序一律读取：`likes_count` / `comments_count` / `views_count` / `validations_count` / `expires_at` / `images`（字符串数组）。
- 影响：
  - `components/post-card/post-card.ts`：首页 / 搜索卡片**封面图消失、点赞 / 评论 / 浏览 / 验证计数全显示 0**。
  - `pages/post-detail/post-detail.ts`：计数 0、倒计时失效（`expires_at` ≠ `expire_at`）、图片轮播把对象当字符串 `map(resolveImageUrl)` 会抛错。
  - home / search / profile 的 normalize 同样按错误字段解析。

### 3.3 「全部已读」接口路径与方法不匹配 —— 404

- 后端：`PUT /notifications/read-all`。
- 小程序 `services/notifications.ts`：`POST /notifications/mark-all-read`。

### 3.4 未读角标响应字段不匹配 —— 恒为 0

- 后端返回 `unread_count`；小程序 `pages/notifications/notifications.ts` 读取 `res.count`。

### 3.5 点赞响应字段不匹配 —— 计数不准确

- 后端 `LikeResponse` 返回 `is_liked` / `like_count`。
- `pages/post-detail/post-detail.ts onLike` 读取 `res.liked` / `res.likes_count`，全靠本地 +1/-1 兜底，多端并发时计数漂移。

### 3.6 学校切换接口不存在 —— 切换失败

- 后端学校切换为 `POST /schools/{code}/join` + `PUT /me/default-school`，**无 `/me/school/switch`**。
- `subpackages/pages/school-select/school-select.ts` 调用 `switchSchool('/me/school/switch')` → 404。
- `pages/profile/profile.ts onSwitchSchool` 仅本地 `setSchool`，未调后端 join / default-school，membership 不更新。

### 3.7 详情页调用不存在的 `/posts/{id}/interactions`

- `pages/post-detail/post-detail.ts` 静默失败，`isLiked` 永远初始 false，点赞高亮态不生效。

### 3.8 添加订阅字段不匹配 —— 订阅失败

- 后端 `SubscriptionCreate` 用 `target_type`；小程序 `pages/subscriptions/subscriptions.ts` 传 `type`。
- 列表读取 `subscription_type`（后端为 `target_type`），导致分类订阅状态不显示、无法切换。

## 4. 一致性差异（功能可用但两端不同）

- 地图数据源：小程序地图页用 `/locations`（地点 points），web `MapPage` 用 `/map/markers`（帖子）。`services/map.ts getMapMarkers` 传 `school_id/status`，与后端 `/map/markers`（`north`/`south`/`east`/`west`/`category_id`）不符，当前地图页未使用，属死代码。
- 图片上限：后端最多 9 张，小程序 publish / edit-post 限 5 张。
- 评论回复：web `createComment` 支持 `reply_to_user_id`，小程序无此参数，被回复者收不到通知。
- web 端仍有 `/topics` 专题页，小程序已移除——需确认 web 端是否也应同步下线，避免两端不一致。
- 登录页默认 `mode='wechat'`，依赖正式 AppID 配置；邮箱注册入口在 login 页缺失（web 有 `/register`，小程序只有 `school-select?mode=register` 走 `switchSchool`，逻辑上非注册）。

## 5. 代码逻辑正常的部分

- `services/request.ts`：401 游客分级处理、refresh 并发锁、token 内存态设计正确。
- `utils/auth-guard`：双守卫、游客可浏览、发布 / 通知 / 我的 onShow 守卫生效。
- profile 的统计 / 浏览历史 / 身份 / 会话 / 校园认证 / 推荐偏好接口均已对照后端，字段匹配。
- locations 详情 / 评价、feedback、notification-preferences、forgot-password、bind-account 契约匹配。
- tabBar 顺序与 selected 索引（home=0 / map=1 / search=2 / publish=3 / profile=4）一致。

## 6. 修复优先级建议

1. 发布页字段改为 `image_urls` / `expire_at` / `location_name` + `location_lat` + `location_lng`（3.1，核心功能，最高优先）。
2. 统一帖子字段映射：列表用 `cover_image`，详情用 `images[].image_url`，计数改用后端 `like_count` / `comment_count` / `view_count` / `valid_count` / `expire_at`（3.2，波及面最大）。
3. 修正通知：全部已读改 `PUT /notifications/read-all`，未读数改 `unread_count`（3.3、3.4）。
4. 修正点赞字段 `is_liked` / `like_count`（3.5）。
5. 学校切换改走 `POST /schools/{code}/join` + `PUT /me/default-school`（3.6），并让 profile 切换时同步后端。
6. 删除详情页 `/interactions` 调用，改用帖子详情返回的 `is_liked`（3.7）。
7. 订阅改 `target_type`（3.8）。

## 7. 测试与验证

本次为纯静态检查，未运行代码、未启动 MCP / 浏览器连接测试，未修改代码，因此未执行 pytest / npm build / E2E。所有结论均通过源代码阅读并与后端契约比对得出。

## 8. 后续建议

- 按第 6 节优先级分批修复，每一批修复后跑 `npm run typecheck` / `npm run build` 回归。
- 修复后建议用 wechatide-skill 对发布、帖子列表封面计数、点赞、通知已读、学校切换、订阅等关键链路做 E2E 真机走查。
- 确认 web 端 `/topics` 专题页是否同步下线，保持两端功能一致。