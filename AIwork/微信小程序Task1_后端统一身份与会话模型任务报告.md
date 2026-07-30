# 任务报告：微信小程序 Task 1 - 后端统一身份与会话模型

## 1. 任务概述

为"此刻校园"项目实现微信小程序接入的后端基础——统一身份模型和服务端会话管理。核心目标是支持微信一键登录，实现 Web 与小程序跨端统一账号体系，同时保证现有 Web 邮箱登录不受影响。

## 2. 已完成内容

- ✅ 创建 `user_auth_identities` 模型：支持 email_password / wechat_miniprogram 等多种身份类型
- ✅ 创建 `auth_sessions` 模型：支持单端会话撤销、设备管理、refresh token 轮换
- ✅ 创建 `binding_tickets` 模型：一次性绑定凭证，5 分钟有效
- ✅ 创建微信认证 schemas（请求/响应模型）
- ✅ 实现 `POST /auth/wechat/exchange`：微信 code 换登录态（已绑定直接签发 JWT，未绑定返回 binding_ticket）
- ✅ 实现 `POST /auth/wechat/bind-existing`：绑定已有 Web 账号到微信 openid
- ✅ 实现 `POST /auth/wechat/register`：微信新用户注册（可选邮箱，自动生成临时邮箱）
- ✅ 实现 `GET /auth/wechat/identities`：查看已绑定身份
- ✅ 实现 `POST /auth/wechat/identities/email`：添加邮箱登录方式
- ✅ 实现 `DELETE /auth/wechat/identities/{id}`：解绑登录方式（至少保留一种）
- ✅ 实现 `GET /auth/wechat/sessions`：查看登录设备列表
- ✅ 实现 `DELETE /auth/wechat/sessions/{id}`：撤销指定设备会话
- ✅ 实现 `POST /auth/wechat/logout-all`：退出全部设备
- ✅ 双读兼容策略：现有注册/登录自动创建 email_password 身份记录
- ✅ 懒迁移策略：老用户首次登录时自动回填身份记录
- ✅ 现有登录/注册流程增加 AuthSession 记录（支持设备会话管理）
- ✅ 微信 AppID/AppSecret 配置项添加到 config.py
- ✅ 17 个新测试 + 14 个现有测试全部通过（31/31）

## 3. 未完成内容

- 正式微信 AppID/AppSecret 配置到 `.env.opengauss`（当前使用模拟模式）
- 迁移脚本 `migrate_identities.py` 需在正式环境执行一次（回填历史用户）
- 全量后端测试回归验证（后台运行中）

## 4. 实现思路

### 4.1 双读迁移策略

采用"并行支持 + 自动回填"策略，确保零停机迁移：

1. **User 表保持不变**：`email` 和 `password_hash` 仍为 NOT NULL，新用户仍需邮箱注册
2. **身份表并行存储**：`user_auth_identities` 表记录所有登录方式
3. **懒迁移**：现有用户首次登录时，自动在身份表中创建 `email_password` 记录
4. **微信用户自动生成邮箱**：`wx_{openid_hash}@momentcampus.local` 格式

### 4.2 会话管理设计

- `AuthSession` 表存储每个 refresh_token 的 SHA-256 哈希（不存明文）
- 支持按设备 ID 标识，便于用户查看登录设备
- 支持单设备撤销（不影响其他设备）和全部撤销
- 会话类型：web / miniprogram / wechat

### 4.3 绑定凭证安全

- `BindingTicket` 存储 SHA-256 哈希，不存明文
- 5 分钟有效期，一次性使用
- 绑定成功后立即标记为已使用

### 4.4 开发模式

- 微信 AppID/AppSecret 未配置时，自动进入模拟模式
- 模拟模式下 code2Session 返回基于 code 的确定性 openid
- 便于本地开发和测试

## 5. 修改文件

### 新增文件
- `backend/app/models/user_auth_identity.py` — 用户身份模型
- `backend/app/models/auth_session.py` — 服务端会话和绑定凭证模型
- `backend/app/schemas/wechat_auth.py` — 微信认证请求/响应 schemas
- `backend/app/services/wechat.py` — 微信 code2Session 和 binding_ticket 服务
- `backend/app/api/wechat_auth.py` — 微信认证 API 路由（9 个端点）
- `backend/app/scripts/migrate_identities.py` — 历史数据迁移脚本
- `backend/tests/test_wechat_auth.py` — 17 个微信认证测试

### 修改文件
- `backend/app/models/user.py` — 添加 auth_identities 和 auth_sessions 关系
- `backend/app/models/__init__.py` — 注册新模型到 __all__
- `backend/app/config.py` — 添加 WECHAT_APPID、WECHAT_APPSECRET、BINDING_TICKET_EXPIRE_SECONDS 配置
- `backend/app/api/auth.py` — 注册/登录时自动创建身份记录和会话记录
- `backend/app/api/router.py` — 注册微信认证路由
- `backend/tests/conftest.py` — test_user fixture 添加 id 字段

## 6. 影响范围

- **认证模块**：现有 auth.py 注册/登录流程增加了身份记录和会话记录创建
- **数据库**：新增 3 张表（user_auth_identities、auth_sessions、binding_tickets）
- **前端小程序**：Task 2 依赖此模块实现微信登录功能
- **现有 Web 用户**：完全兼容，登录体验无变化

## 7. 测试与验证

### 已执行测试
- `pytest tests/test_auth.py -v`：✅ 14/14 通过（现有认证测试无回归）
- `pytest tests/test_wechat_auth.py -v`：✅ 17/17 通过（微信认证新测试）
- 合计：✅ 31/31 通过

### 测试覆盖的关键场景
- 微信 exchange：已绑定直接认证、未绑定返回 binding_ticket
- 绑定已有账号：成功绑定、密码错误、票据过期
- 微信注册：成功注册、自定义邮箱、重复 openid/邮箱检测
- 身份管理：查看列表、添加邮箱方式、解绑、至少保留一种
- 会话管理：查看、撤销单个、退出全部
- 双读兼容：现有邮箱登录仍正常、懒迁移自动回填

### 未执行测试
- 全量后端 `pytest tests/ -v`（后台运行中，预计 5-10 分钟）

## 8. 后续建议

1. **立即**：运行全量后端测试，确认无其他模块回归
2. **正式部署前**：将微信 AppID/AppSecret 配置到 `backend/.env.opengauss`
3. **正式部署前**：执行 `python -m app.scripts.migrate_identities` 回填历史用户身份
4. **Task 2 启动**：小程序工程骨架重构与请求层实现
5. **微信域名配置**：在小程序后台配置 `campus.chaina1.com` 为合法域名
6. **真机验证**：在 Android/iOS 真机上测试完整微信登录流程
