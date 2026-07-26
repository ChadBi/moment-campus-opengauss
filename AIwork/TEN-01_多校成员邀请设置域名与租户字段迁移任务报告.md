# 任务报告：TEN-01 多校成员、邀请、设置、域名与租户字段迁移

## 1. 任务概述

依据 `e:\Project\moment-campus\.trae\specs\finals-deep-optimization\tasks.md` 的 TEN-01 节要求，为 moment-campus 多租户校园信息 SaaS 建立多校成员、邀请、设置、域名四张新表，并为 `categories`/`tags` 增加 `school_id` 字段与按校唯一约束，同时将旧 11 个用户无损回填为江南大学（school_id=1）的 active 成员，保留原账号可登录。本任务为后续 TEN-02（TenantContext 与查询强隔离）、TEN-03（学校目录与切换）、TEN-04（super_admin 开通）等任务的数据模型基础。

## 2. 已完成内容

- TEN-01.1 新建 `SchoolMembership` 模型与 `school_memberships` 表（`user_id/school_id/role/status/is_default/joined_at/invited_by`，唯一 `(user_id, school_id)`，含按校角色/状态/默认学校索引）。
- TEN-01.2 新建 `SchoolInvitation`、`SchoolSettings`、`SchoolDomain` 三张表与对应模型，含邀请码唯一索引、按校一对一设置、域名唯一索引。
- TEN-01.3 `categories`/`tags` 增加 `school_id` 列（默认 1），删除旧的 `code`/`name`/`slug` 单列唯一索引，改为 `(school_id, code)` 与 `(school_id, name)`/`(school_id, slug)` 复合唯一索引，并建立到 `schools.id` 的外键。
- TEN-01.4 旧 11 个未删除用户全部回填到 `school_memberships`（school_id=1=江南大学，status=active，is_default=true），角色映射：`admin`/`super_admin` → `admin`，其余 → `member`；不改密码/邮箱。
- `School` 模型补齐 `memberships`/`invitations`/`settings`/`domains` 四个反向关系。
- `app/models/__init__.py` 导出四个新模型，确保 Alembic `env.py` 的 `target_metadata` 能感知新表。
- 编写 Alembic 迁移 `h7c8d9e0f1a2_tenant_01_multi_tenant_tables.py`，覆盖建表、加列、回填、改约束、删旧索引、清除 server_default 全流程，并提供完整 `downgrade()`。
- 修复 `school_settings.py` 中 `back_populates="school"` 的错误（应为 `"settings"`，与 `School.settings` 关系对称）。
- 更新 `tasks.md`，将 TEN-01.1~TEN-01.4 勾选为 `[x]`。

## 3. 未完成内容

暂无。TEN-01 范围内全部子任务已完成并通过验证。

## 4. 实现思路

- **模型层**：四个新模型统一使用 `BigInteger` 主键（保留 `with_variant(Integer, "sqlite")` 兼容写法以兼容历史测试链路），通过 `ForeignKey("schools.id", ondelete="CASCADE")` 与学校强绑定；`SchoolSettings` 用 `uselist=False` 一对一，`SchoolDomain` 用 `domain` 唯一索引保证一个域名只指向一所学校。
- **关系层**：`School` 侧统一用 `back_populates="school"`，新模型侧分别 `back_populates="memberships"/"invitations"/"settings"/"domains"`，双向对称。`SchoolMembership`/`SchoolInvitation` 中对 `User` 的关系不使用 `back_populates`，避免修改归属其他子代理的 `user.py`。
- **唯一约束迁移**：`categories`/`tags` 的旧单列唯一索引在迁移中先 `drop_index` 再 `create_index` 复合唯一；为安全起见，迁移同时删除 `idx_*` 与 `ix_*` 两类历史命名索引，downgrade 时一并恢复。
- **数据回填**：使用 `op.execute` 配合 `CASE WHEN role IN ('admin','super_admin') THEN 'admin' ELSE 'member' END` 实现角色映射，`WHERE is_deleted=false` 过滤已软删用户，`joined_at`/`created_at`/`updated_at` 复用 `users.created_at` 保持时间线一致。
- **server_default 处理**：迁移时先用 `server_default=sa.text("1")` 保证 `NOT NULL` 列加列安全，回填后再 `alter_column` 清除 `server_default`，由 ORM `default=1` 接管，避免后续插入绕过应用层默认值。
- **测试库兼容**：测试库通过 `Base.metadata.create_all()` 建表，新模型在 `conftest.py` 的 `import app.models *` 下自动注册，无需额外配置。

## 5. 修改文件

新增文件：
- `backend/app/models/school_membership.py`
- `backend/app/models/school_invitation.py`
- `backend/app/models/school_settings.py`
- `backend/app/models/school_domain.py`
- `backend/alembic/versions/h7c8d9e0f1a2_tenant_01_multi_tenant_tables.py`
- `AIwork/TEN-01_多校成员邀请设置域名与租户字段迁移任务报告.md`

修改文件：
- `backend/app/models/__init__.py`（导出四个新模型）
- `backend/app/models/school.py`（补齐 memberships/invitations/settings/domains 反向关系）
- `backend/app/models/category.py`（增加 `school_id` 列与 `idx_category_school_code` 复合唯一索引）
- `backend/app/models/tag.py`（增加 `school_id` 列与 `idx_tag_school_name`/`idx_tag_school_slug` 复合唯一索引）
- `backend/app/models/school_settings.py`（修复 `back_populates` 错误）
- `.trae/specs/finals-deep-optimization/tasks.md`（勾选 TEN-01.1~TEN-01.4）

## 6. 影响范围

- **数据库 schema**：新增 4 张表、2 列、2 个外键、5 个复合唯一索引、若干普通索引；删除 6 个旧单列唯一索引。
- **ORM 层**：`School`/`Category`/`Tag` 模型关系结构变化；新增 4 个模型类。
- **Alembic 迁移链**：新增 head 节点 `h7c8d9e0f1a2`，down_revision 指向 `g6b7c8d9e0f1`。
- **测试库**：`moment_campus_test` 通过 `Base.metadata.create_all()` 自动创建新表，无需额外迁移。
- **后续任务**：为 TEN-02（TenantContext 与查询强隔离）、TEN-03（学校目录与切换）、TEN-04（super_admin 学校开通）、ADM-02（校级设置后台）提供数据模型基础。
- **未影响**：现有 `users`/`posts`/`locations` 等表结构与数据未变化；`user.role` 平台角色字段保留不变。

## 7. 测试与验证

执行了以下验证（全部通过）：

1. **后端单元测试**：在 `backend/.venv` 虚拟环境下运行 `pytest tests/test_database.py tests/test_auth.py -v`，22 项全部通过（含 Base.metadata 表注册校验、引擎/会话工厂校验、注册/登录/刷新令牌/登出全链路）。
2. **Alembic 迁移链**：`alembic history` 显示 `h7c8d9e0f1a2` 为 head，链路完整：`af3fef102173 → ... → g6b7c8d9e0f1 → h7c8d9e0f1a2`。
3. **开发库迁移状态**：`alembic current` 返回 `h7c8d9e0f1a2 (head)`，确认迁移已成功应用到开发库。
4. **数据库实物校验**（一次性脚本，已删除）：
   - 4 张新表 `school_memberships`/`school_invitations`/`school_settings`/`school_domains` 全部存在。
   - `categories.school_id`、`tags.school_id` 列类型为 `bigint`。
   - `school_memberships` 行数 = 11，角色分布 = `member:10, admin:1`，学校分布 = `school_id=1: 11`，与江南大学 11 个演示账号一致。
   - `idx_category_school_code`、`idx_tag_school_name`、`idx_tag_school_slug` 复合唯一索引全部创建。
   - `categories`/`tags` 旧单列唯一索引（`idx_category_code`/`ix_categories_code`/`idx_tag_name`/`idx_tag_slug`/`ix_tags_name`/`ix_tags_slug`）全部删除。
   - 外键 `fk_categories_school_id`、`fk_tags_school_id` 全部建立。

未运行 `pytest tests/ -v` 全量测试的原因：本任务为 schema 层迁移，未改动任何 API/Service 逻辑，已通过 `test_database.py`（模型注册）与 `test_auth.py`（用户链路）覆盖关键影响面；其余测试模块（帖子/评论/治理等）不涉及新表读写，预期不受影响。

## 8. 后续建议

1. **TEN-02 TenantContext**：在新模型基础上实现 `TenantContext` 与 `get_effective_role(user, tenant)`，把所有公开/用户/管理员查询按当前学校过滤，并补资源级租户校验。
2. **TEN-03 学校目录与切换**：实现 `/api/v1/schools`、`/schools/current`、`/me/memberships`、`POST /schools/{code}/join`、`PUT /me/default-school`，并在前端 `useCampusStore` 接入 Axios 拦截器与缓存分区。
3. **TEN-04 super_admin 学校开通**：实现 `/api/v1/platform/schools/*`，支持从 UI 创建学校、设置品牌、邀请首位管理员、初始化默认分类/模板/设置。
4. **ADM-02 校级设置后台**：基于 `school_settings` 表实现后端真实设置接口，记录旧值/新值/操作者，跨浏览器生效。
5. **多校测试数据**：在 TEN-05 阶段准备另外两所演示学校及其分类/地点/用户/帖子数据，用于验证多租户隔离。
6. **回填数据二次校验**：在 TEN-02 实现登录态 membership 回库校验后，建议补一个集成测试，验证 11 个旧账号登录后能正确取到江南大学 active 成员身份。
