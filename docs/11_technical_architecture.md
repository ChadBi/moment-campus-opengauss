# 技术架构

> 此刻校园 · Moment Campus  
> 现行口径同步：2026-07-31
> 版本：1.0  
> 最后更新：2026-06-18

> **现行地图口径（2026-08-07）**：本文早期浏览器定位、GPS/坐标转换和位置权限设计已废弃。当前 Web/小程序只使用学校静态中心坐标与地点坐标，不采集用户当前位置、不计算距离；实现契约以 AI 地点摘要方案和小程序契约矩阵为准。

## 1. 技术选型分析

### 1.1 前端技术栈

| 技术 | 版本建议 | 选型理由 |
|------|----------|----------|
| **React** | 18+ | 生态成熟、社区庞大、组件化开发模式适合中大型 SPA；招聘市场人才充足 |
| **TypeScript** | 5+ | 静态类型检查减少运行时错误，提升代码可维护性和团队协作效率 |
| **Vite** | 5+ | 基于 ES Module 的构建工具，开发启动极快（<1s），HMR 即时生效；生产构建使用 Rollup，产物体积小 |
| **Tailwind CSS** | 3+ | 原子化 CSS，避免样式冲突，无需命名类名；配合响应式断点天然适合移动端优先设计 |
| **React Router** | 6+ | React 官方推荐路由方案，支持嵌套路由、懒加载、数据加载 |
| **Zustand** | 4+ | 轻量级状态管理（<1KB），API 简洁，无 boilerplate；适合管理 UI 状态和全局客户端状态 |
| **TanStack Query** | 5+ | 专为服务端状态设计，内置缓存、去重、后台刷新、分页、无限滚动；大幅减少手动管理加载/错误状态的代码 |
| **React Hook Form** | 7+ | 非受控组件方案，性能优于受控表单；减少不必要的 re-render，API 简洁 |
| **Zod** | 3+ | TypeScript-first 的 schema 验证库，可在前后端共享验证逻辑；与 React Hook Form 深度集成 |
| **Lucide React** | - | 轻量级图标库，支持 Tree Shaking，按需加载；图标风格统一，支持自定义大小和颜色 |
| **MapLibre GL JS** | 3+ | 开源免费的 WebGL 地图库，无 API Key 限制；支持矢量瓦片、自定义样式、3D 视图；是 Mapbox GL JS 的开源分支，API 兼容 |

#### 替代方案对比

| 技术 | 替代方案 | 不选原因 |
|------|----------|----------|
| React | Vue 3 | Vue 3 同样优秀，但 React 生态更大，组件库和第三方库更丰富；团队 React 经验更充足 |
| Vite | Next.js | Next.js 是 SSR 框架，本项目为 SPA 场景，无需服务端渲染；Vite 更轻量，构建速度更快 |
| Tailwind CSS | Ant Design / Material UI | 组件库体积大，样式定制成本高；校园产品需要独特的视觉风格，原子化 CSS 更灵活 |
| Zustand | Redux Toolkit | Redux  boilerplate 过多，对中小项目过重；Zustand 更轻量且满足需求 |
| TanStack Query | SWR | SWR 功能较基础，TanStack Query 支持分页、无限滚动、乐观更新等高级特性 |
| MapLibre GL JS | Leaflet | Leaflet 基于 SVG 渲染，大量标记时性能差；MapLibre 使用 WebGL，支持数千标记流畅渲染 |
| MapLibre GL JS | 高德/百度地图 JS API | 商业地图 API 有调用次数限制和 Key 绑定；校园场景需要自定义地图样式，开源方案更灵活 |

### 1.2 后端技术栈

| 技术 | 版本建议 | 选型理由 |
|------|----------|----------|
| **Python** | 3.11+ | 语法简洁、开发效率高；AI/ML 生态丰富，便于后续集成 AI 能力；社区庞大 |
| **FastAPI** | 0.100+ | 高性能异步框架（基于 Starlette），性能接近 Node.js；自动生成 OpenAPI 文档；原生支持 Pydantic 数据验证和类型提示 |
| **SQLAlchemy** | 2.0+ | Python 最成熟的 ORM，支持异步（2.0+）；类型安全、灵活的查询构建器；支持复杂的表关系映射 |
| **Pydantic** | 2.0+ | 基于类型提示的数据验证和序列化库；与 FastAPI 深度集成，自动验证请求参数和生成 JSON Schema |
| **openGauss** | 7.0.0-RC3 | 唯一数据库；使用 asyncpg 异步驱动，原生 DataVec 提供 `vector(512)`、HNSW 和距离运算 |
| **JWT** | - | 无状态认证方案，适合前后端分离架构；Token 可自包含用户信息，减少数据库查询 |
| **Alembic** | - | SQLAlchemy 官方迁移工具，自动生成迁移脚本；支持版本化管理数据库 Schema 变更 |

#### 替代方案对比

| 技术 | 替代方案 | 不选原因 |
|------|----------|----------|
| FastAPI | Django | Django 功能全面但过于重量级，自带 Admin/ORM/模板；本项目需要前后端完全分离，FastAPI 更轻量灵活 |
| FastAPI | Express (Node.js) | Node.js 生态适合前端团队，但 Python 在 AI/数据处理方面优势明显，且校园产品后续需要 AI 能力 |
| SQLAlchemy | Prisma | Prisma 是 Node.js 生态的 ORM，不适用于 Python 后端 |
| SQLite | MySQL | MySQL 功能足够，但 openGauss 在 JSON 支持、全文搜索、国产化方面更优；校园产品数据量不大，openGauss 完全胜任 |
| JWT | Session | Session 需要服务端存储，不利于水平扩展；JWT 无状态，适合分布式部署 |

---

## 2. 系统架构

### 2.1 系统架构图

```mermaid
graph TD
    subgraph 客户端["客户端 (Browser)"]
        UI["React UI 组件"]
        Router["React Router"]
        Zustand["Zustand<br/>客户端状态"]
        TQ["TanStack Query<br/>服务端状态缓存"]
        MapLibre["MapLibre GL JS<br/>地图引擎"]
    end

    subgraph 前端应用["前端应用 (Vite SPA)"]
        Pages["页面组件"]
        Containers["容器组件"]
        Hooks["自定义 Hooks"]
        Services["API 服务层"]
    end

    subgraph 后端应用["后端应用 (FastAPI)"]
        Router2["路由层<br/>API Endpoints"]
        Middleware["中间件<br/>CORS / Auth / Logger"]
        Services2["服务层<br/>业务逻辑"]
        Models["数据模型<br/>SQLAlchemy ORM"]
        Schemas["数据验证<br/>Pydantic Schemas"]
    end

    subgraph 数据层["数据层"]
        DB[(openGauss 7.0)]
        FS["文件系统<br/>图片存储"]
        Cache["缓存<br/>Redis (后续)"]
    end

    subgraph 外部服务["外部服务 (后续)"]
        OSS["对象存储<br/>阿里云 OSS"]
        AI["AI 服务<br/>意图解析与 Embedding"]
        CDN["CDN<br/>静态资源加速"]
    end

    UI --> Router
    Router --> Pages
    Pages --> Containers
    Containers --> Hooks
    Hooks --> Zustand
    Hooks --> TQ
    Pages --> MapLibre
    Hooks --> Services

    Services -->|HTTP REST| Router2
    Router2 --> Middleware
    Middleware --> Services2
    Services2 --> Models
    Services2 --> Schemas

    Models --> DB
    Services2 --> FS
    Services2 --> Cache

    FS -.->|后续迁移| OSS
    Services2 -->|已集成，可降级| AI
    UI -.->|静态资源| CDN
```

### 2.2 前后端分离架构说明

本项目采用**前后端完全分离**架构：

- **前端**：独立的 SPA 应用，通过 Vite 构建，部署为静态文件
- **后端**：独立的 API 服务，提供 RESTful 接口，不渲染任何 HTML
- **通信**：通过 HTTP/JSON 进行数据交换，JWT 进行身份认证

**优势：**

- 前后端可独立开发、独立部署、独立扩展
- 前端可使用任何 UI 框架，后端可服务多端（Web、App、小程序）
- 职责清晰，团队协作效率高

### 2.3 模块划分

| 模块 | 前端职责 | 后端职责 |
|------|----------|----------|
| **用户认证** | 登录/注册页面、Token 管理 | JWT 签发/验证、密码加密 |
| **信息浏览** | 首页、信息流、地图、搜索、详情 | 信息查询、排序、分页、搜索 |
| **内容创作** | 发布表单、图片上传 | 信息创建、图片处理、验证 |
| **内容管理** | 我的发布、编辑/删除 | 信息更新、软删除 |
| **社区互动** | 点赞、评论 | 互动逻辑、计数更新 |
| **社区治理** | 有效性确认、举报 | 验证统计、举报处理 |
| **用户中心** | 个人中心、通知 | 用户信息管理、通知生成 |
| **后台管理** | 管理后台页面 | 审核逻辑、权限控制 |
| **地图服务** | MapLibre 渲染、标记交互 | 地点数据、坐标查询 |

---

## 3. 前端架构

### 3.1 前端目录规划

```
frontend/
├── index.html                    # HTML 入口
├── package.json                  # 依赖配置
├── vite.config.ts                # Vite 配置
├── tailwind.config.ts            # Tailwind 配置
├── tsconfig.json                 # TypeScript 配置
├── .env                          # 环境变量
├── .env.development              # 开发环境变量
├── .env.production               # 生产环境变量
│
├── public/                       # 静态资源（不经过构建处理）
│   ├── favicon.ico
│   └── robots.txt
│
└── src/
    ├── main.tsx                  # 应用入口
    ├── App.tsx                   # 根组件
    │
    ├── assets/                   # 构建资源（经过构建处理）
    │   ├── images/
    │   └── fonts/
    │
    ├── components/               # 组件目录
    │   ├── ui/                   # 基础 UI 组件
    │   │   ├── Button.tsx
    │   │   ├── Input.tsx
    │   │   ├── Modal.tsx
    │   │   ├── Card.tsx
    │   │   ├── Badge.tsx
    │   │   ├── Avatar.tsx
    │   │   ├── Loading.tsx
    │   │   ├── Empty.tsx
    │   │   ├── Toast.tsx
    │   │   └── index.ts          # 统一导出
    │   │
    │   ├── layout/               # 布局组件
    │   │   ├── Header.tsx
    │   │   ├── Footer.tsx
    │   │   ├── Sidebar.tsx
    │   │   ├── MobileNav.tsx
    │   │   └── MainLayout.tsx
    │   │
    │   ├── common/               # 通用业务组件
    │   │   ├── InfoCard.tsx       # 信息卡片
    │   │   ├── CategoryIcon.tsx   # 分类图标
    │   │   ├── ValidityBadge.tsx  # 有效性状态标识
    │   │   ├── ImageGallery.tsx   # 图片画廊
    │   │   ├── CommentItem.tsx    # 评论项
    │   │   ├── UserAvatar.tsx     # 用户头像
    │   │   └── SearchBar.tsx      # 搜索栏
    │   │
    │   └── map/                  # 地图相关组件
    │       ├── CampusMap.tsx      # 地图容器
    │       ├── InfoMarker.tsx     # 信息标记
    │       ├── MapPopup.tsx       # 标记弹窗
    │       └── MapControls.tsx    # 地图控件
    │
    ├── pages/                    # 页面组件
    │   ├── Home/                 # 首页
    │   │   ├── index.tsx
    │   │   ├── RecommendFeed.tsx
    │   │   └── CategoryEntry.tsx
    │   │
    │   ├── Feed/                 # 信息流
    │   │   ├── index.tsx
    │   │   └── FeedList.tsx
    │   │
    │   ├── Map/                  # 地图页
    │   │   └── index.tsx
    │   │
    │   ├── Search/               # 搜索页
    │   │   └── index.tsx
    │   │
    │   ├── Category/             # 分类页
    │   │   ├── index.tsx
    │   │   └── CategoryDetail.tsx
    │   │
    │   ├── InfoDetail/           # 信息详情页
    │   │   ├── index.tsx
    │   │   ├── InfoContent.tsx
    │   │   ├── CommentSection.tsx
    │   │   └── ActionBar.tsx
    │   │
    │   ├── Publish/              # 发布页
    │   │   ├── index.tsx
    │   │   ├── StepCategory.tsx
    │   │   ├── StepLocation.tsx
    │   │   ├── StepContent.tsx
    │   │   ├── StepImages.tsx
    │   │   ├── StepTags.tsx
    │   │   └── StepPreview.tsx
    │   │
    │   ├── Profile/              # 个人中心
    │   │   ├── index.tsx
    │   │   ├── MyPosts.tsx
    │   │   ├── MyFavorites.tsx
    │   │   └── EditProfile.tsx
    │   │
    │   ├── Notifications/        # 通知页
    │   │   └── index.tsx
    │   │
    │   ├── Auth/                 # 认证页
    │   │   ├── Login.tsx
    │   │   └── Register.tsx
    │   │
    │   └── Admin/                # 管理后台
    │       ├── index.tsx
    │       ├── ReviewQueue.tsx
    │       └── ReportList.tsx
    │
    ├── hooks/                    # 自定义 Hooks
    │   ├── useAuth.ts            # 认证相关
    │   ├── useInfos.ts           # 信息 CRUD
    │   ├── useComments.ts        # 评论
    │   ├── useInteractions.ts    # 点赞
    │   ├── useNotifications.ts   # 通知
    │   ├── useMap.ts             # 地图
    │   ├── useSearch.ts          # 搜索
    │   └── useUpload.ts          # 文件上传
    │
    ├── services/                 # API 服务层
    │   ├── api.ts                # Axios 实例配置
    │   ├── auth.ts               # 认证 API
    │   ├── infos.ts              # 信息 API
    │   ├── comments.ts           # 评论 API
    │   ├── interactions.ts       # 互动 API
    │   ├── notifications.ts      # 通知 API
    │   ├── users.ts              # 用户 API
    │   ├── categories.ts         # 分类 API
    │   ├── locations.ts          # 地点 API
    │   ├── search.ts             # 搜索 API
    │   ├── upload.ts             # 上传 API
    │   └── admin.ts              # 管理 API
    │
    ├── stores/                   # Zustand 状态管理
    │   ├── useAuthStore.ts       # 认证状态（用户信息、Token）
    │   ├── useCampusStore.ts     # 校园选择状态
    │   ├── useUIStore.ts         # UI 状态（侧边栏、弹窗）
    │   └── usePublishStore.ts    # 发布流程状态（草稿）
    │
    ├── types/                    # TypeScript 类型定义
    │   ├── api.ts                # API 请求/响应类型
    │   ├── info.ts               # 信息相关类型
    │   ├── user.ts               # 用户相关类型
    │   ├── category.ts           # 分类类型
    │   ├── location.ts           # 地点类型
    │   └── common.ts             # 通用类型
    │
    ├── utils/                    # 工具函数
    │   ├── format.ts             # 格式化（日期、距离）
    │   ├── validate.ts           # 验证规则
    │   ├── storage.ts            # localStorage 封装
    │   ├── constants.ts          # 常量定义
    │   └── helpers.ts            # 辅助函数
    │
    ├── styles/                   # 全局样式
    │   └── globals.css           # Tailwind 入口 + 全局样式
    │
    └── config/                   # 配置
        └── env.ts                # 环境变量类型定义
```

### 3.2 路由设计

```typescript
// 路由配置
const routes = [
  // 公开路由（游客可访问）
  { path: '/',                  element: <Home /> },
  { path: '/feed',              element: <Feed /> },
  { path: '/map',               element: <MapPage /> },
  { path: '/search',            element: <Search /> },
  { path: '/category/:slug',    element: <CategoryDetail /> },
  { path: '/info/:id',          element: <InfoDetail /> },

  // 需要登录
  { path: '/publish',           element: <Publish /> },
  { path: '/info/:id/edit',     element: <EditInfo /> },
  { path: '/profile',           element: <Profile /> },
  { path: '/profile/posts',     element: <MyPosts /> },
  { path: '/notifications',     element: <Notifications /> },

  // 认证页面
  { path: '/login',             element: <Login /> },
  { path: '/register',          element: <Register /> },

  // 管理后台（需要管理员权限）
  { path: '/admin',             element: <AdminLayout /> },
  { path: '/admin/review',      element: <ReviewQueue /> },
  { path: '/admin/reports',     element: <ReportList /> },
];
```

**路由守卫策略：**

- 公开页面：游客和登录用户均可访问
- 受保护页面：未登录时重定向到登录页，登录后返回原页面
- 管理页面：检查用户角色是否为管理员

### 3.3 状态管理边界

#### Zustand 管理（客户端状态）

| 状态 | 说明 | 示例 |
|------|------|------|
| **认证状态** | 当前用户信息、Token、登录状态 | `user`, `token`, `isLoggedIn` |
| **校园状态** | 当前选择的校园 | `currentCampus`, `campusList` |
| **UI 状态** | 侧边栏开关、弹窗显示、主题模式 | `sidebarOpen`, `modalVisible`, `theme` |
| **发布草稿** | 发布流程中的临时数据 | `draft`, `currentStep`, `uploadedImages` |
| **搜索历史** | 本地搜索历史记录 | `searchHistory` |

#### TanStack Query 管理（服务端状态）

| 数据 | 说明 | 缓存策略 |
|------|------|----------|
| **信息列表** | 首页、信息流、分类页的信息列表 | 分页缓存，后台刷新 |
| **信息详情** | 单条信息的完整内容 | 按需缓存，过期刷新 |
| **评论列表** | 信息下的评论 | 分页缓存 |
| **搜索结果** | 搜索查询结果 | 短期缓存 |
| **用户信息** | 当前用户或他人公开信息 | 长期缓存 |
| **通知列表** | 用户通知 | 短期缓存，实时更新 |
| **分类列表** | 所有分类 | 长期缓存，极少变化 |
| **地图标记** | 当前视图范围内的标记 | 视图变化时刷新 |

#### 服务端状态 vs 客户端状态

| 特征 | 服务端状态 | 客户端状态 |
|------|-----------|-----------|
| **数据来源** | 后端 API | 本地 UI 交互 |
| **所有权** | 服务端是真实来源 | 客户端是唯一来源 |
| **同步需求** | 需要与服务端保持同步 | 无需同步 |
| **持久化** | 服务端持久化 | 通常不持久化（部分存 localStorage） |
| **共享性** | 多用户共享同一份数据 | 仅当前用户可见 |
| **管理工具** | TanStack Query | Zustand |

### 3.4 组件分层

```
┌─────────────────────────────────────┐
│          页面组件 (Pages)            │  路由入口，组合容器组件
│  /Home, /Feed, /InfoDetail, ...     │  负责数据获取和页面布局
├─────────────────────────────────────┤
│        容器组件 (Containers)         │  业务逻辑容器
│  InfoCardList, CommentSection, ...  │  连接数据与展示组件
├─────────────────────────────────────┤
│       通用业务组件 (Common)          │  跨页面复用的业务组件
│  InfoCard, ValidityBadge, ...       │  包含业务逻辑但可复用
├─────────────────────────────────────┤
│        UI 组件 (UI Components)       │  纯展示组件，无业务逻辑
│  Button, Input, Modal, Card, ...    │  通过 props 接收数据
└─────────────────────────────────────┘
```

---

## 4. 后端架构

### 4.1 后端关键目录

```
backend/
├── requirements.txt              # Python 依赖
├── alembic.ini                   # Alembic 配置
├── alembic/                      # 数据库迁移
│   └── versions/
├── app/
│   ├── main.py                   # FastAPI 应用入口
│   ├── config.py                 # 配置管理
│   ├── database.py               # 数据库连接
│   ├── dependencies.py           # 依赖注入
│   ├── api/                      # 路由层，互动写端点位于 interactions.py
│   ├── core/                     # 权限、租户、状态与验证契约
│   ├── jobs/                     # 自动过期等独立任务逻辑
│   ├── models/                   # SQLAlchemy 模型
│   ├── schemas/                  # Pydantic Schema
│   └── services/                 # AI 搜索、Embedding 等服务
├── scripts/                      # worker、回填和运维脚本
└── tests/                        # pytest 测试与独立测试库夹具
```

### 4.2 分层架构

```
请求 → 路由层 (API) → 服务层 (Service) → 数据层 (Model)
         ↓                  ↓                  ↓
    参数验证           业务逻辑           数据库操作
    权限检查           数据转换           查询构建
    响应格式化         异常处理           事务管理
```

**路由层 (API Layer)**

- 定义 API 端点和 HTTP 方法
- 接收和验证请求参数（Pydantic Schema）
- 调用服务层处理业务逻辑
- 格式化响应数据
- 不包含业务逻辑

**服务层 (Service Layer)**

- 实现核心业务逻辑
- 协调多个数据模型的操作
- 处理业务规则和约束
- 触发通知等副作用
- 可被多个路由复用

**数据层 (Data Layer)**

- 定义数据库表结构（SQLAlchemy Model）
- 执行数据库查询和更新
- 管理事务
- 不包含业务逻辑

### 4.3 中间件设计

| 中间件 | 职责 |
|--------|------|
| **CORS 中间件** | 处理跨域请求，配置允许的源、方法和头部 |
| **认证中间件** | 解析 JWT Token，注入当前用户信息到请求上下文 |
| **日志中间件** | 记录每个请求的方法、路径、状态码、耗时 |
| **异常处理中间件** | 捕获未处理异常，返回统一错误格式 |
| **请求限流中间件** | 防止 API 滥用（后续使用 Redis 实现） |

### 4.4 错误处理

**统一错误响应格式：**

```json
{
  "error": {
    "code": "INFO_NOT_FOUND",
    "message": "信息不存在或已被删除",
    "details": null
  }
}
```

**错误码分类：**

| 错误码 | HTTP 状态码 | 说明 |
|--------|------------|------|
| `VALIDATION_ERROR` | 400 | 请求参数验证失败 |
| `UNAUTHORIZED` | 401 | 未认证或 Token 过期 |
| `FORBIDDEN` | 403 | 无权限执行操作 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `CONFLICT` | 409 | 资源冲突（如重复操作） |
| `RATE_LIMITED` | 429 | 请求过于频繁 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |

---

## 5. 前后端通信

### 5.1 RESTful API 通信方式

**基础规范：**

- 基础 URL：`/api/v1`
- 数据格式：JSON
- 字符编码：UTF-8
- 认证方式：Bearer Token（JWT）

**HTTP 方法语义：**

| 方法 | 语义 | 示例 |
|------|------|------|
| `GET` | 获取资源 | `GET /api/v1/infos` |
| `POST` | 创建资源 | `POST /api/v1/infos` |
| `PUT` | 全量更新资源 | `PUT /api/v1/infos/{id}` |
| `PATCH` | 部分更新资源 | `PATCH /api/v1/infos/{id}` |
| `DELETE` | 删除资源 | `DELETE /api/v1/infos/{id}` |

### 5.2 请求/响应格式

**请求示例：**

```
GET /api/v1/infos?category=food&sort=latest&page=1&page_size=20
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**成功响应：**

```json
{
  "data": {
    "items": [
      {
        "id": 1,
        "title": "三食堂二楼的麻辣香锅",
        "category": { "id": 1, "name": "校园美食", "slug": "food" },
        "location": { "id": 10, "name": "三食堂二楼" },
        "summary": "味道不错，分量足，价格15元左右",
        "images": ["https://.../image1.jpg"],
        "governance": {
          "confirmation_count": 12,
          "refutation_count": 1,
          "validity_status": "valid"
        },
        "stats": { "likes": 25, "comments": 8 },
        "author": { "id": 1, "nickname": "小明", "avatar": "https://..." },
        "is_anonymous": false,
        "created_at": "2026-06-15T10:30:00Z",
        "updated_at": "2026-06-15T10:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 156,
      "total_pages": 8
    }
  }
}
```

### 5.3 错误码规范

**业务错误码：**

| 错误码 | HTTP 状态码 | 说明 |
|--------|------------|------|
| `AUTH_INVALID_CREDENTIALS` | 401 | 用户名或密码错误 |
| `AUTH_TOKEN_EXPIRED` | 401 | Token 已过期 |
| `AUTH_ACCOUNT_LOCKED` | 403 | 账户已锁定 |
| `INFO_NOT_FOUND` | 404 | 信息不存在 |
| `INFO_ALREADY_DELETED` | 409 | 信息已被删除 |
| `COMMENT_TOO_LONG` | 400 | 评论超过长度限制 |
| `DUPLICATE_LIKE` | 409 | 重复点赞 |
| `DUPLICATE_REPORT` | 409 | 重复举报 |
| `UPLOAD_FILE_TOO_LARGE` | 400 | 上传文件过大 |
| `UPLOAD_INVALID_FORMAT` | 400 | 不支持的文件格式 |
| `CAMPUS_NOT_SELECTED` | 400 | 未选择校园 |

### 5.4 文件上传方式

**上传流程：**

```
1. 前端选择图片 → 前端压缩（可选）
2. POST /api/v1/upload/image
   Content-Type: multipart/form-data
   Body: { file: <binary> }
3. 后端接收 → 验证格式和大小 → 生成唯一文件名 → 保存
4. 返回图片 URL
```

**上传限制：**

- 支持格式：JPG、PNG、GIF、WebP
- 单张大小：不超过 5MB
- 每条信息最多 9 张图片
- 图片自动压缩（宽度超过 1920px 时缩放）
- 生成缩略图（300x300）用于列表展示

**上传响应：**

```json
{
  "data": {
    "url": "https://.../uploads/images/2026/06/abc123.jpg",
    "thumbnail_url": "https://.../uploads/images/2026/06/abc123_thumb.jpg",
    "width": 1920,
    "height": 1080,
    "size": 245678
  }
}
```

---

## 6. 地图服务方案

### 6.1 MapLibre GL JS 方案说明

**选择 MapLibre GL JS 的理由：**

- **开源免费**：基于 BSD 许可，无 API Key 要求，无调用次数限制
- **WebGL 渲染**：使用 GPU 加速，支持数千标记流畅渲染
- **矢量瓦片**：支持矢量瓦片地图，缩放平滑，样式自定义能力强
- **兼容 Mapbox**：API 与 Mapbox GL JS 兼容，迁移成本低
- **活跃社区**：由 Mapbox GL JS 开源分支发展，社区活跃

**核心使用场景：**

- 校园地图展示（底图 + 校园范围）
- 信息标记点展示（按分类着色）
- 标记点击弹窗（显示信息摘要）
- 发布时选择地点（点击地图获取坐标）
- 缩放级别动态控制标记密度

### 6.2 瓦片地图数据源

| 数据源 | 说明 | 适用场景 |
|--------|------|----------|
| **OpenStreetMap** | 免费开源的全球地图数据 | 底图数据源 |
| **MapTiler** | 提供免费的矢量瓦片服务 | 快速接入，每月 10 万次免费请求 |
| **Stadia Maps** | 提供多种地图样式 | 备用瓦片服务 |
| **自建瓦片服务** | 使用 tileserver-gl 部署 | 完全自定义，无外部依赖 |

**第一版方案：** 使用 MapTiler 免费层 + OpenStreetMap 数据，后续根据用量考虑自建。

### 6.3 备选方案 Leaflet

| 对比项 | MapLibre GL JS | Leaflet |
|--------|---------------|---------|
| 渲染方式 | WebGL（GPU 加速） | SVG / Canvas（CPU） |
| 标记性能 | 数千标记流畅 | 数百标记开始卡顿 |
| 矢量瓦片 | 原生支持 | 需要插件 |
| 3D 支持 | 支持 | 不支持 |
| 包体积 | ~200KB | ~40KB |
| 学习曲线 | 中等 | 低 |
| 兼容性 | 现代浏览器 | 所有浏览器（含 IE） |

**结论：** 校园地图需要展示大量标记点，MapLibre 的 WebGL 渲染性能优势明显。Leaflet 虽然轻量，但性能无法满足需求。

### 6.4 坐标系统

- **唯一业务坐标系：** GCJ-02，与高德栅格底图及未来微信地图保持一致
- **地图投影：** Web Mercator；MapLibre 负责屏幕投影，业务经纬度仍按 GCJ-02 解释
- **浏览器定位：** `navigator.geolocation` 的 WGS-84 结果先转换为 GCJ-02 再用于地图
- **后端存储与 API：** `longitude` / `latitude`、学校中心、地图边界、距离搜索和导入数据均使用 GCJ-02
- **详细目录：** 见 [GCJ-02 坐标规范与三校点位目录](35_GCJ02坐标规范与三校点位目录.md)

---

## 7. 图片存储方案

### 7.1 第一版：本地存储

**方案说明：**

- 图片保存在服务器本地文件系统
- 目录结构：`uploads/images/{year}/{month}/{uuid}.{ext}`
- 缩略图：`uploads/images/{year}/{month}/{uuid}_thumb.{ext}`
- 通过 FastAPI 静态文件服务提供访问

**优点：** 零成本、零配置、开发调试方便  
**缺点：** 不支持水平扩展、单点存储风险、占用服务器磁盘

### 7.2 后续：对象存储

**迁移方案：**

- 使用阿里云 OSS / 腾讯云 COS / AWS S3
- 通过抽象存储接口，切换存储后端只需修改配置
- 图片通过 CDN 分发，提升加载速度

**存储接口抽象：**

```python
class StorageBackend:
    async def upload(self, file: bytes, path: str) -> str: ...
    async def delete(self, path: str) -> None: ...
    async def get_url(self, path: str) -> str: ...

class LocalStorage(StorageBackend): ...      # 本地存储
class OSSStorage(StorageBackend): ...         # 阿里云 OSS
```

### 7.3 图片压缩和缩略图

**处理流程：**

```
原图上传 → 格式验证 → 尺寸检查
    ↓
宽度 > 1920px → 等比缩放至 1920px
    ↓
质量压缩（JPEG quality=85）
    ↓
保存原图（压缩后）
    ↓
生成缩略图（300x300，居中裁剪）
    ↓
返回原图 URL + 缩略图 URL
```

**处理库：** Python Pillow（PIL Fork）

---

## 8. 数据库方案

### 8.1 openGauss 7.0（唯一数据库）

**选择理由：**

- 国产化：华为开源，自主可控
- 兼容 PostgreSQL 协议：使用 asyncpg 驱动，SQLAlchemy 通过 PostgreSQL dialect 访问
- 功能丰富：支持 JSON、全文搜索、地理空间数据
- 性能优秀：支持并发读写，适合生产负载
- 轻量版容器：部署简单，资源占用低

**连接配置：**

```python
# backend/app/config.py
DATABASE_URL: str = "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus"
```

**注意事项：**

- 密码中 `@` 需转义为 `%40`
- 主键与外键类型按 openGauss 方言保持一致，不再保留 SQLite 运行分支
- 测试只连接 `TEST_DATABASE_URL` 指向的独立 openGauss 测试库，并强制校验库名包含 `_test` 且不等于开发库地址

### 8.2 数据库迁移方案（Alembic）

**工作流程：**

```
1. 修改 SQLAlchemy Model
2. 运行 alembic revision --autogenerate -m "描述"
3. 检查生成的迁移脚本
4. 运行 alembic upgrade head 应用迁移
5. 提交迁移脚本到版本控制
```

**迁移原则：**

- 每次 Schema 变更必须生成迁移脚本
- 迁移脚本必须可回滚（提供 `downgrade` 方法）
- 迁移脚本纳入 Git 版本管理
- 生产环境部署前执行 `alembic upgrade head`

---

## 9. 认证方案

### 9.1 JWT 认证流程

```
1. 用户提交用户名/邮箱 + 密码
   POST /api/v1/auth/login

2. 后端验证凭据
   - 查找用户
   - 验证密码（bcrypt 哈希比对）
   - 检查账户状态

3. 验证通过，签发 JWT
   - Access Token：有效期 30 分钟
   - Refresh Token：有效期 7 天
   - Token 中包含：user_id, role, campus_id

4. 前端保存 Token
   - Access Token → 内存（Zustand）
   - Refresh Token → HttpOnly Cookie 或 localStorage

5. 后续请求携带 Token
   Authorization: Bearer <access_token>

6. 后端中间件验证 Token
   - 解析 JWT
   - 检查有效期
   - 注入用户信息到请求上下文
```

### 9.2 Token 刷新机制

```
Access Token 过期
    ↓
前端检测到 401 响应
    ↓
使用 Refresh Token 请求新 Token
POST /api/v1/auth/refresh
    ↓
后端验证 Refresh Token
    ↓
签发新的 Access Token + Refresh Token
    ↓
前端更新 Token，重试原请求
```

**安全策略：**

- Access Token 短有效期（30 分钟），减少泄露风险
- Refresh Token 长有效期（7 天），支持轮换（每次刷新签发新 Refresh Token）
- Refresh Token 使用后立即失效（一次性使用）
- 支持主动注销（用户退出时清除所有 Token）

### 9.3 权限控制

**角色定义：**

| 角色 | 权限 |
|------|------|
| **游客** | 浏览公开信息、搜索、查看详情 |
| **用户** | 游客权限 + 发布、编辑、删除自己的信息、点赞、评论、有效性确认、举报 |
| **管理员** | 用户权限 + 审核内容、处理举报、管理分类和校园 |

**实现方式：**

- 路由级别：通过依赖注入检查用户角色
- 资源级别：检查资源所有权（只能编辑/删除自己的内容）

```python
# 路由级权限
@router.get("/admin/review")
async def review_queue(
    current_user: User = Depends(get_current_admin)  # 需要管理员角色
):
    ...

# 资源级权限
@router.delete("/infos/{info_id}")
async def delete_info(
    info_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    info = await info_service.get(db, info_id)
    if info.author_id != current_user.id:
        raise ForbiddenException("只能删除自己的信息")
    ...
```

---

## 10. 日志方案

### 10.1 前端日志

| 日志类型 | 内容 | 存储方式 |
|----------|------|----------|
| **操作日志** | 用户关键操作（发布、编辑、删除） | 发送到后端 API |
| **错误日志** | JS 运行时错误、API 请求失败 | 发送到后端 API |
| **性能日志** | 页面加载时间、API 响应时间 | 开发环境 console，生产环境上报 |

**实现方式：**

- 开发环境：`console.log/warn/error` + Vite 控制台
- 生产环境：封装 `logger` 工具，关键日志通过 API 上报
- 错误边界：React Error Boundary 捕获组件渲染错误

### 10.2 后端日志

| 日志类型 | 内容 | 说明 |
|----------|------|------|
| **请求日志** | 方法、路径、状态码、耗时、IP | 每个请求记录 |
| **业务日志** | 关键业务操作（登录、发布、审核） | 包含操作者和目标 |
| **错误日志** | 异常堆栈、请求上下文 | 未捕获异常和已知错误 |
| **安全日志** | 认证失败、权限拒绝、异常行为 | 安全审计 |

**实现方式：**

- 使用 Python 标准 `logging` 模块
- 配置结构化日志格式（JSON 格式便于后续接入日志系统）
- 开发环境输出到控制台，生产环境输出到文件

### 10.3 日志级别

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| `DEBUG` | 开发调试信息 | SQL 查询、函数入参出参 |
| `INFO` | 正常业务事件 | 用户登录、信息发布、审核通过 |
| `WARNING` | 异常但可恢复 | Token 过期、文件不存在、参数边界值 |
| `ERROR` | 错误但系统可运行 | API 调用失败、数据库连接超时 |
| `CRITICAL` | 系统不可用 | 数据库连接失败、磁盘空间不足 |

**环境策略：**

- 开发环境：`DEBUG` 级别
- 生产环境：`INFO` 级别
- 安全相关日志：始终记录

---

## 11. 配置管理

### 11.1 环境变量管理

**原则：**

- 敏感信息（密钥、数据库密码）不写入代码
- 不同环境使用不同的 `.env` 文件
- `.env` 文件不纳入版本控制（`.gitignore`）
- 提供 `.env.example` 作为配置模板

**文件结构：**

```
.env                # 默认配置（纳入版本控制，不含敏感信息）
.env.development    # 开发环境配置
.env.production     # 生产环境配置
.env.local          # 本地覆盖（不纳入版本控制）
```

### 11.2 前端配置

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_MAP_TILE_URL=https://api.maptiler.com/maps/streets/style.json
VITE_MAP_API_KEY=dev_key
VITE_APP_TITLE=此刻校园（开发）

# .env.production
VITE_API_BASE_URL=https://api.momentcampus.com/api/v1
VITE_MAP_TILE_URL=https://api.maptiler.com/maps/streets/style.json
VITE_MAP_API_KEY=prod_key
VITE_APP_TITLE=此刻校园
```

**前端环境变量类型定义：**

```typescript
// src/config/env.ts
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_MAP_TILE_URL: string
  readonly VITE_MAP_API_KEY: string
  readonly VITE_APP_TITLE: string
}
```

### 11.3 后端配置

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "此刻校园"
    APP_ENV: str = "opengauss"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # 数据库（openGauss，asyncpg 异步驱动）
    DATABASE_URL: str = "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"]

    # 日志
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env.opengauss"

settings = Settings()
```

---

## 12. 测试方案

### 12.1 前端测试（Vitest + Testing Library）

| 测试类型 | 工具 | 覆盖范围 |
|----------|------|----------|
| **单元测试** | Vitest | 工具函数、Hooks、Store |
| **组件测试** | Vitest + Testing Library | UI 组件渲染、交互 |
| **集成测试** | Vitest + MSW | API Mock + 组件交互流程 |

**测试重点：**

- 表单验证逻辑（React Hook Form + Zod）
- 状态管理逻辑（Zustand Store）
- API 请求逻辑（TanStack Query Hooks）
- 关键 UI 交互（发布流程、搜索、筛选）

**示例：**

```typescript
// tests/components/InfoCard.test.tsx
import { render, screen } from '@testing-library/react'
import { InfoCard } from '@/components/common/InfoCard'

describe('InfoCard', () => {
  it('renders info title and category', () => {
    render(<InfoCard info={mockInfo} />)
    expect(screen.getByText(mockInfo.title)).toBeInTheDocument()
    expect(screen.getByText(mockInfo.category.name)).toBeInTheDocument()
  })

  it('shows validity badge', () => {
    render(<InfoCard info={mockInfo} />)
    expect(screen.getByText('仍然有效')).toBeInTheDocument()
  })
})
```

### 12.2 后端测试（pytest）

| 测试类型 | 工具 | 覆盖范围 |
|----------|------|----------|
| **单元测试** | pytest | 服务层业务逻辑 |
| **集成测试** | pytest + httpx | API 端点完整流程 |
| **数据库测试** | pytest + test DB | 数据模型和查询 |

**测试策略：**

- 使用独立 openGauss 测试库，只从 `TEST_DATABASE_URL` 读取连接串
- 数据库名必须包含 `_test`，且不得与开发库连接相同；任一条件不满足时在清理数据前直接停止
- 测试会话创建 ORM 表结构，用按外键逆序的 `DELETE` 清理数据并重置序列
- 使用 `conftest.py` 管理测试 fixtures，Python 命令必须通过 `backend/.venv` 执行

### 12.3 现行后台任务与混合检索

- 自动过期由独立 `moment-expire-posts.timer` 在系统启动后 5 分钟首次触发 oneshot worker，此后每 30 分钟触发一次，避免 4 个 Uvicorn worker 重复调度
- 任务使用数据库 advisory lock、60 分钟脏任务租约、运行记录和幂等通知；手动接口仅 `super_admin` 可调用
- AI 搜索先限定当前租户、公开状态和有效期，再使用 DataVec 语义候选与结构化条件检索
- 排序权重为语义 35%、新鲜度 25%、验证数 20%、关键词 20%；Embedding 或向量查询失败时回退关键词检索
- 分类由当前学校 API 动态提供，前端通过 `category.code` 稳定计算视觉，不使用固定 ID/名称映射

**示例：**

```python
# tests/test_infos.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_info(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/infos",
        json={
            "title": "测试信息",
            "description": "测试描述内容超过十个字符",
            "category_id": 1,
            "location_id": 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["data"]["title"] == "测试信息"

@pytest.mark.asyncio
async def test_create_info_unauthorized(client: AsyncClient):
    response = await client.post(
        "/api/v1/infos",
        json={"title": "测试"},
    )
    assert response.status_code == 401
```

### 12.4 E2E 测试（Playwright）

| 测试场景 | 说明 |
|----------|------|
| **用户注册登录** | 注册 → 登录 → 选择校园 → 进入首页 |
| **发布信息** | 选择分类 → 选择地点 → 填写内容 → 上传图片 → 发布 |
| **浏览搜索** | 首页浏览 → 分类筛选 → 搜索 → 查看详情 |
| **互动操作** | 点赞 → 评论 → 有效性确认 |
| **管理审核** | 登录管理员 → 查看待审核 → 通过/拒绝 |

**示例：**

```typescript
// e2e/publish-info.spec.ts
import { test, expect } from '@playwright/test'

test.describe('发布信息', () => {
  test('完整发布流程', async ({ page }) => {
    // 登录
    await page.goto('/login')
    await page.fill('[name="username"]', 'testuser')
    await page.fill('[name="password"]', 'password123')
    await page.click('button[type="submit"]')

    // 进入发布页
    await page.goto('/publish')

    // 选择分类
    await page.click('[data-category="food"]')

    // 填写内容
    await page.fill('[name="title"]', '三食堂麻辣香锅推荐')
    await page.fill('[name="description"]', '味道不错，分量足...')

    // 发布
    await page.click('button:has-text("发布")')

    // 验证跳转到详情页
    await expect(page).toHaveURL(/\/info\/\d+/)
  })
})
```

---

## 13. 部署方案

### 13.1 开发环境部署

**前端：**

```bash
cd frontend
npm install
npm run dev          # 启动 Vite 开发服务器 (localhost:5173)
```

**后端：**

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head # 初始化数据库
uvicorn main:app --reload --port 8000
```

**数据库：** openGauss 7.0 容器（详见 `deploy/docker-compose.yml`）

### 13.2 生产环境部署

**架构：**

```
                    ┌─────────────┐
                    │   Nginx     │
                    │  反向代理    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │ 静态文件   │ │ API   │ │ WebSocket │
        │ (前端SPA) │ │ 服务  │ │ (后续)    │
        └───────────┘ └───┬───┘ └───────────┘
                          │
                    ┌─────┴─────┐
                    │ openGauss  │
                    │  7.0       │
                    └───────────┘
```

**Nginx 配置要点：**

- `/` → 前端静态文件
- `/api/` → 反向代理到 FastAPI（uvicorn）
- 静态资源缓存策略
- Gzip 压缩
- HTTPS（Let's Encrypt）

### 13.3 Docker 容器化

**docker-compose.yml：**

```yaml
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=opengauss
      - DATABASE_URL=postgresql+asyncpg://gaussdb:Gaussdb%40123@db:5432/moment_campus
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - opengauss
    volumes:
      - uploads:/app/uploads

  opengauss:
    image: opengauss:7.0.0-RC3
    environment:
      GAUSSD_INITDB_ROOT_USERNAME: gaussdb
      GAUSSD_INITDB_ROOT_PASSWORD: Gaussdb@123
      GAUSSD_INITDB_DATABASE: moment_campus
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/opengauss/data

volumes:
  pgdata:
  uploads:
```

### 13.4 CI/CD 规划

**GitHub Actions 工作流：**

```
代码推送 / PR
    ↓
1. 代码检查（ESLint + Ruff）
    ↓
2. 类型检查（TypeScript + mypy）
    ↓
3. 单元测试（Vitest + pytest）
    ↓
4. 构建检查（Vite build）
    ↓
5. E2E 测试（Playwright）
    ↓
6. 构建 Docker 镜像
    ↓
7. 部署到测试/生产环境
```

**分支策略：**

| 分支 | 用途 | 部署目标 |
|------|------|----------|
| `main` | 生产代码 | 生产环境 |
| `develop` | 开发集成 | 测试环境 |
| `feature/*` | 功能开发 | - |
| `hotfix/*` | 紧急修复 | 生产环境 |

---

## 14. 相关文档

- [项目总览](00_project_overview.md)
- [产品需求文档](01_product_requirements.md)
- [功能范围与优先级](03_feature_scope_and_priority.md)
- [安全与隐私](14_security_and_privacy.md)
