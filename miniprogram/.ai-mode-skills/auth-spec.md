# Auth Spec - 此刻校园小程序

## 1. 鉴权方式

JWT Bearer Token 鉴权。所有需要登录的请求在 Header 中携带 `Authorization: Bearer {access_token}`。

## 2. Token 来源

- **access_token**: `wx.getStorageSync('access_token')`
- **refresh_token**: `wx.getStorageSync('refresh_token')`

## 3. 登录方式

### 3.1 微信登录
1. `wx.login()` 获取临时 code
2. POST `/auth/wechat/exchange` body: `{ code }`
3. 返回 `{ status: 'authenticated', access_token, refresh_token, user }` 或 `{ status: 'binding_required', binding_ticket }`
4. 存储 token: `wx.setStorageSync('access_token', access_token)` + `wx.setStorageSync('refresh_token', refresh_token)`

### 3.2 邮箱密码登录
1. POST `/auth/login` body: `{ email, password }`
2. 返回 `{ access_token, refresh_token, user }`

## 4. 请求鉴权

### 4.1 Authorization Header
```
Authorization: Bearer {access_token}
```

### 4.2 学校代码 Header
```
X-School-Code: {school_code}
```
- school_code 来自 `wx.getStorageSync('school_code')`
- 默认值: `jiangnan`

### 4.3 Token 自动刷新
- 当请求返回 401 时，自动尝试用 refresh_token 换取新的 access_token
- POST `/auth/refresh` body: `{ refresh_token }`
- 刷新成功后重发原请求
- 刷新失败则清除 token 并跳转登录页

## 5. 公开接口（无需鉴权）

以下 URL 路径包含 `/auth/`，请求时不携带 Authorization header：
- `/auth/login`
- `/auth/register`
- `/auth/refresh`
- `/auth/wechat/exchange`
- `/auth/wechat/bind-existing`
- `/auth/wechat/register`

## 6. 初始化流程

1. `onLaunch`: `authStore.initFromStorage()` 从 storage 恢复登录态
2. 检查 `authStore.getState().isLoggedIn`
3. 未登录则 `wx.reLaunch({ url: '/pages/login/login' })`

## 7. 登出

1. POST `/auth/logout`
2. 清除 storage: `wx.removeStorageSync('access_token')` + `wx.removeStorageSync('refresh_token')`
3. 清除内存状态
4. `wx.reLaunch({ url: '/pages/login/login' })`