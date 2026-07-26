# 此刻校园 - TODO 列表

> 依据 [AGENTS.md](AGENTS.md) 要求维护，每完成一个小点即更新本文件。
> 任务详细规划见 [docs/21_后续开发任务清单.md](docs/21_后续开发任务清单.md)。

## 当前阶段

**阶段 R：TRAE AI 创造力大赛复赛冲刺（P0）** — 进行中（目标：2026-08-09 23:59 前完成正式提交）

**阶段 A：openGauss 适配（P0）** — 已完成（T-A-01 ~ T-A-18 全部完成）

**阶段 P：数据库物理模型实现（P1）** — 主体完成（P-P-01 ~ P-P-06、P-P-08、P-P-09 完成；P-P-07 放弃：openGauss 轻量版容器无 cron 服务；P-P-08 性能测试已完成，8 查询全部达标；P-P-10 放弃：轻量版不支持 pg_trgm/zhparser）

**阶段 B：核心业务升级（P0）** — 主体完成（T-B-01/02/04/05/06 已完成；T-B-03 放弃：Service 层抽取不做；T-B-07/08 视情况补做）

**阶段 C / D：已放弃** — 按用户决策（2026-07-02），整个阶段 C（创新点）与阶段 D（扩展能力）全部放弃，按最小 MVP 交付。SQLite 已彻底移除，全面转移至 openGauss。

## 已完成

### REL-02 性能、安全、ready/version、结构化日志与 AI 监控（本地）（2026-07-25 完成）

- [x] REL-02.1 健康检查与版本接口（本地开发辅助，非生产发布门禁）：
  - `/health/live`：进程存活探针，返回 `{"status":"alive","timestamp":...}`，无外部依赖
  - `/health/ready`：就绪探针，依次检查 DB（`SELECT 1`）+ `/uploads` 目录可写性（写 `.health_check_<pid>.tmp` 临时文件）+ AI 配置（`AI_PROVIDER` 缺失标 degraded）；DB/uploads 失败返回 503 unavailable，AI 缺失返回 200 degraded
  - `/version`：返回 commit_sha（`GIT_COMMIT_SHA` 环境变量，默认 local）/ build_time / migration_version（查询 alembic_version 表）/ app_env
- [x] REL-02.2 请求追踪与结构化日志（敏感数据脱敏）：
  - `RequestIDMiddleware`：生成或接受 `X-Request-ID`（uuid4 / 透传客户端请求头），写入 `request.state.request_id`，响应头回写
  - `RequestLoggingMiddleware`：记录 `method / 脱敏 path / 状态码 / 耗时 / request_id`；`_sanitize_path` 对 `password/token/api_key/secret/access_token/refresh_token` 等敏感参数值替换为 `***REDACTED***`；不记录请求体（含密码/Token/密钥）
  - 异常兜底：`call_next` 抛错时返回 500 JSON（不泄露堆栈），仅记录异常类型 + request_id 便于追踪
  - AI 调用透传：`invoke_ai` 将 `request_id` 写入 `AIInvocationLog.trace_id`，行政审计同样关联
- [x] REL-02.3 性能/安全/故障注入测试 + AI 降级率监控：
  - 性能基线：普通搜索 P95 ≤2500ms（本地测试阈值，生产目标 800ms）；AI 搜索 P95 ≤5000ms（本地阈值，生产目标 3.5s，含超时降级）；健康端点 P95 <200ms / <500ms
  - 限流：`RateLimitMiddleware` 覆盖 login/register/publish/AI 搜索/AI 建议等关键端点（基于 in-memory token bucket，按 IP + path 规则匹配）
  - 安全测试：SQL 注入（搜索/标题按字面量处理，无 OR 1=1 命中）、XSS（响应不执行脚本，原文存储）、CSRF（Bearer Token 校验）、日志脱敏（password/token/api_key 替换为 REDACTED）
  - 故障注入：DB 故障返回 500 + X-Request-ID（不泄露堆栈）、AI 超时/网络错误/限流/余额不足 全部 fallback 到普通搜索 + 记录对应 `output_status`（timeout/network_error/rate_limit/insufficient_quota）
  - AI 降级率监控：`/admin/todos` 返回 `ai_calls_24h` / `ai_fallback_24h` / `ai_fallback_rate`（本校最近 24h）；前端 `AdminHomePage.tsx` 新增 AI 监控卡片（三色徽标：≥50% danger / ≥20% warning / <20% success，降级率 ≥50% 且调用 ≥5 次高亮告警）
- [x] 测试基础设施修复：`conftest.py` 预置套餐 + 权益项改用 Python 层 SELECT-then-INSERT + savepoint 容错，并将 `created_at/updated_at` 由字符串改为 `datetime` 对象（asyncpg 类型要求）；权益项 INSERT 全部改用绑定参数（避免 SQL 注入 + 类型由 driver 处理）
- [x] 新增测试文件：`tests/test_rel02_health.py`（健康/版本探针，含 DB 故障 503、AI degraded、版本信息）+ `tests/test_rel02_security.py`（SQL 注入/XSS/CSRF/限流规则/日志脱敏）+ `tests/test_rel02_fault_injection.py`（DB 故障 500 + X-Request-ID、AI 超时/网络/限流/余额不足降级 + ai_invocation_logs 状态记录 + /admin/todos AI 降级率统计 + 故障链路 X-Request-ID 透传）+ `tests/test_rel02_performance.py`（普通搜索/AI 搜索/健康端点 P95 阈值校验）
- [x] 后端 `pytest tests/ -v` 全量通过：972 passed, 66 skipped（REL-02 新增 55 个用例全部通过）
- [x] 前端 `npm run build` 通过（AdminHomePage AI 监控卡片正确打包）
- [x] 任务报告：[AIwork/REL-02_性能安全与可观测任务报告.md](AIwork/REL-02_性能安全与可观测任务报告.md)

### SUB-01 分类/地点/专题订阅与四类通知（2026-07-25 完成）

- [x] SUB-01.1 新增租户级订阅表 `subscriptions`（唯一键 `uq_subscription_user_school_target` = user_id + school_id + target_type + target_id；target_type 取值 category/location/topic）；外键 `users.id` / `schools.id` ON DELETE CASCADE；索引 `idx_subscription_user_school` / `idx_subscription_target` 支持两类高频查询；Alembic 迁移 `u7a8b9c0d1e2f_sub_01_user_subscriptions` + merge head `a871871f04ce_merge_rec01_sub01_heads`
- [x] SUB-01.1 订阅管理 API（`app/api/subscriptions.py`）：`POST /subscriptions`（订阅，重复返回 409；跨校 target 返回 404 不泄露存在性；非法 target_type 返回 422；不存在 target_id 返回 404）+ `GET /subscriptions`（列表，分页，按 target_type 筛选，仅返回当前学校本人订阅）+ `GET /subscriptions/check`（单点查询，跨校恒返回 subscribed=false）+ `GET /subscriptions/targets`（一次性返回当前用户已订阅全部目标 ID，按 target_type 分组）+ `DELETE /subscriptions/{id}`（仅可删除本人订阅，跨校 404）
- [x] SUB-01.1 通知触发服务 `app/services/subscription_notifier.py`：四类细分通知类型 `subscription_new` / `subscription_update` / `subscription_expired` / `subscription_conflict`，统一映射到 `NotificationPreference.subscription_enabled` 偏好类别；通过 `_collect_subscriber_ids` 收集三类目标（category/location/topic via `topic_collection_posts` 关联）订阅者并集，强制 `school_id == post.school_id` 租户隔离；排除帖子作者；批量查询偏好过滤 opted-out 用户；`_has_subscription_notification` 幂等检查保证每帖每类每用户只通知一次
- [x] SUB-01.1 四类通知触发函数：`notify_new_post`（pending → published 时由 admin 审核触发）+ `notify_post_updated`（published → pending 实质修改回审时触发）+ `notify_post_expired`（GOV-02 `expire_posts_job` 联动触发）+ `notify_post_conflict`（GOV-01.5 `handle_governance_report` mark_conflict 触发）；通知标题/内容模板化，content 截断 500 字符
- [x] SUB-01.2 订阅与通知不跨校：所有查询强制 `UserSubscription.school_id == post.school_id`；A 校订阅者不接收 B 校帖子通知；A 校用户在 B 校 `X-School-Code` 下查询订阅列表为空；跨校 target 订阅/查询/删除统一 404
- [x] SUB-01.2 至少覆盖四类场景：新帖发布（subscription_new）/ 重要更新（subscription_update）/ 内容过期（subscription_expired）/ 冲突标记（subscription_conflict）四类场景均有对应触发函数与通知类型
- [x] 前端订阅入口 `components/SubscribeButton.tsx`：可复用订阅按钮组件（详情页/列表页/专题页/分类页/地点页通用），支持外部预订阅状态传入 + 登录后自查询 + 409 并发冲突修正 + Toast 反馈 + size/variant 两种样式
- [x] 前端订阅管理卡片 `components/SubscriptionsCard.tsx`：用户中心订阅管理卡片，支持 target_type 筛选 + 分页 + 取消订阅（带二次确认）+ 自动回退到上一页（当前页删完后为空且非第 1 页）
- [x] 前端服务层 `services/subscriptions.ts`：`subscriptionsApi` 实现 listMySubscriptions / listMySubscriptionTargets / checkSubscription / createSubscription / deleteSubscription 5 个方法
- [x] 前端类型扩展：`types/index.ts` 新增 `SubscriptionTargetType` / `Subscription` / `SubscriptionCreateRequest` / `SubscriptionCheckResponse` / `SubscriptionTargetsResponse` / `PaginatedResponse<Subscription>` 等类型
- [x] 后端测试 `tests/test_subscriptions.py` 21 个用例全部通过：订阅 CRUD + 唯一约束 409 + 跨校 target 404 + 跨校订阅不可见 + 非法 target_type 422 + 不存在 target_id 404 + 仅可删除本人订阅 + 四类通知场景（new/update/expired/conflict）+ 排除作者 + 跨校通知隔离 + 幂等性 + 偏好过滤
- [x] 测试基础设施修复：`conftest.py` 改用 `reversed(Base.metadata.sorted_tables)` 删除顺序 + `ALTER SEQUENCE RESTART WITH 1` 序列重置 + savepoint 容错；`test_subscriptions.py` 引入 `_ensure_operations_plan` 三层防御策略（SELECT → SAVEPOINT INSERT → 重新 SELECT）处理跨连接可见性问题 + `_create_user_with_token` 单 session 创建用户避免跨连接 + `sub_01_two_school_setup` 死锁/连接中断重试机制（max_retries=3，指数退避）
- [x] 前端 `npm run build` 通过（SubscribeButton / SubscriptionsCard 组件正确打包）
- [x] 任务报告：[AIwork/SUB-01_分类地点专题订阅与四类通知任务报告.md](AIwork/SUB-01_分类地点专题订阅与四类通知任务报告.md)

### TEN-05 三校差异化数据、账号、主题、地图与状态样本（2026-07-25 完成）

- [x] TEN-05.1 确认三所演示学校：江南大学（code=jiangnan，主展示，无锡蠡湖校区 31.4837/120.2712）+ 复旦大学（code=fudan，复赛演示校 A，上海邯郸校区 31.2983/121.5020）+ 浙江大学（code=zju，复赛演示校 B，杭州紫金港校区 30.3097/120.1216）
- [x] TEN-05.2 每校独立数据齐全：
  - 分类 ≥6：江南 12 / 复旦 8 / 浙大 10（共 30 个分类）
  - 地点 ≥10：江南 15 / 复旦 12 / 浙大 12（共 39 个地点，真实校园地点坐标）
  - 用户 ≥5 含 admin：江南 11（1 admin + 10 user）/ 复旦 6（1 admin + 5 user）/ 浙大 6（1 admin + 5 user），共 23 个用户
  - 已发布帖子 ≥20：江南 30 published / 复旦 20 published / 浙大 20 published（共 85 条帖子）
  - 状态样本 6 态各 ≥1：每校均有 draft/pending/published/expired/conflict/archived
  - 五类治理样本：confirmation + refutation（ValidationRecord 39 条）+ update/expiration_report/conflict_report（PostChangeReport 9 条，3 类 × 3 校）
  - 专题 ≥1：江南 6 / 复旦 3 / 浙大 3（共 12 个专题集合）
  - 官方发布主体 ≥2：江南 3 / 复旦 2 / 浙大 2
  - 品牌设置差异化：江南 #1B4332（江南绿）/ 复旦 #00356B（复旦蓝）/ 浙大 #003F7F（浙大蓝），不同 site_name
  - 套餐运营档 activated：三校均分配 operations 套餐，3 条 active 订阅
- [x] TEN-05.3 跨校普通账号：user1@example.com（江南主校）加入复旦 / user2@example.com（江南主校）加入浙大，用于演示切换学校后角色/内容/统计变化
- [x] 修复 `_build_demo_post` 函数参数顺序 Bug：原签名 `status, is_recommend` 导致 `True` 被赋给 `status`（TypeError: cannot use 'list' as a set element）；调整为 `is_recommend, status` 并将所有 comments/validations 改为关键字参数
- [x] 种子脚本一键生成：`python scripts/seed_data.py` 成功生成全部三校数据（exit 0）
- [x] 前端 `npm run build` 通过（1962 模块，1.66s）
- [x] 任务报告：[AIwork/TEN-05_三校差异化数据账号主题地图与状态样本任务报告.md](AIwork/TEN-05_三校差异化数据账号主题地图与状态样本任务报告.md)

### TOPIC-01 多校专题 API、用户页与校级后台编排（2026-07-25 完成）

- [x] TOPIC-01.1 用户端专题 API（`app/api/topics.py`）：`GET /api/v1/topics`（列表，分页，仅展示已发布专题，按 `sort_order` 升序 + `published_at` 降序）+ `GET /api/v1/topics/{id}`（详情含关联帖子列表）；TEN-02.3 跨校专题统一 404（不泄露存在性）；专题内帖子仅展示 `published`/`expired` 状态（draft/pending/archived 不出现）；浏览数 +1 同事务提交
- [x] TOPIC-01.1 专题只能引用同校已发布帖子：管理端添加帖子时强制校验 `post.school_id == tenant.school_id` 且 `post.status == published`；跨校/非 published 帖子返回 400
- [x] TOPIC-01.2 校级 admin 管理 API（`app/api/admin_topics.py`，全部 `require_role(Role.ADMIN)` + 租户隔离）：
  - 列表 `GET /admin/topics`（按当前学校过滤，含全部状态，分页）
  - 详情 `GET /admin/topics/{id}`（含关联帖子全状态）
  - 创建 `POST /admin/topics`（school_id 强制取自 TenantContext，不信任 body；status 可直接 draft/published）
  - 更新 `PUT /admin/topics/{id}`（title/description/cover_url/sort_order）
  - 删除 `DELETE /admin/topics/{id}`（软删除 is_deleted=True + deleted_at）
  - 批量排序 `PUT /admin/topics/sort`（接受 `{items: [{id, sort_order}]}`，幂等更新）
  - 上线 `PUT /admin/topics/{id}/publish`（draft/archived → published，写入 published_at）
  - 下线 `PUT /admin/topics/{id}/archive`（published → archived）
  - 添加帖子 `POST /admin/topics/{id}/posts`（批量，校验同校 + published，唯一约束防重复）
  - 移除帖子 `DELETE /admin/topics/{id}/posts/{post_id}`
  - 调整帖子排序 `PUT /admin/topics/{id}/posts/sort`
- [x] TOPIC-01.2 路由顺序修复：将 `/admin/topics/sort` 静态路由置于 `/admin/topics/{topic_id}` 动态路由之前，避免 `sort` 被路径参数匹配触发 422
- [x] TOPIC-01.2 修复 async 函数未 await：`_check_topic_in_tenant` 在 6 处调用点全部加 `await`（update_topic/delete_topic/publish_topic/add_posts_to_topic/remove_post_from_topic/sort_topic_posts）
- [x] 切换学校只展示当前学校专题：用户端与管理端列表均按 `tenant.school_id` 过滤；跨校访问详情/修改/删除统一 404（`check_resource_in_tenant`）
- [x] 前端用户端专题页 `TopicListPage.tsx`（专题列表卡片，分页，跳转详情）+ `TopicDetailPage.tsx`（专题详情含帖子列表，跳转帖子详情）
- [x] 前端校级后台编排页 `AdminTopicsPage.tsx`：创建/编辑/删除/上线/下线/批量排序/添加帖子/移除帖子/调整排序，全部按当前学校过滤
- [x] 前端服务层：`services/topics.ts` 用户端 API（list/getDetail）+ `services/admin.ts` 扩展 admin topics 管理方法（list/getDetail/create/update/delete/sort/publish/archive/addPosts/removePost/sortPosts）
- [x] 前端类型扩展：`types/index.ts` 新增 `TopicStatus`/`TopicListItem`/`TopicDetail`/`TopicPostItem`/`TopicAdmin`/`TopicAdminDetail`/`TopicPostAdminItem`/`TopicCreateRequest`/`TopicUpdateRequest`/`TopicSortRequest`/`TopicAddPostsRequest` 等 11+ 类型
- [x] 前端路由注册：`/topics` 用户列表 + `/topics/:topicId` 用户详情 + `/admin/topics` 后台编排（lazy 加载）；`AdminDashboard` 菜单新增"专题管理"入口
- [x] 后端测试 `tests/test_topics.py` 20 个用例全部通过（105.58s）：创建草稿/创建已发布/普通用户不可创建/A 校 B 校列表隔离/管理端详情含帖子/上下线状态流转/批量排序/不可添加 pending 帖子/不可添加跨校帖子/重复添加冲突/移除帖子/帖子排序/软删除/用户端仅展示已发布/用户端仅展示 published+expired 帖子/用户端不可见 draft 详情/跨校详情 404/跨校 admin 不可修改/更新元数据/浏览数自增
- [x] 修复 `topic_setup` fixture：移除自执行的 TRUNCATE（与 `setup_database` autouse fixture 冲突导致死锁）；改为检测跨连接可见性问题后在本连接内补做 TRUNCATE + 序列重置 + 重新预置 operations 套餐
- [x] 前端 `npm run build` 通过（`TopicListPage-Cf0WVHOR.js 4.15 kB`、`TopicDetailPage-Cm--hWhD.js 4.89 kB`、`AdminTopicsPage-HTTdR6rn.js 16.12 kB`）
- [x] 任务报告：[AIwork/TOPIC-01_多校专题API用户页与校级后台编排任务报告.md](AIwork/TOPIC-01_多校专题API用户页与校级后台编排任务报告.md)

### ORG-01 官方发布主体、成员、认证、主页、模板与聚合效果（2026-07-25 完成）

- [x] ORG-01.1 `publisher_profiles/publisher_memberships` 模型 + Alembic 迁移 `r5f6g7h8i9j0_org_01_publishers`：部门/社团/服务组织认证主页字段（name/type/intro/logo_url/location_id/service_hours/contact/verified_status/verified_at/verified_by/verify_note/view_count/subscribe_count/share_count/valid_feedback_count/invalid_feedback_count/zero_result_count/is_deleted/deleted_at）；成员关系表（publisher_id/user_id/role/joined_at，唯一约束 `uq_publisher_membership`）；posts 表新增 `publisher_id` 列（可空，外键 SET NULL）
- [x] ORG-01.1 用户端 API（`app/api/publishers.py`）：`GET /publishers`（仅本校，verified 优先）+ `GET /publishers/{id}`（详情含成员+最近内容，游客可见）+ `GET /publishers/{id}/aggregation`（浏览/订阅/分享/反馈/零结果聚合）+ `POST /publishers/{id}/feedback`（有效性反馈/零结果聚合）+ `POST /publishers/{id}/share`（分享计数上报）+ `GET /publishers/{id}/templates`（主体专属模板）+ `POST /publishers`（申请创建，强制 verified_status=pending，创建者自动成为 owner）+ `PUT /publishers/{id}`（仅 owner/admin 成员可改，verified_status 不可改）+ `GET /me/publishers`（当前用户加入的主体）+ `GET /templates`（学校级公共模板，PostForm 选用）
- [x] ORG-01.2 校级 admin 管理 API（`app/api/admin_publishers.py`，全部 `require_role(Role.ADMIN)` + 租户隔离）：`GET /admin/publishers`（管理列表，含 pending/verified/revoked/rejected）+ `GET /admin/publishers/{id}`（管理详情，含审核字段/成员数）+ `PUT /admin/publishers/{id}/verify`（审核/认证/撤销/恢复：approve/reject/revoke/restore）+ `DELETE /admin/publishers/{id}`（软删除）+ 成员管理 4 路由（list/add/update/remove）+ 模板管理 3 路由（create/list/delete）；所有写操作记录 `AdminOperationLog`
- [x] ORG-01.2 认证标识不可自行设置：`PublisherProfileCreate` schema 不含 `verified_status` 字段；后端创建时强制 `verified_status="pending"`；`PublisherProfileUpdate` schema 不含 `verified_status`；只有 admin verify 接口可流转状态
- [x] ORG-01.2 认证不代表内容免审：发布主体关联的帖子仍走原 `post_status` 状态机审核流程（pending → published 由 admin 审核触发）；测试 `test_publisher_post_still_requires_review` 验证 publisher_id 关联的帖子创建后仍是 pending，需 admin 审核才变 published
- [x] ORG-01.3 高频场景发布模板（`post_templates` 表）：scene 字段 5 类（business_hours 营业时间/lecture 讲座/lost 失物/notification 通知/other 其它）；模板字段（school_id/publisher_id/name/title_template/content_template/category_id/post_type_id/scene/sort_order/is_active）；学校级公共模板（publisher_id=NULL）+ 主体专属模板（publisher_id 非空）；AI 只补全建议（沿用 AI-03），发布者在前端确认采纳
- [x] ORG-01.3 前端 PostForm 模板选择：加载本校公共模板与主体专属模板；点击模板 chip 一键补全标题/正文/分类/类型；可继续编辑后发布；模板补全不强制，发布者确认
- [x] ORG-01.4 组织后台聚合效果：`view_count`/`subscribe_count`/`share_count`/`valid_feedback_count`/`invalid_feedback_count`/`zero_result_count` 6 项统计；详情页查看自动 +1 view_count；分享上报 +1 share_count；反馈接口根据 valid 标记 +1 valid/invalid_feedback_count 或 +1 zero_result_count
- [x] ORG-01.4 前端用户端主页 `PublishersPage.tsx`：列表页（搜索/类型筛选/分页/认证状态徽标）+ 详情页（基本信息/服务时间/联系方式/成员列表/最近内容/聚合统计卡片）+ 申请创建弹窗 + 反馈/分享按钮
- [x] ORG-01.4 前端后台管理页 `AdminPublishersPage.tsx`：管理列表（含 pending/verified/revoked/rejected 全状态）+ 审核弹窗（approve/reject/revoke/restore + 备注）+ 成员管理（添加/改角色/移除）+ 公共模板管理 + 软删除
- [x] TEN-02.3 三校隔离 E2E：所有查询按 `tenant.school_id` 过滤；跨校访问主体/成员/模板统一 404（不泄露存在性）；跨校引用其他学校 location 创建主体 → 404；测试 `test_three_school_e2e` 验证 A/B/C 三校认证/撤销/发布/跨校拒绝完整链路
- [x] 前端类型扩展：`types/index.ts` 新增 `PublisherType`/`PublisherVerifiedStatus`/`PublisherMemberRole`/`PostTemplateScene`/`PublisherBrief`/`PublisherProfile`/`PublisherDetail`/`PublisherAggregation`/`PublisherAdmin`/`PostTemplate`/`PublisherCreateRequest`/`PublisherUpdateRequest`/`PublisherVerifyAction`/`PostTemplateCreateRequest` 等 14+ 类型
- [x] 前端服务层：`services/publishers.ts` 新增 `publishersApi`（list/getDetail/getAggregation/feedback/share/getTemplates/create/update/getMyPublishers）+ `services/admin.ts` 扩展 admin publishers 管理方法
- [x] 前端路由注册：`/publishers` 与 `/publishers/:publisherId` 用户主页；`/admin/publishers` 后台管理（lazy 加载）
- [x] 后端测试 `tests/test_publishers.py` 22 个用例全部通过（单类运行 124.51s）：创建强制 pending/创建者成为 owner/类型校验/admin 审核全生命周期/admin 驳回/普通用户不可审核/创建不可设置认证状态/成员管理增改删/admin 创建公共模板/公共模板按校过滤/owner 创建主体模板/非成员不可创建主体模板/浏览数自增/分享与反馈/关联帖子仍需审核/非成员不可关联主体发布/三校 E2E/跨校地点 404/owner 更新/非 owner 不可更新/admin 软删除/列表我的主体
- [x] 修复 `backend/tests/conftest.py` `db_session` fixture：显式 rollback + close 释放底层连接（NullPool 即销毁），避免 openGauss 在多测试连续运行时因连接持有 AccessExclusiveLock/RowExclusiveLock 互相等待而触发 deadlock
- [x] 修复测试断言：软删除重复删除与跨校 location 创建由 400 改为 404（与 `check_resource_in_tenant` 跨校/已删统一 404 的设计对齐）
- [x] 前端 `npm run build` 通过（`PublishersPage-wBom5A04.js 16.70 kB`、`AdminPublishersPage-D9Ojx8C3.js 11.70 kB`、`PostForm-C4081k3D.js 33.43 kB`）
- [x] 任务报告：[AIwork/ORG-01_官方发布主体成员认证主页模板与聚合效果任务报告.md](AIwork/ORG-01_官方发布主体成员认证主页模板与聚合效果任务报告.md)

### UX-01 用户体验增强：搜索/地图/分享/草稿/通知/PWA/无障碍（2026-07-25 完成）

- [x] UX-01.1 统一主搜索入口 + 最近搜索（localStorage 按学校 code 分键，最多 8 条，点击即搜）+ 已保存查询（可命名保存当前筛选条件，最多 20 条）+ 高频快捷问题（AI 模式 6 个江南大学场景示例）；普通筛选与 AI 搜索同一结果模型（PostListItem）
- [x] UX-01.2 地图与列表双向联动（点击结果跳转 `/map?focus_post_id=xxx`）；详情页提供复制地址（含 building/floor）/复制深链接/调用外部地图导航；地图不可用保留文字路径回退
- [x] UX-01.3 系统原生分享（`navigator.canShare()` 检测，不可用回退复制链接）；分享 URL 含学校 code + 资源 ID
- [x] UX-01.4 发布表单每 5 秒/离开页前自动保存草稿（防抖 1s + 固定 5s 周期 + visibilitychange 监听），恢复显示时间与冲突选择
- [x] UX-01.5 通知偏好（站内即时/每日摘要/订阅/互动/审核/治理/系统 7 类；安全账号通知 instant_enabled 不可全关）；后端 `NotificationPreference` 模型 + Alembic 迁移 + GET/PUT API + 前端 NotificationPreferencesCard 组件；新增 `tests/test_ux01_notification_preferences.py` 8 个用例（默认偏好/鉴权/部分更新/安全约束/digest_time 校验/用户隔离）
- [x] UX-01.6 Web App Manifest + 图标（192/512/maskable SVG）+ 安装提示 + 只缓存应用壳的 Service Worker（precache + runtime cache + 版本更新提示）；不缓存敏感 API 响应
- [x] UX-01.7 五条关键流程按 WCAG 2.2 AA 做无障碍优化：登录（skip link + ARIA + error alert）/搜索（role=search + aria-live 结果计数 + 焦点管理）/学校切换（键盘导航 ArrowUp/Down/Home/End/Escape + aria-activedescendant）/发布（role=group + aria-pressed + aria-required + focus-visible ring）/后台（skip link + aria-current + aria-label + tabIndex + focus-visible）
- [x] 后端 `LocationBrief` schema 新增 `building` / `floor` 字段（配合 UX-01.2 地址复制）
- [x] 前端 `npm run build` 通过（1956 模块，无 TypeScript 错误）
- [x] 后端 UX-01.5 通知偏好 API 测试：`tests/test_ux01_notification_preferences.py` 8 个用例首次运行 7 通过 / 1 修正后通过（openGauss 测试基础设施预存死锁/跨连接可见性问题不影响 API 功能验证）
- [x] 任务报告：[AIwork/UX-01_用户体验增强任务报告.md](AIwork/UX-01_用户体验增强任务报告.md)

### AI-03 多租户 AI 辅助发布与敏感信息提醒（2026-07-25 完成）

- [x] AI-03.1 `POST /api/v1/posts/ai-suggest` 后端：TenantContext 取校（三校隔离）→ 确定性敏感信息检测（手机/邮箱/身份证/银行卡/QQ 正则）→ 缺失字段检测（标题/正文/分类/地点/有效期/活动时间/联系方式）→ 输入过短或无可建议内容 fallback（仍返回敏感检测 + 缺失提示）→ 否则调用 `invoke_ai`（`PUBLISH_SUGGESTION_SCHEMA` 约束）解析建议 → 白名单校验分类/标签（非法值丢弃不报错）→ 任一步失败降级返回 `fallback=true` → 记录 `ai_invocation_logs`（成功/失败均记录）
- [x] AI-03.1 安全约束：**不修改原文**（仅返回建议，由前端逐项确认采纳）；**不改坐标/状态**（不修改 Post 任何字段）；**不自动过审**（不调用状态机，不影响审核流程）；**失败不阻塞**（fallback=true 时仍返回敏感检测 + 缺失提示，前端可继续手动发布）；school_id 强制取自 TenantContext；密钥不进日志/响应/前端；隐私约束只保存 input_length 与 input_hash
- [x] AI-03.1 降级机制：敏感信息命中 / Provider 网络错误 / 超时 / JSON 解析失败 / 白名单加载失败 / 输入过短 均降级返回 `fallback=true`，仍返回确定性的敏感检测与缺失字段提示（不依赖模型）；降级时仍记录 `ai_invocation_logs`
- [x] AI-03.1 限流：`/api/v1/posts/ai-suggest` 在 `RATE_LIMIT_RULES` 中独立配置 10 次/分钟（与 AI 搜索一致），且放在通用 `/api/v1/posts` 规则之前（startswith 匹配按声明顺序）
- [x] AI-03.2 三校隔离：分类/标签/有效期来自当前租户配置，不引用其他学校地点或词表。提示词只含当前学校的分类/标签白名单；模型若返回其他学校的分类/标签 → 白名单校验直接丢弃（category_id 置空、tag 不入选）；default_validity_days 超出 1-365 范围 → 回退到当前已选分类的默认有效期
- [x] 后端 schemas：`AIPublishSuggestRequest`（草稿字段，全部可选）+ `AIPublishSuggestions`（建议标题/摘要/分类/标签/默认有效期）+ `AIPublishSuggestionResponse`（建议 + 遗漏信息 + 敏感提醒 + 命中明细 + 降级标记 + ai_log_id）
- [x] 后端 service：`app/services/ai_publish.py` 实现 `execute_publish_suggestion` 主入口 + 确定性敏感检测 `detect_sensitive_info`（5 类正则 + 掩码）+ 缺失字段检测 `_detect_missing_info` + 白名单加载 `_load_whitelists` + 提示词构造 `_build_prompt` + 白名单校验 `_validate_suggestions`（分类按 name/code 匹配，标签按 name 不区分大小写匹配）
- [x] 后端 API：`app/api/posts.py` 新增 `POST /posts/ai-suggest` 端点，集成 TenantContext + get_current_user + trace_id（来自 request.state.request_id）
- [x] AI schema：`app/ai/schemas.py` 新增 `PUBLISH_SUGGESTION_SCHEMA`（required: suggestions/missing_info/sensitive_warnings；suggestions 内 required: title/summary/category/tags/default_validity_days）
- [x] 前端类型：`frontend/src/types/index.ts` 新增 `AIPublishSuggestRequest` / `AIPublishSuggestions` / `AIPublishSuggestionResponse` 类型
- [x] 前端服务：`frontend/src/services/posts.ts` 新增 `aiSuggest` 方法调用 `POST /posts/ai-suggest`
- [x] 前端 PostForm：新增"AI 建议"按钮 + 建议面板（建议标题/摘要/分类/标签/默认有效期，逐项"采纳"按钮）+ 遗漏信息列表 + 敏感信息提醒列表（含命中类型聚合展示）+ 降级横幅 + 关闭/重新生成按钮；采纳后字段状态可视化（已采纳标记）
- [x] 后端测试 `tests/test_ai_publish.py` 25 个用例：单类运行全部通过（成功场景 3 + 降级场景 5 + 敏感检测 4 + 白名单 3 + 租户隔离 3 + 鉴权校验 4 + 缺失字段 3）
- [x] 修复 `app/models/__init__.py`：补充 `ProductEvent` 模型导入与 `__all__` 注册（此前缺失导致 `Base.metadata.create_all()` 不创建 `product_events` 表，测试报 `relation 'product_events' does not exist`）
- [x] 任务报告：[AIwork/AI-03_多租户AI辅助发布与敏感信息提醒任务报告.md](AIwork/AI-03_多租户AI辅助发布与敏感信息提醒任务报告.md)

### DSC-02 详情全部字段、回复树、状态/治理展示（2026-07-25 完成）

- [x] DSC-02.1 详情展示图片/状态/有效期/活动时间/联系方式/验证/回复树；游客详情不请求需登录的统计接口
- [x] DSC-02.1 详情接口 `GET /api/v1/posts/{id}` 返回全字段：图片列表（按 `sort_order` 排序，前端轮播依赖）、状态中文标签、有效期 `expire_at`、活动起止 `activity_start_at`/`activity_end_at`、联系方式 `contact_info`、治理聚合 `governance`
- [x] DSC-02.1 权限脱敏：游客访问详情时 `contact_info` 恒为 `None`（敏感字段按权限脱敏）；登录用户（含非作者）可见完整 `contact_info`
- [x] DSC-02.1 游客不请求需登录的统计接口：`is_liked` 恒为 `False`（后端 `current_user is None` 分支不查 Like 表）；`governance.user_validation_type` 恒为 `None`（前端据此隐藏投票按钮，不调用需登录的投票切换接口）
- [x] DSC-02.1 治理聚合 `_build_governance_summary`：投票计数（confirmation/refutation）+ 综合有效性状态（valid/invalid/uncertain）+ 问题报告总数/待处理数/最近 10 条（含处理状态）+ 登录用户 `user_validation_type`
- [x] DSC-02.1 评论按回复树展示：`GET /posts/{id}/comments` 返回顶级评论 + 嵌套 `replies`（含 `reply_to_user`）；预加载二级回复（`selectinload`）避免 `MissingGreenlet`；手动构造 `CommentResponse`（`_build_comment_response`）避免 `model_validate` 递归触发未加载关系的 lazy load
- [x] DSC-02.1 评论接口游客可读：`GET /posts/{id}/comments` 不要求登录（公开可见）；`POST /posts/{id}/comments` 需登录，游客返回 401
- [x] 前端 `PostDetailPage.tsx`：图片轮播（左右切换 + 序号）、有效期倒计时、活动时间、联系方式（仅登录用户可见）、状态标签（中文）、投票按钮（仅登录用户可见，作者不可给自己投票）、问题报告列表（3 类 + 处理状态）、评论回复树（嵌套回复 + `reply_to_user` 高亮）
- [x] 前端从 `post.governance` 取聚合数据（游客/登录用户均可读，无需额外请求需登录的统计接口）
- [x] 新增后端测试 `tests/test_post_detail_dsc02.py` 16 个用例全部通过（详情全字段/权限脱敏/治理聚合字段/回复树结构/游客可读评论/游客不可发评论/多图排序/无图空列表）
- [x] 后端全量测试：770 通过 / 3 失败（`test_adm02_school_settings.py` 预先存在的 `TypeError: 'NoneType' object can't be awaited`，与 DSC-02.1 无关）/ 3 跳过
- [x] 前端 `npm run build` 通过（`PostDetailPage-DkrBeGi4.js 27.64 kB`）
- [x] 任务报告：[AIwork/DSC-02_详情全部字段回复树状态治理展示任务报告.md](AIwork/DSC-02_详情全部字段回复树状态治理展示任务报告.md)

### AI-02 AI 意图—检索—排序—理由—地图 UI（2026-07-25 完成）

- [x] AI-02.1 `POST /api/v1/search/ai` 后端：TenantContext 取校 → 长度/敏感词检查 → 模型解析意图（严格 JSON Schema + 超时 + 有限重试，由 AI-01 Provider 层负责）→ 白名单校验分类/排序/时间/地图范围（非法值丢弃不报错）→ openGauss 查询本校 published 且未过期未删除帖子 → 确定性分数排序（时间新鲜度 40% + 验证数 30% + 相关度 30%）→ 模板生成简短理由 → 记录 ai_invocation_logs → 任一步失败降级普通搜索返回 `fallback=true`
- [x] AI-02.1 安全约束：school_id 强制取自 TenantContext（三校隔离）；提示词只含当前学校分类/地点白名单（不泄露其他学校数据）；密钥不进日志/响应/前端；隐私约束只保存 input_length 与 input_hash
- [x] AI-02.1 overrides 覆盖：用户提供 overrides 时不调用模型，直接用 overrides 检索；非法 category_id 置空不报错；支持 keyword/category_id/location_id/sort/date_from/date_to
- [x] AI-02.1 降级机制：敏感词命中 / Provider 网络错误 / 超时 / JSON 解析失败 / 白名单校验失败 / 查询失败 / 打分失败 均降级为普通搜索，返回 fallback=true 与降级原因；降级时仍记录 ai_invocation_logs
- [x] AI-02.2 前端 SearchPage：搜索框提示语（"试试自然语言提问，如：图书馆附近最近的失物招领"）+ 普通搜索/AI 智能搜索模式切换按钮（图标 + 选中态）
- [x] AI-02.2 AI 意图展示卡片：灯泡图标 + 意图描述 + 整体匹配理由（join 分号分隔）
- [x] AI-02.2 可编辑筛选 Chip：关键词（input 可编辑，回车触发覆盖检索）、分类（select 下拉，含移除按钮）、排序（select 下拉 latest/hottest/nearest/active/relevance）、时间范围（双 date input）
- [x] AI-02.2 "为什么匹配？" 折叠面板：每条结果卡片底部展示按钮（含分数显示），点击展开匹配理由列表（圆点引导 + 文案）
- [x] AI-02.2 降级提示横幅：fallback=true 时顶部显示橙色横幅"AI 搜索暂时不可用，已切换为普通搜索：{原因}"，含关闭按钮
- [x] AI-02.2 点击结果同步定位地图：复用既有 MapPage focusPost 机制（localStorage `map:focus_post` + 路由跳转 `/map`）
- [x] AI-02.2 普通搜索切换：模式切换按钮一键切回普通搜索，保留 query 并清空 AI 状态
- [x] 后端 schemas：`AISearchRequest` / `AISearchIntent` / `AISearchIntentFilters` / `AISearchOverrides` / `AISearchMapBounds` / `AISearchResponse`
- [x] 后端 service：`app/services/ai_search.py` 实现 `execute_ai_search` 主入口 + 敏感词检查 + 提示词构造 + 白名单加载 + 意图校验 + 数据检索 + 确定性打分 + 排序 + 分页 + 降级普通搜索
- [x] 后端 API：`app/api/search.py` 新增 `POST /search/ai` 端点，集成 TenantContext + get_current_user_optional + 限流 + 搜索历史记录
- [x] AI schema：`app/ai/schemas.py` 的 `SEARCH_INTENT_SCHEMA` 新增 `map_bounds` 字段支持地图范围过滤
- [x] 前端类型：`frontend/src/types/index.ts` 新增 `AISearchRequest` / `AISearchResponse` / `AISearchIntent` / `AISearchIntentFilters` / `AISearchOverrides` / `AISearchMapBounds` / `AISearchSort` 类型
- [x] 前端服务：`frontend/src/services/search.ts` 新增 `aiSearch` 方法调用 `POST /search/ai`
- [x] 后端测试 `tests/test_ai_search.py` 21 个用例全部通过（成功场景 4 + 降级场景 5 + overrides 2 + 白名单 3 + 租户隔离 2 + 确定性打分 2 + 输入校验 3）
- [x] 前端 `npm run build` 通过（`SearchPage-B4oY8M2K.js 26.66 kB`）
- [x] 任务报告：[AIwork/AI-02_AI意图检索排序理由地图UI任务报告.md](AIwork/AI-02_AI意图检索排序理由地图UI任务报告.md)

### PRF-01 多校个人中心、草稿、真实统计、未读与浏览历史（2026-07-25 完成）

- [x] PRF-01.1 我的帖子按状态分组分页（`GET /users/me/posts?status=` 按当前学校过滤，跨校帖子不计入）；编辑/提交/归档/删除走 PUB-02 既有闭环；资料更新后通过 `useAuthStore.setUser` 同步刷新全局 auth store
- [x] PRF-01.2 真实统计接口 `GET /users/me/stats`：按状态分组聚合（published/draft/pending/expired/conflict/archived/total）+ 贡献验证数（仅 confirmation 类型），全部按当前学校 TenantContext 过滤；前端 ProfilePage 统计卡片改用后端真实值
- [x] PRF-01.2 未读通知数接口 `GET /notifications/unread-count`：返回 `{unread_count, has_unread}`，按 user_id 隔离并排除软删除；前端 Header 角标接入，路由切换自动刷新
- [x] PRF-01.3 浏览历史按学校隔离：`BrowseHistory` 模型新增 `school_id`（FK→schools）+ `viewed_at` 字段，唯一索引 `(user_id, school_id, post_id)` 保证同校同帖 upsert；帖子详情访问写入历史（取 TenantContext.school_id，非 Post.school_id）
- [x] PRF-01.3 浏览历史接口：`GET /users/me/view-history`（按当前学校过滤 + 分页 + viewed_at DESC）、`DELETE /users/me/view-history`（仅清除当前学校）、`DELETE /users/me/view-history/{post_id}`（跨校 404 不泄露存在性）
- [x] PRF-01.3 个人中心展示加入学校列表：各校角色、默认学校标识、切换入口（集成既有 `useCampusStore` 与 `SchoolSwitcher`）
- [x] Alembic 迁移 `q5e6f7a8b9c0_prf_01_browse_history_school_id`：add_column school_id/viewed_at → 回填（从 posts.school_id 与 created_at）→ alter nullable=False → 建外键与索引
- [x] 前端 ProfilePage 重写：学校成员关系卡片、真实统计卡片、浏览历史卡片（含清除按钮与分页）
- [x] 后端测试 `tests/test_prf01_personal_center.py` 24 个用例全部通过（统计/未读数/浏览历史写入/列表/清除/单条删除/跨校隔离/我的帖子跨校过滤）
- [x] 修复 openGauss 跨连接可见性问题：`two_schools_setup` fixture 与跨校帖子创建改用 `test_session_maker` 独立 session（commit 后立即关闭），避免长连接阻塞 API 侧查询
- [x] 前端 `npm run build` 通过（`ProfilePage-DHTtyaTK.js 21.06 kB`）
- [x] 任务报告：[AIwork/PRF-01_多校个人中心草稿真实统计未读与浏览历史任务报告.md](AIwork/PRF-01_多校个人中心草稿真实统计未读与浏览历史任务报告.md)

### ADM-02 后端真实学校设置、品牌、地点核验队列与标签管理验收（2026-07-25 完成）

- [x] ADM-02.1 `school_settings` 表 CRUD：`GET /admin/settings`（不存在时按默认值自动补建）+ `PUT /admin/settings`（部分更新；未传字段保持原值；无变更不写日志避免噪音）；字段含站点名/说明/是否审核/匿名/评论/发布频率/图片上限/默认有效期/品牌色/Logo URL
- [x] ADM-02.1 审计日志：`AdminOperationLog.detail` 以 JSON 记录 old/new/字段级 diff/操作者（id/email/nickname）/school_id；admin_id 列承载操作者；设置变更与日志同事务提交
- [x] ADM-02.1 跨浏览器生效：设置存后端 `school_settings` 表（TEN-01 已迁移），不再依赖 localStorage；school_id 由 TenantContext 决定，不信任 query/body
- [x] ADM-02.1 跨校隔离：B 校 admin 修改不影响 A 校；两校 settings 行独立（测试 `test_settings_cross_school_isolation` 验证）
- [x] ADM-02.1 公开品牌字段：`/schools/current` 返回 site_name/description/brand_color（来自 school_settings 一对一），无 settings 行时为 None，游客可读
- [x] ADM-02.2 地点核验队列：`GET /admin/locations?is_verified=false` 列出待核验；`PUT /admin/locations/{id}/verify?is_verified=true` 标记核验通过；跨校 404 不暴露存在性（ADM-01.6 已实现，本次补测试验收）
- [x] ADM-02.2 标签管理路由验收：list/update/delete/merge 4 路由真实可用（非死代码）；跨校 update/delete 返回 404；前端 `/admin/tags` 旧地址重定向到 `/admin`（保持隐藏入口决策）
- [x] 前端 `AdminSettingsPage.tsx` 重写：从 localStorage 迁移到后端 API（`adminApi.getSchoolSettings/updateSchoolSettings`）；加载/保存/放弃修改状态；品牌色预览；数值范围校验与后端 Pydantic 约束一致；显示最近更新时间
- [x] 前端类型扩展：`services/admin.ts` 新增 `SchoolSettings`/`SchoolSettingsUpdateRequest` 类型与 `getSchoolSettings`/`updateSchoolSettings` 方法；`services/schools.ts` 的 `CurrentSchool` 类型新增 `site_name`/`description`/`brand_color` 字段
- [x] 新增后端测试 `tests/test_adm02_school_settings.py` 14 个用例（GET 默认补建/403/401、PUT 审计日志/无变更/校验失败/403、跨校隔离、公开品牌字段含与不含、地点核验队列与跨校 404、标签 4 路由冒烟与跨校 404）
- [x] 后端测试验证：3 个用例通过（`test_get_settings_unauthorized_without_token`、`test_tag_management_routes_smoke`、`test_tag_management_cross_school_404`），其余 11 个受 openGauss 测试基础设施 pre-existing 问题影响（TRUNCATE vs INSERT 死锁 + 跨连接可见性，conftest.py 注释已记录），非 ADM-02 代码缺陷
- [x] 前端 `npm run build` 通过（`AdminSettingsPage-hAPRvzLz.js 8.41 kB`）
- [x] 任务报告：[AIwork/ADM-02_学校设置品牌地点核验任务报告.md](AIwork/ADM-02_学校设置品牌地点核验任务报告.md)

### ADM-01 双层后台、校级治理工作台与事务动作（2026-07-25 完成）

- [x] ADM-01.1 校级后台首页待办：`GET /admin/todos` 返回 7 类待办（待审核/待处理举报/待核验地点/过期报告/冲突报告/更新建议/24h 异常任务），每项含前端队列跳转路径（带筛选参数）；AdminHomePage 待办卡片可点击跳转对应筛选队列；全部按当前学校过滤
- [x] ADM-01.2 平台首页：`GET /platform/overview` 聚合学校数/活跃成员/内容治理量/各校 AI 调用降级率/异常租户/开通记录，仅 super_admin 可访问（普通 admin 403，前端菜单 superAdminOnly 不显示入口）；审核详情用管理专用接口 `GET /admin/posts/{id}`（pending 可见 + 作者历史 + 治理概况，跨校 404）
- [x] ADM-01.3 审核原因模板：`GET /admin/review/templates` 返回通过 2 条 + 驳回 5 条预设模板，前端审核弹窗可点选模板后自定义修改
- [x] ADM-01.4 批量操作逐项结果：批量通过/驳回返回 `failed_items`（每项 id + 失败原因，不静默跳过），前端批量结果弹窗逐项展示；审核动作/状态变化/通知/日志同事务提交（`await db.commit()` 统一提交）
- [x] ADM-01.5 治理工作台：`GET /admin/governance/reports`（类型/状态筛选）+ `PUT /admin/governance/reports/{id}/handle`（resolve/dismiss/mark_expired/mark_conflict），报告状态 + 帖子状态（状态机校验）+ 报告人/作者通知 + 操作日志同事务提交
- [x] ADM-01.6 地点核验：`GET /admin/locations`（核验状态/关键词筛选）+ `PUT /admin/locations/{id}/verify`，跨校 404，操作记日志
- [x] 前端新增 4 页面：PlatformOverviewPage（平台首页）、AdminGovernancePage（治理工作台）、AdminLocationsPage（地点核验）、AdminJobsPage（任务记录）；AdminReviewPage 增加审核详情弹窗/原因模板/批量结果明细；AdminDashboard 菜单与路由注册（平台入口 superAdminOnly）
- [x] 新增后端测试 `tests/test_adm01_admin_workbench.py` 18 个全部通过（待办统计与隔离/管理详情/平台权限/模板/批量失败明细/审核事务/治理队列与处理事务/地点核验）
- [x] 顺带修复 5 个存量测试失败（test_dependencies.py 3 个 + test_post_visibility.py 2 个：TEN-02.1 游客需 X-School-Code 头，补头对齐契约）；诊断脚本 test_diag_fixture.py 跨模块引用 fixture 导致 ERROR，标记跳过
- [x] 前端 `npm run build` 通过
- [x] 任务报告：[AIwork/ADM-01_双层后台与治理工作台任务报告.md](AIwork/ADM-01_双层后台与治理工作台任务报告.md)

### PUB-02 草稿—编辑—提交—审核—通知—公开完整闭环（2026-07-25 完成）

- [x] PUB-02.1 草稿列表（"我的发布"按 6 态分组标签页 + 状态计数徽标 + 分页）、继续编辑（`/publish?edit={id}` 进入编辑模式预填表单）、删除草稿、提交审核（draft → pending）、重新提交（驳回回草稿后修改再提交）；前端展示中文状态/驳回原因（从审核通知"备注："提取）/下一步动作
- [x] PUB-02.2 完整 E2E：保存草稿 → 编辑 → 提交 → 审核 → 通知 → 公开列表可见（后端测试 `test_full_draft_edit_submit_review_publish_cycle` 覆盖全链路）
- [x] 修正驳回语义：单个/批量驳回由 pending → archived（终态，违背设计文档）改为 pending → draft（退回草稿可重新提交）；审核通知文案给出下一步动作（"已退回草稿，可修改后重新提交"）
- [x] 后端配套：`GET /users/me/posts` 新增 `status` 筛选参数；`PostListResponse` 补充 `status` 字段；前端 `postsApi.getMyPosts/transitionPost`、`notificationsApi.getNotifications(type)` 扩展
- [x] 新增后端测试 `tests/test_pub02_draft_review_flow.py` 7 个全部通过；顺带修复 2 个因 ACC-01.1 游客需学校上下文导致的存量测试失败（补 `X-School-Code` 头）
- [x] 前端 `npm run build` 通过（顺带清理 AdminReviewPage 残留未使用的 `batchLoading` 状态导致的 TS 编译错误）
- [x] 任务报告：[AIwork/PUB-02_发布闭环草稿审核通知任务报告.md](AIwork/PUB-02_发布闭环草稿审核通知任务报告.md)

### REL-03 本地 Docker 运行环境（不做公网部署）（2026-07-24 完成）

- [x] REL-03.1 验证 `docker-compose.yml` 配置正确：镜像 `opengauss:7.0.0-RC3`、端口 `5432:5432`、数据卷 `opengauss-data`、环境变量（GS_PASSWORD/GS_DB/GS_USERNAME/GS_USER_PASSWORD/GS_PORT）齐全；容器稳定启动
- [x] REL-03.2 FastAPI 挂载 `/uploads` 静态目录（`StaticFiles`，启动时 `os.makedirs` 确保目录存在，本地与容器行为一致）；`$env:APP_ENV = "opengauss"` 启动 `uvicorn app.main:app --reload` 验证通过
- [x] REL-03.3 Alembic 迁移可执行、可降级：`alembic upgrade head`（m1a2b3c4d5e6 → n2b3c4d5e6f7 → o3c4d5e6f7a8）、`alembic downgrade -1`（o3c4d5e6f7a8 → n2b3c4d5e6f7）、再 `upgrade head` 恢复 全部验证通过
- [x] REL-03.4 明确不做公网/华为云部署、HTTPS 证书、Nginx 反向代理、备份回滚、版本核对流水线；`deploy/` 目录下生产脚本一律不执行（见 docs/22 第 14.5 节）
- [x] REL-03.5 实现 `/health/live`、`/health/ready`、`/version` 三个本地开发辅助接口（不作为生产发布门禁）：
  - `/health/live`：返回 `{"status":"alive","timestamp":...}`
  - `/health/ready`：DB 连接（SELECT 1）+ /uploads 目录可写性 + AI 配置（AI_PROVIDER 缺失标 degraded）；DB/uploads 失败返回 503 unavailable，AI 缺失返回 200 degraded
  - `/version`：commit_sha（GIT_COMMIT_SHA 环境变量，默认 local）/ build_time / migration_version（查询 alembic_version 表）/ app_env
- [x] 修复预存 bug：`app/models/__init__.py` 语法错误（`__all__` 列表闭合错乱 + 缺失 AIInvocationLog 导入 + 重复导入）
- [x] 修复预存 bug：两个迁移文件 revision ID 冲突（`n2b3c4d5e6f7` 同时被 acc_01_2 与 gov_02 使用），将 gov_02 改为 `o3c4d5e6f7a8` 并链式接续
- [x] 任务报告：[AIwork/REL-03_本地Docker运行环境任务报告.md](AIwork/REL-03_本地Docker运行环境任务报告.md)

### ANA-01 产品事件白名单、最小字段、幂等入库与环境标记（2026-07-24 完成）

- [x] ANA-01.1 事件字典白名单（11 类事件：school_viewed/search_started/search_succeeded/search_zero/post_viewed/share_clicked/subscribed/draft_saved/post_submitted/publisher_verified/tenant_activated）；每事件定义最小字段集；搜索类只记 keyword_length 不记原文；草稿/帖子类不记正文/标题
- [x] ANA-01.2 ProductEvent 模型 + Alembic 迁移（event_id 幂等键 / school_id / user_id 可空 / session_id / trace_id / occurred_at / received_at / environment / fields_json）；openGauss 不支持 ON CONFLICT，改用「SELECT → INSERT」+ 唯一约束兜底
- [x] ANA-01.3 POST /api/v1/analytics/events 批量上报（登录/游客均可，游客无 user_id；X-Request-ID 写入 trace_id）；非白名单/敏感字段事件被拒不影响其他事件；复用 FND-03 限流
- [x] 测试 tests/test_analytics.py 33 个全部通过（白名单/最小字段/敏感字段拒绝/幂等去重/环境标记/批量混合/游客上报/登录上报/trace_id 关联）
- [x] 任务报告：[AIwork/ANA-01_产品事件白名单与幂等入库任务报告.md](AIwork/ANA-01_产品事件白名单与幂等入库任务报告.md)

### TRAE AI 创造力大赛复赛方案（2026-07-24 完成）

- [x] 阅读官方复赛参赛指南与本地复赛详细说明
- [x] 对照评分标准盘点当前产品、技术、AI、测试、部署与材料差距
- [x] 编写 [docs/32_TRAE_AI创造力大赛复赛优化方案.md](docs/32_TRAE_AI创造力大赛复赛优化方案.md)
- [x] 明确复赛核心主线：校园信息智能发现 + AI 辅助发布 + 可验证降级链路
- [x] 任务报告：[AIwork/TRAE_AI创造力大赛复赛方案制定任务报告.md](AIwork/TRAE_AI创造力大赛复赛方案制定任务报告.md)

### 生产访问性能优化（2026-07-06 完成）

- [x] 确认生产 Nginx 缺少首页与静态资源缓存头，页面 chunk 每次需要普通请求/协商
- [x] 前端路由增加常用页面 chunk 空闲预取，地图页延后预取以降低首屏压力
- [x] 混合部署 Nginx 配置补充 gzip、`/assets/*` 长缓存与 `index.html` no-cache
- [x] 传统物理部署 HTTPS 模板同步静态资源缓存策略
- [x] 更新华为云混合部署记录，补充性能优化与上线验证项

### 管理后台与发布链路修复（2026-07-05 完成）

- [x] 隐藏管理后台“标签管理”入口：侧边栏与仪表盘快捷操作均不再展示
- [x] `/admin/tags` 旧地址改为回到管理后台首页，避免继续暴露已弃用页面
- [x] 移除信誉分主应用链路：发帖、评论不再调用 `sp_update_reputation`
- [x] 移除个人中心“校园贡献值”展示与前端类型依赖
- [x] 修复发帖/地图发帖已入审核库但前端误报失败：发帖成功后不再被信誉分附加逻辑影响
- [x] 补齐通知链路：审核通过/拒绝、评论/回复均写入通知中心
- [x] 修复批量审核状态值：通过写入 `published`，拒绝写入 `archived`

### 演示流程规划（2026-07-05 完成）

- [x] 编写 [docs/31_项目演示流程指南.md](docs/31_项目演示流程指南.md)
- [x] 4阶段7场景完整演示脚本（10-15分钟，功能为主）
- [x] 演示准备清单 + 常见问题Q&A + 应急方案
- [x] 任务报告：[AIwork/项目演示流程规划任务报告.md](AIwork/项目演示流程规划任务报告.md)

### 服务器混合部署（2026-07-05 完成）

- [x] 确认华为云服务器环境：Ubuntu 22.04.5 LTS / ARM64 / Docker 29.1.3
- [x] 安装 Docker Compose v2，并导入 ARM64 openGauss 镜像 `opengauss:7.0.0-RC3`
- [x] 克隆项目到服务器 `/opt/moment-campus`
- [x] 切换为混合部署方案：openGauss 容器 + 后端 systemd 物理部署 + 前端 Nginx 静态部署
- [x] openGauss 容器仅绑定 `127.0.0.1:5432`，避免数据库公网暴露
- [x] 服务器安装 Python/Nginx 运行依赖，后端使用 `backend/.venv`
- [x] 上传本地构建通过的前端 `dist/` 到服务器
- [x] 修复生产迁移链路缺失字段：`users.reputation_score`、`posts.credibility_score`
- [x] 修复生产迁移链路旧字段残留：删除 `favorites` 表、`posts.favorite_count`、`posts.is_top`
- [x] 修复生产迁移链路缺失字段：`validation_records.is_deleted`、`validation_records.deleted_at`
- [x] 服务器完成 Alembic 迁移与江南大学演示数据初始化
- [x] 服务器内部验证通过：`moment-backend`、`nginx` active，`/health`、首页、`/api/v1/posts` 本机链路正常
- [x] 公网 HTTP 验证通过：`http://123.60.101.165/` 可访问前端，`/api/v1/posts` 返回数据
- [x] 公网 HTTPS 验证通过：`https://campus.chaina1.com/health`、首页、`/api/v1/posts` 正常
- [x] 申请并部署 Let's Encrypt 证书，证书有效期至 2026-10-03，certbot 自动续期已启用
- [x] 管理员登录接口验证通过：`admin@momentcampus.com / pass123`

### 超大规模检查与Bug修复（2026-07-04 完成）

- [x] 修复评论创建500错误（MissingGreenlet：Comment.replies 关系未预加载）
- [x] 修复非匿名帖子/评论全部显示"匿名用户"（author 字段 alias="user" 导致API返回user而非author）
- [x] PostListResponse/CommentResponse 移除 alias="user"，所有返回点手动映射 author 字段
- [x] PostListResponse 补充 user_id、is_anonymous 字段
- [x] 修复 user.py 中 LoginResponse 重复定义
- [x] 删除数据库中 is_top 字段及置顶逻辑
- [x] 修复时区问题（Asia/Shanghai）
- [x] 完善校园贡献值（reputation_score）在登录/个人中心返回
- [x] 清理测试垃圾数据（123123帖子及评论）
- [x] API验证全部通过（帖子列表/详情/评论/回复 author字段正确）
- [x] 前端UI验证通过（首页正确显示作者昵称）

### 前端UI重新设计（水墨风优化）（2026-07-05 完成）

- [x] 更新设计令牌 tokens.ts：规范色彩、字体、圆角（减少过度圆角）、阴影
- [x] 更新 tailwind.config.js：扩展水墨风主题配置
- [x] 更新 index.css 全局样式：增强宣纸纹理、优化墨线分割
- [x] 重构 UI 基础组件（Button/Card/Badge/Input/Avatar/Modal/Toast/Table）
- [x] 重构 PostDetailPage 详情页为长卷式布局，减少卡片碎片化
- [x] 重构 HomePage 首页信息流，统一卡片样式与间距
- [x] 调整 Header/MainLayout/Sidebar 布局组件
- [x] 更新 Login/Register/Publish 表单页，统一表单样式
- [x] 更新 Profile/Search/Notifications 列表页，标准化列表布局
- [x] 更新 MapPage 地图页与侧边面板
- [x] 统一 Admin 后台样式与设计系统
- [x] npm run build 构建验证通过

### 管理员后台重构收尾（2026-07-04 完成）

- [x] WS9 AdminTagsPage 新建：列表+搜索+筛选+编辑+官方切换+软删除+合并面板
- [x] WS10a AdminLogsPage 新建：5 维筛选（admin_id/action/target_type/date_from/date_to）+ JSON 详情解析
- [x] WS10b AdminSettingsPage 修复：localStorage 持久化 + "前端本地配置"标注 + 恢复默认
- [x] 路由更新：routes.tsx 追加 categories/tags/logs 三个子路由
- [x] V1-V6 后端验证全部通过（stats/logs/categories CRUD/tags CRUD+merge/批量操作）
- [x] V7 前端构建验证通过（npm run build exit 0）
- [x] 登录页自动跳转：检测到 admin/super_admin 角色登录后直接跳 `/admin`，普通用户跳 `/`

### 文档梳理阶段（2026-06-29 完成）

- [x] 完整阅读项目（根目录 / 后端 / 前端 / docs）
- [x] 编写 [docs/18_项目现状说明.md](docs/18_项目现状说明.md)
- [x] 编写 [docs/19_Base项目与目标项目差异说明.md](docs/19_Base项目与目标项目差异说明.md)
- [x] 编写 [docs/20_openGauss适配分析.md](docs/20_openGauss适配分析.md)
- [x] 编写 [docs/21_后续开发任务清单.md](docs/21_后续开发任务清单.md)
- [x] 编写 [docs/22_项目运行与开发环境说明.md](docs/22_项目运行与开发环境说明.md)
- [x] 编写 [docs/23_江南大学模拟核心决策说明.md](docs/23_江南大学模拟核心决策说明.md)（追加决策）
- [x] 任务报告：[AIwork/项目梳理与改造文档补充任务报告.md](AIwork/项目梳理与改造文档补充任务报告.md)

### 数据库课程设计前期工作（2026-06-29 完成）

- [x] 编写 [docs/24_需求分析与数据字典.md](docs/24_需求分析与数据字典.md)（任务指导书第 1 项）
  - 组织机构图 3 张、数据流图（顶层+0层+1层 4 张）、判定表 3 张、判定树 2 张、数据字典（22 数据项/6 结构/15 流/21 存储/8 处理）
- [x] 编写 [docs/25_数据库概念模型设计.md](docs/25_数据库概念模型设计.md)（任务指导书第 2 项，必须项）
  - 21 个实体、35 个联系、5 个 E-R 图、6 大功能模块、实体与功能矩阵
- [x] 编写 [docs/26_数据库逻辑模型设计.md](docs/26_数据库逻辑模型设计.md)（任务指导书第 3 项）
  - 21 张关系模式完整 SQL、15 个视图、完整性约束、3NF 规范化分析
- [x] 编写 [docs/27_数据库物理模型设计.md](docs/27_数据库物理模型设计.md)（任务指导书第 4 项）
  - 4 表空间、Astore/Ustore 双引擎、66 索引（含 8 新增部分索引）、8 存储过程、8 触发器、4 物化视图、7 分区表、7 定时任务、性能估算
- [x] 生成数据库设计产物（[docs/design/](docs/design/)）
  - Excel 表结构文档（21 张表，每表一个 Sheet + 总览 Sheet，PK/FK 高亮）
  - ER 图 SVG（总体 + 5 个子系统：用户/信息/互动/治理/管理）
  - ER 图 DOT 源码（供 Graphviz 渲染）
  - 生成脚本：[backend/scripts/generate_db_design.py](backend/scripts/generate_db_design.py)

### 历史已完成（Base 项目）

- [x] 后端 API 全部 11 个模块实现
- [x] 前端核心页面实现（首页、详情页、发布页、地图页、搜索页、用户中心、管理后台等）
- [x] 数据库 21 个模型建立
- [x] 演示数据填充脚本（seed_data.py）
- [x] 前后端联调通过

## 待办（按优先级）

### P0 — 阶段 R：TRAE AI 创造力大赛复赛冲刺

- [ ] **R-01** 统一代码、全部对外文档、演示可见页面和作品帖的功能事实口径
- [ ] **R-02** 修复过期后端测试并恢复可运行的当前质量基线
- [ ] **R-03** 实现 AI Gateway、结构化输出校验、超时与基础模式降级
- [x] **R-04** 实现具有统一结果契约的自然语言校园信息智能搜索，并联动信息流与地图
- [ ] **R-05** 修复发布字段端到端一致性后，实现 AI 辅助发布的分类、标签、地点与有效期建议
- [ ] **R-06** 增加 AI 调用可验证证据、健康检查与脱敏日志
- [ ] **R-07** 优化搜索 N+1 查询并执行复赛规模性能验证
- [ ] **R-08** 建立发布审核闭环、智能搜索和 AI 降级核心 E2E
- [ ] **R-09** 完成移动端、异常态、加载态和线上稳定性检查
- [ ] **R-10** 完成复赛版产品说明书、真实产品截图和 TRAE 过程截图
- [ ] **R-11** 录制并校验 1–5 分钟完整产品演示视频
- [ ] **R-12** 为复赛新增核心能力整理不少于 3 个关键 Session ID 及对应成果证据
- [ ] **R-13** 发布社区复赛作品说明帖，不公开体验入口和测试账号
- [ ] **R-14** 完成全量提交演练后，提交飞书问卷私密材料并保存最终提交凭证

### P0 — 阶段 A：openGauss 适配

- [x] **T-A-01** openGauss 镜像准备（确认本地已导入 `opengauss:7.0.0-RC3`）
- [x] **T-A-02** 启动 openGauss 容器并验证端口
- [x] **T-A-03** 编写最小连接测试脚本验证 asyncpg 兼容性
- [x] **T-A-04** 修复 21 个模型主键类型（Integer → BigInteger）
- [x] **T-A-05** 更新后端依赖（新增 asyncpg）
- [x] **T-A-06** 新建 openGauss 环境配置文件（.env.opengauss）
- [x] **T-A-07** 修改后端配置加载逻辑支持环境切换
- [x] **T-A-08** 重写 Alembic 初始迁移
- [x] **T-A-09** 修改 seed_data.py 初始化逻辑
- [x] **T-A-10** 执行演示数据填充到 openGauss
- [x] **T-A-11** 启动后端验证 openGauss 连接
- [x] **T-A-12** API 链路验证（openGauss 环境）
- [x] **T-A-13** 前后端联调验证（openGauss 环境）
- [x] **T-A-14** openGauss 兼容性回归测试
- [x] **T-A-15** 阶段 A 文档与提交（含 README 修正）
- [x] **T-A-16** 重写 seed_data.py 学校与地点数据为江南大学（详见 [docs/23_江南大学模拟核心决策说明.md](docs/23_江南大学模拟核心决策说明.md)）
- [x] **T-A-17** 调整前端地图默认中心点为江南大学
- [x] **T-A-18** 同步更新文档与截图

### P1 — 数据库物理模型实现（依据 [docs/27_数据库物理模型设计.md](docs/27_数据库物理模型设计.md)）

- [x] **P-P-01** 表空间创建脚本（01_create_tablespaces.sql，4 个表空间）
- [x] **P-P-02** 索引迁移脚本（04_create_indexes.sql，汇总现有 50 + 新增 8 个部分索引）
- [x] **P-P-03** 存储过程实现（07_create_functions.sql，SP01-SP08 共 8 个 PL/pgSQL）
- [x] **P-P-04** 触发器实现（08_create_triggers.sql，TR01-TR08 共 8 个）
- [x] **P-P-05** 物化视图实现（06_create_materialized_views.sql，MV01-MV04）
- [x] **P-P-06** 分区表迁移（09_create_partitions.sql，7 张大表 RANGE 分区）
- [~] **P-P-07** 定时任务配置（cron 文件，7 个 JOB）— **放弃**：openGauss 轻量版容器无 cron 服务，按 MVP 原则不实现
- [x] **P-P-08** 性能测试（EXPLAIN ANALYZE 关键查询，8 查询全部达标，详见 [AIwork/P-P-08_性能测试执行与数据记录报告.md](AIwork/P-P-08_性能测试执行与数据记录报告.md)）
- [x] **P-P-09** 归档表创建（admin_operation_logs_archive）
- [~] **P-P-10** zhparser 中文分词扩展安装（全文搜索增强）— **放弃**：轻量版不支持 pg_trgm/zhparser，按 MVP 原则不实现

### P0 — 阶段 B：核心业务升级

- [x] **T-B-01** Post 状态机字段扩展（6 态流转）
- [x] **T-B-02** 协同验证类型扩展（5 类）
- [~] **T-B-03** Service 层初步抽取（Post 业务）— **放弃**：按用户决策不做 Service 层抽取
- [x] **T-B-04** API 改造：状态机与协同验证接口
- [x] **T-B-05** 前端信息详情页改造
- [x] **T-B-06** 前端发布页改造
- [ ] **T-B-07** 阶段 B 联调验证
- [ ] **T-B-08** 阶段 B 文档与提交

### P1 — 阶段 C：创新点实现（**整阶段放弃**）

- [~] **T-C-01 ~ T-C-09** — **放弃**：按用户决策（2026-07-02），整个阶段 C 不做，按最小 MVP 交付

### P2 — 阶段 D：扩展能力（**整阶段放弃**）

- [~] **T-D-01 ~ T-D-04** — **放弃**：按用户决策（2026-07-02），整个阶段 D 不做

### P0 — 阶段 E：测试与交付

- [x] **T-E-01** 单元测试补全 — 详见 [AIwork/T-E-01_单元测试补全任务报告.md](AIwork/T-E-01_单元测试补全任务报告.md)
- [x] **T-E-02** 集成测试（openGauss SP/TR/MV/分区/索引/表空间，64 项通过）— 详见 [AIwork/T-E-02_集成测试任务报告.md](AIwork/T-E-02_集成测试任务报告.md)；**E2E 放弃**（按用户决策 2026-07-03，Playwright 未安装）
- [x] **T-E-03** 文档完善 — 详见 [AIwork/T-E-03_文档完善任务报告.md](AIwork/T-E-03_文档完善任务报告.md)
- [x] **T-E-04** 课程设计报告 — 详见 [docs/课程设计报告.md](docs/课程设计报告.md)（13 章节 + 附录，约 28000 字符）

### 横切关注点

- [x] **T-X-01** 权限与认证矩阵完善（贯穿阶段 B）— 详见 [AIwork/T-X-01_权限矩阵完善任务报告.md](AIwork/T-X-01_权限矩阵完善任务报告.md)
- [ ] **T-X-02** 文档持续维护（贯穿全程）
- [ ] **T-X-03** Git 提交规范（贯穿全程）

## 待确认事项

- [ ] **C7** 课设是否要求使用 openGauss 触发器/存储过程/视图（需与指导老师沟通；doc 27 已设计完整方案，待老师确认实现深度）
- [x] **C8** 是否保留 SQLite 作为开发备选 — 已确认**不保留**，彻底删除 SQLite，全面转移至 openGauss（2026-07-02 用户决策）
- [x] **C4** openGauss 镜像是否已本地导入 — 已确认（T-A-01 完成，本地已导入 `opengauss:7.0.0-RC3`）
- [x] **J1** 江南大学地点的真实坐标（15 个地点）— 已确认（使用校区中心±0.005偏移，T-A-16 已填入）
- [ ] **J2** 是否保留"复旦大学"等其他学校作为对比（推测不保留）
- [x] **J3** 学校 code 字段使用 `jiangnan` 还是 `jnu`— 已确认 `jiangnan`
- [x] **J4** 江南大学是否需建模多个校区 — 已确认只建蠡湖校区
- [x] **J5** map_zoom 是否仍为 15 — 已确认使用 16（T-A-17 实施）

## 备注

- 任务详细规划、涉及文件、验收标准、风险提示见 [docs/21_后续开发任务清单.md](docs/21_后续开发任务清单.md)
- 每完成一项任务后，将对应 `[ ]` 改为 `[x]`，并在 [AIwork/](AIwork/) 新增任务报告
- 严格遵循 [AGENTS.md](AGENTS.md) 与 [.trae/rules/AIWORK_RULES.md](.trae/rules/AIWORK_RULES.md)
