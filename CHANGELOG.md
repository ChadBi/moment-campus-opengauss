# 更新日志

本文件记录"此刻校园"项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> **说明**：自 2026-07-26 起，详细的任务级变更追踪改由 `TODO.md` + `AIwork/` 任务报告维护，本文件仅保留版本级里程碑摘要。

## [2.2.6] - 2026-08-07

### 变更

- `AGENTS.md` 演示账号清单从单行简表扩展为江南大学 + 复旦大学 + 浙江大学完整三校清单，与 `backend/scripts/seed_data.py` 中 `JIANGNAN_USERS` / `FUDAN_USERS` / `ZJU_USERS` 三组常量对齐；标注各校已 `campus_verified=True` 的用户编号，并明确 `@momentcampus.com` 为平台运营专用域名（不受学校 `domain`/`addl_domains` 校验，不参与校园身份认证）
- `backend/tests/manual/` 7 个手动验证脚本（verify_comments / verify_e2e_extra / verify_governance / verify_notifications / verify_profile / verify_subscription_fix / verify_subscription_flow）中 15 处 `login("user1~3@example.com")` 统一替换为 `login("user1~3@example.jiangnan.edu.cn")`，避免使用与 seed 不一致的旧邮箱，7 个脚本 `py_compile` 语法编译全部通过

### 前端

- `Header.tsx`：移除学校切换按钮（桌面端 + 移动端两处 `<SchoolSwitcher />`），简化页头布局并避免切换入口与"一对一绑定"设计割裂
- `MapPage.tsx`：地图地点侧滑面板（`<aside>`）改为评价可点击展开/收起查看完整评价列表；内嵌评分表单（5 星点击 + 500 字可选正文 + 提交/撤回 + 未认证 `VerifyGate` 门禁）；打开面板时并行拉取 reviews + my_review + detail；提交/撤回后自动回写 `avg_score` / `rating_count` / `review_count`；与 `LocationPage` 表现一致；**评分表单常态防误触**：已有评价时常态只显示我已提交的只读摘要卡片 + 「更新评价」按钮，点击后才展开星星编辑器 + 文本框 + 撤回/取消编辑/更新按钮，避免常态裸露编辑器误点；**布局紧凑化**：常态卡片从「外层 border + 内层 bg-mist 嵌套 + 标题/按钮两行」重构为「单层 border 卡片，标题与更新按钮同排 + 我/认证/星级/评分横向 1px 竖线合并 + 正文直接平铺」，padding p-3 → p-2.5；**未评价/编辑态与常态彻底统一**：主按钮（提交/更新）移到顶行右侧与标题同排对齐，仅次按钮（取消编辑/撤回）放在底部，主按钮统一 h-8 px-3 text-[11px] rounded-[8px]
- `LocationPage.tsx`：在地点列表容器上方新增搜索框（bg-paper 卡片 + Search 图标 + 一键清除），前端按「名称/描述/楼栋/楼层」四字段过滤，无匹配时 EmptyState 友好提示；评分表单**常态防误触**同步改：已有评价时常态只读摘要卡片 + 「更新评价」按钮展开编辑态；新增 `editingReview` 状态，提交/撤回/关闭详情/取消编辑 后自动重置为 false；**布局紧凑化**与 MapPage 同步：常态去掉内层 bg-mist 嵌套卡片，标题与更新按钮同排；padding p-4 → p-3.5；我/认证/星级/评分用 1px 竖线横向合并；**未评价/编辑态与常态彻底统一**：主按钮（提交评价/更新评价）移到顶行右侧与标题同排对齐，仅次按钮（取消编辑/撤回评价）放底部，主按钮统一 h-[34px] px-3.5 text-[12px] rounded-[9px]
- `ProfilePage.tsx`：移除已废弃的 `<SubscriptionsCard />` 订阅模块卡片与对应 import，避免展示不存在的订阅功能造成用户困惑
- `PostForm.tsx`：发布页新增地点交互重做——地点下拉新增独立选项「✚ 新增地点（地图选点，提交后进入核验队列）」（value=`__new__`）；下方虚线边框整块（含新地点名称、地图选点按钮、已选坐标显示）改为「只在选中『新增地点』时才显示」，默认隐藏不再裸露；删除「纬度（GCJ-02）/ 经度（GCJ-02）」两个手填输入框，改为「在地图上选择位置 / 重新选点」按钮统一触发 MapLocationPicker 弹窗；选点后用 2 枚只读 chip 徽章（圆角 8px + 地图图标 + GCJ-02 经纬度保留 4 位小数）展示坐标；未选点时显示虚线占位提示「尚未选点 —— 请点击右上角『在地图上选择位置』完成选点」；validate() 校验改为「新增地点请填写名称 / 请先在地图上选好位置」；submit 创建地点分支的判定从「三件套非空」改为「isNewLocationSelected 且三件套齐备」，与 UI 状态严格对应；同时兼容 MapPage 侧滑发帖面板（variant='panel'）通过 `defaultLocationLat/Lng/Name` 传入的地图点选坐标——这些情况下即使未显式切换下拉，也视为进入「新增地点」模式，虚线 div 自动出现并预填 name + chip 展示坐标；**Bugfix：引入显式 `newLocationMode` 状态**，解决「下拉选新增地点但字段为空时立刻跳回空值显示，像选不中」的受控值回退问题；`handleLocationSelect`、草稿恢复（handleRestoreDraft）、切校清理、编辑模式回读（getPost）四处同步维护该状态
- `index.css` + 全站 `<select>`：**全局原生 select 外框统一美化**——新增两档通用工具类 `.select-nice`（40px / 圆角 10px / 纸面白底 / 内嵌 SVG ChevronDown 替换默认箭头 / 湖蓝 focus ring / hover 边框加深 / disabled 灰显）与 `.select-nice-sm`（紧凑 36px / 圆角 8px，供 admin 列表筛选）；覆盖 PostForm 2 处（地点/失物类型）、LocationPage 1 处、SearchPage 筛选区 3 处、admin 后台 8 处（ActivationFunnel / AdminLogs / AdminTopics / Analytics / PlatformOverview / PlatformPlans 3 / PlatformSchools / SchoolImport）共 14+ 原生 select；**明确放弃自定义展开面板方案**（因原生 `<option>` 弹窗由 OS 渲染，CSS 无法覆盖，经评估改造成本与收益不匹配后回滚，仅保留外框美化）
- `routes.tsx` + `Sidebar.tsx` + `MobileNav.tsx`：**地图升级为主页**——导航顺序从「首页→地图→地点…」改为「地图→首页→地点…」；默认路由 `/` 改为 `<Navigate to="/map" replace />` 重定向，原 HomePage 改挂 `/home`；Sidebar 顶部 Logo 方块 `to="/map"`（不再 `/`）；`commonRouteLoaders` 预加载顺序 `loadMapPage` 移至首位（用户最常打开的页面优先准备）
- `Header.tsx`：**页头新增当前学校名称徽章**——Logo「此刻校园」右侧新增 ≥sm 可见的学校徽章（`School` 图标 + 校名，`bg-lake/8` 浅湖蓝底胶囊 + `text-lake` 湖蓝字 + 1px 湖蓝描边）；数据取自 `useCampusStore().currentSchoolName`，未选校/游客态 `&&` 短路不渲染；避免旧 `<SchoolSwitcher />` 移除后用户「不知道自己在看哪个学校」的上下文缺失问题
- `PostDetailPage.tsx`：**修复点击证实/证伪后整页闪一下的感知 Bug**——原 `handleValidate()` 成功后 `void loadPost(true)` 会在 `loadPost` 里触发 `setLoading(true)`，进而命中 L391 `if (loading) return <LoadingState />` 整页骨架屏 Early Return，用户感知为「页面重新加载」；修复方案：给 `loadPost()` 新增第 2 参 `silent=false`（为 true 时跳过 `setLoading` 切换），`handleValidate()` 改为 `loadPost(true, true)` 静默刷新 governance 数据；首屏加载 / ErrorState onRetry 仍保持 `silent=false`（需显示骨架屏加载态）

## [2.2.5] - 2026-08-06

### 修复

- `alembic`：消除重复 revision（`a1b2c3d4e5f6` 在两处迁移同时使用），把 `unify_edu_email_drop_campus_fields.py` 的 revision 改为 `m1n2o3p4q5r6`，并新增 `n2o3p4q5r6s7_merge_drop_publisher_and_location_knowledge.py` 作为唯一 merge head，`alembic heads` 输出单 head
- `location_summary`：修复 `GET /api/v1/locations/{id}/summary` 手动录入简化格式触发的 500 错误；新增 `_normalize_claim()` / `_normalize_conflict()` 兼容简化 `{type,value,confidence,sources}` 与原生 `{claim_id,text,confidence_level,source_refs}` 两种 claim 结构；`load_summary_sources()` 对 `source_refs_json` 中缺失 `source_type` / `source_id` 的引用做合法性过滤，避免 `KeyError: 'source_type'`
- `CORS`：在 `app/config.py` 与 `.env.opengauss` 中补充 `http://127.0.0.1:5173/5174/5175` 允许源，修复前端使用 `127.0.0.1` 访问时的跨域预检失败

### 测试

- 新增 `tests/test_location_summary_flow.py` 8 项地点摘要主链路集成测试（Scenario A~H：生成待审、批准回写、驳回、证据不足、跨租户隔离、冲突、来源哈希去重、管理员刷新标记）
- 全量 `pytest tests/ -v` 拆分为 auth/users/schools/posts/location/others 5 批次在本地环境依次执行，合计约 1021 项全部通过；原 10 分钟单次窗口超时问题在分批策略下解除
- Web 7 步真实 E2E（browser_use + integrated_browser）7/7 通过：登录、管理员跳转后台、地图渲染、图书馆 AI「此刻摘要」展示、网络层无 4xx/5xx + API 返回 `approved`、管理员审核队列空状态、普通用户登录后摘要可见

### 验证

- 小程序 wechatide-skill：`check_wechatide_status` 通过（登录未过期），`simulator_refresh` 编译通过，`simulator_open_page` 成功导航 `pages/map/map` 与 `subpackages/pages/locations/locations?id=5`；静态走查确认 `locations.wxml:117-133` / `locations.ts:129` / `locations.wxss:268-335` AI 摘要板块完整接入

## [2.2.4] - 2026-08-06

### 变更

- 新增 AI 地点摘要实施方案中文任务报告，真实记录专项测试、全量测试超时、Alembic 图和 E2E 阻塞
- 更新 `TODO.md` 验收状态，区分已通过的 Web/小程序静态门禁与待完成的全量回归/真实试点

## [2.2.3] - 2026-08-06

### 变更

- 清理新手引导中的旧 `handleGoNearby` 命名，并将历史 TODO 方案明确标注为已废弃
- 将附近回归测试改为接口不可访问边界测试，演示检查脚本改用有效的最近发布排序

## [2.2.0] - 2026-08-06

### 新增

- `location_knowledge`：地点稳定资料提议、管理员审核、AI 地点摘要版本、来源卡片和摘要审核接口
- `location_summary_worker`：按来源快照异步生成待审核摘要，失败时保留最近一次已批准版本
- Web/小程序地点详情展示稳定资料、AI“此刻摘要”、冲突与证据不足状态，并提供认证用户资料提议入口

### 变更

- 地点摘要引入 7 天动态帖子、30 天评价、双用户证据门槛、虚构来源拒绝和服务端可信层级计算
- 删除实时定位、距离字段、Haversine/`/locations/nearby` 和 `nearest` 产品入口，保留静态校园地图与地点坐标
- 重写评委反馈文档为六部分 AI 地点摘要内部实施方案，并标注历史方案废弃口径

## [2.2.1] - 2026-08-06

### 修复

- `Location.current_summary_id` 外键改为 `use_alter`，解除地点与摘要版本的循环依赖，避免 openGauss 测试清理时先删学校导致外键错误

### 运维

- 新增地点摘要 worker 的 systemd service/timer，并接入安装、更新和混合部署脚本

## [2.2.2] - 2026-08-06

### 测试

- 新增地点资料提议审核、摘要证据门槛、虚构来源拒绝和来源快照稳定性测试；专项测试 5 项通过
- 修正摘要来源归一化逻辑，证据不足的结论不会把来源计入公开来源集合

## [2.1.12] - 2026-08-06

### 变更

- `auth` **统一教育邮箱**：登录邮箱 = 教育邮箱 = 认证邮箱（同一字段 `email`），消除"登录邮箱 ≠ 认证邮箱"的割裂体验。删除 `users.campus_email`、`users.student_id` 字段（Alembic 迁移 `a1b2c3d4e5f6`），认证改为向当前登录邮箱发码验证，无需单独提交学号/认证邮箱
- `auth` 校园认证接口收敛：`POST /users/me/verify-campus/send` 去掉 `student_id`/`campus_email` 入参，直接用登录邮箱校验域名并发码；`confirm` 同理仅需 `token`/`code`
- `auth` 演示账号改为教育邮箱并加 example 域名：`user1@example.jiangnan.edu.cn`（fudan→`example.fudan.edu.cn`、zju→`example.zju.edu.cn`），各校 `addl_domains` 追加 example 域使演示账号能过域名校验但 example 域不会真实发邮
- `web` 注册页收窄为教育邮箱：邮箱域名须命中目标学校允许域名，否则提示"请使用学校官方邮箱注册"；`CampusVerifyCard` 移除学号输入框，认证邮箱只读展示当前登录邮箱
- `miniprogram` 我的页校园认证 UI 收敛：移除学号/校园邮箱输入框，改为只读展示登录邮箱 + "向我的邮箱发送验证码"，与 Web 端一致；注册模式邮箱保持选填（微信首登可先建号，认证时要求教育邮箱）

## [2.1.11] - 2026-08-06

### 移除

- `miniprogram` 从 `app.json` 路由注册中移除 `pages/topics/topics` 与分包 `topic-detail/topic-detail` 两个专题页；同步删除首页 `home.wxml` 专题入口按钮与对应样式、`goToTopics` 方法，满足用户"早就说已经删除了专题和收藏功能"的要求（订阅管理 bookmark 图标属正常订阅功能，予以保留）

### 变更

- `miniprogram(tabbar)` 底部 tabBar 由原生样式升级为自定义 `custom-tab-bar` 组件：深湖蓝浮动胶囊底色 + 毛玻璃 backdrop-filter + 柔阴影 + 安全区适配，发布按钮高亮为橙色圆形主操作；五个 tab 页 `onShow` 时同步 selected 索引修复高亮不同步
- `miniprogram(avatar)` 新增 `resolveAvatar()` 与 `defaultAvatar()` 默认头像工具，使用内联 SVG data:image（蓝灰渐变圆形 + 白色人形剪影）替代不存在的 `/assets/default-avatar.png`；覆盖 `post-card`、`profile`、`post-detail`、`search` 四页的作者/评论作者头像显示

## [2.1.10] - 2026-08-06

### 新增

- `map` 地图页统一地点数据源：发帖地点与评分地点同为 `locations` 表，地图页只渲染「带评分的地点标记」，移除「附近」按钮与帖子标记（小水滴），信息全部集成在每个地点上——点击地点打开面板展示评分/描述/楼层与相关帖子（`GET /posts?location_id=`）
- `miniprogram` 小程序正式版 M2 功能完善：新增 `components/empty-state`、`components/skeleton` 空态/骨架屏组件；新增 `utils/auth-guard.ts`（`requireLogin` 写操作引导 + `guardPageLogin` 页面守卫）；新增 `subpackages/pages/about` 关于页（品牌展示、版本号、检查更新）；`subpackages/sub-pages.json` 分包 5 个低频页面
- `miniprogram` 小程序正式版 M3 性能优化：`components/post-card` 图片 `lazy-load`；新增 `utils/cache.ts` 按 schoolCode 分区 10 分钟缓存；`app.ts` 启动时 auth/campus store 首屏预恢复
- `miniprogram` 小程序正式版 M4 兼容性：`app.wxss` iOS 安全区 `.safe-bottom-*` 适配；老基础库 `wx.getUpdateManager` 类型保护
- `miniprogram` 小程序正式版 M5 安全加固：上传前 5MB 大小 + jpg/png/gif 格式 + 5 张数三重预检；Token 存储用 `wx.setStorageSync` 隔离沙盒 + 请求日志脱敏；发布二次确认；举报 6 种 Reason 枚举对齐后端 enums
- `miniprogram` 小程序正式版 Task 14 测试脚本：新增 `scripts/test-format.mjs` formatCount/truncateText/formatDate/getRemainingTime 单测；`typings/global.d.ts` 补齐 `URLSearchParams` 类型声明
- `feedback` 用户反馈模块（前后端）：后端 `feedback.py` 路由 + `feedback` 模型 + schema + Alembic 迁移 `f4b5c6d7a8b9_fdb_01_feedbacks.py`；前端 `AdminFeedbackPage.tsx` 管理端处理页；小程序 `services/feedback.ts`
- `miniprogram` 小程序分包：`miniprogram/subpackages/pages/about/about.*` 关于页 4 件套

### 变更

- `map` 增强 `GET /locations` 返回评分汇总（avg_score/rating_count/review_count/post_count），前端新增 `locationsApi.getLocations()` 复用，地图页与地点页共用同一份地点数据
- `rev` 地点页（/locations）移除定位按钮、半径筛选与距离显示，改为展示学校全部地点（看评分做选择）
- `home` 移除首页「附近好去处」区块，不再显示「几公里内」与距离
- `auth` 为江南大学补充允许的校园邮箱域名 `stu.jiangnan.edu.cn`（seed 支持 `addl_domains` 多域名写入），使 `@stu.jiangnan.edu.cn` 教育邮箱可通过校园身份认证
- `auth` 配置 QQ 邮箱 SMTP（smtp.qq.com:465，授权码存 `.env.opengauss` 不进 Git），实测向 `1030424433@stu.jiangnan.edu.cn` 成功发送验证邮件
- `miniprogram(app)` `app.ts` 移除 `onLaunch/onShow` 强制登录跳转，游客可直接浏览首页/地图/搜索/详情/专题/地点
- `miniprogram(request)` `services/request.ts` 401 分支分场景处理：游客场景（无 refreshToken）401 只抛异常不 `reLaunch` 跳登录，由页面调用方 `try/catch` 静默；登录过期场景才清 Token 并跳转
- `miniprogram(publish)` `pages/publish/publish.ts` 新增 `onShow` 守卫（`guardPageLogin('请先登录后再发布帖子')`），避免游客填半天表单才发现不能发布
- `miniprogram(auth)` 登录页新增「以游客身份继续浏览」链接入口
- `miniprogram(upload)` `services/upload.ts` 上传 URL 从硬编码 `http://localhost:8000/api/v1/uploads` 改为 `${BASE_URL}/upload/image` 与后端路由一致
- `miniprogram(ts)` `typings/types/wx/lib.wx.app.d.ts` 修复 `GetApp<T>` 泛型约束：由 `<T = IAnyObject>` 改为 `<T extends IAnyObject = IAnyObject>`，解决 TypeScript 编译错误
- `miniprogram(notifications)` `pages/notifications` onShow `guardPageLogin('请先登录后查看通知')` 守卫生效
- `miniprogram(profile)` `pages/profile` onShow 守卫生效 + 关于页入口
- `miniprogram(post-detail)` 点赞/验证/举报/评论 4 种写操作统一 `requireLogin(具体文案)`，双按钮（再看看 / 去登录）给用户选择权

## [2.1.9] - 2026-08-06

### 新增

- `UC-01` 用户-学校严格一对一绑定：`school_memberships` 新增部分唯一索引 `idx_membership_user_active`，一个用户同一时刻只能有 1 个 active membership；`POST /schools/join` 语义升级为"切校"（leave old + join new 原子操作）；super_admin 保留跨校静默切换特权（platform 管理需要）
- `UC-02` 教育邮箱验证系统：后端 `email_service.py` 接入 SMTP（SSL，支持 `smtp.qq.com` 等主流服务商，授权码经环境变量 `SMTP_*` 注入）；`school_domains` 后台管理端点（`GET/PUT/POST /admin/school-domains`）支持管理员配置学校邮箱后缀；`/verify-campus/send` 返回 `verify_link` 供 SMTP 未配置时的 dev 模式使用；verify 凭据支持双通道（6 位验证码或 24 位 token 哈希），token 落地页 `/verify-campus?token=xxx` 自动跳转个人中心完成认证
- `UC-03` 学校切换功能：个人中心新增"切换学校"浮窗 `SwitchSchoolModal`（搜索学校→后果确认→执行切换）；切校后 `school_switch.py` 原子执行：原校 membership 置 inactive + 新校 membership 建/激活 + 重置 `campus_verified=false` + 清空 student_id/campus_email + 将原校 posts/comments/location_reviews 匿名化为「已离校用户」；SchoolSwitcher 普通用户选择未加入学校时打开切换浮窗
- `D-04` 地点页面与地图整合：`MapPage` 地图地点标记（MAP_LOCATION_LAYER_ID）点击弹出地点侧面板，展示地点名称/类别/评分/评价数/距离，并并行拉取该地点相关帖子（`GET /posts?location_id=`，最多 5 条），可跳转地点详情页；保留 `/locations` 独立页面并支持深链 `?location={id}` 自动打开对应地点详情
- `D4-gate` 未认证用户只读门禁：后端所有写入端点（发帖/评论/点赞/证实/证伪/举报/评分/订阅/回复）统一加 `require_campus_verified()` 依赖，返回 403；前端 `VerifyGate` 组件提供大卡/紧凑两种门禁模式；发布页/评论区/评分区均由 VerifyGate 包裹；PostDetailPage 点赞/协同验证/举报/回复按钮仅对已认证用户渲染；未认证已登录用户有明显"去认证"引导
- `UX` 认证链接落地页 `/verify-campus`：读取 URL `token` 参数存 sessionStorage 后重定向个人中心，CampusVerifyCard 自动读取 token 完成确认

### 变更

- `perf(ui)` 修复 PostDetailPage 未认证已登录用户可见点赞/协同验证/举报/回复按钮的遗漏（补充 `canInteract = isAuthenticated && campusVerified` 判断）
- `fix(schema)` CampusVerifyConfirmRequest.code 字段长度由 6 放宽到 128，以支持 24 位 token 凭据（此前 token 提交返回 422）
- `test` 测试 fixture 全面适配 UC-01 一对一约束：普通用户仅保留 1 个 active membership（通过 super_admin 测试多校场景）；默认 fixture 用户标记 `campus_verified=True`（D4 门禁默认放行，未认证场景由 `test_campus_gate.py` 专项覆盖）
- `test` 新增 `test_campus_gate.py` 覆盖未认证写入 403 场景
- `fix(ui)` LocationPage 挂载 effect 读取 useCallback 定义的 openDetail 顺序导致的 `react-hooks/immutability` 警告，将 effect 移到 openDetail 定义之后；set-state-in-effect 警告统一用 `Promise.resolve().then(...)` 包裹
- `chore(config)` config.py 新增 SMTP 配置字段（SMTP_HOST/PORT/USER/PASSWORD/USE_SSL/FROM_EMAIL/FROM_NAME）+ APP_BASE_URL 用于构造 verify_link

## [2.1.8] - 2026-08-06

### 新增

- `auth` 新增校园身份认证能力（B-01/B-02）：`User` 增 campus_verified/student_id/campus_email/campus_verified_at；新建 `campus_verify_tokens` 表（一次性、限时、哈希存储）；`POST /users/me/verify-campus/send` 提交学号+校园邮箱并校验域名命中 `school_domains`，`POST /users/me/verify-campus/confirm` 校验验证码后置为已认证；`GET /users/me` 返回 campus_verified
- `auth` 帖子/评论/评价作者信息（author）新增 `is_verified` 认证标识（B-03），前端可据此展示「已认证」徽标
- `auth` 前端 Web 校园身份认证（B-05）：新增 `VerifiedBadge` 已认证徽标组件与 `CampusVerifyCard` 认证流程卡片（学号+校园邮箱发送验证码→确认认证，dev 环境直接展示验证码）；个人中心接入认证入口，帖子/评论区作者昵称旁展示「已认证」徽标
- `rev` 小程序校园地点页（A-07）：新增 `pages/locations/locations`（附近地点列表按距离+半径筛选+星星评分；详情弹层含评分汇总/我的评价/全部评价，登录后可提交/更新/撤回评价）；地图页新增「帖子/附近」模式切换，附近地点渲染为带评分的 marker 并可跳详情；首页新增「校园地点·附近评分」入口；封装 `services/locations.ts`
- `auth` 小程序校园身份认证（B-06）：`pages/profile` 新增认证卡片（学号+校园邮箱发送验证码→确认认证，dev 展示验证码，成功切已认证态）；post-card / post-detail（帖子与评论）/ search / topic-detail 作者昵称旁「已认证」徽标；`services/auth.ts` 封装 send/confirm；is_verified 字段归一化对齐后端嵌套 author
- `seed` 演示数据 seed 支持校园认证域名（B-01）：为三校写入 `school_domains`（jiangnan.edu.cn / fudan.edu.cn / zju.edu.cn）
- `seed` 演示数据为部分用户标记校园身份认证（B-07）：`seed_users` 依据用户清单 `campus_verified` 标记，为已认证用户写入 campus_email（学校域名）/student_id/campus_verified_at，使前端与小程序展示「已认证」徽标（江南 8/10、复旦 3/5、浙大 3/5）
- `miniprogram` 小程序 API 指向公网 HTTPS（C-01）：`services/request.ts` API_HOST 设为 `https://campus.chaina1.com`，`resolveImageUrl` 统一把 `/uploads/` 相对路径解析到生产域名
- `docs` 新增小程序上线落地指引（C-02）：`docs/36_微信小程序上线落地指引.md` 覆盖合法域名配置、隐私保护指引、体验版发布与体验成员管理流程
- `docs` 定位与叙事打磨（D-01/D-02/D-03）：`00_project_overview` 新增「差异化优势（为什么学生会持续用）」三壁垒并更新产品边界；复赛方案 32/33 补充认证/附近评分/小程序已完成能力与证据；Demo作品帖、视频脚本、社媒文案同步补充附近探索/设施评分/校园认证/小程序场景
- `ui` 新用户引导突出附近/评分/认证价值（D-04）：`FirstUseGuide.tsx` 第 3 步改为「三步开启校园生活」价值入口，可直达附近地点与校园认证页面
- `test` 同步 AI 混合排序权重测试断言（Q-01）：`test_t7_vector_search.py` 断言由过时权重 0.35/0.25/0.20/0.20 改为与实现一致的 0.5/0.15/0.15/0.20（期望分 0.825）
- `fix(ui)` 消除 `LocationPage.tsx` set-state-in-effect lint warning（Q-02），使 `npm run lint` 零错误零警告
- `fix(ops)` E2E 走查发现 `school_domains` 表为空导致「校园邮箱域名不匹配」（Q-03）：重新执行 `seed_data.py` 填充三校域名与 `campus_verified` 标记后，地点评分/地图附近/校园认证/作者徽标链路全部验证通过

## [2.1.7] - 2026-08-05

### 新增

- `rev` 新增地点评分/评价能力（REV-01）：`location_reviews` 表 + `locations` 评分汇总字段（avg_score/rating_count/review_count），每地点每用户一条可改可撤回
- `rev` 新增地点 API（`/locations`）：地点详情含评分汇总与"我的评价"、评价提交/更新/撤回、评价分页列表
- `rev` 新增"附近地点"接口 `GET /locations/nearby`：Haversine 距离升序 + 半径过滤 + 距离字段，多租户隔离
- `rev` 作者简明信息（UserBrief）新增 `is_verified` 认证标识字段
- `rev` 前端 Web 新增校园地点页 `/locations`（A-05）：附近地点列表（GPS/校园中心定位 + 半径筛选 + 距离与评分展示）+ 详情 Modal（评分汇总、评价列表、提交/更新/撤回评价），侧边栏新增「地点」入口
- `rev` 前端 Web 地图页新增「附近」模式（A-06）：切换后渲染带评分徽标的地点标记（水滴内显 avg_score，未评分显「新」），点击弹出地点侧滑面板（评分/距离/评价数 + 跳转评价页），学校切换自动重拉；首页新增「附近好去处」区块（定位 + 评分卡片横向滚动 + 查看全部）
- `rev` 演示数据 seed 新增地点评分/评价（A-08）：`seed_location_reviews` 按地点类型差异化评分倾向生成真实感评价，回写 avg_score/rating_count/review_count；实测生成 157 条评价覆盖 39 地点

### 变更

- `ai` 移除 AI 发布建议校验中 `summary` 必填约束，避免模型未生成摘要时校验失败
- `deploy` 新增华为云 Nginx 部署配置 `deploy/nginx-moment.conf`：HTTP→HTTPS 跳转、Gzip 预压缩、静态资源永久缓存、SPA 路由与 API 代理

## [2.1.6] - 2026-08-03

### 新增

- `video` 为 13 段旁白逐段配置独立情感指令（instruction）：痛点段紧迫、产品段沉稳、个人故事温暖感性、参赛宣言深情坚定，SDK 与 REST API 双通道均已接入
- `video` 新增社媒发布文案：适配哔哩哔哩、抖音、小红书三平台，含标题、正文、标签及发布策略建议；抖音标题以「VibeCoding大赏」开头，30字以内
- `video` 个人介绍视频旁白脚本全量改造：移除所有真人实拍要求，统一改为 AI 生图 + AI 视频 + 模拟截图 + 产品录屏，附 AI 生图提示词方向和完整素材清单
- `video` 作品演示视频旁白脚本新增"后台管理系统"段落（3:35-4:05）：数据总览、审核队列、数据分析、定时任务、操作日志录屏展示；TTS 脚本同步新增 demo_07_admin 段并更新全部段 ID；总时长从 4:10 延长至 4:45

### 变更

- `video` 修正 Qwen-Audio-3.0-TTS-Plus 旁白生成方案：脚本从纯 REST API 改为 DashScope SDK（WebSocket）优先 + REST API 回退双模式；修复中文引号导致 Python 语法错误；更新方案文档补充模型能力、指令控制、地域限制等信息

## [2.1.5] - 2026-08-02

### 变更

- `post` 修复新建帖子选择信息截止时间报错：前端 UTC 时区 ISO 字符串被 Pydantic 解析为带时区 datetime，asyncpg 无法插入 `TIMESTAMP WITHOUT TIME ZONE` 列；`PostCreate` 和 `PostUpdate` 的 `expire_at` 字段添加 `field_validator` 统一转为北京时间 naive datetime
- `ai_search` 混合排序权重调整：语义相似度 35% → **50%**，新鲜度 25% → 15%，验证数 20% → 15%，关键词相关度保持 20%（提升语义/向量检索主导地位）

## [2.1.4] - 2026-08-02

### 仓库全面整理与优化

- 全量梳理仓库文件：移除误提交的小程序 AI 工具链产物（`miniprogram/.ai-mode-skills/`、`miniprogram/cli-agent-run/`）、一次性图标生成脚本 `miniprogram/components/icon/._gen.cjs`、含硬编码 JWT 的调试脚本 `AIwork/全链路API校验脚本.ps1`
- 解除跟踪（文件保留本地）：`miniprogram/project.private.config.json`（微信开发者工具私有配置）、`frontend/.env.development`
- `.gitignore` 新增规则：微信开发者工具私有配置、小程序 AI 工具链产物目录、`AIwork/*.ps1`，防止同类文件再次误提交
- 决策：**不重写 Git 历史**（历史上已删除的 E2E 截图等旧文件保留，总量约 1.15MB）
- 验证：前端 `npm run build` 通过；后端全量 `pytest` 983 passed（openGauss 环境，14min24s）

### 测试数据规模扩充：每校 500 帖 + 50 用户程序化生成

- 新增 `backend/scripts/generate_bulk_data.py`：程序化生成全新演示数据（清空现有数据后填充），复用 seed_data.py 的清库/学校/分类/地点/套餐基础设施
- 规模：每校 50 活跃用户（1 管理员 + 49 普通用户，含现有演示账号）、500 条有效帖子（published）+ 5 条 6 态样本
- 互动数据基于真实校园社区量级（幂律分布）：浏览数按热度分层（热门 5% / 中等 60% / 冷门 35%），点赞率 6%~15%，点赞:评论 ≈ 6:1，所有帖子 ≥1 条主题相关评论
- 真实填充 `likes` 表：帖子 `like_count` 与实际 `Like` 记录严格一致（此前 likes 表从未填充）
- 用户-帖子-评论-验证关联同校准确：跨校关联数为 0；帖子计数与明细 1500/1500 一致
- 已回填 1515 条帖子 embedding（512 维，0 失败）；后端关键测试 55 passed
- 生成方式：`$env:APP_ENV="opengauss"; python scripts/generate_bulk_data.py`（含清库），随后 `python scripts/generate_embeddings.py --batch-size 50`

### 华为云 v2.1.4 全量部署

- 全量部署 v2.1.4 到华为云 `campus.chaina1.com`：关停 `moment-backend` → 上传后端代码与前端 dist → 重置测试库（DROP/CREATE `moment_campus`）→ `alembic upgrade head`（head=`d5e6f7a8b9c1`）→ 大数据集填充（三校各 505 帖 / 50 用户，1515 帖 embedding 全部回填）
- 修复部署阻断 Bug：`alembic/versions/d5e6f7a8b9c1_remove_invitation_codes.py` 缺少 `from typing import Union` 导入导致 alembic 加载版本文件失败
- 服务器 `deploy/.env.prod` 与 `backend/.env.prod`/`.env.opengauss` 更新（新增 `EMBEDDING_*` 配置）；AI/Embedding Key 仅经服务器端内存注入，未落文档
- 验证：`/health`=ok、admin 登录、HTTPS 首页与 API、MCP 浏览器端到端 7 项全部 PASS

## [2.1.3] - 2026-08-02

### 修复：注册完成后进入系统误报"无该学校访问权限，已切换回 xxx"

- 现象：游客态浏览过其他学校（URL/store 残留如 `?school=fudan`）后再注册新账号，注册成功后进入系统弹出"您没有该学校的访问权限，已切换回 江南大学"
- 根因 1：注册成功后仅 `setCurrentSchool` 同步 store，URL 仍残留旧学校值，`useSchoolSync` 的 URL 监听器读到旧值反向覆盖当前学校，最终 `ensureValidSchool` 回退并弹提示
- 根因 2：`useSchoolSync` 登录态 effect 用 effect 闭包捕获的 `currentSchoolCode` 作为回退前后对比基准，注册瞬间存在渲染竞态，未真正回退也会误弹提示
- 修复：注册成功后立即同步改写 URL 的 `school` 参数（与 store 同一批次）；回退对比基准改为读取实时 store 值
- 验证：`npm run build` 通过；浏览器多次注册实测无权限提示消除

## [2.1.2] - 2026-08-02

### 修复：学校切换器加入新学校后误报"无该学校访问权限"

- 现象：注册单校账号后，通过页头学校切换器选择未加入学校时提示"您没有该学校的访问权限"，无法切换
- 根因：切换流程先调用 `joinSchool`（后端已创建 membership），但未刷新前端 store 的 memberships，随后 `useSwitchSchool` 用过期数据校验权限导致误拦截
- 修复：`SchoolSwitcher.handleSelect` 在 join 成功后重新拉取 `me/memberships` 并更新 store，再执行切换
- 验证：浏览器实测单校账号切换其他学校成功（申请加入 + 切换 + 学校上下文生效）；`npm run build` 通过

## [2.1.1] - 2026-08-02

### 删除邀请码 + 注册时自由选择学校

- 用户决策（2026-08-01）：注册不再需要邀请码，初始加入的学校由用户注册时下拉选择（不再默认绑定江南大学）
- 后端：删除 `SchoolInvitation` 模型与 `school_invitations` 表（迁移 `d5e6f7a8b9c1`），`register` 端点改为 `body.school_id` 优先、`X-School-Code` 头回退，注册成功自动创建所选学校 active membership（is_default=true）；`join` 端点移除邀请码校验直接加入；平台创建学校不再生成管理员邀请
- 前端：注册页移除邀请码输入框，新增"选择加入的学校"下拉（公开学校目录）；登录页移除邀请码消费逻辑；`schools.joinSchool` 移除邀请码参数
- 小程序：`emailRegister` 移除 `invite_code` 参数
- 测试：删除 9 个邀请码相关用例，新增注册无学校 400 / X-School-Code 回退 / body 优先用例；后端全量 `pytest` 983 passed
- 端到端验证：浏览器实测选择复旦大学注册 → 自动登录 → 首页学校上下文为复旦大学，全链路通过

## [2.1.0] - 2026-08-01

### 最终归档（v2.1.0）

- 遗留后端配套补齐：`GET /api/v1/search/hot-tags` 热门标签接口、`permissions.py` 协同验证端点注释对齐、`interaction.py` ValidationCreate/ValidationResponse 收敛为 2 类枚举（含 action/counts 字段）
- 新增微信身份体系迁移 `0898a6eeb570`：`user_auth_identities` / `auth_sessions` / `binding_tickets` 三表，支持小程序登录与邮箱密码多身份绑定
- `README.md`、`Demo 作品帖`、`AGENTS.md` 全量校对：协同验证收敛 2 类、自动过期定时器、DataVec 512 维混合检索、测试覆盖 987 后端 / 38 前端 E2E
- `docs/` 与 `docs/design/` 系统校对：34 份文档 + 7 份 ER 图 + 数据库表结构 xlsx 与现行契约对齐（6 态状态机、2 类验证、openGauss 7.0、三校多租户）
- `AIwork/` 归档 20+ 份任务报告与校验脚本（复赛冲刺 Web 完善、T7 向量检索、自动过期、Analytics 清理、pytest 治理、小程序 AI-Skills 等）
- 至此完成 v2.0.1 → v2.1.0 共 9 批次归档提交

## [2.0.8] - 2026-08-01

### 运维 SQL 与部署脚本收敛

- openGauss 运维 SQL 与现行数据库契约对齐：索引、物化视图、函数、触发器、分区、表空间、性能测试脚本全面修订
- 新增 `test_opengauss_sql_contract` 契约测试，校验 SQL 文件与迁移/ORM 模型一致性
- `deploy/` 安装/更新/混合部署脚本补充自动过期 systemd 单元安装与定时器启用
- 后端系统层修复与加固：auth 限流、upload 安全、db_compat 兼容补丁、main 启动收敛、`verify_data`/`generate_full_report` 数据校验脚本重构

## [2.0.7] - 2026-08-01

### 小程序 AI-Skills 校验与配置

- 新增 `miniprogram/skills/moment-campus`：14 个原子接口（listPosts/createPost/aiSearch/searchPosts/validatePost 等）+ request 工具 + mcp.json + SKILL.md，符合 `wx.modelContext` 规范
- `project.config.json` 开启 urlCheck=false、packOptions 纳入 skills 目录；`project.private.config.json` 关闭 urlCheck
- 归档小程序 AI 校验产物：`.ai-mode-skills/`（鉴权规范与探测）与 `cli-agent-run/`（运行报告与验证结果）

## [2.0.6] - 2026-08-01

### 后端 pytest 警告治理与测试清理

- 全量消除 `-W error` 下的 DeprecationWarning 等告警：`datetime.utcnow` 弃用、pytest-asyncio 等，新增 `test_deprecation_cleanup` 契约防回潮
- 移除已废弃的 `tests/integration/` 集成测试目录（tablespaces/indexes/materialized_views/partitions/stored_procedures/triggers 共 6 个测试 + conftest），高级 SQL 对象改由 SQL 契约测试覆盖
- 修复 / 同步 12 个既有测试文件（ai_publish、ai_search、config、posts、publish_flow、rel02、schemas、search、tenant_isolation、upload_security、post_detail、post_transition）
- 后端 `pytest tests -q -W error`：987 passed / 0 failed / 0 warnings

## [2.0.5] - 2026-08-01

### 前端统一状态组件与分类视觉

- 新增 `components/state/`（EmptyState / ErrorState / LoadingState / StateLayout）统一异常态与加载态，替换各页面手写占位
- 新增 `GlobalToast` 全局提示与 `utils/categoryVisual.ts`（`category.code` 稳定配色），切换学校时清理旧校分类、筛选值与地图标记
- 全量前端 lint 治理：0 error / 0 warning；`npm run build` 通过
- 新增 Playwright E2E：`state-components`、`admin-category-live-sync`、`validation-and-categories`；同步修复既有 `accessibility` / `business` 用例

## [2.0.4] - 2026-08-01

### T7 向量检索 384→512 维度改造

- Embedding 独立 OpenAI 兼容配置（阿里云百炼 DashScope `compatible-mode/v1`，模型 `qwen3.7-text-embedding`），`EMBEDDING_*` 配置项入 `.env.opengauss.example`；真实密钥仅存本地 `.env.opengauss`（不入库）
- `Post.embedding` 列 `vector(384)` → `vector(512)`：迁移 `b6c7d8e9f0a1`（ALTER 列类型 + 重建 HNSW 索引），配合 `a1b2c3d4e5f6` 历史迁移
- 新增 `app/services/embedding_service.py`（生成/构建 512 维向量文本、超时降级）与 `app/db_types.py` Vector 类型；`scripts/generate_embeddings.py` 回填脚本实测 90 条帖子全部回填成功
- 真实链路验证：同义查询（"打印店在哪里" vs "附近哪里有打印服务"）正确召回同一组打印店帖子；测试环境通过 conftest autouse fixture 完全隔离外部 Embedding 调用（消除代理连接泄漏 ResourceWarning）

## [2.0.3] - 2026-08-01

### 自动过期定时器 30 分钟周期统一

- 统一自动过期任务调度周期为 30 分钟（deploy/bare-metal/moment-expire-posts.service + .timer）
- `expire_posts` job 增强：running 记录超时租约回收（60 分钟），advisory lock 获取失败改为 fail-closed（禁止无锁执行）
- 手动触发/记录查询接口权限收紧为 super_admin 专属（`require_role(Role.SUPER_ADMIN)`）
- 新增 systemd 单元结构测试与过期任务回归测试

## [2.0.2] - 2026-08-01

### Analytics 运行时废弃清理

- 移除 Analytics 服务与接口中对已删除业务表（post_change_reports 等）的残留引用与文档说明
- 前端 AnalyticsPage / analytics.ts 同步移除废弃指标展示
- 新增契约测试 `test_analytics_removed_metrics_contract.py`，防止废弃指标回潮

## [2.0.1] - 2026-08-01

### 变更

- `.gitignore` 修复 `rubbish/` 目录未被正确忽略的问题，移除 17 个已跟踪的回收站文件，仅保留 `rubbish/README.md`
- `.gitignore` 新增部署临时文件忽略规则（`deploy/_*.zip`、`deploy/_*.tar.gz` 等）和 `!.env.opengauss.example` 例外规则
- `docs/` 系统性整理与校对：16 份核心设计文档全面修正，移除 PostType/Tag/Favorite 等已废弃实体引用，更新状态机为 6 态、协同验证为 5 类、数据库统一为 openGauss 7.0
- `AIwork/` 新增 TRAE 复赛项目审查与评分报告、复赛展示帖子、任务报告，完成 R-13 社区作品帖任务
- `AIwork/` 新增复赛待完善清单与评委视角评分，提取 13 项待完善点并制定实现规划，按"看帖/视频"与"实操"两种场景重打分（79.4 vs 68.8）
- `AIwork/` 新增复赛冲刺实施计划（基于用户决策），8 项任务：删除 3 类验证、自动过期、状态组件、分类对齐、租户隔离、测试清理、向量检索、文档更新
- `backend/scripts/test_vector.py` 验证脚本：确认 openGauss 7.0.0-RC3 原生支持 DataVec 向量引擎，无需升级数据库
- `miniprogram/` 修复 WXML 编译错误：`wx:elif`/`wx:else` 不能直接用于自定义组件（empty-state、icon），统一用 `<block>` 包裹；修复 `wx:else` 与 `wx:for` 同元素导致的 `wx:if not found` 错误
- `miniprogram/` 修复 TypeScript ES2020 语法兼容性：将 `?.` 可选链替换为 `obj && obj.prop`、`??` 空值合并替换为三元表达式（home.ts、profile.ts、post-detail.ts、school-select.ts、search.ts、services/request.ts）
- `miniprogram/` 修复 7 个页面 WXML 模板结构（profile、school-select、search、subscriptions、topics、notifications、post-detail），全部通过 `compile_wxml` 验证

### 治理模块清理与协同验证收敛（本批归档）

- 移除治理模块遗留代码：`app/api/governance.py`、`app/schemas/governance.py`、`frontend/src/pages/admin/AdminGovernancePage.tsx`、`frontend/src/services/governance.ts`、`tests/test_governance.py` 及 `router.py` 注册引用
- 协同验证收敛为 2 类（confirmation/refutation）：删除 legacy 别名兼容逻辑（valid/invalid），统计口径只计 confirmation + refutation
- 不允许用户为自己的帖子投票（新增 `ForbiddenException` 校验）
- 验证接口响应新增 `action`（created/removed/switched）、`current_validation_type`、`confirmation_count`/`refutation_count` 字段，切换类型改为原地更新而非删除重建
- 同步更新 enums、post schema、interactions 及 6 个相关测试文件

## \[2.0.0] - 2026-07-29

### 多轮测试问题修复

- 增强 `ProtectedRoute` 组件的 token 有效性检查，防止匿名用户访问 `/publish` 页面
- 修复协同治理报告 API 路径不匹配问题（前端从 `/admin/governance/reports` 改为 `/admin/reports`）
- 为浏览历史接口添加异常处理，防止 500 错误影响用户体验
- 更新 `react-router-dom` 至最新版本以修复已知安全漏洞
- 更新 API 文档，补充当前 19 个路由模块概览
- 更新项目概述文档，反映已实现的多租户/多学校切换功能

### 浏览量与举报表单修复

- 为 `GET /posts/{id}` 添加 `increment_view` 查询参数，防止点赞/评论/回复等操作虚增浏览量
- 重构点赞、评论、回复、验证的前端状态更新逻辑，使用 API 响应本地更新而非重新加载帖子
- 修复举报表单重复提交问题，添加防重复提交守卫
- 修复帖子详情页与列表预览页数据不一致问题

### 前端 E2E 基线维护

- 更新 axe、注册、AI 搜索、跨租户和平台 API 测试以匹配当前依赖与接口，完整 Playwright 恢复为 27 通过 / 1 个已下线能力跳过
- 为发布表单地点与失物类型下拉框补充关联 label，消除 axe `select-name` critical 违规

### AI 发布建议摘要修复

- 修复 `ai-suggest` 已解析摘要却在响应构造时硬编码为 `None` 的缺陷，恢复结构化 `summary` 建议

### MapLibre 原生 Marker 图层重写

- 地图页帖子点由 DOM `maplibregl.Marker` 重写为 GeoJSON source + symbol layer，与高德瓦片共用 WebGL canvas 和投影帧
- 保留水滴几何、分类色、单帖/聚合数量、hover、点击侧栏和深链接，并增加跨学校请求竞态保护
- 新增三校基准相对位移回归：第二食堂、本部食堂、西区食堂与同校其他点在 zoom 14/16/18 下使用同一投影变换；对齐 E2E 5/5 通过

### 地图 GCJ-02 契约与三校坐标校正

- 数据库/API/地图/导入统一使用 GCJ-02，浏览器 WGS-84 定位在前端转换后显示
- 建立三校 39 地点坐标目录，更新种子数据并新增保护式 openGauss 数据迁移
- 修正浙大紫金港中心与地点整体偏东约 4km 的数据问题，新增只读离群审计与目录回归测试

### MapLibre SVG Marker 几何对齐

- 废弃旋转方块与 X+Y 人工补偿，改用尖端位于 SVG 底部中心的无描边水滴路径
- hover 以底部中心为 transform origin，单帖/聚合 Marker 在 hover 与 zoom 14/16/18 下尖端误差均不超过 0.5px
- 新增 Playwright 几何矩阵回归测试，并修正旧报告对零圆角位置的错误推导

### 地图 Marker 尖端 X+Y 补偿修复

- `MapPage.tsx` 修正水滴形 marker 补偿公式：compensator div 从仅 Y 平移 `translate(0, -tipOffset)` 改为 X+Y 同时平移 `translate(-compX, -compY)`，消除视觉尖端相对 anchor:'bottom' 偏右 25px 的问题
- MCP 浏览器验证 3 个缩放级 10+ marker 偏移稳定（S=36 聚合 marker：dx≈7.5/dy≈-3.1；S=28 单帖 marker：dx≈5.8/dy≈-2.4），无 zoom 漂移
- `npm run build` 构建成功

### 地图缩放漂移彻底修复

- `MapPage.tsx` marker 容器添加 `transition: none` 内联样式 + Marker 构造参数 `subpixelPositioning: true`
- `index.css` 新增 `.maplibregl-marker` 与 `.maplibregl-canvas-container` 全局 CSS 覆盖，禁用所有 transition/animation
- `MapLocationPicker.tsx` Picker 组件 Marker 同步添加 `subpixelPositioning: true`
- MCP 浏览器 E2E 验证：13 个 marker 缩放前后位置稳定，39 个 DOM 元素 0 CSS transition 违规

### 阶段四+五：性能优化与质量收尾

- `P2-001` vite.config.ts 添加 manualChunks 拆分 maplibre-gl/react-vendor/icons，MapPage chunk 1043KB→16KB（97% 下降），index.js 307KB→128KB
- `P2-008` MapPage 瓦片源 OSM→高德栅格（4 个 webrd0{1-4}.is.autonavi.com 子域加速），国内可达性提升
- `P2-006` api.ts 401 并发刷新加锁：refreshPromise 单例 promise 复用，避免并发 401 多次消费 refresh\_token
- `P2-007` 新增 utils/logger.ts（dev 打印/prod 静默），48 处 console.\* 替换为 logger.\*（21 个文件）
- `P2-003` SearchPage HOT\_TAGS 改为多租户动态化：useMemo 从当前学校 categories 派生 top 8，fallback 到 FALLBACK\_HOT\_TAGS
- `P3-001` 删除 AdminTagsPage.tsx（602 行死代码）+ 4 个零引用 tag API + 3 个 tag 类型
- `P3-003` 新增 utils/date.ts 4 个函数（formatRelativeTime/formatDate/formatDateTime/formatShortDateTime），15 个文件的本地实现替换为导入
- `P3-004` 删除 3 对重复 API 定义：uploadApi.uploadAvatar / usersApi.getMyPosts / interactionsApi.transitionPost（零引用）
- `P3-006` nginx.conf 生产环境关闭 /docs 与 /openapi.json 对外暴露（return 404）
- `P3-007` CHANGELOG.md 补记阶段一/二/三/四/五全部变更
- `P3-008` docs/ 下 11 个文件 160+ 处 `file:///d:/Project/database-class/...` 旧盘符路径批量替换为相对路径
- `P3-011` frontend/README.md 由 Vite 模板默认文案替换为项目说明

### 阶段三：仓库卫生与部署配置

- `P2-009` 7 个 verify\_\*.py 调试脚本迁移到 backend/tests/manual/（git mv 保留历史），.gitignore 新增 `/verify_*.py` 规则
- `P2-010` 清理 backend/ 76 个 + 根目录 16 个调试脚本/日志（全部已被 .gitignore 覆盖）
- `P2-012` 新增 backend/.dockerignore 与 frontend/.dockerignore，排除 .git/.venv/node\_modules/tests/logs/.env 等
- `P2-011` deploy/.env.prod.example 与 backend/.env.example 同步补齐 9 项 AI\_\* 变量模板；backend/.env.example 修复 SQLite 残留改为 openGauss
- `P2-002` index.html title/description 移除江南大学硬编码，改为多租户通用文案
- `P2-005` ProfilePage 与 AdminDashboard 的 handleLogout 改为先 await authApi.logout() 后清本地 state

### 阶段二：多租户与代码质量

- `P1-002` MapPage 接入 useCampusStore 学校中心点 + 分类映射动态化（categoriesApi 拉取，CATEGORY\_COLORS/NAMES 保留 fallback）
- `P1-001` 确认收藏相关代码已彻底移除（前端无残留 UI/调用，后端无残留路由）
- `P1-004` 清零 ESLint 24 个 error（react-hooks/exhaustive-deps 等），保留 set-state-in-effect 为 warning（项目设计）
- `P2-013` auth.py:380 移除明文 reset\_token 日志，降级为 DEBUG 级别且只记 token 前 8 位

### 阶段一：紧急修复

- `P0-001` frontend/Dockerfile 补 `ARG VITE_API_BASE_URL=/api/v1` + `ENV VITE_API_BASE_URL=$VITE_API_BASE_URL`，修复生产构建 API 地址回退 localhost 的问题
- `P1-005` README/docs/27 物理模型描述修正（说明为课设交付物，实际部署仅 Alembic 索引）
- `P1-006` docs/12/13/22 头部增加「⚠️ 本文档已过时」声明
- `P2-014` AGENTS.md「演示学校唯一」更新为三校口径（江南为主，附带 fudan/zju）

## \[1.0.0] - 2026-07-04

### 变更

- `api/posts` 修复帖子列表/详情/创建/更新接口 author 字段返回问题（移除 alias="user"，手动映射 author，非匿名帖子正确显示作者昵称）
- `api/comments` 修复评论创建 500 错误（MissingGreenlet，添加 selectinload 预加载 replies）；修复评论/回复 author 字段返回
- `api/search` 修复搜索结果 author 字段名称不一致问题，content 返回完整内容
- `schemas/post` PostListResponse 补充 user\_id、is\_anonymous 字段；PostResponse/PostListResponse 移除 author 的 alias="user"
- `schemas/comment` CommentResponse 移除 author 的 alias="user"
- `schemas/user` 删除重复 LoginResponse 定义，改用 Pydantic v2 的 model\_config
- `frontend` 个人中心显示真实信誉分（reputation\_score），User 类型补充 reputation\_score 字段
- 信誉分系统完善：登录/个人信息接口正确返回 reputation\_score，发帖后信誉分正确触发存储过程更新
- 清理数据库测试垃圾数据（"123123"帖子及相关评论）
- `.gitignore` 添加 .trae/ 目录

## [0.1.0](https://github.com/yourusername/moment-campus/releases/tag/v0.1.0) - 2026-06-18

### 新增

- 完成第一阶段产品与技术规划文档（18 个核心文档）
- 项目总览与产品需求文档
- 用户角色与使用场景分析
- 功能范围与优先级定义（P0/P1/P2）
- 信息架构与导航设计
- 18 个核心用户流程设计
- 37 个页面规格说明（用户端 29 页 + 管理端 8 页）
- 12 个内容分类与字段设计
- 社区治理机制设计
- AI 能力规划与降级方案
- UI/UX 设计规范（颜色、字体、组件等）
- 技术架构设计（React + FastAPI + PostgreSQL）
- 数据库设计（21 个核心实体）
- API 接口规范（19 个模块，60+ 接口）
- 安全与隐私保护方案
- 测试策略与验收标准
- 9 阶段开发路线图
- 风险识别与应对措施
