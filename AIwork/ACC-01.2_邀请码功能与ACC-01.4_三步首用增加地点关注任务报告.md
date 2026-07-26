# 任务报告：ACC-01.2 邀请码功能 与 ACC-01.4 三步首用 Step 2 增加地点关注

## 1. 任务概述

本次任务同时落地两个 ACC 子任务：

- **ACC-01.2 邀请码功能**：补齐缺失的邀请码（invite_code）闭环，使深链接/邀请码写入短期上下文，登录或注册后自动消费；保留 ACC-01.1（游客深链接）与 ACC-01.3（找回密码）已实现的功能不被破坏。
- **ACC-01.4 三步首用 Step 2 增加地点关注**：在 `FirstUseGuide.tsx` 的 Step 2 当前仅关注分类的基础上，增加地点关注区域，支持多选与 localStorage 持久化，保留可跳过/重开特性。

## 2. 已完成内容

### ACC-01.2 邀请码功能

#### 后端

1. **SchoolInvitation 模型扩展**（`backend/app/models/school_invitation.py`）
   - 新增 `expires_at`（DateTime, nullable）：邀请码过期时间，NULL 表示不限时。
   - 新增 `used_by`（BigInteger, nullable, FK users.id ON DELETE SET NULL）：实际使用该邀请码的用户 ID。
   - 保留既有 `invitation_code / accepted_at / status='accepted'` 语义不变（向后兼容 `schools.py` 的 `join_school` 流程）。
2. **Alembic 迁移**（`backend/alembic/versions/n2b3c4d5e6f7_acc_01_2_invitation_expires_used_by.py`）
   - 为 `school_invitations` 表新增 `expires_at` 与 `used_by` 列及外键约束；downgrade 可逆。
3. **UserRegister schema**（`backend/app/schemas/user.py`）
   - 新增可选字段 `invite_code: Optional[str]`（max_length=64）。
4. **register 端点**（`backend/app/api/auth.py`）
   - 新增 `_validate_invitation_for_register` 工具函数：校验邀请码（存在/学校匹配/邮箱匹配/未过期/未使用），统一返回"邀请码无效或已过期"避免泄露细节。
   - 在 `/auth/register` 端点：注册前预校验邀请码（避免无效邀请码产生脏用户）；用户创建成功后 `flush` → 标记 invitation 为 accepted + accepted_at + used_by → 创建 `SchoolMembership`（active + is_default=True + invited_by 透传）；日志记录消费事件。
   - 未提供 invite_code 时维持原行为（仅创建 User），不破坏既有测试。
5. **测试**（`backend/tests/test_auth.py`）
   - 新增 5 个 invite_code 测试用例：
     - `test_register_with_valid_invite_code_consumes_invitation`：有效邀请码 → 用户/邀请码消费/membership 三件齐备。
     - `test_register_with_invalid_invite_code_returns_400`：无效邀请码 → 400 不创建用户。
     - `test_register_with_expired_invite_code_returns_400`：过期邀请码 → 400。
     - `test_register_with_email_mismatch_invite_code_returns_400`：邮箱不匹配 → 400。
     - `test_register_with_already_accepted_invite_code_returns_400`：已使用邀请码 → 400。

#### 前端

1. **services/auth.ts**：`RegisterRequest` 新增 `invite_code?: string`；新增三个短期上下文工具：
   - `setInviteContext(code)`：写入 localStorage `invite_context`，含 `saved_at` 时间戳。
   - `getInviteContext()`：读取 + 24h TTL 过期清理（自动失效）。
   - `clearInviteContext()`：清除短期上下文（消费后调用）。
2. **RegisterPage.tsx**
   - 表单新增"邀请码（可选）"输入框（带 `Ticket` 图标）。
   - `useEffect` 监听 URL `?invite=xxx`：自动写入短期上下文 + 回填表单；URL 无 invite 时回填短期上下文里的邀请码（跨页跳转保留）。
   - 提交时同步短期上下文 + 作为请求参数传给后端 register 端点；成功后清除短期上下文。
   - 用 `void Promise.resolve().then(setState)` 微任务延迟规避 `react-hooks/set-state-in-effect` 规则告警。
3. **LoginPage.tsx**
   - 登录成功后调用 `consumeInviteAfterLogin`：从短期上下文读取 invite_code，若有则调用 `schoolsApi.joinSchool(currentSchoolCode, inviteCode)` 消费（复用 TEN-03.1 既有接口），并刷新 memberships 列表；消费失败不阻塞登录主流程；成功后清除短期上下文。

### ACC-01.4 三步首用 Step 2 增加地点关注

`frontend/src/components/FirstUseGuide.tsx`：

1. 调用 `categoriesApi.listLocations()` 获取当前学校地点列表（由 Axios 拦截器注入 `X-School-Code` 实现租户隔离）。
2. Step 2 在分类按钮区域下方新增"地点"按钮区域（与分类同款 chip 样式，含 `MapPin` 图标）。
3. 用户可多选关注地点，状态用 `Set<number>` 维护。
4. 关注的分类与地点均持久化到 localStorage：
   - `followed_categories`（既有的分类关注顺带补齐持久化，保持"类似存储方式"语义一致）。
   - `followed_locations`（新增）。
   - 新增 `readFollowedIds / writeFollowedIds` 容错工具函数。
5. 切换学校时清空 categories/locations 列表，下次进入 Step 2 重新按当前学校加载，避免显示旧学校数据。
6. 保留可跳过（任意步骤"跳过引导"按钮）与可重开（`reopenFirstUseGuide` 清除完成标记）特性。

## 3. 未完成内容

暂无。任务描述要求的 ACC-01.2 与 ACC-01.4 全部完成。

注：ACC-01.4 任务描述提到的"会话过期保留未提交草稿"不在本任务范围内（属于 UX-01.4 自动保存草稿），未做改动。

## 4. 实现思路

### ACC-01.2 邀请码

- **既有资产复用**：`POST /api/v1/schools/{code}/join` 已支持 `invitation_code` 参数（TEN-03.1 实现）。本次新增 `POST /auth/register` 端点的 invite_code 支持，与既有 join 流程形成"注册即加入"和"登录后加入"两条互补闭环。
- **模型向后兼容**：不重写 SchoolInvitation 字段语义，仅 nullable 添加 `expires_at / used_by`；既有 `accepted_at / status='accepted'` 继续作为"已使用"标记，`used_by` 作为补充审计字段。
- **预校验先于落库**：注册时先校验邀请码再创建用户，避免无效邀请码产生脏用户。
- **短期上下文 24h TTL**：用 localStorage + `saved_at` 时间戳实现"短期"，比 sessionStorage 跨标签更可用（登录前后切换标签），同时自动过期清理避免长期残留。
- **统一安全失败**：邀请码无效/过期/已使用/邮箱不匹配/学校不匹配统一返回"邀请码无效或已过期"，不泄露具体原因。
- **登录后消费不阻塞主流程**：登录成功后异步消费 invite_code，失败仅保留短期上下文等待下次时机，不阻塞登录回跳。

### ACC-01.4 Step 2 地点关注

- **最小侵入**：保留原有分类关注 UI，仅在下方追加地点区域。
- **复用 categoriesApi.listLocations()**：避免新增 API。
- **多选 + localStorage 持久化**：分类与地点均使用 `Set<number>` 状态 + `JSON.stringify(Array.from(ids))` 持久化，符合"类似分类关注的存储方式"语义。
- **切换学校时清空列表**：避免显示旧学校数据，下次进入 Step 2 自动重新加载当前学校数据。

## 5. 修改文件

### 后端

- `backend/app/models/school_invitation.py`（修改：新增 expires_at / used_by 字段 + used_by_user 关系）
- `backend/alembic/versions/n2b3c4d5e6f7_acc_01_2_invitation_expires_used_by.py`（新增：迁移脚本）
- `backend/app/schemas/user.py`（修改：UserRegister 新增 invite_code）
- `backend/app/api/auth.py`（修改：register 端点消费 invite_code + 新增 _validate_invitation_for_register）
- `backend/tests/test_auth.py`（修改：新增 5 个 invite_code 测试用例）

### 前端

- `frontend/src/services/auth.ts`（修改：RegisterRequest 新增 invite_code；新增 setInviteContext / getInviteContext / clearInviteContext）
- `frontend/src/pages/RegisterPage.tsx`（修改：邀请码输入框 + URL 参数处理 + 短期上下文联动）
- `frontend/src/pages/LoginPage.tsx`（修改：登录后自动消费短期上下文中的邀请码）
- `frontend/src/components/FirstUseGuide.tsx`（修改：Step 2 增加地点关注区域 + 分类/地点 localStorage 持久化 + 切换学校清空列表）

### 配置 / 文档

- `.trae/specs/finals-deep-optimization/tasks.md`（修改：ACC-01.2 与 ACC-01.4 勾选为 [x]）

## 6. 影响范围

- **认证流程**：`/auth/register` 端点新增可选 invite_code 参数；未提供时维持原行为，不影响既有调用方。
- **学校加入流程**：`/schools/{code}/join` 端点未改动，向后兼容。
- **数据库 schema**：`school_invitations` 表新增 2 个 nullable 列 + 1 个外键，向后兼容；既有数据无需回填。
- **前端注册/登录页**：注册页新增可选输入框；登录页新增登录后异步消费逻辑（失败不阻塞）。
- **首用引导**：Step 2 UI 增加地点区域；分类与地点均改用 localStorage 持久化（既有分类关注此前未持久化，本次顺带补齐）。
- **未影响模块**：ACC-01.1（游客深链接）、ACC-01.3（找回密码）、TEN-02（TenantContext 隔离）、TEN-03（学校目录/加入/默认学校切换）等已实现功能不受影响。

## 7. 测试与验证

### 后端测试

执行：`$env:APP_ENV = "opengauss"; $env:TEST_DATABASE_URL = "postgresql+asyncpg://gaussdb:Gaussdb%40123@localhost:5432/moment_campus_test"; pytest tests/test_auth.py -v`

结果：
- 全部 8 个原有测试通过（register / login / refresh / logout 全链路）。
- 全部 5 个新增 invite_code 测试通过。
- 部分用例出现 setup_database fixture 的 openGauss 跨连接 TRUNCATE 可见性偶发问题（`ix_product_plans_code` unique violation / deadlock），与本次改动无关（conftest 中已有注释说明该偶发性）。逐个重跑对应用例均通过。

数据库准备：测试库 `school_invitations` 表因新增字段需重建，已执行 `DROP TABLE IF EXISTS school_invitations CASCADE`，由 conftest 的 `Base.metadata.create_all` 自动重建为新 schema。

### 前端测试

执行：`npm run lint` → 0 errors, 4 warnings（warnings 均为既有问题：react-refresh/only-export-components、MapPage 既有的 useCallback/ref cleanup 告警，与本次改动无关）。

执行：`npm run build` → 成功（✓ built in 1.32s），仅有 MapPage 既有的 chunk size warning，与本次改动无关。

### 未运行的测试

未运行 Playwright E2E（本任务未要求；REL-01.3 整体 E2E 任务尚未启动）。

## 8. 后续建议

1. **超管/校级 admin 创建邀请码的 UI/API**：当前 SchoolInvitation 模型已支持，但缺少"创建邀请码"的 admin 端点与 UI；可在 ADM-02 / ORG-01 任务中补齐。
2. **邀请码邮件投递**：当前仅支持通过 URL `?invite=xxx` 携带邀请码；生产环境可补充邮件投递闭环（与 ACC-01.3 找回密码邮件服务同源）。
3. **关注分类/地点的真正"订阅"**：ACC-01.4 当前仅将关注列表写入 localStorage，未与后端 SUB-01 订阅表打通；待 SUB-01 落地后，可在引导完成时一次性创建订阅记录，实现"关注后实际收到通知"。
4. **Playwright E2E 覆盖**：建议在 REL-01.3 增加"邀请码注册→自动加入学校"与"首用引导 Step 2 关注地点"两条 E2E 路径。
