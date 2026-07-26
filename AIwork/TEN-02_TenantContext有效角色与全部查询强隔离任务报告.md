# 任务报告：TEN-02 TenantContext、有效角色与全部查询强隔离

## 1. 任务概述

实现多租户隔离的核心基础设施：TenantContext 上下文解析、有效角色计算、资源级校验、全部查询按当前学校过滤，并通过三校 API 隔离测试验证隔离完整性。目标是确保每个租户（学校）只能访问自己的数据，跨校访问统一返回 404（不泄露存在性）。

对应 spec：`.trae/specs/finals-deep-optimization/tasks.md` 中 TEN-02 的 4 个子任务。

## 2. 已完成内容

### TEN-02.1 实现 TenantContext
- 新建 `app/core/tenant.py`，实现 `TenantContext` 不可变数据类与 `get_tenant_context` FastAPI 依赖
- 解析优先级：`X-School-Code` 头 / `?school=` query 参数 → 登录用户默认学校（回查 schools 表确认存在且启用）
- 游客必须显式提供 school code，否则 404（不泄露学校列表）
- 写请求忽略 body 里的 school_id（在 posts.py / categories.py 等接口内部强制使用 tenant.school_id）

### TEN-02.2 get_effective_role + 资源级校验
- 实现 `get_effective_role(user, tenant)`：按 super_admin → membership.role → 旧用户兼容 → guest 计算有效角色
- 实现 `check_resource_in_tenant(resource_school_id, tenant)`：跨校访问统一抛 404（不返回 403 以免泄露存在性）
- 实现 `assert_writable_in_tenant(tenant)`：游客禁止写操作
- super_admin 跨校操作跳过 membership 校验，但资源级校验仍生效

### TEN-02.3 全部查询按当前学校过滤
- 为以下 9 个 API 模块接入 `TenantContext` 依赖并按 `tenant.school_id` 过滤：
  - `app/api/posts.py`：列表、详情、创建、更新均按租户过滤；跨校资源 404
  - `app/api/categories.py`：分类与地点列表按租户过滤；创建忽略 body school_id
  - `app/api/map.py`：地图标记按租户过滤
  - `app/api/search.py`：搜索结果按租户过滤
  - `app/api/notifications.py`：通知按租户过滤
  - `app/api/users.py`：用户帖子按租户过滤
  - `app/api/admin.py`：管理接口按租户过滤；跨校审核 404
  - `app/api/interactions.py`：点赞、评论资源级校验
  - `app/api/comments.py`：评论按租户过滤与资源级校验

### TEN-02.4 三校 API 隔离测试
- 新建 `tests/test_tenant_isolation.py`，37 条测试覆盖：
  - TenantContext 解析（header / query / 默认学校 / 游客无 code 404 / 不存在学校 404 / 无 membership 404）
  - get_effective_role 与 check_resource_in_tenant 单元测试
  - 查询隔离（帖子列表 / 分类 / 地点 / 搜索 / 地图标记 / 三校各自隔离）
  - 资源级校验（跨校帖子详情 404 / 同校详情 200）
  - 写请求忽略 body school_id（创建帖子 / 创建地点）
  - 跨校分类创建 404
  - 管理员隔离（A 校管理员只看 A 校待审核 / 跨校访问 404 / 跨校审核 404）
  - super_admin 跨校访问（可访问任意学校 / 资源级校验仍 404 / 同校资源 200）
  - 互动隔离（跨校点赞 / 评论 404 / 同校点赞 200）
  - 跨校创建无 DB 写入验证

## 3. 未完成内容

暂无。TEN-02 的 4 个子任务全部完成，37 条三校隔离测试全部通过。

## 4. 实现思路

### TenantContext 解析
设计为 FastAPI 依赖，单次请求解析一次，不可变（`@dataclass(frozen=True)`）。
- 游客分支：必须显式提供 school code，回查 schools 表确认存在且 is_active=true
- 登录用户分支：显式 code 优先，否则用 user.school_id；super_admin 跳过 membership 校验；普通用户需 active membership（兼容旧用户 user.school_id 匹配）

### 有效角色
平台角色与租户角色分离：super_admin 平台级优先；其他用户按 membership.role 映射（admin→admin, member→user）；旧用户无 membership 但 user.school_id 匹配视为 user。

### 资源级校验
统一 `check_resource_in_tenant()`，跨校返回 404 而非 403，避免泄露资源存在性。在所有详情/更新/审核接口加载资源后调用。

### 查询过滤
所有列表接口的 select 查询加 `.where(Model.school_id == tenant.school_id)`。

## 5. 修改文件

### 新建
- `app/core/tenant.py`：TenantContext、get_tenant_context、get_effective_role、check_resource_in_tenant
- `tests/test_tenant_isolation.py`：37 条三校隔离测试

### 修改（接入 TenantContext 与租户过滤）
- `app/api/posts.py`
- `app/api/categories.py`
- `app/api/map.py`
- `app/api/search.py`
- `app/api/notifications.py`
- `app/api/users.py`
- `app/api/admin.py`
- `app/api/interactions.py`
- `app/api/comments.py`
- `app/core/permissions.py`：集成 get_effective_role（延迟导入避免循环依赖）
- `tests/conftest.py`：setup_database 幂等预置套餐数据

### 更新
- `.trae/specs/finals-deep-optimization/tasks.md`：TEN-02 的 4 个子任务勾选完成

## 6. 影响范围

- 多租户隔离核心：所有按租户过滤的 API（帖子/分类/地点/搜索/地图/通知/用户/管理/互动/评论）
- 权限系统：effective_role 计算与资源级校验
- 测试：三校隔离测试套件
- 不影响：数据模型（未改 models/*）、迁移（未改 alembic/*）、platform 路由（COM-01 负责）

## 7. 测试与验证

执行命令：
```powershell
cd e:\Project\moment-campus\backend
$env:APP_ENV="opengauss"
$env:TEST_DATABASE_URL="postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"
.\.venv\Scripts\python.exe -m pytest tests/test_tenant_isolation.py -v --tb=short
```

结果：**37 passed, 190 warnings in 147.89s**

测试期间修复了 2 个测试问题：
1. `test_admin_cross_school_approve_returns_404`：approve 接口需要 `ApproveRequest` body（reason 可选），补充 `json={"reason": "审核通过"}` 后通过
2. `test_cross_school_create_no_db_write`：`db_session.expire_all()` 是同步方法不能 await，改为用全新 session 统计 count_after 后通过

## 8. 后续建议

1. TEN-03 可基于本任务的 TenantContext 实现学校目录、加入、默认学校、切换与缓存分区
2. 安全日志：跨校访问目前返回 404，建议在 middleware 或 check_resource_in_tenant 中补记安全日志（checklist 中提到"产生安全日志"）
3. AI 日志/历史/统计的租户过滤：当前测试覆盖了核心 API，AI 日志与浏览历史接口待 AI-01/PRF-01 实现后补充隔离验证
4. 缓存分区：TEN-03.2 前端缓存分区需配合后端 TenantContext 的 X-School-Code 头实现
