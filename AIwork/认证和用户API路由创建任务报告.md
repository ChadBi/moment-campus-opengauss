# 任务报告：认证和用户API路由创建

## 1. 任务概述

在 `backend/app/api/` 目录下创建认证（auth.py）和用户（users.py）相关的 API 路由，实现用户注册、登录、Token 刷新、登出，以及用户信息获取、更新、头像上传、我的帖子列表、我的收藏列表等功能。

## 2. 已完成内容

### 2.1 认证 API（auth.py）
- `POST /auth/register` - 用户注册
  - 验证邮箱唯一性
  - 密码加密存储
  - 创建用户并返回 token 对
- `POST /auth/login` - 用户登录
  - 验证邮箱和密码
  - 检查用户状态（是否被禁用/删除）
  - 更新最后登录时间
  - 返回 access_token 和 refresh_token
- `POST /auth/refresh` - 刷新 Token
  - 验证 refresh_token 有效性
  - 验证 token 类型
  - 返回新的 token 对
- `POST /auth/logout` - 登出
  - 返回成功消息（前端清除 token）

### 2.2 用户 API（users.py）
- `GET /users/me` - 获取当前用户信息（需要认证）
- `PUT /users/me` - 更新用户信息（昵称、头像、简介）
- `POST /users/me/avatar` - 上传头像
  - 验证文件格式（JPG、PNG、GIF、WEBP）
  - 验证文件大小（不超过 5MB）
  - 生成唯一文件名
  - 保存到 uploads/avatars 目录
  - 更新用户头像 URL
- `GET /users/me/posts` - 获取我的信息列表（分页）
  - 预加载关联数据（用户、分类、地点、标签）
  - 支持 page 和 page_size 参数
- `GET /users/me/favorites` - 获取我的收藏列表（分页）
  - 预加载关联数据
  - 支持 page 和 page_size 参数

### 2.3 Schema 更新
- 新增 `RefreshTokenRequest` schema 用于刷新 token 请求
- 更新导入以支持 ConfigDict

### 2.4 路由注册
- 在 `router.py` 中注册 auth_router 和 users_router

## 3. 未完成内容

暂无

## 4. 实现思路

### 4.1 认证流程
- 使用 bcrypt 进行密码哈希
- 使用 python-jose 生成和验证 JWT token
- access_token 和 refresh_token 分别设置不同的过期时间
- token 中包含用户 ID 和 token 类型标识

### 4.2 用户信息操作
- 使用 FastAPI 的 `Depends(get_current_user)` 依赖注入获取当前用户
- 使用 SQLAlchemy async session 进行数据库操作
- 头像上传使用 FastAPI 的 UploadFile 处理文件上传

### 4.3 分页实现
- 使用 `PaginatedResponse.create()` 工厂方法创建分页响应
- 使用 SQLAlchemy 的 `offset()` 和 `limit()` 实现分页
- 使用 `selectinload` 预加载关联数据，避免 N+1 查询问题

## 5. 修改文件

### 新增文件
- `backend/app/api/auth.py` - 认证 API 路由
- `backend/app/api/users.py` - 用户 API 路由

### 修改文件
- `backend/app/schemas/user.py` - 新增 RefreshTokenRequest schema，更新导入
- `backend/app/api/router.py` - 注册新的路由

## 6. 影响范围

### 6.1 API 路由
新增以下 API 端点：
- `/api/v1/auth/register`
- `/api/v1/auth/login`
- `/api/v1/auth/refresh`
- `/api/v1/auth/logout`
- `/api/v1/users/me`
- `/api/v1/users/me` (PUT)
- `/api/v1/users/me/avatar`
- `/api/v1/users/me/posts`
- `/api/v1/users/me/favorites`

### 6.2 依赖模块
- 依赖 `core/security.py` 中的密码哈希和 JWT 函数
- 依赖 `dependencies.py` 中的 `get_current_user` 依赖
- 依赖 `schemas/user.py` 和 `schemas/common.py` 中的 schema
- 依赖 `models/user.py`、`models/post.py`、`models/favorite.py` 等模型

## 7. 测试与验证

由于当前环境没有运行测试，代码验证主要基于：
- 代码审查确保与现有代码风格一致
- 检查导入路径和依赖关系
- 验证 schema 和模型字段使用正确
- 确保异步 session 操作正确（使用 selectinload 预加载关联数据）

建议后续执行以下测试：
1. 启动服务验证路由注册成功
2. 测试注册接口，验证邮箱唯一性检查
3. 测试登录接口，验证密码验证
4. 测试 token 刷新接口
5. 测试需要认证的接口
6. 测试头像上传，验证文件格式和大小限制
7. 测试分页接口

## 8. 后续建议

### 8.1 功能增强
- 实现 token 黑名单机制（用于登出）
- 添加邮箱验证功能
- 添加密码重置功能
- 添加用户注销功能

### 8.2 安全增强
- 添加请求频率限制
- 添加登录日志记录
- 实现更细粒度的权限控制

### 8.3 性能优化
- 考虑使用 Redis 缓存用户信息
- 优化头像上传，支持图片压缩和裁剪
- 实现 CDN 加速静态资源访问
