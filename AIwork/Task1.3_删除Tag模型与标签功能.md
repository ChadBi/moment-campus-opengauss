# 任务报告：Task 1.3 删除 Tag 模型与标签功能

## 1. 任务概述

根据 `docs/需要调整的地方.md` 中关于"标签（Tag）功能与分类（Category）冲突"的问题，Task 1.3 的目标是：

- 删除 Tag 模型与 tags 表
- 删除 PostTag 关联模型与 post_tags 表
- 清理所有 Tag / PostTag / TagBrief / tags 字段残留引用
- 清理标签管理 4 个 admin 端点（list/update/delete/merge）
- 调整 AI 发布建议：不再加载标签白名单，tags 恒定返回空列表
- 确保所有后端测试通过

## 2. 已完成内容

### 2.1 数据库迁移
- 创建 Alembic 迁移 `x3c4d5e6f7g8_remove_tag_model.py`
- DROP post_tags 表（含 4 个索引：ix_post_tags_tag_id / ix_post_tags_post_id / idx_posttag_tag / idx_posttag_post_tag）
- DROP tags 表（含 4 个索引：idx_tag_school_slug / idx_tag_school_name / idx_tag_usage / idx_tag_official）
- 提供 downgrade 方法支持回滚（重建表与索引）

### 2.2 模型层
- 删除 `app/models/tag.py` 文件
- 删除 `app/models/post_tag.py` 文件
- 修改 `app/models/post.py`：移除 post_tags 关系
- 更新 `app/models/__init__.py`：移除 Tag / PostTag 导入与 __all__ 导出

### 2.3 Schema 层
- `app/schemas/post.py`：删除 TagBrief 类、PostCreate/PostUpdate 中的 tags 字段、PostResponse/PostListResponse 中的 tags 字段
- `app/schemas/admin.py`：删除 TagAdminResponse / TagUpdate / TagMergeRequest 三个类

### 2.4 API 层
- `app/api/admin.py`：移除 Tag/PostTag 导入，删除 4 个标签管理端点（GET /admin/tags、PUT /admin/tags/{id}、DELETE /admin/tags/{id}、POST /admin/tags/merge）
- `app/api/posts.py`：移除 Tag/PostTag 导入、create_post/update_post 中的标签处理逻辑、selectinload(Post.post_tags)
- `app/api/search.py`：移除 Tag/PostTag 导入、tag 筛选参数与逻辑、selectinload(Post.post_tags)
- `app/api/recommendations.py`：移除 PostTag 导入与 tags 赋值逻辑
- `app/api/users.py`：移除 PostTag/Tag 导入与 selectinload(Post.post_tags)

### 2.5 服务层
- `app/services/ai_search.py`：移除 PostTag/TagBrief 导入、tag 处理逻辑、selectinload(Post.post_tags)
- `app/services/ai_publish.py`：移除 Tag 导入、_load_whitelists 不再加载标签白名单、_build_prompt 移除标签引用、_validate_suggestions 恒定返回 tags=[]
- `app/services/recommender.py`：移除 PostTag 导入与 selectinload(Post.post_tags)

### 2.6 核心配置
- `app/core/post_status.py`：SUBSTANTIAL_FIELDS 注释中移除 tags 引用
- `app/core/analytics.py`：post_submitted 事件白名单注释中移除 tags 引用

### 2.7 测试文件
- `tests/test_ai_publish.py`：移除 Tag 导入与 _create_tag 辅助函数；fixture 不再创建标签；test_returns_structured_suggestions 与 test_invalid_category_dropped 改为断言 tags==[]；跳过 test_invalid_tags_dropped 与 test_b_school_tag_dropped_in_a_school
- `tests/test_adm02_school_settings.py`：跳过 test_tag_management_routes_smoke 与 test_tag_management_cross_school_404
- `tests/test_publish_flow.py`：移除 Tag/PostTag 导入与 _add_tag 辅助函数；test_create_post_with_full_fields 不再传 tags；跳过 test_create_post_with_tags_limit
- `tests/test_search.py`：移除 Tag/PostTag 导入与 _add_tag 辅助函数；search_setup fixture 不再添加标签
- `tests/test_api_contract.py`：test_allowed_fields_present 从预期字段集合中移除 tags
- `tests/test_schemas.py`：跳过 test_tags_max_five
- `tests/test_post_transition.py`：跳过 test_non_substantial_tags_change_stays_published
- `tests/test_posts.py`：跳过 test_create_post_with_tags
- `tests/test_topics.py`：TRUNCATE 表清单中移除 tags / post_tags

### 2.8 脚本文件
- `scripts/verify_data.py`：移除 Tag/PostTag 导入
- `scripts/seed_data.py`：移除 Tag/PostTag 导入；TRUNCATE 表清单中移除 tags / post_tags
- `scripts/generate_db_design.py`：移除 tags / post_tags 表定义、关系图 M:N 关系、子系统表清单、实体类别分类中的相关条目

## 3. 未完成内容

暂无。Task 1.3 的所有目标已完成。

## 4. 实现思路

### 4.1 沿用 Task 1.2 的分阶段清理策略
1. **模型层先动**：删除 Tag / PostTag 模型文件和 Post.post_tags 关系
2. **Schema 层跟进**：更新所有引用 TagBrief / tags 字段的 schema
3. **API 层清理**：移除所有标签管理端点与 selectinload(Post.post_tags)
4. **服务层收尾**：清理 AI 发布建议、AI 搜索、推荐器中的 tag 逻辑
5. **核心配置**：更新 SUBSTANTIAL_FIELDS 与事件白名单注释
6. **测试修复**：分批清理测试文件中的 Tag 引用，跳过纯标签功能测试
7. **脚本与工具**：更新 seed_data / verify_data / generate_db_design

### 4.2 AI 发布建议的兼容设计
- AIPublishSuggestions schema 保留 tags 字段（恒定为空列表）以保证向前兼容
- `_validate_suggestions` 函数不再做标签白名单校验，直接返回 tags=[]
- 提示词中不再展示标签白名单，避免误导模型

### 4.3 测试策略
- 纯标签功能测试（如标签 CRUD、标签白名单校验、跨校标签隔离）直接 `@pytest.mark.skip` 跳过
- 涉及 tags 字段但主流程不依赖标签的测试（如 test_returns_structured_suggestions）改为断言 `tags == []`
- 测试 fixture 不再创建标签，避免数据库写入失败

## 5. 修改文件

### 新增文件
- `backend/alembic/versions/x3c4d5e6f7g8_remove_tag_model.py`
- `AIwork/Task1.3_删除Tag模型与标签功能.md`（本报告）

### 删除文件
- `backend/app/models/tag.py`
- `backend/app/models/post_tag.py`

### 修改文件（核心）
- `backend/app/models/post.py`、`__init__.py`
- `backend/app/schemas/post.py`、`admin.py`
- `backend/app/api/admin.py`、`posts.py`、`search.py`、`recommendations.py`、`users.py`
- `backend/app/services/ai_search.py`、`ai_publish.py`、`recommender.py`
- `backend/app/core/post_status.py`、`analytics.py`
- `backend/tests/test_ai_publish.py`、`test_adm02_school_settings.py`、`test_publish_flow.py`、`test_search.py`、`test_api_contract.py`、`test_schemas.py`、`test_post_transition.py`、`test_posts.py`、`test_topics.py`
- `backend/scripts/verify_data.py`、`seed_data.py`、`generate_db_design.py`

## 6. 影响范围

### 6.1 数据模型
- Tag 模型完全删除
- PostTag 关联模型完全删除
- Post 模型不再有 post_tags 关系

### 6.2 API 接口
- 移除 `GET /api/v1/admin/tags` 端点
- 移除 `PUT /api/v1/admin/tags/{tag_id}` 端点
- 移除 `DELETE /api/v1/admin/tags/{tag_id}` 端点
- 移除 `POST /api/v1/admin/tags/merge` 端点
- 帖子创建/更新不再接受 tags 字段（Pydantic 默认忽略）
- 帖子响应不再返回 tags 字段
- 搜索接口不再支持 tag 筛选参数

### 6.3 业务逻辑
- 帖子实质修改字段集合（SUBSTANTIAL_FIELDS）注释不再提及 tags
- AI 分析事件不再记录 tags
- AI 发布建议 tags 恒定返回空列表
- 推荐器不再加载 post_tags 关系

### 6.4 前端影响
- 前端需移除标签选择器、标签筛选器（Task 3.x 阶段处理）
- 前端需移除标签管理后台页面（Task 3.x 阶段处理）

## 7. 测试与验证

### 7.1 后端测试
- 运行命令：`pytest tests/ --tb=short -q --ignore=tests/integration --ignore=tests/manual`
- 测试环境：`TEST_DATABASE_URL=postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test`，`APP_ENV=test`
- 测试结果：**936 passed, 16 skipped, 0 failed**（812.74s）
- 16 个 skipped 明细：
  - 2 个 ADM-02 标签管理路由测试（test_tag_management_routes_smoke / test_tag_management_cross_school_404）
  - 2 个 AI 发布标签白名单测试（test_invalid_tags_dropped / test_b_school_tag_dropped_in_a_school）
  - 1 个发布流程标签上限测试（test_create_post_with_tags_limit）
  - 1 个 schema 标签上限测试（test_tags_max_five）
  - 1 个帖子创建带标签测试（test_create_post_with_tags）
  - 1 个非实质字段 tags 修改测试（test_non_substantial_tags_change_stays_published）
  - 其余为既有跳过（integration 模块级跳过、PostType 相关跳过等）

### 7.2 未运行测试
- integration 测试（依赖存储过程/触发器/分区等高级 SQL 对象，模块级跳过）
- manual 测试（手动验证脚本，不纳入自动化测试）

### 7.3 未执行端到端自动化测试
- 因 Task 1.3 仅涉及后端模型/接口清理，未引入新的用户交互链路，本次未执行 integrated_code_mode 端到端浏览器测试。前端标签 UI 清理在 Task 3.x 阶段统一处理后另行验证。

## 8. 后续建议

1. **前端清理**（Task 3.1-3.2）：移除前端标签选择器、标签筛选器、标签管理后台页面
2. **数据库迁移执行**：在演示环境执行 `alembic upgrade head` 应用 x3c4d5e6f7g8 迁移，DROP tags / post_tags 表
3. **种子脚本重跑**：清理后的 seed_data.py 可直接重跑，不再写入 tags / post_tags 数据
4. **文档更新**（Task 7.4）：更新 TODO.md 和相关文档反映 Tag 删除
