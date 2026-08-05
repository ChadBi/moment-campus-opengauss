# 更新日志

本文件记录"此刻校园"项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> **说明**：自 2026-07-26 起，详细的任务级变更追踪改由 `TODO.md` + `AIwork/` 任务报告维护，本文件仅保留版本级里程碑摘要。

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

