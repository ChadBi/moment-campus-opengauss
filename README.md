# 此刻校园 (Moment Campus)

> 版本：2.0.0
> 由校园成员共同建设的校园信息共享与沉淀平台

## 项目简介

**"此刻校园"** 是一个面向大学校园的时空信息图谱与可信协同平台。校园中存在大量真实、有用但容易消失的信息——哪里有好吃的食堂窗口、哪家打印店更便宜、哪里适合自习、哪里经常出现校园小猫——这些信息分散在微信群、QQ 群、朋友圈和口口相传中，发布得快，消失得也快。

"此刻校园"通过地图、时间、分类和协同验证组织校园信息，让校园信息变得可搜索、可浏览、可验证、可更新、可长期沉淀。

产品不是传统校园论坛，也不是普通社交平台，而是一张由校园成员共同维护的"校园生活地图"。

## 核心价值

- **信息沉淀**：让有价值的校园信息不再随时间消失
- **社区验证**：通过社区共同维护确保信息有效性
- **地图发现**：结合地图和信息流，从空间维度发现校园信息
- **AI 赋能**：智能搜索与 AI 辅助发布，降低使用门槛
- **轻量发布**：简单几步即可完成信息发布
- **隐私保护**：不收集用户行动轨迹，尊重用户隐私

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端框架 | React | 19.2 |
| 语言 | TypeScript | 6.0 |
| 构建工具 | Vite | 8.0 |
| 样式 | Tailwind CSS | 3.4 |
| 地图 | MapLibre GL JS | 5.24 |
| 状态管理 | Zustand | 5.0 |
| 服务端状态 | @tanstack/react-query | 5.101 |
| 路由 | react-router-dom | 7.18 |
| 表单 | react-hook-form + zod | 7.79 / 4.4 |
| 图标 | lucide-react | 1.21 |
| 后端框架 | FastAPI | 0.115+ |
| ASGI 服务器 | uvicorn | 0.30+ |
| ORM | SQLAlchemy | 2.0 (async) |
| 数据校验 | Pydantic | 2.10+ |
| 数据库 | openGauss | 7.0.0-RC3 |
| 数据库驱动 | asyncpg | 0.29+ |
| 认证 | python-jose (JWT) + passlib (bcrypt) | — |
| AI 能力 | DeepSeek API (兼容 OpenAI) | deepseek-v4-flash |
| 容器化 | Docker + Docker Compose | — |

## 核心特性

### 6 态状态机
`draft` → `pending` → `published` → `expired` / `conflict` → `archived`，共 13 条合法流转规则，普通用户与管理员分级权限控制。

### 2 类协同验证
- **confirmation**（证实）：确认信息仍然有效
- **refutation**（证伪）：指出信息不准确或已经失效
- 每名用户对每条帖子仅保留一条验证记录；可切换类型，再次点击同类验证即取消
- 单数写端点为 `POST /api/v1/posts/{post_id}/validate`；登录态统计端点为 `GET /api/v1/posts/{post_id}/validation-stats`
- 历史文档中的 `update`、`expiration_report`、`conflict_report` 是已放弃的五类治理方案，不属于现行验证契约

### RBAC 权限矩阵
三级角色层级：`user < admin < super_admin`，统一通过 `require_role()` 依赖工厂进行权限校验。

### 多租户架构
支持多学校切换，当前演示学校：
- **江南大学**（主校，code=`jiangnan`，map_zoom=16）
- **复旦大学**（code=`fudan`）
- **浙江大学**（code=`zju`）

各校数据独立隔离，跨校访问需相应权限。

### AI 智能能力
- **AI 搜索**：自然语言意图解析 + openGauss DataVec 语义召回 + 结构化条件过滤 + 匹配理由展示
- **混合检索**：语义相似度 35% + 新鲜度 25% + 验证数 20% + 关键词相关度 20%
- **AI 辅助发布**：智能标题建议、分类推荐、有效期建议、敏感信息提醒
- **降级模式**：Embedding 或向量查询不可用时自动降级为关键词搜索，不阻断核心功能

### 动态分类
- 分类由当前学校的 `/api/v1/categories` 接口动态加载，不依赖前端固定 ID 或中文名称映射
- 分类视觉由 `category.code` 稳定计算；切换学校时同步清理旧校分类、筛选值和地图标记

### 自动过期
- 独立 `moment-expire-posts.timer` 在系统启动后 5 分钟首次触发 oneshot worker，此后每 30 分钟触发一次，不在 4 个 Uvicorn Web worker 中重复调度
- 任务使用数据库锁、60 分钟运行租约和幂等通知；手动触发及运行记录仅 `super_admin` 可访问

### 地图集成
- MapLibre GL JS 原生 symbol layer 实现，WebGL 渲染
- GCJ-02 坐标契约（适配高德瓦片）
- 支持单帖水滴图标、多帖聚合显示
- 缩放/平移流畅无漂移
- 地点选点与发布表单集成

### 协同治理
管理员后台进行内容审核、举报处理、协同验证管理。

## 项目架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端                                   │
│  React + TypeScript + Tailwind CSS + MapLibre GL JS              │
├─────────────────────────────────────────────────────────────────┤
│                         通信层                                   │
│  axios · react-query · zustand · JWT Bearer Token                │
├─────────────────────────────────────────────────────────────────┤
│                         后端 API                                │
│  FastAPI · SQLAlchemy 2.0 (async) · asyncpg                      │
├─────────────────────────────────────────────────────────────────┤
│                         数据层                                   │
│  openGauss 7.0.0-RC3 · Alembic 迁移 · 41 张表                    │
├─────────────────────────────────────────────────────────────────┤
│                         AI 能力                                  │
│  DeepSeek API · 智能搜索 · 辅助发布 · 降级模式                   │
└─────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
moment-campus/
├── backend/                    # 后端 FastAPI 项目
│   ├── app/
│   │   ├── api/               # 路由层（19 个路由模块）
│   │   ├── ai/                # AI Provider 适配层
│   │   ├── core/              # 核心配置（权限/状态机/校验类型）
│   │   ├── models/            # SQLAlchemy 数据模型（41 张表）
│   │   ├── schemas/           # Pydantic 数据校验
│   │   ├── services/          # 业务服务层
│   │   ├── jobs/              # 定时任务
│   │   ├── config.py          # 配置加载
│   │   ├── main.py            # FastAPI 入口
│   │   └── middleware.py      # 中间件
│   ├── alembic/               # 数据库迁移
│   ├── scripts/               # 脚本（seed_data 等）
│   ├── tests/                 # 测试用例
│   └── requirements.txt
├── frontend/                   # 前端 React 项目
│   ├── src/
│   │   ├── components/        # 组件（布局/UI/功能）
│   │   ├── pages/             # 页面（用户端/管理端）
│   │   ├── services/          # API 调用封装
│   │   ├── store/             # Zustand 状态管理
│   │   └── routes.tsx         # 路由配置
│   ├── public/                # 静态资源
│   └── package.json
├── docs/                       # 项目文档
├── deploy/                     # 部署配置
├── docker-compose.yml          # openGauss 容器编排
├── README.md
├── CHANGELOG.md
└── AGENTS.md
```

## 快速启动

### 环境要求

- Node.js >= 18.0.0
- Python >= 3.10
- npm >= 9.0.0
- Docker Desktop >= 24.0
- openGauss 7.0.0-RC3 镜像（本地已导入）

### 1. 启动 openGauss 数据库

```bash
# 项目根目录
docker compose up -d opengauss

# 等待数据库就绪（约 10-30 秒）
docker logs -f opengauss
# 看到 "database system is ready to accept connections" 后按 Ctrl+C
```

### 2. 启动后端服务

```bash
# 进入后端目录
cd backend

# 创建并激活虚拟环境（首次）
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 切换到 openGauss 环境
# Windows PowerShell:
$env:APP_ENV = "opengauss"
# macOS/Linux:
# export APP_ENV=opengauss

# 执行数据库迁移
alembic upgrade head

# 填充演示数据
python scripts/seed_data.py

# 启动后端服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API 服务：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 3. 启动前端服务

```bash
# 进入前端目录
cd ../frontend

# 安装依赖（首次）
npm install

# 启动开发服务器
npm run dev
```

- 前端页面：http://localhost:5173

### 4. 演示账号与登录方式

手机号是业务唯一身份。Web 端可使用手机号+密码或手机号+短信验证码登录；教育邮箱只用于校园认证，不作为登录凭证。小程序使用「微信登录并授权手机号」，无需传统注册。

| 角色 | 手机号 | 密码 | 权限 |
|------|------|------|------|
| 平台超管（江南） | `13900000001` | `pass123` | 全部权限 + 跨校管理 |
| 学校管理员（复旦） | `13900000101` | `pass123` | 复旦大学管理 |
| 学校管理员（浙大） | `13900000201` | `pass123` | 浙江大学管理 |
| 普通用户（江南） | `13900000002 ~ 13900000011` | `pass123` | 江南大学基础功能 |
| 普通用户（复旦） | `13900000102 ~ 13900000106` | `pass123` | 复旦大学基础功能 |
| 普通用户（浙大） | `13900000202 ~ 13900000206` | `pass123` | 浙江大学基础功能 |
| 微信手机号登录演示账号（江南） | `13800138000` | 未设置 | Mock 微信登录；可登录后设置密码 |

其中，已认证演示账号另外绑定教育邮箱；`13800138000` 为未认证、无密码的微信手机号登录示例账号。

**演示数据概况**（由 `python scripts/seed_data.py` 生成）：
- 3 所学校（江南大学/复旦大学/浙江大学）
- 3 个订阅套餐（基础/标准/高级）
- 每校 5 个信息分类（分享吐槽/组队交友/二手交易/失物招领/其他）
- 20+ 用户（含超级管理员、学校管理员、普通用户）
- 80+ 帖子（含 6 态状态样本：draft/pending/published/expired/conflict/archived）
- 12 个专题集合（每校 4 个）
- 39 个地点（GCJ-02 坐标，适配高德瓦片）

### 5. 运行测试

```bash
# 后端测试
cd backend
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "opengauss"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://<user>:<password>@127.0.0.1:5432/moment_campus_test"
pytest tests/ -v

# 前端测试
cd ../frontend
npm run build          # 类型检查 + 构建
npm run lint           # ESLint 检查
npm run e2e            # Playwright E2E 测试
```

后端测试只允许连接独立 openGauss 测试库。`TEST_DATABASE_URL` 缺失、数据库名不含 `_test`，或与开发库地址相同时，测试会在清理数据前直接停止。请使用本地安全凭据，不要把真实密码写入文档或提交记录。

## 部署说明

### 线上环境

项目已部署至华为云：[https://campus.chaina1.com](https://campus.chaina1.com)

### 部署架构

混合部署方案：openGauss 容器 + 后端 systemd + 前端 Nginx 静态托管

- **数据库**：openGauss 7.0.0-RC3 Docker 容器
- **后端**：uvicorn × 4 workers，systemd 服务管理
- **后台任务**：独立 systemd timer + oneshot worker，系统启动后 5 分钟首次处理，此后每 30 分钟处理到期帖子
- **前端**：Vite 构建后由 Nginx 托管静态文件
- **反向代理**：Nginx 代理 API 请求至后端

### 本地构建与部署

```bash
# 1. 本地构建前端
cd frontend
npm run build

# 2. 打包上传
# 前端 dist/ → SCP 上传至服务器
# 后端 app/、scripts/、alembic/、requirements.txt → SCP 上传

# 3. 服务器端
# - 数据库迁移：alembic upgrade head
# - 种子数据：python scripts/seed_data.py
# - 后端重启：systemctl restart moment-backend
# - Nginx 重载：nginx -t && systemctl reload nginx
```

详细部署流程见 [docs/30_华为云混合部署记录.md](docs/30_华为云混合部署记录.md)。

## 项目状态

### 当前阶段

**阶段 R：TRAE AI 创造力大赛复赛冲刺** — 进行中

- 已完成 6 项：R-02（测试基线）、R-03（AI Gateway）、R-04（智能搜索）、R-05（AI 辅助发布）、R-06（可观测）、R-08（核心 E2E）
- 关键路径：产品说明书 → 演示视频 → Session ID → 社区作品帖 → 飞书问卷提交

### 完成度

| 阶段 | 状态 | 完成度 | 说明 |
|------|------|--------|------|
| 阶段 A：openGauss 适配 | ✅ 已完成 | 18/18 | T-A-01~18 全部完成 |
| 阶段 P：数据库物理模型 | ✅ 主体完成 | 8/10 | 2 项放弃（轻量版限制） |
| 阶段 B：核心业务升级 | ✅ 已完成 | 7/8 | 1 项放弃 |
| 阶段 E：测试与交付 | ✅ 已完成 | 4/4 | 全部完成 |
| 阶段 OPT：项目优化 | ✅ 已完成 | 28/32 | 87.5% 关闭率 |
| 阶段 R：复赛冲刺 | 🔄 进行中 | 6/14 | 冲刺目标 2026-08-09 |

### 测试覆盖率

- **后端**：987 PASS / 0 FAIL / 0 WARNING（`pytest tests -q -W error`）
- **前端**：Playwright 38 PASS / 0 SKIP / 0 FAIL
- **E2E 全链路**：74 场景覆盖 7 大功能域，通过率 97.3%
- **MCP 浏览器**：多轮端到端验证通过（注册→发布→审核→协同→跨校切换→地图）

## 项目边界

### 当前版本包含

- ✅ 校园信息发布、浏览、搜索
- ✅ 地图与信息流结合（MapLibre GL JS）
- ✅ 分类筛选与 AI 智能搜索
- ✅ 6 态状态机 + 2 类协同验证（证实/证伪）
- ✅ 评论、点赞、协同治理
- ✅ 举报与管理员后台
- ✅ 多学校切换（多租户架构）
- ✅ 主题订阅与推荐
- ✅ AI 辅助发布与敏感信息提醒
- ✅ DataVec 512 维混合检索链路与关键词降级
- ✅ 动态分类与 `category.code` 稳定视觉
- ✅ 独立 systemd timer 自动过期任务
- ✅ 移动端适配（响应式布局）
- ✅ 三校演示数据（江南/复旦/浙大）
- ✅ 华为云线上部署

### 当前版本不包含

- ❌ 关注系统与私信
- ❌ PWA 离线能力
- ❌ 校园实名认证
- ❌ 复杂多级组织权限
- ❌ 公开发布主体功能（已移除）
- ❌ 更新建议/过期报告/冲突报告三类治理队列（历史五类方案已放弃）

## 文档目录

| 文档 | 说明 |
|------|------|
| [项目总览](docs/00_project_overview.md) | 项目背景、定位、核心价值、目标用户 |
| [产品需求文档](docs/01_product_requirements.md) | 完整 PRD，包含功能需求、非功能需求 |
| [用户角色与场景](docs/02_user_roles_and_scenarios.md) | 用户类型、需求、使用场景、用户故事 |
| [功能范围与优先级](docs/03_feature_scope_and_priority.md) | P0/P1/P2 功能分级与优先级依据 |
| [信息架构](docs/04_information_architecture.md) | 页面层级、导航结构、信息架构图 |
| [用户流程](docs/05_user_flows.md) | 核心用户流程与流程图 |
| [页面规格说明](docs/06_page_specifications.md) | 每个页面的详细功能、信息和状态说明 |
| [内容与分类设计](docs/07_content_and_category_design.md) | 内容分类、字段差异、有效期规则 |
| [社区治理](docs/08_community_governance.md) | 审核、举报、社区治理机制 |
| [AI 能力规划](docs/09_ai_capability_plan.md) | AI 能力边界、降级方案 |
| [UI/UX 设计规范](docs/10_ui_ux_design_system.md) | 颜色、字体、间距、组件规范 |
| [技术架构](docs/11_technical_architecture.md) | 前后端架构、技术选型、部署方案 |
| [安全与隐私](docs/14_security_and_privacy.md) | 安全策略、权限模型、隐私保护 |
| [测试与验收](docs/15_testing_and_acceptance.md) | 测试范围、验收标准 |
| [开发路线图](docs/16_development_roadmap.md) | 开发阶段、任务顺序 |
| [风险管理](docs/17_risk_management.md) | 产品、技术、内容、隐私风险 |
| [项目现状说明](docs/18_项目现状说明.md) | 项目当前状态、技术栈、目录结构 |
| [openGauss 适配分析](docs/20_openGauss适配分析.md) | openGauss 数据库适配详细分析 |
| [后续开发任务清单](docs/21_后续开发任务清单.md) | 开发任务清单与优先级 |
| [服务器部署全流程指南](docs/28_服务器部署全流程指南.md) | 服务器部署完整流程 |
| [华为云混合部署记录](docs/30_华为云混合部署记录.md) | 华为云 v2.0.0 部署记录 |
| [项目演示流程指南](docs/31_项目演示流程指南.md) | 项目演示标准流程 |
| [GCJ02 坐标规范与三校点位目录](docs/35_GCJ02坐标规范与三校点位目录.md) | 三校坐标规范与地点目录 |

## 快速开始顺序

1. **了解项目**：阅读 [项目总览](docs/00_project_overview.md) → [产品需求文档](docs/01_product_requirements.md)
2. **环境搭建**：参考 [快速启动](#快速启动) 章节
3. **开发指南**：参考 [技术架构](docs/11_technical_architecture.md) → [API 接口文档](http://localhost:8000/docs)
4. **部署上线**：参考 [部署说明](#部署说明) → [华为云混合部署记录](docs/30_华为云混合部署记录.md)

## 相关链接

- **线上演示**：[https://campus.chaina1.com](https://campus.chaina1.com)
- **后端 API 文档**：[http://localhost:8000/docs](http://localhost:8000/docs)（本地开发）
- **变更日志**：[CHANGELOG.md](CHANGELOG.md)
- **任务列表**：[TODO.md](TODO.md)
- **项目报告**：[AIwork/](AIwork/)

---

**版本历史**：详见 [CHANGELOG.md](CHANGELOG.md)
