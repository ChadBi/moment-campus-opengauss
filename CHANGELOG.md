# 更新日志

本文件记录"此刻校园"项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

> **说明**：自 2026-07-26 起，详细的任务级变更追踪改由 `TODO.md` + `AIwork/` 任务报告维护，本文件仅保留版本级里程碑摘要。

## [Unreleased] - 2026-07-29

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

## [Unreleased] - 2026-07-26

### 阶段四+五：性能优化与质量收尾

- `P2-001` vite.config.ts 添加 manualChunks 拆分 maplibre-gl/react-vendor/icons，MapPage chunk 1043KB→16KB（97% 下降），index.js 307KB→128KB
- `P2-008` MapPage 瓦片源 OSM→高德栅格（4 个 webrd0{1-4}.is.autonavi.com 子域加速），国内可达性提升
- `P2-006` api.ts 401 并发刷新加锁：refreshPromise 单例 promise 复用，避免并发 401 多次消费 refresh_token
- `P2-007` 新增 utils/logger.ts（dev 打印/prod 静默），48 处 console.* 替换为 logger.*（21 个文件）
- `P2-003` SearchPage HOT_TAGS 改为多租户动态化：useMemo 从当前学校 categories 派生 top 8，fallback 到 FALLBACK_HOT_TAGS
- `P3-001` 删除 AdminTagsPage.tsx（602 行死代码）+ 4 个零引用 tag API + 3 个 tag 类型
- `P3-003` 新增 utils/date.ts 4 个函数（formatRelativeTime/formatDate/formatDateTime/formatShortDateTime），15 个文件的本地实现替换为导入
- `P3-004` 删除 3 对重复 API 定义：uploadApi.uploadAvatar / usersApi.getMyPosts / interactionsApi.transitionPost（零引用）
- `P3-006` nginx.conf 生产环境关闭 /docs 与 /openapi.json 对外暴露（return 404）
- `P3-007` CHANGELOG.md 补记阶段一/二/三/四/五全部变更
- `P3-008` docs/ 下 11 个文件 160+ 处 `file:///d:/Project/database-class/...` 旧盘符路径批量替换为相对路径
- `P3-011` frontend/README.md 由 Vite 模板默认文案替换为项目说明

### 阶段三：仓库卫生与部署配置

- `P2-009` 7 个 verify_*.py 调试脚本迁移到 backend/tests/manual/（git mv 保留历史），.gitignore 新增 `/verify_*.py` 规则
- `P2-010` 清理 backend/ 76 个 + 根目录 16 个调试脚本/日志（全部已被 .gitignore 覆盖）
- `P2-012` 新增 backend/.dockerignore 与 frontend/.dockerignore，排除 .git/.venv/node_modules/tests/logs/.env 等
- `P2-011` deploy/.env.prod.example 与 backend/.env.example 同步补齐 9 项 AI_* 变量模板；backend/.env.example 修复 SQLite 残留改为 openGauss
- `P2-002` index.html title/description 移除江南大学硬编码，改为多租户通用文案
- `P2-005` ProfilePage 与 AdminDashboard 的 handleLogout 改为先 await authApi.logout() 后清本地 state

### 阶段二：多租户与代码质量

- `P1-002` MapPage 接入 useCampusStore 学校中心点 + 分类映射动态化（categoriesApi 拉取，CATEGORY_COLORS/NAMES 保留 fallback）
- `P1-001` 确认收藏相关代码已彻底移除（前端无残留 UI/调用，后端无残留路由）
- `P1-004` 清零 ESLint 24 个 error（react-hooks/exhaustive-deps 等），保留 set-state-in-effect 为 warning（项目设计）
- `P2-013` auth.py:380 移除明文 reset_token 日志，降级为 DEBUG 级别且只记 token 前 8 位

### 阶段一：紧急修复

- `P0-001` frontend/Dockerfile 补 `ARG VITE_API_BASE_URL=/api/v1` + `ENV VITE_API_BASE_URL=$VITE_API_BASE_URL`，修复生产构建 API 地址回退 localhost 的问题
- `P1-005` README/docs/27 物理模型描述修正（说明为课设交付物，实际部署仅 Alembic 索引）
- `P1-006` docs/12/13/22 头部增加「⚠️ 本文档已过时」声明
- `P2-014` AGENTS.md「演示学校唯一」更新为三校口径（江南为主，附带 fudan/zju）

## [0.1.1] - 2026-07-04

### 变更

- `api/posts` 修复帖子列表/详情/创建/更新接口 author 字段返回问题（移除 alias="user"，手动映射 author，非匿名帖子正确显示作者昵称）
- `api/comments` 修复评论创建 500 错误（MissingGreenlet，添加 selectinload 预加载 replies）；修复评论/回复 author 字段返回
- `api/search` 修复搜索结果 author 字段名称不一致问题，content 返回完整内容
- `schemas/post` PostListResponse 补充 user_id、is_anonymous 字段；PostResponse/PostListResponse 移除 author 的 alias="user"
- `schemas/comment` CommentResponse 移除 author 的 alias="user"
- `schemas/user` 删除重复 LoginResponse 定义，改用 Pydantic v2 的 model_config
- `frontend` 个人中心显示真实信誉分（reputation_score），User 类型补充 reputation_score 字段
- 信誉分系统完善：登录/个人信息接口正确返回 reputation_score，发帖后信誉分正确触发存储过程更新
- 清理数据库测试垃圾数据（"123123"帖子及相关评论）
- `.gitignore` 添加 .trae/ 目录

## [0.1.0] - 2026-06-18

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

[0.1.0]: https://github.com/yourusername/moment-campus/releases/tag/v0.1.0
