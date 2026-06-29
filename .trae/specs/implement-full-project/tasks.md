# 此刻校园 - 完整项目开发任务清单

## 阶段一：项目初始化与基础配置

### 任务 1.1：创建前端项目结构
- [x] 1.1.1 初始化 React + TypeScript + Vite 项目
  - 执行 `npm create vite@latest frontend -- --template react-ts`
  - 配置项目基础目录结构
- [x] 1.1.2 配置 Tailwind CSS
  - 安装 tailwindcss, postcss, autoprefixer
  - 生成 tailwind.config.js 和 postcss.config.js
  - 配置 design token（颜色、字体、间距）
- [x] 1.1.3 配置代码规范工具
  - 配置 ESLint + Prettier
  - 配置路径别名（@/ -> src/）
  - 配置 TypeScript 严格模式
- [x] 1.1.4 安装核心依赖
  - React Router v6（路由管理）
  - Zustand（状态管理）
  - TanStack Query（服务端状态）
  - Axios（HTTP 客户端）
  - React Hook Form + Zod（表单验证）
  - MapLibre GL JS（地图）
  - Lucide React（图标库）
- [x] 1.1.5 验证前端项目可正常启动
  - 执行 `npm run dev` 确认启动成功
  - 确认无 TypeScript 错误
  - 确认 Tailwind CSS 生效

### 任务 1.2：创建后端项目结构
- [x] 1.2.1 初始化 FastAPI 项目
  - 创建 backend/ 目录结构
  - 创建 requirements.txt（fastapi, uvicorn, sqlalchemy, alembic, pydantic, python-jose, passlib, python-multipart）
  - 创建 .env.example 配置文件
- [x] 1.2.2 配置数据库连接
  - 配置 SQLAlchemy 异步引擎
  - 配置 SQLite 开发数据库（dev.db）
  - 配置 PostgreSQL 生产数据库连接（可选）
- [x] 1.2.3 配置 Alembic 数据库迁移
  - 初始化 Alembic
  - 配置 alembic.ini
  - 配置 env.py 支持异步迁移
- [x] 1.2.4 配置 CORS 和中间件
  - 配置 CORS 允许前端域名
  - 配置日志中间件
  - 配置异常处理中间件
- [x] 1.2.5 验证后端项目可正常启动
  - 执行 `uvicorn main:app --reload` 确认启动成功
  - 访问 /docs 确认 Swagger 文档可用
  - 确认数据库连接正常

### 任务 1.3：创建开发环境配置
- [x] 1.3.1 创建环境变量文件
  - 前端：.env.development, .env.production
  - 后端：.env.development, .env.production
- [x] 1.3.2 创建 .gitignore 文件
  - 前端：node_modules, dist, .env.local
  - 后端：__pycache__, *.pyc, .env, dev.db, uploads/
- [x] 1.3.3 创建 README.md
  - 项目简介
  - 技术栈说明
  - 快速启动指南
  - 开发环境要求

---

## 阶段二：数据库设计与实现

### 任务 2.1：创建数据模型（SQLAlchemy）
- [x] 2.1.1 创建 User 模型
  - 定义字段：id, email, nickname, password_hash, avatar_url, school_id, role, bio, is_active, last_login_at, created_at, updated_at, is_deleted, deleted_at
  - 定义关系：posts, comments, likes, favorites, notifications
  - 添加唯一约束和索引
- [x] 2.1.2 创建 School 模型
  - 定义字段：id, name, code, logo_url, province, city, address, center_lat, center_lng, map_zoom, is_active, created_at, updated_at
  - 定义关系：users, posts, locations
- [x] 2.1.3 创建 Post 模型
  - 定义字段：id, user_id, school_id, category_id, post_type_id, location_id, title, content, is_anonymous, status, view_count, like_count, comment_count, favorite_count, valid_count, invalid_count, expire_at, activity_start_at, activity_end_at, lost_type, contact_info, is_top, is_recommend, created_at, updated_at, is_deleted, deleted_at
  - 定义关系：user, school, category, post_type, location, tags, images, comments, likes, favorites, validation_records
- [x] 2.1.4 创建 Category 模型
  - 定义字段：id, name, code, icon, description, default_validity_days, sort_order, is_active, created_at, updated_at
  - 定义关系：posts
- [x] 2.1.5 创建 PostType 模型
  - 定义字段：id, name, code, description, sort_order, is_active, created_at, updated_at
  - 定义关系：posts
- [x] 2.1.6 创建 Tag 模型
  - 定义字段：id, name, slug, usage_count, is_official, created_at, updated_at, is_deleted, deleted_at
  - 定义关系：posts（通过 PostTag）
- [x] 2.1.7 创建 PostTag 关联模型
  - 定义字段：id, post_id, tag_id, created_at
  - 定义唯一约束：(post_id, tag_id)
- [x] 2.1.8 创建 PostImage 模型
  - 定义字段：id, post_id, image_url, thumbnail_url, sort_order, file_size, width, height, created_at, is_deleted, deleted_at
  - 定义关系：post
- [x] 2.1.9 创建 Location 模型
  - 定义字段：id, school_id, name, description, latitude, longitude, floor, building, post_count, is_verified, created_at, updated_at, is_deleted, deleted_at
  - 定义关系：school, posts
- [x] 2.1.10 创建 Comment 模型
  - 定义字段：id, post_id, user_id, parent_id, reply_to_user_id, content, like_count, status, created_at, updated_at, is_deleted, deleted_at
  - 定义关系：post, user, parent, replies
- [x] 2.1.11 创建 Like 模型
  - 定义字段：id, post_id, user_id, created_at
  - 定义唯一约束：(post_id, user_id)
- [x] 2.1.12 创建 Favorite 模型
  - 定义字段：id, post_id, user_id, created_at
  - 定义唯一约束：(post_id, user_id)
- [x] 2.1.13 创建 ValidationRecord 模型
  - 定义字段：id, post_id, user_id, validation_type, comment, created_at
  - 定义关系：post, user
- [x] 2.1.14 创建 Report 模型
  - 定义字段：id, post_id, comment_id, reporter_id, report_type, description, status, handler_id, handle_result, handled_at, created_at, updated_at
  - 定义关系：post, comment, reporter, handler
- [x] 2.1.15 创建 Notification 模型
  - 定义字段：id, user_id, type, title, content, target_type, target_id, actor_id, is_read, read_at, created_at, is_deleted, deleted_at
  - 定义关系：user, actor
- [x] 2.1.16 创建 TopicCollection 模型
  - 定义字段：id, title, description, cover_url, school_id, creator_id, post_count, view_count, status, sort_order, published_at, created_at, updated_at, is_deleted, deleted_at
  - 定义关系：school, creator, posts（通过 TopicCollectionPost）
- [x] 2.1.17 创建 TopicCollectionPost 关联模型
  - 定义字段：id, topic_collection_id, post_id, sort_order, created_at
  - 定义唯一约束：(topic_collection_id, post_id)
- [x] 2.1.18 创建 Draft 模型
  - 定义字段：id, user_id, title, content, category_id, post_type_id, location_id, is_anonymous, extra_data, created_at, updated_at, is_deleted, deleted_at
  - 定义关系：user, category, post_type, location
- [x] 2.1.19 创建 BrowseHistory 模型
  - 定义字段：id, user_id, post_id, created_at
  - 定义关系：user, post
- [x] 2.1.20 创建 SearchHistory 模型
  - 定义字段：id, user_id, keyword, result_count, created_at
  - 定义关系：user
- [x] 2.1.21 创建 AdminOperationLog 模型
  - 定义字段：id, admin_id, action, target_type, target_id, detail, ip_address, user_agent, created_at
  - 定义关系：admin

### 任务 2.2：执行数据库迁移
- [x] 2.2.1 生成初始迁移脚本
  - 执行 `alembic revision --autogenerate -m "Initial migration"`
  - 检查生成的迁移脚本
- [x] 2.2.2 应用迁移
  - 执行 `alembic upgrade head`
  - 验证所有表创建成功
- [x] 2.2.3 创建索引和约束
  - 验证所有索引创建成功
  - 验证唯一约束生效

### 任务 2.3：填充演示数据
- [x] 2.3.1 创建演示数据脚本
  - 创建 2 所学校（华东师范大学、复旦大学）
  - 创建 12 个分类
  - 创建 3 个信息类型（normal, event, lost_found）
  - 创建 10 个测试用户
  - 创建 15 个地点
  - 创建 30 条信息
  - 创建 40 条评论
  - 创建 20 条有效性记录
  - 创建 10 条通知
  - 创建 6 个专题
  - 创建 10 条举报记录
- [x] 2.3.2 执行演示数据填充
  - 运行填充脚本
  - 验证数据正确性
- [x] 2.3.3 创建管理员账号
  - 创建默认管理员（admin@momentcampus.com / admin123）
  - 验证管理员权限

---

## 阶段三：后端 API 开发

### 任务 3.1：认证系统 API
- [x] 3.1.1 实现用户注册接口
  - POST /api/v1/auth/register
  - 验证用户名、邮箱、密码
  - 密码 bcrypt 加密
  - 返回 access_token 和 refresh_token
- [x] 3.1.2 实现用户登录接口
  - POST /api/v1/auth/login
  - 支持用户名/邮箱登录
  - 验证密码
  - 返回 access_token（30分钟）和 refresh_token（7天）
- [x] 3.1.3 实现 Token 刷新接口
  - POST /api/v1/auth/refresh
  - 验证 refresh_token
  - 返回新的 token 对
- [x] 3.1.4 实现用户登出接口
  - POST /api/v1/auth/logout
  - 清除 token（前端处理）
- [x] 3.1.5 实现 JWT 认证中间件
  - 解析 Bearer Token
  - 验证 token 有效性
  - 注入当前用户到请求上下文
- [x] 3.1.6 实现权限控制依赖
  - get_current_user：获取当前登录用户
  - get_current_admin：获取当前管理员用户
  - 资源所有权检查

### 任务 3.2：用户 API
- [x] 3.2.1 实现获取当前用户信息接口
  - GET /api/v1/users/me
  - 返回用户详细信息
- [x] 3.2.2 实现更新用户信息接口
  - PUT /api/v1/users/me
  - 更新昵称、头像、个人简介
- [x] 3.2.3 实现上传用户头像接口
  - POST /api/v1/users/me/avatar
  - 处理图片上传
  - 返回头像 URL

### 任务 3.3：信息（Post）API
- [x] 3.3.1 实现获取信息列表接口
  - GET /api/v1/posts
  - 支持分页（page, page_size）
  - 支持筛选（category_id, post_type_id, status）
  - 支持排序（latest, hottest, nearest）
  - 返回信息列表和分页信息
- [x] 3.3.2 实现获取信息详情接口
  - GET /api/v1/posts/{id}
  - 返回完整信息内容
  - 增加浏览次数
- [x] 3.3.3 实现创建信息接口
  - POST /api/v1/posts
  - 验证必填项（title, content, category_id, location_id）
  - 处理标签和图片
  - 设置有效期
  - 支持匿名发布
- [x] 3.3.4 实现更新信息接口
  - PUT /api/v1/posts/{id}
  - 验证资源所有权
  - 更新信息内容
- [x] 3.3.5 实现删除信息接口
  - DELETE /api/v1/posts/{id}
  - 验证资源所有权
  - 软删除
- [x] 3.3.6 实现获取我的信息列表接口
  - GET /api/v1/users/me/posts
  - 返回当前用户发布的信息（包括已删除）

### 任务 3.4：评论 API
- [x] 3.4.1 实现获取评论列表接口
  - GET /api/v1/posts/{id}/comments
  - 返回顶级评论和子评论
  - 支持分页
- [x] 3.4.2 实现创建评论接口
  - POST /api/v1/posts/{id}/comments
  - 支持顶级评论和回复
  - 验证内容长度
- [x] 3.4.3 实现删除评论接口
  - DELETE /api/v1/comments/{id}
  - 验证资源所有权
  - 软删除

### 任务 3.5：互动 API
- [x] 3.5.1 实现点赞接口
  - POST /api/v1/posts/{id}/like
  - 创建/取消点赞
  - 更新信息点赞数
- [x] 3.5.2 实现收藏接口
  - POST /api/v1/posts/{id}/favorite
  - 创建/取消收藏
  - 更新信息收藏数
- [x] 3.5.3 实现有效性确认接口
  - POST /api/v1/posts/{id}/validate
  - 创建有效性确认记录
  - 更新信息有效性计数
- [x] 3.5.4 实现获取我的收藏列表接口
  - GET /api/v1/users/me/favorites
  - 返回收藏的信息列表

### 任务 3.6：搜索 API
- [x] 3.6.1 实现搜索接口
  - GET /api/v1/search
  - 支持关键词搜索（title, content, location_name, category_name, tags, author_nickname）
  - 支持筛选（category_id, distance, created_at, validity_status, has_images）
  - 支持排序（relevance, nearest, latest, hottest）
  - 返回搜索结果和分页信息

### 任务 3.7：地图 API
- [x] 3.7.1 实现获取地图标记接口
  - GET /api/v1/map/markers
  - 根据地图边界返回标记
  - 限制最多 100 个标记
  - 返回地点坐标和信息摘要

### 任务 3.8：分类和地点 API
- [x] 3.8.1 实现获取分类列表接口
  - GET /api/v1/categories
  - 返回所有启用的分类
- [x] 3.8.2 实现获取地点列表接口
  - GET /api/v1/locations
  - 支持按学校筛选
  - 返回地点列表
- [x] 3.8.3 实现创建地点接口
  - POST /api/v1/locations
  - 验证地点名称和坐标
  - 创建新地点

### 任务 3.9：通知 API
- [x] 3.9.1 实现获取通知列表接口
  - GET /api/v1/notifications
  - 返回当前用户的通知列表
  - 支持分页
- [x] 3.9.2 实现标记通知已读接口
  - PUT /api/v1/notifications/{id}/read
  - 标记单个通知为已读
- [x] 3.9.3 实现标记所有通知已读接口
  - PUT /api/v1/notifications/read-all
  - 标记所有通知为已读

### 任务 3.10：举报 API
- [x] 3.10.1 实现创建举报接口
  - POST /api/v1/posts/{id}/report
  - 验证举报类型和说明
  - 创建举报记录
- [x] 3.10.2 实现获取举报列表接口（管理员）
  - GET /api/v1/admin/reports
  - 返回所有举报记录
  - 支持筛选状态
- [x] 3.10.3 实现处理举报接口（管理员）
  - PUT /api/v1/admin/reports/{id}/handle
  - 更新举报状态和处理结果

### 任务 3.11：管理后台 API
- [x] 3.11.1 实现获取待审核信息列表接口
  - GET /api/v1/admin/posts/pending
  - 返回待审核信息列表
- [x] 3.11.2 实现审核通过接口
  - PUT /api/v1/admin/posts/{id}/approve
  - 更新信息状态为已发布
- [x] 3.11.3 实现审核拒绝接口
  - PUT /api/v1/admin/posts/{id}/reject
  - 更新信息状态为已拒绝
  - 记录拒绝原因
- [x] 3.11.4 实现获取用户列表接口
  - GET /api/v1/admin/users
  - 返回所有用户列表
- [x] 3.11.5 实现禁用/启用用户接口
  - PUT /api/v1/admin/users/{id}/toggle-active
  - 切换用户激活状态

### 任务 3.12：文件上传 API
- [x] 3.12.1 实现图片上传接口
  - POST /api/v1/upload/image
  - 验证文件格式和大小
  - 保存图片到本地
  - 生成缩略图
  - 返回图片 URL 和缩略图 URL

### 任务 3.13：API 测试
- [x] 3.13.1 编写认证 API 测试
  - 测试注册、登录、Token 刷新
  - 测试错误凭据处理
- [x] 3.13.2 编写信息 API 测试
  - 测试 CRUD 操作
  - 测试权限控制
  - 测试分页和筛选
- [x] 3.13.3 编写互动 API 测试
  - 测试点赞、收藏、评论
  - 测试重复操作处理
- [x] 3.13.4 运行所有 API 测试
  - 执行 pytest
  - 修复失败的测试

---

## 阶段四：前端基础工程

### 任务 4.1：实现设计系统
- [x] 4.1.1 配置 Tailwind 主题
  - 定义颜色系统（主色、辅色、中性色、语义色）
  - 定义字体系统（字号、字重、行高）
  - 定义间距系统（4px 基础单位）
  - 定义圆角、阴影
- [x] 4.1.2 创建全局样式
  - 创建 globals.css
  - 定义 CSS 变量
  - 定义全局重置样式

### 任务 4.2：开发基础 UI 组件
- [x] 4.2.1 开发 Button 组件
  - 支持 variant（primary, secondary, outline, ghost, danger）
  - 支持 size（sm, md, lg）
  - 支持 loading 状态
  - 支持 disabled 状态
- [x] 4.2.2 开发 Input 组件
  - 支持 label 和 placeholder
  - 支持错误提示
  - 支持 disabled 状态
  - 支持前后缀图标
- [x] 4.2.3 开发 Card 组件
  - 支持 variant（elevated, outlined, filled）
  - 支持 padding 配置
- [x] 4.2.4 开发 Modal 组件
  - 支持标题和内容
  - 支持关闭按钮
  - 支持点击背景关闭
  - 支持 ESC 键关闭
- [x] 4.2.5 开发 Toast 组件
  - 支持 success, error, warning, info 类型
  - 支持自动消失
  - 支持手动关闭
- [x] 4.2.6 开发 Loading 组件
  - 支持 spinner 和 skeleton
  - 支持 size 配置
- [x] 4.2.7 开发 Avatar 组件
  - 支持图片 URL
  - 支持 fallback 文字
  - 支持 size 配置
- [x] 4.2.8 开发 Badge 组件
  - 支持 variant（success, warning, danger, info）
  - 支持 size 配置

### 任务 4.3：实现路由系统
- [x] 4.3.1 配置 React Router
  - 定义路由结构
  - 配置路由守卫
  - 实现懒加载
- [x] 4.3.2 实现公开路由
  - / -> 首页
  - /feed -> 信息流
  - /map -> 地图页
  - /search -> 搜索页
  - /category/:slug -> 分类详情
  - /info/:id -> 信息详情
  - /login -> 登录页
  - /register -> 注册页
- [x] 4.3.3 实现受保护路由
  - /publish -> 发布页
  - /info/:id/edit -> 编辑信息
  - /profile -> 个人中心
  - /profile/posts -> 我的发布
  - /profile/favorites -> 我的收藏
  - /notifications -> 通知页
- [x] 4.3.4 实现管理员路由
  - /admin -> 管理后台
  - /admin/review -> 内容审核
  - /admin/reports -> 举报管理

### 任务 4.4：实现布局组件
- [x] 4.4.1 实现 Header 组件
  - 显示 Logo 和应用名称
  - 显示搜索框（桌面端）
  - 显示用户菜单（已登录）或登录按钮
  - 显示通知图标和未读数
- [x] 4.4.2 实现 Sidebar 组件（桌面端）
  - 显示导航菜单
  - 显示分类列表
  - 支持折叠/展开
- [x] 4.4.3 实现 MobileNav 组件（移动端）
  - 底部导航栏
  - 显示首页、地图、发布、通知、我的
  - 高亮当前页面
- [x] 4.4.4 实现 MainLayout 组件
  - 组合 Header、Sidebar、MobileNav
  - 响应式布局（移动端/桌面端）

### 任务 4.5：实现状态管理
- [x] 4.5.1 实现 useAuthStore
  - 管理用户信息、Token、登录状态
  - 实现登录、登出、刷新 Token 方法
- [x] 4.5.2 实现 useCampusStore
  - 管理当前选择的校园
  - 实现切换校园方法
- [x] 4.5.3 实现 useUIStore
  - 管理侧边栏开关、弹窗显示
  - 实现 UI 状态切换方法

### 任务 4.6：实现 API 服务层
- [x] 4.6.1 配置 Axios 实例
  - 设置 baseURL
  - 配置请求拦截器（添加 Token）
  - 配置响应拦截器（处理错误、刷新 Token）
- [x] 4.6.2 实现认证 API 服务
  - register, login, logout, refresh
- [x] 4.6.3 实现信息 API 服务
  - getPosts, getPost, createPost, updatePost, deletePost
- [x] 4.6.4 实现评论 API 服务
  - getComments, createComment, deleteComment
- [x] 4.6.5 实现互动 API 服务
  - likePost, favoritePost, validatePost
- [x] 4.6.6 实现搜索 API 服务
  - search
- [x] 4.6.7 实现通知 API 服务
  - getNotifications, markAsRead, markAllAsRead
- [x] 4.6.8 实现上传 API 服务
  - uploadImage

### 任务 4.7：实现自定义 Hooks
- [x] 4.7.1 实现 useAuth Hook
  - 提供登录、登出、注册方法
  - 提供当前用户信息
- [x] 4.7.2 实现 usePosts Hook
  - 使用 TanStack Query 获取信息列表
  - 支持分页、筛选、排序
- [x] 4.7.3 实现 usePost Hook
  - 使用 TanStack Query 获取信息详情
- [x] 4.7.4 实现 useComments Hook
  - 使用 TanStack Query 获取评论列表
  - 提供创建、删除评论方法
- [x] 4.7.5 实现 useInteractions Hook
  - 提供点赞、收藏、有效性确认方法
  - 实现乐观更新
- [x] 4.7.6 实现 useSearch Hook
  - 使用 TanStack Query 执行搜索
  - 支持防抖

---

## 阶段五：前端核心页面开发

### 任务 5.1：实现登录/注册页面
- [x] 5.1.1 实现登录页面
  - 表单验证（用户名/邮箱、密码）
  - 调用登录 API
  - 登录成功跳转首页
  - 显示错误提示
  - 提供注册链接
- [x] 5.1.2 实现注册页面
  - 表单验证（用户名、邮箱、密码、确认密码）
  - 调用注册 API
  - 注册成功跳转登录页
  - 显示错误提示
  - 提供登录链接

### 任务 5.2：实现首页
- [x] 5.2.1 实现首页布局
  - 显示推荐信息和最新信息
  - 显示分类入口
  - 响应式布局
- [x] 5.2.2 实现信息流列表
  - 使用 InfoCard 组件展示信息
  - 支持下拉刷新
  - 支持上拉加载更多
  - 显示空状态
- [x] 5.2.3 实现分类入口
  - 显示所有分类图标
  - 点击跳转分类详情页

### 任务 5.3：实现地图页
- [x] 5.3.1 集成 MapLibre GL JS
  - 初始化地图
  - 配置地图样式
  - 设置校园中心坐标
- [x] 5.3.2 实现地图标记
  - 获取地图标记数据
  - 在地图上显示标记
  - 根据分类着色标记
- [x] 5.3.3 实现标记弹窗
  - 点击标记显示信息摘要
  - 显示标题、分类、有效性状态
  - 提供查看详情链接
- [x] 5.3.4 实现地图控件
  - 缩放控件
  - 定位控件
  - 分类筛选控件

### 任务 5.4：实现搜索页
- [x] 5.4.1 实现搜索框
  - 输入关键词
  - 支持实时搜索（防抖）
  - 显示搜索历史
- [x] 5.4.2 实现筛选面板
  - 分类筛选
  - 距离筛选
  - 发布时间筛选
  - 有效性状态筛选
  - 是否有图片筛选
- [x] 5.4.3 实现排序选择
  - 综合排序
  - 距离最近
  - 发布时间最新
  - 热度最高
- [x] 5.4.4 实现搜索结果列表
  - 显示搜索结果
  - 支持分页
  - 显示空状态

### 任务 5.5：实现信息详情页
- [x] 5.5.1 实现信息内容展示
  - 显示标题、分类、地点
  - 显示正文内容
  - 显示图片轮播
  - 显示标签
  - 显示发布时间和有效期
  - 显示有效性状态和确认人数
- [x] 5.5.2 实现发布者信息
  - 显示头像和昵称
  - 点击跳转用户主页
- [x] 5.5.3 实现操作栏
  - 点赞按钮（显示点赞数）
  - 收藏按钮（显示收藏数）
  - 评论按钮（显示评论数）
  - 分享按钮
  - 举报按钮
- [x] 5.5.4 实现评论区
  - 显示评论列表
  - 支持发表评论
  - 支持回复评论
  - 支持删除自己的评论
  - 显示评论数

### 任务 5.6：实现发布页
- [x] 5.6.1 实现发布表单
  - 选择分类
  - 选择地点（地图选点或搜索）
  - 填写标题和描述
  - 上传图片（最多 9 张）
  - 添加标签（最多 5 个）
  - 设置有效期
  - 选择是否匿名发布
- [x] 5.6.2 实现表单验证
  - 验证必填项
  - 验证标题长度（5-100 字符）
  - 验证描述长度（10-5000 字符）
  - 验证图片格式和大小
- [x] 5.6.3 实现发布逻辑
  - 调用创建信息 API
  - 发布成功跳转详情页
  - 显示错误提示
- [x] 5.6.4 实现编辑功能
  - 加载现有信息
  - 预填充表单
  - 调用更新信息 API

### 任务 5.7：实现个人中心
- [x] 5.7.1 实现个人资料页
  - 显示用户信息（头像、昵称、个人简介）
  - 显示统计信息（发布数、收藏数、获赞数）
  - 提供编辑资料入口
- [x] 5.7.2 实现编辑资料页
  - 修改昵称、头像、个人简介
  - 上传头像
  - 保存修改
- [x] 5.7.3 实现我的发布页
  - 显示当前用户发布的信息
  - 显示信息状态（已发布、待审核、已拒绝、已删除）
  - 提供编辑、删除操作
- [x] 5.7.4 实现我的收藏页
  - 显示收藏的信息列表
  - 支持取消收藏
  - 按收藏时间倒序排列

### 任务 5.8：实现通知页
- [x] 5.8.1 实现通知列表
  - 显示所有通知
  - 区分通知类型（评论、点赞、系统、审核）
  - 未读通知显示红点
  - 点击通知跳转相关内容
- [x] 5.8.2 实现通知操作
  - 标记单个通知已读
  - 标记所有通知已读

### 任务 5.9：实现管理后台
- [x] 5.9.1 实现管理后台布局
  - 侧边栏导航
  - 顶部工具栏
  - 内容区域
- [x] 5.9.2 实现内容审核页
  - 显示待审核信息列表
  - 查看信息详情
  - 通过或拒绝信息
  - 填写拒绝原因
- [x] 5.9.3 实现举报管理页
  - 显示举报列表
  - 查看举报详情
  - 处理举报（删除、隐藏、警告、驳回）

---

## 阶段六：前后端联调

### 任务 6.1：替换 Mock 数据为真实 API
- [x] 6.1.1 替换认证相关 Mock
  - 替换登录、注册、登出 Mock
  - 验证 Token 管理正常
- [x] 6.1.2 替换信息相关 Mock
  - 替换信息列表、详情、创建、更新、删除 Mock
  - 验证数据正确加载和保存
- [x] 6.1.3 替换互动相关 Mock
  - 替换点赞、收藏、评论 Mock
  - 验证互动数据实时更新
- [x] 6.1.4 替换搜索相关 Mock
  - 替换搜索 Mock
  - 验证搜索结果正确

### 任务 6.2：联调核心业务流程
- [x] 6.2.1 联调认证流程
  - 注册 -> 登录 -> 选择校园 -> 进入首页
  - 验证 Token 刷新机制
- [x] 6.2.2 联调信息发布流程
  - 选择分类 -> 选择地点 -> 填写内容 -> 上传图片 -> 发布
  - 验证信息创建成功并跳转详情页
- [x] 6.2.3 联调信息浏览流程
  - 首页浏览 -> 查看详情 -> 返回
  - 验证信息正确加载
- [x] 6.2.4 联调互动流程
  - 点赞 -> 收藏 -> 评论 -> 有效性确认
  - 验证数据实时更新
- [x] 6.2.5 联调搜索流程
  - 输入关键词 -> 筛选 -> 排序 -> 查看结果
  - 验证搜索结果正确
- [x] 6.2.6 联调管理流程
  - 登录管理员 -> 查看待审核 -> 通过/拒绝
  - 验证审核操作生效

### 任务 6.3：处理跨域和错误
- [x] 6.3.1 配置 CORS
  - 确保后端允许前端域名
  - 验证跨域请求正常
- [x] 6.3.2 处理错误码
  - 统一错误处理
  - 显示友好的错误提示
- [x] 6.3.3 处理异常情况
  - 网络错误处理
  - Token 过期处理
  - 资源不存在处理

---

## 阶段七：测试与修复

### 任务 7.1：功能测试
- [x] 7.1.1 测试认证功能
  - 注册新用户
  - 登录/登出
  - Token 刷新
- [x] 7.1.2 测试信息发布功能
  - 创建信息（含图片上传）
  - 编辑信息
  - 删除信息
- [x] 7.1.3 测试信息浏览功能
  - 首页信息流加载
  - 地图标记显示
  - 信息详情查看
- [x] 7.1.4 测试互动功能
  - 点赞/取消点赞
  - 收藏/取消收藏
  - 发表评论
  - 有效性确认
- [x] 7.1.5 测试搜索功能
  - 关键词搜索
  - 筛选和排序
- [x] 7.1.6 测试管理功能
  - 内容审核
  - 举报处理

### 任务 7.2：API 测试
- [x] 7.2.1 运行后端 API 测试
  - 执行 pytest
  - 修复失败的测试
- [x] 7.2.2 验证 API 响应格式
  - 检查响应数据结构
  - 检查错误码正确返回

### 任务 7.3：响应式测试
- [ ] 7.3.1 测试移动端适配（320px - 768px）
  - 检查布局正确性
  - 检查触摸操作友好
- [ ] 7.3.2 测试桌面端适配（768px - 1920px）
  - 检查布局正确性
  - 检查鼠标操作正常

### 任务 7.4：修复 Bug
- [ ] 7.4.1 修复发现的功能 Bug
  - 修复前端逻辑错误
  - 修复后端接口错误
  - 修复数据不一致问题
- [ ] 7.4.2 修复发现的 UI Bug
  - 修复样式问题
  - 修复响应式问题
  - 修复交互问题

### 任务 7.5：性能优化
- [ ] 7.5.1 前端性能优化
  - 代码分割
  - 图片懒加载
  - 组件懒加载
- [ ] 7.5.2 后端性能优化
  - 数据库查询优化
  - 添加必要的索引
  - 缓存热点数据

---

## 阶段八：文档与交付

### 任务 8.1：编写项目文档
- [ ] 8.1.1 更新 README.md
  - 项目简介
  - 功能说明
  - 技术栈
  - 快速启动指南
  - 开发环境要求
  - 部署说明
- [ ] 8.1.2 编写 API 文档
  - 使用 Swagger 自动生成
  - 补充手动说明
- [ ] 8.1.3 编写部署文档
  - 开发环境部署
  - 生产环境部署
  - Docker 部署

### 任务 8.2：准备演示环境
- [ ] 8.2.1 准备演示账号
  - 创建演示用户账号
  - 创建演示管理员账号
- [ ] 8.2.2 准备演示数据
  - 确保演示数据完整
  - 验证数据正确性
- [ ] 8.2.3 编写演示脚本
  - 核心功能演示流程
  - 关键用户场景

### 任务 8.3：最终检查
- [ ] 8.3.1 检查所有 P0 功能
  - 验证所有核心功能可用
  - 验证核心用户闭环可走通
- [ ] 8.3.2 检查代码质量
  - 运行 lint 检查
  - 运行 typecheck
  - 修复所有警告
- [ ] 8.3.3 检查文档完整性
  - 验证文档与代码一致
  - 验证命令可复制执行
- [ ] 8.3.4 构建项目
  - 前端构建（npm run build）
  - 后端构建（无错误）
  - 验证构建产物

### 任务 8.4：提交代码
- [ ] 8.4.1 提交所有代码
  - 添加所有文件
  - 编写提交信息
  - 提交到 Git
- [ ] 8.4.2 推送到远程仓库（如有）
  - 配置远程仓库
  - 推送代码

---

## 任务依赖关系

```
阶段一（项目初始化）
  ↓
阶段二（数据库设计） → 阶段三（后端 API）
  ↓                      ↓
阶段四（前端基础） → 阶段五（前端页面）
                          ↓
                    阶段六（前后端联调）
                          ↓
                    阶段七（测试与修复）
                          ↓
                    阶段八（文档与交付）
```

**并行开发可能性：**
- 阶段二和阶段四可以并行（数据库设计和前端基础工程）
- 阶段三和阶段五可以并行（后端 API 和前端页面开发）
- 阶段六必须等待阶段三和阶段五都完成

---

## 验收标准

### 功能验收
- [ ] 所有 P0 功能已实现并可正常使用
- [ ] 核心用户闭环可走通（浏览→查看→发布→互动→验证）
- [ ] 无严重 Bug

### 性能验收
- [ ] 页面加载时间 ≤ 2 秒
- [ ] API 响应时间 ≤ 500ms
- [ ] 系统稳定运行

### 安全验收
- [ ] 无严重安全漏洞
- [ ] 敏感信息保护到位
- [ ] 权限控制正确

### 用户体验验收
- [ ] 界面美观、易用
- [ ] 移动端和桌面端适配良好
- [ ] 空状态、错误状态处理完善

### 技术验收
- [ ] 代码符合规范，无 lint 错误
- [ ] TypeScript 类型完整，无 any
- [ ] API 文档完整
- [ ] 测试覆盖率达标

### 交付验收
- [ ] 项目可正常启动
- [ ] 项目可正常构建
- [ ] 演示环境可正常访问
- [ ] 文档完整且准确
