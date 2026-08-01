# 更新日志

本文件记录"此刻校园"项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> **说明**：自 2026-07-26 起，详细的任务级变更追踪改由 `TODO.md` + `AIwork/` 任务报告维护，本文件仅保留版本级里程碑摘要。

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

