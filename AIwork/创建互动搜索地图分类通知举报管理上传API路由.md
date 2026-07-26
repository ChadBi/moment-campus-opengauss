# 任务报告：创建互动、搜索、地图、分类、通知、举报、管理、上传 API 路由

## 1. 任务概述

在 `backend/app/api/` 目录下创建 8 个 API 路由模块，实现互动、搜索、地图、分类、通知、管理、上传等功能。

## 2. 已完成内容

### 2.1 interactions.py - 互动 API
- ✅ POST /posts/{id}/like - 点赞/取消点赞（切换逻辑）
- ✅ POST /posts/{id}/favorite - 收藏/取消收藏（切换逻辑）
- ✅ POST /posts/{id}/validate - 有效性确认
- ✅ POST /posts/{id}/report - 创建举报
- ✅ 更新 Post 的 like_count, favorite_count, valid_count, invalid_count
- ✅ 创建通知（点赞、收藏时通知帖子作者）

### 2.2 search.py - 搜索 API
- ✅ GET /search - 搜索信息
- ✅ 支持关键词搜索（多字段模糊匹配：title, content, contact_info）
- ✅ 支持筛选（category_id, location_id, post_type_id, school_id, tag）
- ✅ 支持排序（created_at, like_count, comment_count, view_count）
- ✅ 支持分页
- ✅ 记录搜索历史

### 2.3 map.py - 地图 API
- ✅ GET /map/markers - 获取地图标记
- ✅ 根据经纬度边界筛选（north, south, east, west）
- ✅ 最多返回 100 个标记
- ✅ 支持按分类筛选

### 2.4 categories.py - 分类 API
- ✅ GET /categories - 获取分类列表
- ✅ GET /locations - 获取地点列表（按学校筛选）
- ✅ POST /locations - 创建地点（需要认证）

### 2.5 notifications.py - 通知 API
- ✅ GET /notifications - 获取通知列表（分页）
- ✅ 支持按类型和已读状态筛选
- ✅ PUT /notifications/{id}/read - 标记单个已读
- ✅ PUT /notifications/read-all - 标记所有已读
- ✅ 正确处理 actor_id 和 target

### 2.6 admin.py - 管理后台 API
- ✅ GET /admin/posts/pending - 获取待审核信息
- ✅ PUT /admin/posts/{id}/approve - 审核通过
- ✅ PUT /admin/posts/{id}/reject - 审核拒绝
- ✅ GET /admin/users - 获取用户列表
- ✅ PUT /admin/users/{id}/toggle-active - 禁用/启用用户
- ✅ GET /admin/reports - 获取举报列表
- ✅ PUT /admin/reports/{id}/handle - 处理举报
- ✅ 所有管理 API 使用 get_current_admin 依赖
- ✅ 记录管理员操作日志

### 2.7 upload.py - 文件上传 API
- ✅ POST /upload/image - 上传图片
- ✅ 验证格式（jpg, png, gif）
- ✅ 验证大小（5MB）
- ✅ 保存到 uploads 目录
- ✅ 返回 URL 和缩略图 URL
- ✅ 使用 Pillow 生成缩略图（300x300）

### 2.8 路由注册
- ✅ 更新 router.py 注册所有新路由

## 3. 未完成内容

暂无

## 4. 实现思路

### 4.1 互动 API
- 使用切换逻辑：查询是否存在记录，存在则删除，不存在则创建
- 使用事务保证数据一致性（IntegrityError 处理）
- 更新 Post 表的计数字段
- 创建通知时检查是否为作者本人操作

### 4.2 搜索 API
- 使用 SQLAlchemy 的 ilike 进行模糊匹配
- 使用 or_ 实现多字段搜索
- 支持多条件筛选
- 使用 subquery 计算总数
- 记录搜索历史到 search_histories 表

### 4.3 地图 API
- 使用经纬度边界条件筛选 Location
- 关联 Post 表获取帖子信息
- 限制返回数量为 100 个

### 4.4 分类 API
- 分类列表按 sort_order 排序
- 地点列表支持按 school_id 筛选
- 创建地点时验证学校是否存在

### 4.5 通知 API
- 查询当前用户的通知
- 支持按类型和已读状态筛选
- 标记已读时更新 is_read 和 read_at 字段
- 获取操作者信息（nickname, avatar_url）

### 4.6 管理 API
- 使用 get_current_admin 依赖确保管理员权限
- 审核帖子时更新 status 字段
- 禁用用户时更新 is_active 字段
- 处理举报时根据 action 执行相应操作（删除帖子、禁用用户等）
- 所有操作记录到 admin_operation_logs 表

### 4.7 文件上传 API
- 验证文件类型（content_type）
- 验证文件大小（5MB）
- 使用 Pillow 验证图片有效性
- 生成唯一文件名（UUID）
- 使用 Pillow 生成缩略图（300x300）
- GIF 保持原格式，其他格式转为 JPEG

## 5. 修改文件

### 新增文件
1. `backend/app/api/interactions.py` - 互动 API
2. `backend/app/api/search.py` - 搜索 API
3. `backend/app/api/map.py` - 地图 API
4. `backend/app/api/categories.py` - 分类 API
5. `backend/app/api/notifications.py` - 通知 API
6. `backend/app/api/admin.py` - 管理后台 API
7. `backend/app/api/upload.py` - 文件上传 API

### 修改文件
1. `backend/app/api/router.py` - 注册所有新路由

## 6. 影响范围

### 新增功能模块
- 互动功能（点赞、收藏、有效性确认、举报）
- 搜索功能（关键词搜索、多条件筛选、排序、分页）
- 地图功能（根据边界显示标记）
- 分类功能（分类列表、地点列表、创建地点）
- 通知功能（通知列表、标记已读）
- 管理功能（审核帖子、管理用户、处理举报）
- 上传功能（图片上传、缩略图生成）

### 依赖模块
- 使用现有的 models（Post, Like, Favorite, ValidationRecord, Report, Notification, Category, Location, User 等）
- 使用现有的 schemas（interaction, post, common）
- 使用现有的 dependencies（get_current_user, get_current_admin）
- 使用 Pillow 库生成缩略图

## 7. 测试与验证

未运行测试。原因：
1. 需要确认数据库是否已初始化
2. 需要确认是否有测试数据
3. 需要启动后端服务进行接口测试

建议后续执行：
- 启动后端服务：`cd backend && uvicorn app.main:app --reload`
- 访问 API 文档：`http://localhost:8000/api/v1/docs`
- 测试各个接口的功能

## 8. 后续建议

### 8.1 功能完善
1. 添加评论相关的互动 API（点赞评论）
2. 添加批量操作接口（批量删除、批量审核）
3. 添加统计接口（用户统计、帖子统计）
4. 添加导出功能（导出用户列表、帖子列表）

### 8.2 性能优化
1. 搜索功能添加全文索引
2. 热点数据添加缓存（Redis）
3. 图片上传添加 CDN 支持
4. 大量数据查询添加分页优化

### 8.3 安全增强
1. 添加请求频率限制
2. 添加敏感词过滤
3. 添加图片内容审核
4. 添加操作日志审计

### 8.4 测试覆盖
1. 编写单元测试
2. 编写集成测试
3. 添加接口自动化测试
4. 添加性能测试

### 8.5 文档完善
1. 添加 API 使用示例
2. 添加错误码说明
3. 添加部署文档
4. 添加开发指南
