# refreshToken 改 httpOnly Cookie 方案评估报告

> **问题编号**：P2-004
> **决策结论**：**仅评估，不实施**（当前 localStorage + Bearer Token 方案保留至复赛演示后）
> **评估日期**：2026-07-26
> **评估依据**：`docs/project-audit/此刻校园项目全量排查报告.md`、`.trae/documents/项目优化实施计划.md` §6.2

---

## 1. 评估背景

当前 "此刻校园" 项目的认证令牌存储方案如下：

| 项                | 现状                                                                  |
| ---------------- | ------------------------------------------------------------------- |
| access_token 存储  | 前端 `localStorage`（zustand `useAuthStore`），所有 API 请求通过 Axios 拦截器注入 `Authorization: Bearer <token>` |
| refresh_token 存储 | 同上，前端 `localStorage`                                              |
| 后端接口风格          | RESTful，返回 JSON `{ access_token, refresh_token, user }`            |
| 跨域配置            | 后端 CORS 已开启，前端通过 `VITE_API_BASE_URL` 直连后端                        |
| 401 并发刷新         | 已加锁（`refreshPromise` 单例 promise，P2-006 修复）                       |
| 部署形态            | 单域名 Nginx 反代（前端静态资源 + `/api` 转发后端）                                 |

### 1.1 现状安全分析

**优点**：
- 实现简单，前后端解耦清晰；
- 跨域友好（CORS + Bearer Header）；
- 移动端 / 第三方客户端接入成本低；
- refresh_token 已通过 `refresh_tokens_invalid_before` 机制支持全局失效。

**风险点**：
- **XSS 风险**：localStorage 中 token 可被注入脚本读取（CSP 已配置缓解，但未根除）；
- **CSRF 风险**：低（Bearer Token 不会被浏览器自动附加，需手动注入 Header）；
- **持久化泄露**：浏览器 DevTools 可直接复制 token，复赛演示期间存在被截屏泄露风险。

---

## 2. httpOnly Cookie 方案设计

### 2.1 目标架构

```
┌────────────┐       POST /auth/login        ┌──────────────┐
│  Frontend  │ ───────────────────────────► │   Backend    │
│ (浏览器)    │ ◄──────────────────────────  │  (FastAPI)   │
└────────────┘    Set-Cookie:                └──────────────┘
                  access_token (httpOnly, Secure, SameSite=Lax)
                  refresh_token (httpOnly, Secure, SameSite=Lax, Path=/auth)
                       │
                       ▼
┌────────────┐   普通请求自动携带 Cookie       ┌──────────────┐
│  Frontend  │ ───────────────────────────► │   Backend    │
└────────────┘                               └──────────────┘
                       │
                       ▼
┌────────────┐   401 → 后端读 refresh_token    ┌──────────────┐
│  Frontend  │ ◄──────────────────────────  │   自动续签     │
│            │    Set-Cookie: 新 token        └──────────────┘
└────────────┘
```

### 2.2 关键改造点

#### 后端（FastAPI）

1. **`app/api/auth.py`**：
   - `/auth/login` 返回 JSON 同时通过 `Response.set_cookie` 写入 `access_token` / `refresh_token`；
   - `/auth/refresh` 改为从 `Request.cookies` 读取 `refresh_token`，不再接受 body；
   - `/auth/logout` 调用 `Response.delete_cookie` 清除两个 cookie；
   - 接口签名需注入 `response: Response` 与 `request: Request` 参数。

2. **`app/core/security.py`**：
   - `get_current_user` 依赖项增加 fallback：优先读 `Authorization: Bearer`，缺失时回退到 `request.cookies.get("access_token")`（兼容过渡期）。

3. **`app/main.py`**：
   - 新增 `CookieMiddleware` 或在 CORS 中间件配置 `allow_credentials=True`；
   - CORS `allow_origins` 必须从 `*` 改为白名单（`allow_credentials=True` 时禁止 `*`）。

4. **配置项**：
   - 新增 `COOKIE_DOMAIN`、`COOKIE_SECURE`、`COOKIE_SAMESITE` 环境变量；
   - `backend/.env.example` 与 `deploy/.env.prod.example` 同步补齐。

#### 前端（React + Axios）

1. **`src/services/api.ts`**：
   - Axios 实例新增 `withCredentials: true`；
   - 移除请求拦截器中 `Authorization` Header 注入（保留兼容期 fallback）；
   - 401 响应拦截器简化：直接 `POST /auth/refresh`（无需传 refresh_token，浏览器自动带 cookie）。

2. **`src/store/useAuthStore.ts`**：
   - 移除 `refreshToken` 字段；
   - `accessToken` 保留（仅用于前端判断登录态，不再发送）；
   - `setAuth` / `logout` 方法精简。

3. **`src/services/auth.ts`**：
   - 登录 / 登出 / 刷新接口签名简化（无需手动管理 token 字符串）。

#### 部署

1. **`frontend/nginx.conf`**：
   - 反代 `/api` 时 `proxy_pass_header Set-Cookie`；
   - `proxy_cookie_path` 重写（如需跨路径）。

2. **HTTPS 强制**：
   - `Secure` cookie 要求生产环境必须 HTTPS；
   - 本地开发可用 `localhost`（浏览器对 localhost 例外处理）。

3. **CORS 白名单**：
   - 生产环境 `allow_origins=https://moment-campus.example.com`，禁止 `*`。

---

## 3. 风险与成本评估

### 3.1 风险矩阵

| 风险等级 | 风险描述                                         | 影响                                | 应对策略                                                              |
| ---- | -------------------------------------------- | --------------------------------- | ----------------------------------------------------------------- |
| 🔴 高 | CORS + Cookie 改造涉及前后端联调，可能引入跨域认证失败          | 演示前阻塞                            | **不在演示前实施**；本地完整联调后再切生产                                           |
| 🔴 高 | 移动端 / 第三方客户端（如未来小程序）不便于处理 cookie            | 扩展性受限                             | 保留 Bearer Token 双模式 fallback（接口同时支持 cookie 与 Header）              |
| 🟡 中 | `SameSite=Lax` 可能导致第三方跳转回来时丢失登录态            | OAuth 回调场景受影响                      | 本项目无 OAuth，影响小；如需可改 `SameSite=None; Secure`（要求 HTTPS）              |
| 🟡 中 | 本地开发 HTTP 环境下 `Secure` cookie 不生效             | 开发体验下降                            | `COOKIE_SECURE` 通过环境变量控制，开发环境关闭                                  |
| 🟢 低 | refresh_token 走 cookie 后，前端无法主动续签            | 用户体验略变                            | 401 自动重试由后端触发，前端无感                                                |

### 3.2 改造成本估算

| 模块          | 改动文件数 | 代码行数（估） | 测试覆盖       |
| ----------- | ----- | ------ | ---------- |
| 后端 auth     | 4     | ~120   | 需新增 cookie 测试用例 |
| 后端 main/CORS | 2     | ~20    | 现有测试需调整    |
| 前端 api/store | 3     | ~80    | 现有 E2E 需重跑 |
| 配置 / 部署     | 5     | ~30    | 部署回归测试     |
| **合计**      | **14** | **~250** | **新增 6 用例** |

---

## 4. 收益评估

### 4.1 安全性提升

| 攻击向量          | 现状风险 | 改造后 | 备注                          |
| ------------- | ---- | ---- | --------------------------- |
| XSS 读取 token  | 中    | 低    | httpOnly 后 JS 无法读取          |
| CSRF          | 低    | 中    | cookie 自动携带，需配合 `SameSite`  |
| DevTools 复制泄露 | 高    | 低    | DevTools 仍可看 cookie，但无法 JS 读取 |
| 物理磁盘取证        | 高    | 中    | localStorage 持久化，cookie 会话级可选 |

### 4.2 工程化收益

- **统一认证态管理**：登录态生命周期由后端控制，前端无需感知 token 过期时间；
- **简化前端逻辑**：移除 `refreshPromise` 单例（P2-006）、移除 `useAuthStore.refreshToken`；
- **更易扩展**：未来支持 SSO / OAuth 时，cookie 方案天然兼容。

### 4.3 负面影响

- **跨端兼容性下降**：未来接入小程序 / App 时需保留 Bearer 双模式；
- **本地开发复杂度上升**：需配置 `COOKIE_SECURE=false` 或使用 mkcert 自签证书；
- **测试隔离变难**：cookie 在测试间需主动清理，否则会话串扰。

---

## 5. 决策与建议

### 5.1 决策结论

**当前阶段（复赛演示前）：保持现状（localStorage + Bearer Token），不实施 httpOnly Cookie 改造。**

**理由**：
1. **风险高于收益**：演示前 3 天改动认证核心模块，一旦引入回归 bug 将影响整个演示链路；
2. **现状已满足演示需求**：`refresh_tokens_invalid_before` + `refreshPromise` 加锁 + CSP 已将风险降至可接受水平；
3. **CORS 改造不可逆**：从 `allow_origins=*` 切换到白名单会影响所有现有客户端，需协调；
4. **时间成本不匹配**：~250 行代码 + 6 个测试用例 + 联调，预计 1.5 天，超出阶段五剩余预算。

### 5.2 后续版本规划

**建议在 v0.3.0（演示后）实施，分两阶段**：

1. **v0.3.0-alpha**：后端接口双模式（同时支持 cookie 与 Bearer），前端不改；
2. **v0.3.0-beta**：前端切换到 cookie 模式，保留 1 周灰度期；
3. **v0.3.0**：移除 Bearer Token 兼容代码，仅保留 cookie。

### 5.3 演示前临时加固措施（已实施）

- ✅ `refreshPromise` 单例加锁（P2-006）；
- ✅ `auth.py:380` 移除明文 `reset_token` 日志（P2-013）；
- ✅ `nginx.conf` 生产环境关闭 `/docs` 与 `/openapi.json`（P3-006）；
- ✅ CSP 头部已配置（缓解 XSS）；
- ✅ `refresh_tokens_invalid_before` 支持密码重置后全局失效。

---

## 6. 验收清单

| 项                                | 状态     | 备注                          |
| -------------------------------- | ------ | --------------------------- |
| 评估报告输出                            | ✅ 完成   | 本文档                         |
| 现状风险分析                            | ✅ 完成   | §1.1                        |
| 改造方案设计                            | ✅ 完成   | §2                          |
| 风险与成本评估                           | ✅ 完成   | §3                          |
| 收益评估                              | ✅ 完成   | §4                          |
| 决策结论                              | ✅ 完成   | §5.1：仅评估不实施                 |
| 后续版本规划                            | ✅ 完成   | §5.2                        |
| 临时加固措施                            | ✅ 完成   | §5.3                        |

---

## 7. 参考资料

- [RFC 6265bis: HTTP State Management Mechanism](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis)
- [OWASP Cookie Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cookie_Security_Cheat_Sheet.html)
- [FastAPI CORS Middleware](https://fastapi.tiangolo.com/tutorial/cors/)
- 项目内文档：`docs/project-audit/此刻校园项目全量排查报告.md` §4.3 安全
- 项目内文档：`.trae/documents/项目优化实施计划.md` §6.2 决策项汇总
