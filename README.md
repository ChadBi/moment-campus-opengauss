# 此刻校园 (Moment Campus)

> 由校园成员共同建设的校园信息共享与沉淀平台

## 项目简介

"此刻校园"是一个面向大学校园的信息共享与沉淀平台。校园中存在大量真实、有用但容易消失的信息——哪里有好吃的窗口、哪家打印店更便宜、哪里适合自习、哪里经常出现校园小猫——这些信息分散在微信群、QQ群、朋友圈和口口相传中，发布得快，消失得也快。

"此刻校园"通过地点、时间、分类、标签和有效期组织校园信息，让校园信息变得可搜索、可浏览、可验证、可更新、可收藏、可长期沉淀。

产品不是传统校园论坛，也不是普通社交平台，而是一张由校园成员共同维护的"校园生活地图"。

## 核心价值

- **信息沉淀**：让有价值的校园信息不再随时间消失
- **社区验证**：通过社区共同维护确保信息有效性
- **地图发现**：结合地图和信息流，从空间维度发现校园信息
- **轻量发布**：简单几步即可完成信息发布
- **隐私保护**：不收集用户行动轨迹，尊重用户隐私

## 当前阶段

**阶段三：完整项目开发（进行中）**

本阶段将完成从项目初始化到最终交付的完整开发流程，包括：
- 前端：React + TypeScript + Vite + Tailwind CSS
- 后端：Python + FastAPI + SQLAlchemy 2.0（async）+ asyncpg
- 数据库：openGauss 7.0.0-RC3 轻量版（Docker 部署，唯一数据库，已彻底移除 SQLite）

> **演示学校**：江南大学蠡湖校区（坐标 31.4837, 120.2712，map_zoom=16）。Base 项目原使用"华东师范大学、复旦大学"作为模拟对象，已于 T-A-16/17 任务中统一替换为江南大学。

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
| [内容与分类设计](docs/07_content_and_category_design.md) | 内容分类、字段差异、标签体系、有效期规则 |
| [社区治理](docs/08_community_governance.md) | 审核、举报、失效确认、社区治理机制 |
| [AI 能力规划](docs/09_ai_capability_plan.md) | AI 能力边界、降级方案、实现顺序 |
| [UI/UX 设计规范](docs/10_ui_ux_design_system.md) | 颜色、字体、间距、组件规范 |
| [技术架构](docs/11_technical_architecture.md) | 前后端架构、技术选型、部署方案 |
| [数据库设计](docs/12_database_design.md) | 数据模型、字段设计、ER 图 |
| [API 接口规范](docs/13_api_specification.md) | 完整 RESTful API 文档 |
| [安全与隐私](docs/14_security_and_privacy.md) | 安全策略、权限模型、隐私保护 |
| [测试与验收](docs/15_testing_and_acceptance.md) | 测试范围、验收标准、发布检查清单 |
| [开发路线图](docs/16_development_roadmap.md) | 开发阶段、任务顺序、依赖关系 |
| [风险管理](docs/17_risk_management.md) | 产品、技术、内容、隐私风险与应对 |

## 建议阅读顺序

1. 项目总览 → 了解项目是什么
2. 产品需求文档 → 了解产品要做什么
3. 用户角色与场景 → 了解为谁而做
4. 功能范围与优先级 → 了解第一版做什么
5. 信息架构 → 了解页面结构
6. 用户流程 → 了解核心交互
7. 页面规格说明 → 了解每个页面细节
8. 内容与分类设计 → 了解数据结构
9. 数据库设计 → 了解数据模型
10. API 接口规范 → 了解接口设计
11. 技术架构 → 了解技术方案
12. UI/UX 设计规范 → 了解视觉规范
13. 安全与隐私 → 了解安全策略
14. 社区治理 → 了解运营机制
15. AI 能力规划 → 了解 AI 方案
16. 测试与验收 → 了解质量标准
17. 开发路线图 → 了解开发计划
18. 风险管理 → 了解风险与应对

## 快速启动

### 环境要求

- Node.js >= 18.0.0
- Python >= 3.10
- npm >= 9.0.0

### 1. 后端启动

```bash
# 1. 启动 openGauss 容器（项目根目录）
docker compose up -d opengauss

# 2. 后端目录下激活虚拟环境
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate    # macOS/Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 切换到 openGauss 环境（通过 APP_ENV 加载 backend/.env.opengauss）
# Windows PowerShell:
$env:APP_ENV = "opengauss"
# macOS/Linux:
export APP_ENV=opengauss

# 5. 执行数据库迁移
alembic upgrade head

# 6. 填充江南大学演示数据
python scripts/seed_data.py

# 7. 启动后端服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

详细环境配置、连接串、容器管理见 [docs/22_项目运行与开发环境说明.md](docs/22_项目运行与开发环境说明.md)。

- API 服务：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

- 前端页面：http://localhost:5173

### 3. 演示账号

| 角色 | 邮箱 | 密码 |
|------|------|------|
| 管理员 | admin@momentcampus.com | pass123 |
| 普通用户 | user1@example.com ~ user10@example.com | pass123 |

**演示学校**：江南大学蠡湖校区（code=`jiangnan`，中心坐标 31.4837 / 120.2712）。

### 4. 运行测试

```bash
cd backend
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate    # macOS/Linux
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## 后续开发阶段

| 阶段 | 名称 | 说明 |
|------|------|------|
| 一 | 产品与技术文档 | ✅ 已完成 |
| 二 | UI/UX 设计与静态原型 | ✅ 已完成 |
| 三 | 完整项目开发 | ✅ 核心功能完成 |
| 四 | 测试与部署 | ⏳ 待开始 |

## 项目边界

### 第一版包含

- 校园信息发布与浏览
- 地图与信息流结合
- 分类筛选与搜索
- 社区验证（有效性确认）
- 评论、点赞、收藏
- 基础管理审核
- 移动端适配

### 第一版不包含

- 多学校切换（仅支持单校）
- 关注系统与私信
- AI 语义搜索（规划但不在第一版实现）
- PWA 离线能力
- 校园实名认证
- 复杂多级组织权限

## 技术栈概览

- **前端**：React + TypeScript + Vite + Tailwind CSS + MapLibre GL JS
- **后端**：Python + FastAPI + SQLAlchemy 2.0（async）+ asyncpg
- **数据库**：openGauss 7.0.0-RC3 轻量版（Docker 部署，唯一数据库）
- **认证**：JWT + 3 级角色层级（user / admin / super_admin）
- **地图**：MapLibre GL JS / Leaflet

## 核心特性

- **6 态状态机**：draft / pending / published / expired / conflict / archived，13 条合法流转规则，普通用户与管理员分级权限
- **5 类协同验证**：confirmation（证实）/ refutation（证伪）/ update（补充更新）/ expiration_report（过期上报）/ conflict_report（冲突上报），兼容旧别名
- **RBAC 权限矩阵**：user < admin < super_admin 层级向下兼容，`require_role()` 依赖工厂统一校验
- **数据库物理模型**：实际部署使用 Alembic 迁移脚本创建的 41 张表 + 231 个索引；表空间/存储过程/触发器/物化视图/分区表为课设交付物（脚本见 `backend/scripts/opengauss/`，未在生产数据库执行，原因见 [docs/27_数据库物理模型设计.md](docs/27_数据库物理模型设计.md) 头部说明）

## 项目状态

核心功能开发完成，前后端联调通过，172 项自动化测试全部通过。

当前已完成：openGauss 适配、6 态状态机、5 类协同验证、RBAC 权限矩阵、江南大学数据改造、地图页集成、信息发布与浏览、搜索与分类筛选、评论与互动、用户中心、管理后台。

按 MVP 原则已放弃：阶段 C（创新点：可信度/过期/冲突/版本/信誉）、阶段 D（扩展能力：时间轴/裁定/共同修正）、SQLite 开发备选。

详见 [TODO.md](TODO.md)。
