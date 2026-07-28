# 任务报告：Task 2.2 删除「保存当前查询」与「每日摘要」「邮件通知」相关后端

## 1. 任务概述

从后端移除三项功能：
1. **保存当前查询**：经审查后端从未实现此功能（无 `saved_searches` 表/API/模型），无需修改
2. **每日摘要**：从 `NotificationPreference` 模型移除 `site_digest_enabled` 开关与 `digest_time` 投递时间
3. **邮件通知**：从 `NotificationPreference` 模型移除 `email_enabled` 开关

属于「需要调整的地方」Issue #15、#16 的后端部分，前端 SearchPage/通知设置 UI 改造由 Task 3.3 处理。

## 2. 已完成内容

### 模型层
- `backend/app/models/notification_preference.py`：
  - 删除 `site_digest_enabled: Mapped[bool]` 字段
  - 删除 `digest_time: Mapped[str]` 字段
  - 删除 `email_enabled: Mapped[bool]` 字段
  - `NOTIFICATION_CATEGORIES` 从 7 类降为 6 类（移除 `site_digest`）
  - 更新类 docstring 说明 Task 2.2 调整

### API 层
- `backend/app/api/notifications.py`：
  - `NotificationPreferenceResponse` schema 移除 `site_digest_enabled` / `digest_time` / `email_enabled` 字段
  - `NotificationPreferenceUpdate` schema 移除同样三个字段
  - `_to_response()` 函数移除三个字段的赋值
  - 删除 `_validate_digest_time()` 函数（不再需要）
  - `update_notification_preferences` 端点移除三个字段的部分更新逻辑
  - `get_notification_preferences` 端点 docstring 从「7 类」改为「6 类」

### 数据库迁移
- `backend/alembic/versions/z5e6f7g8h9i0_remove_digest_email_preferences.py`：
  - `upgrade()`：drop_column 三个字段
  - `downgrade()`：恢复三个字段（默认值与原迁移 `s6g7h8i9j0k1` 一致）
  - 接续 Task 1.4 的 `y4d5e6f7g8h9`

### 测试更新
- `backend/tests/test_ux01_notification_preferences.py`：
  - `test_get_preferences_first_time_creates_default`：移除三个字段断言，新增「已下线字段不应出现在响应中」的反向断言
  - `test_update_preferences_partial_update`：改用 `governance_enabled` + `interaction_enabled` 验证部分更新（替代原 `site_digest_enabled` + `digest_time`）
  - 删除 `test_update_preferences_invalid_digest_time_format` 测试（字段已下线）
  - 文件头注释更新
- `backend/tests/manual/verify_notifications.py`：
  - 移除 digest_time 格式校验 E2E 步骤
  - 文件头注释更新

## 3. 未完成内容

暂无。前端 SearchPage 移除「保存查询」按钮、通知设置 UI 移除「每日摘要」「邮件通知」开关由 Task 3.3 处理。

## 4. 实现思路

1. **审查优先**：先搜索 `saved_search` / `SavedSearch` / `save_search` 关键字，确认后端从未实现「保存当前查询」功能，避免无谓修改。
2. **关键字搜索定位**：通过 `daily_digest` / `email_digest` / `digest` / `email_notification` 定位到 `NotificationPreference` 模型与 `notifications.py` API。
3. **三层同步移除**：
   - Model 层：移除字段定义与 `NOTIFICATION_CATEGORIES` 元组项
   - API 层：移除 Response/Update schema 字段、`_to_response` 赋值、`_validate_digest_time` 函数、`update_notification_preferences` 端点字段更新逻辑
   - DB 层：创建 Alembic 迁移 `drop_column` 三个字段
4. **测试同步更新**：
   - 默认值断言：移除三个字段断言，新增「字段不应出现」反向断言保护契约
   - 部分更新测试：改用未下线字段验证
   - 格式校验测试：整个删除（字段已下线）
5. **不过度清理**：`auth.py` / `ai/service.py` 中的 `digest` 是 `hashlib.sha256().hexdigest()`，与本任务无关，不修改。

## 5. 修改文件

### 后端代码（2 个）
- `backend/app/models/notification_preference.py`：模型字段与类别元组
- `backend/app/api/notifications.py`：API schema、辅助函数、端点逻辑

### 数据库迁移（1 个，新增）
- `backend/alembic/versions/z5e6f7g8h9i0_remove_digest_email_preferences.py`

### 测试文件（2 个）
- `backend/tests/test_ux01_notification_preferences.py`：断言更新 + 删除 1 个测试
- `backend/tests/manual/verify_notifications.py`：E2E 步骤移除

## 6. 影响范围

- **API 契约**：`GET/PUT /notifications/preferences` 响应字段减少 3 个（向后不兼容，前端需同步更新 Task 3.3）
- **数据库**：`notification_preferences` 表删除 3 列（`site_digest_enabled` / `digest_time` / `email_enabled`）
- **业务逻辑**：通知偏好类别从 7 类降为 6 类；安全约束（system/audit/instant 不可全关）保持不变
- **权限**：无影响（端点仍为登录用户可访问）
- **多租户**：无影响（偏好按 user_id 隔离，不涉及学校）
- **性能**：略微提升（少 3 列 IO，但影响微乎其微）

## 7. 测试与验证

### 单元测试

执行命令（PowerShell）：
```powershell
cd e:\Project\moment-campus\backend
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test'
$env:APP_ENV = 'test'
.\.venv\Scripts\python.exe -m pytest tests/test_ux01_notification_preferences.py -v --tb=short
```

**测试结果**：
```
7 passed, 15 warnings in 9.66s
```

- **7 个测试全部通过**
- 0 个失败

### 验证要点
1. `test_get_preferences_first_time_creates_default` 通过 → 默认偏好仅含 6 类开关，已下线字段不出现在响应中
2. `test_update_preferences_partial_update` 通过 → 改用未下线字段（governance/interaction）验证部分更新
3. `test_update_preferences_security_constraint_rejects_all_off` 通过 → 安全约束（system/audit/instant 全关拒绝）未受影响
4. `test_update_preferences_allows_closing_system_when_instant_on` 通过 → instant 开启时可关闭 system/audit
5. `test_preferences_isolated_per_user` 通过 → 用户隔离未受影响

### 未执行端到端自动化操作测试的原因

本任务为后端字段下线，影响面仅限于 `/notifications/preferences` 端点。已通过 7 个单元测试覆盖关键链路（默认值、部分更新、安全约束、用户隔离）。前端 SearchPage/通知设置 UI 改造在 Task 3.3 完成后，再统一进行端到端浏览器验证。

## 8. 后续建议

1. **前端同步**（Task 3.3）：
   - `SearchPage` 移除「保存当前查询」按钮（后端从未实现，前端按钮应为死代码）
   - 通知设置 UI 移除「每日摘要」「邮件通知」开关
   - `frontend/src/types/index.ts` 的 `NotificationPreference` 接口移除 `site_digest_enabled` / `digest_time` / `email_enabled` 字段
2. **回归测试**（Task 7.1）：重点验证通知偏好 API 在字段下线后仍正常工作，安全约束未失效
3. **API 文档**：若项目维护 OpenAPI 文档，需同步更新 `/notifications/preferences` 端点的响应 schema
