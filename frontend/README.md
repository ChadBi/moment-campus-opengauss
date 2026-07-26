# 此刻校园 - 前端

> 多租户校园信息共享平台前端，基于 React 19 + TypeScript + Vite + Tailwind CSS。

## 技术栈

- **框架**：React 19.2 + TypeScript 5.x
- **构建**：Vite 7（Rolldown 引擎）
- **路由**：React Router 7
- **状态**：Zustand（轻量全局状态）+ React Query（服务端状态，按需使用）
- **HTTP**：Axios（拦截器自动注入 Bearer Token + X-School-Code 多租户头）
- **样式**：Tailwind CSS 4 + 自定义设计 token（src/styles/tokens.ts）
- **地图**：MapLibre GL（栅格瓦片，国内默认走高德栅格源）
- **图标**：lucide-react
- **PWA**：Vite PWA 插件（service worker 自动注册）
- **ESLint**：react-hooks + react-refresh + typescript-eslint（0 error，set-state-in-effect 降级为 warning）

## 目录结构

```
frontend/
├── public/                 # 静态资源（PWA manifest, icons）
├── src/
│   ├── components/         # 通用组件（ui/ 基础组件 + 业务组件）
│   │   ├── ui/             # Avatar/Badge/Button/Card/Input/Loading/Modal/Table/Toast
│   │   └── layout/         # Header/MainLayout/MobileNav/Sidebar/SchoolSwitcher
│   ├── hooks/              # 自定义 hooks（useSchoolSync, useServiceWorker 等）
│   ├── pages/              # 页面组件
│   │   ├── admin/          # 管理后台页面（22 个）
│   │   └── *.tsx           # 用户端页面（首页/地图/搜索/帖子详情/个人中心等）
│   ├── services/           # API 服务封装（按模块拆分：auth/posts/comments/search 等）
│   ├── store/              # Zustand stores（useAuthStore, useCampusStore, useUIStore）
│   ├── styles/             # 设计 token 定义
│   ├── types/              # TypeScript 类型定义
│   └── utils/              # 工具函数（logger, date）
├── e2e/                    # Playwright E2E 测试
├── eslint.config.js        # ESLint 配置（flat config）
├── nginx.conf              # 生产 nginx 配置（同源代理 /api → backend:8000）
├── tsconfig.app.json       # TypeScript 应用配置
├── tsconfig.json           # TypeScript 根配置
├── tsconfig.node.json      # TypeScript Node 配置
└── vite.config.ts          # Vite 配置（含 manualChunks 拆分）
```

## 开发

### 环境要求

- Node.js ≥ 20
- npm ≥ 10

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
# 默认 http://localhost:5173
# 后端默认连接 http://localhost:8000/api/v1（可通过 .env.development 修改）
```

### 环境变量

复制 `.env.example` 为 `.env.development`，按需修改：

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

生产构建通过 Docker `ARG VITE_API_BASE_URL=/api/v1` 注入同源路径（详见 `Dockerfile`）。

### 构建生产版本

```bash
npm run build
# 输出到 dist/
# chunk 拆分：maplibre-gl / react-vendor / icons / 业务代码
```

### 代码检查

```bash
npm run lint        # ESLint 检查
npx tsc --noEmit    # TypeScript 类型检查
```

## 多租户机制

前端通过 Axios 请求拦截器自动注入 `X-School-Code` 头实现租户隔离：

- 用户切换学校时，`useCampusStore` 更新 `currentSchoolCode`
- 拦截器在所有需租户上下文的请求中注入 `X-School-Code: <code>` 头
- 公开接口（`/schools`, `/auth/login`, `/auth/refresh` 等）跳过注入
- 后端根据 header 解析 school_id 并强制作用于写请求

## 演示账号

- 管理员：`admin@momentcampus.com / pass123`
- 普通用户：`user1@example.com ~ user10@example.com / pass123`

## 关键设计决策

### Chunk 拆分（P2-001）

`vite.config.ts` 配置 `manualChunks` 函数，将 maplibre-gl / react-dom / lucide-react 拆分为独立 chunk：
- MapPage 业务代码从 1043KB 降至 16KB
- 首屏 index.js 从 307KB 降至 128KB
- maplibre-gl 仅在访问地图页时按需加载

### Logger 工具（P2-007）

`src/utils/logger.ts` 提供 dev 打印 / prod 静默的日志能力，替换散落的 48 处 `console.*` 调用。

### 401 并发刷新加锁（P2-006）

`src/services/api.ts` 响应拦截器使用 `refreshPromise` 单例，多个并发 401 请求复用同一 refresh promise，避免 refresh_token 被多次消费。

### 瓦片源（P2-008）

MapPage 默认使用高德栅格瓦片（`webrd0{1-4}.is.autonavi.com`），国内访问可达性优于 OSM。如需切换瓦片源，修改 `MapPage.tsx` 中的 `sources.amap.tiles` 配置。

## 部署

生产部署通过 Docker 构建静态文件，由 nginx 提供：

```bash
docker compose -f deploy/docker-compose.prod.yml up --build
# 前端 nginx 监听 80，/api/* 反向代理到 backend:8000
# 生产关闭 /docs 与 /openapi.json 对外暴露（P3-006）
```

详见 `Dockerfile` 与 `nginx.conf`。

## 相关文档

- [项目根 README](../README.md)
- [项目优化实施计划](../.trae/documents/项目优化实施计划.md)
- [全量排查报告](../docs/project-audit/此刻校园项目全量排查报告.md)
- [更新日志](../CHANGELOG.md)
- [任务进度](../TODO.md)
