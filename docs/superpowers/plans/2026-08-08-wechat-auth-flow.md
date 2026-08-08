# 微信登录/绑定链路规范化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把小程序登录链路按用户期望清晰化：①点击「微信登录」先查当前微信是否已绑定账号 → 已绑定直接登录；未绑定 → 进入注册页填表单 → 注册完成自动将账号与该微信绑定并自动登录 → 跳个人中心显示"未进行校园邮箱验证"的登录态；②点击「绑定并登录」→ 先查该账号是否已绑定微信 → 未绑定才绑定并登录；已绑定则返回冲突错误；③登录/注册/绑定成功后统一回到个人中心页而不是首页，让用户看到登录态结果。

**Architecture:**

**后端侧（2 处小改动）**：
1. 补 `/auth/wechat/bind-existing` 中缺失的"该账号是否已绑定过微信"检查（目前只查 openid 是否已绑定其他用户，用户明确要求双向检查）——冲突返回 409 Conflict。
2. `WechatRegisterResponse` 和 `WechatBindExistingResponse` 响应补 `user` 字段（目前只返回 access_token/refresh_token，但 authStore.setAuth 依赖 `user in data` 才会置 isLoggedIn=true），避免前端再额外调一次 `/users/me`。

**前端侧（4 处改动）**：
1. 登录页 login：
   - 微信登录 Tab 成功后跳 `/pages/profile/profile`（个人中心）而不是 home
   - 邮箱登录 Tab 新增一个副按钮「绑定该微信并登录」→ wx.login → /exchange 拿 ticket → /bind-existing → setAuth → switchTab profile
   - 「还没有账号？立即注册」 goToRegister 成功拿到 binding_ticket 后跳 register 页，注册页注册成功后再自动跳 profile
2. 注册页 register：
   - mode=register（微信新用户注册）：成功后 switchTab profile
   - mode=bind（绑定并登录）：成功后 switchTab profile；错误 409 "该账号已绑定其他微信" + "该微信已绑定其他账号" 分别友好 toast
3. services/auth.ts：新增类型与入参不做结构性调整，仅确保 authStore.setAuth 时能拿到 user 字段
4. store/auth.ts：setAuth 兼容两种成功响应（exchange 成功的 user 对象 / register 和 bind-existing 成功后的 user 对象），如果响应带 user_id 但没 user，自动调 /users/me 回退拉取（防御性编程）

**Tech Stack:**
- 后端：FastAPI + SQLAlchemy 2.0 async + Pydantic v2（openGauss）
- 前端：微信原生小程序（WXML/WXSS/TS） + 自研 `authStore`/`campusStore` 状态 + `services/auth.ts` HTTP 封装
- 测试：`pytest tests/test_wechat_auth.py -v --asyncio-mode=auto` 后端；`wechatide simulator_*` 模拟器端到端

---

## File Structure（锁定修改边界）

| 路径 | 变更性质 | 本次改动职责 |
|---|---|---|
| `backend/app/schemas/wechat_auth.py` | 修改 | `WechatRegisterResponse` / `WechatBindExistingResponse` 新增 `user: dict` 字段 |
| `backend/app/api/wechat_auth.py` | 修改 | (A) `bind-existing` 加"该账号 user_id 是否已有 wechat_miniprogram 身份"检查，冲突 409；(B) register / bind-existing 成功时把 `UserResponse.model_validate(user).model_dump()` 塞进响应 |
| `backend/tests/test_wechat_auth.py` | 修改 | (A) 新测 `test_bind_existing_account_already_has_wechat_identity_fails`；(B) 原有的 3 个成功用例断言响应含 `user` 且 id 正确；(C) 微信注册后该用户邮箱未默认 campus_verified=True 的断言 |
| `miniprogram/pages/login/login.ts` | 修改 | (A) onWechatLogin status=authenticated 成功后 switchTab `/pages/profile/profile` 而非 home；(B) 新增 `onBindExistingTap()`（邮箱 Tab 中"绑定并登录"按钮 handler），内部 wx.login → wechatExchange(binding_required 取 ticket) → wechatBindExisting(email/password) → setAuth → profile；(C) 原有 goToRegister 保持，但拿到 binding_ticket 后跳转 register?ticket=xxx&from=login |
| `miniprogram/pages/login/login.wxml` | 修改 | 邮箱 Tab 中，在"登录"主按钮下方，新增一个次按钮「绑定该微信并登录」（用现有 submit-btn 样式 + 描边 secondary），并加一段说明副文案"已有此刻校园账号？可以用账号密码登录后绑定当前微信，下次直接用微信登录"。 |
| `miniprogram/pages/login/login.wxss` | 修改 | 新增 `.submit-btn-secondary`（描边湖蓝色，白底）+ `.bind-info-text` 样式 |
| `miniprogram/pages/register/register.ts` | 修改 | (A) mode=register 注册成功、mode=bind 绑定成功后，统一 `wx.switchTab({ url: '/pages/profile/profile' })`；(B) 错误时针对 409 的中文详情做更友好的 toast 前缀"绑定失败：" + detail |
| `miniprogram/store/auth.ts` | 修改 | `setAuth` 增加防御性兜底：如果 `('access_token' in data && !('user' in data) && 'user_id' in data)` → 内部调一次 `services/users.ts` 里的 getMe() 拿到 user 对象再写入，确保不会丢 user。保持向后兼容。 |
| `TODO.md` | 修改 | 新增 2026-08-08 微信登录链路规范化 12 条 [x] |
| `CHANGELOG.md` | 修改 | 新增 `[2.2.15] - 2026-08-08` 节点（修复登录链路不清晰） |
| `AIwork/微信登录绑定链路规范化_任务报告.md` | 新增 | 8 节真实报告 |

---

## Task 1: 后端 - `bind-existing` 补"账号已有绑定微信"冲突检查

**Files:**
- Modify: `backend/app/api/wechat_auth.py:169-260`（`wechat_bind_existing` 函数）
- Test: `backend/tests/test_wechat_auth.py`

- [ ] **Step 1: 先看现有代码位置（已读，确认缺口）**
  缺口：`wechat_bind_existing` 第 202-212 行只检查"该 openid 是否已被绑定为 wechat_miniprogram 身份"（即微信已被绑走），但未检查"该邮箱用户本身是否已经有一条 wechat_miniprogram 身份"——如果有，说明这个账号已经绑定了另一个微信，不该再绑第二个。返回 409。

- [ ] **Step 2: 写 failing 测试 test_bind_existing_account_already_has_wechat_identity_fails**
  放到 `backend/tests/test_wechat_auth.py` 末尾：
  ```python
  @pytest.mark.asyncio
  async def test_bind_existing_account_already_has_wechat_identity_fails(
      client: AsyncClient, test_user: dict, db_session: AsyncSession
  ):
      """绑定失败：账号本身已经绑过另一个微信了 → 409。"""
      # 先给 test_user 预先绑定一个 wechat_miniprogram 身份（模拟"该账号已经绑过微信"）
      pre_existing_identity = UserAuthIdentity(
          user_id=test_user["id"],
          identity_type="wechat_miniprogram",
          identity_key="pre_bound_openid_for_conflict_test",
          openid="pre_bound_openid_for_conflict_test",
      )
      db_session.add(pre_existing_identity)
      await db_session.commit()

      # 拿一张新的 binding_ticket（代表另一个微信）
      exchange_resp = await client.post(
          "/api/v1/auth/wechat/exchange",
          json={"code": "conflict_already_bound_account_code"},
      )
      assert exchange_resp.status_code == 200
      ticket = exchange_resp.json()["binding_ticket"]

      # 尝试绑定（同一个账号 userX 已经绑过微信 A，现在要再绑微信 B → 应 409 拒绝）
      bind_resp = await client.post(
          "/api/v1/auth/wechat/bind-existing",
          json={
              "binding_ticket": ticket,
              "email": test_user["email"],
              "password": test_user["password"],
          },
      )
      assert bind_resp.status_code == 409
      assert "该账号已绑定其他微信" in bind_resp.json()["detail"]
  ```

- [ ] **Step 3: 运行测试确认 FAIL（因为后端还没加检查）**
  Run:
  ```powershell
  cd backend; .venv\Scripts\python.exe -m pytest tests/test_wechat_auth.py::test_bind_existing_account_already_has_wechat_identity_fails -v --asyncio-mode=auto
  ```
  Expected: FAIL（应该拿 200 成功绑定而非 409）

- [ ] **Step 4: 在 wechat_bind_existing 中插入账号冲突检查**
  在验证密码通过之后、创建 wechat_identity 之前（L201 与 L202 之间），插入：
  ```python
      # 3.1 防御：该账号本身是否已绑定了另一个微信？
      # 一个账号只能有一条 wechat_miniprogram 身份（防止一号多绑导致用户下次登录时不知道登到谁）
      account_already_wechat_check = await db.execute(
          select(UserAuthIdentity).where(
              UserAuthIdentity.user_id == user.id,
              UserAuthIdentity.identity_type == "wechat_miniprogram",
              UserAuthIdentity.is_deleted == False,
          )
      )
      if account_already_wechat_check.scalar_one_or_none() is not None:
          raise ConflictException(detail="该账号已绑定其他微信，不能重复绑定")
  ```

- [ ] **Step 5: 运行测试确认 PASS**
  Run:
  ```powershell
  cd backend; .venv\Scripts\python.exe -m pytest tests/test_wechat_auth.py::test_bind_existing_account_already_has_wechat_identity_fails -v --asyncio-mode=auto
  ```
  Expected: PASS 409

- [ ] **Step 6: 提交 git（先不提交，整个 task 8 后一次性提交，保持小步也可以分开）**
  分开提交（本任务保持小步）：
  ```bash
  git add backend/app/api/wechat_auth.py backend/tests/test_wechat_auth.py
  git commit -m "fix(wechat): bind-existing 拒绝账号已绑定过另一微信的重复绑定"
  ```

---

## Task 2: 后端 - WechatRegisterResponse / WechatBindExistingResponse 响应补 user 字段

**Files:**
- Modify: `backend/app/schemas/wechat_auth.py`（35-42, 53-60 两个 Response 类）
- Modify: `backend/app/api/wechat_auth.py`（L252-259 bind-existing 的 return；L364-371 register 的 return）
- Test: `backend/tests/test_wechat_auth.py`（3 个成功用例断言 user 字段存在）

- [ ] **Step 1: 修改两个 schema 类，加 user 字段**
  ```python
  class WechatBindExistingResponse(BaseModel):
      """绑定成功响应（直接签发 JWT）。"""
      access_token: str
      refresh_token: str
      token_type: str = "bearer"
      user_id: int
      user: dict  # <-- 新增，与 exchange 成功响应保持一致
      message: str = "绑定成功"

  class WechatRegisterResponse(BaseModel):
      """微信注册成功响应。"""
      access_token: str
      refresh_token: str
      token_type: str = "bearer"
      user_id: int
      user: dict  # <-- 新增
      message: str = "注册成功"
  ```

- [ ] **Step 2: 改 api/wechat_auth.py 的 return 塞入 UserResponse.model_validate(user).model_dump()**
  bind-existing return 处（L252-259）：
  ```python
      user_data = UserResponse.model_validate(user).model_dump()
      return WechatBindExistingResponse(
          access_token=access_token,
          refresh_token=refresh_token,
          user_id=user.id,
          user=user_data,
          message="绑定成功",
      )
  ```
  register return 处（L364-371）：
  ```python
      user_data = UserResponse.model_validate(user).model_dump()
      return WechatRegisterResponse(
          access_token=access_token,
          refresh_token=refresh_token,
          user_id=user.id,
          user=user_data,
          message="注册成功",
      )
  ```

- [ ] **Step 3: 加 3 个断言到现有测试**
  - `test_wechat_exchange_bound`：已经断言 user_id，现在加 `assert data["user"]["id"] == test_user["id"]`
  - `test_wechat_bind_existing_success`：末尾加 `assert "user" in data` 和 `data["user"]["id"] == test_user["id"]`
  - `test_wechat_register_success`：末尾加 `assert "user" in data` 和 `data["user"]["id"] == user.id` 和 `data["user"]["campus_verified"] is False`（验证新用户默认未邮箱验证）

- [ ] **Step 4: 运行测试**
  ```powershell
  cd backend; .venv\Scripts\python.exe -m pytest tests/test_wechat_auth.py::test_wechat_exchange_bound tests/test_wechat_auth.py::test_wechat_bind_existing_success tests/test_wechat_auth.py::test_wechat_register_success -v --asyncio-mode=auto
  ```
  Expected: 3 PASS

- [ ] **Step 5: 提交 git**
  ```bash
  git add backend/app/schemas/wechat_auth.py backend/app/api/wechat_auth.py backend/tests/test_wechat_auth.py
  git commit -m "fix(wechat): register / bind-existing 响应带 user 字段，前端 setAuth 不再缺 user 置空登录态"
  ```

---

## Task 3: 前端 store/auth.setAuth 防御兜底（调 getMe 回退）

**Files:**
- Modify: `miniprogram/store/auth.ts`（`setAuth` 方法 L37-L47）
- Create or use existing: `miniprogram/services/users.ts`（若不存在就新建，加 `getMe(): Promise<User>`）

- [ ] **Step 1: 确认 services 里有没有 getMe**
  先 grep 一下：
  ```powershell
  cd miniprogram; grep -rn "getMe\|/users/me" services/
  ```
  若不存在就新建 `services/users.ts`：
  ```ts
  import { http } from './request'
  import type { User } from '../types'

  export async function getMe(): Promise<User> {
    return http.get<User>('/users/me')
  }
  ```

- [ ] **Step 2: 改 store/auth.ts setAuth**
  把原 L37-47 改成：
  ```ts
  async setAuth(
    data:
      | { access_token: string; refresh_token: string; user: User }
      | WechatExchangeResponse
      | { access_token: string; refresh_token: string; user_id: number; user?: User },
  ) {
    if ('access_token' in data) {
      state.accessToken = data.access_token
      state.refreshToken = data.refresh_token
      syncAuthTokens(data.access_token, data.refresh_token)
      if ('user' in data && data.user) {
        state.user = data.user
        state.isLoggedIn = true
      } else if ('user_id' in data) {
        // 防御性兜底：后端没返回 user 就自己 /users/me 拉一次
        state.isLoggedIn = false
        notify() // 先通知，避免 UI 卡住
        try {
          const { getMe } = await import('../services/users')
          const user = await getMe()
          state.user = user
          state.isLoggedIn = true
        } catch (err) {
          console.warn('[authStore] setAuth 后拉取 user 失败', err)
          state.isLoggedIn = false
        }
      } else {
        state.isLoggedIn = false
      }
    }
    notify()
  }
  ```
  注意 `setAuth` 调用方（前端 login/register.ts）目前是同步写法。调用方如果不 await 也能接受——先渲染 loading 然后 notify 第二次刷新。

- [ ] **Step 3: 提交 git**
  ```bash
  git add miniprogram/store/auth.ts miniprogram/services/users.ts 2>$null
  git commit -m "fix(auth): setAuth 响应缺 user 时走 /users/me 兜底拉取，避免 isLoggedIn=false 闪烁"
  ```

---

## Task 4: 前端 login 页改微信登录成功后跳 profile，邮箱 Tab 加「绑定并登录」按钮

**Files:**
- Modify: `miniprogram/pages/login/login.ts`（onWechatLogin 末尾；加 onBindExistingTap；加 data 字段）
- Modify: `miniprogram/pages/login/login.wxml`（邮件登录 Tab，主按钮下新增副按钮）
- Modify: `miniprogram/pages/login/login.wxss`（新增 .submit-btn-secondary + .bind-info-text）

- [ ] **Step 1: 改 login.ts**
  ① `onWechatLogin` L54-55：把 `wx.switchTab({ url: '/pages/home/home' })` 改为 `/pages/profile/profile`
  ② `onEmailLogin` L81-82：把 switchTab 也改为 `/pages/profile/profile`（用户体验一致：登录完回个人中心看自己是谁，邮箱是否验证）
  ③ 新增 data 字段 `bindLoading: false, bindErrorMsg: ''`
  ④ 新增 handler `onBindExistingTap`：
  ```ts
  async onBindExistingTap() {
    if (this.data.loading || this.data.bindLoading) return
    if (!this.data.email || !this.data.password) {
      this.setData({ errorMsg: '请填写邮箱和密码' })
      return
    }
    this.setData({ bindLoading: true, bindErrorMsg: '', errorMsg: '' })
    try {
      const code = await new Promise<string>((resolve, reject) => {
        wx.login({
          success: res => (res.code ? resolve(res.code) : reject(new Error('微信登录失败'))),
          fail: () => reject(new Error('微信登录失败')),
        })
      })
      const exchangeRes = await wechatExchange(code)
      if (exchangeRes.status !== 'binding_required') {
        // 该微信已绑定账号：要么直接登录，要么提示"已绑定"
        if (exchangeRes.status === 'authenticated') {
          authStore.setAuth(exchangeRes as any)
          wx.showToast({ title: '该微信已直接登录', icon: 'success' })
          setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 500)
          return
        }
        throw new Error('微信状态异常，请重试')
      }
      const bindRes = await wechatBindExisting(
        exchangeRes.binding_ticket,
        this.data.email,
        this.data.password,
      )
      await authStore.setAuth(bindRes as any)
      wx.showToast({ title: '绑定并登录成功', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 500)
    } catch (e: any) {
      this.setData({ bindErrorMsg: e.message || '绑定失败' })
    } finally {
      this.setData({ bindLoading: false })
    }
  }
  ```
  并在文件顶部 import `wechatBindExisting`（现在 services/auth.ts 已经有了，直接加到现有 import 里）。

- [ ] **Step 2: 改 login.wxml**
  在邮箱 Tab WXML（L35-L73）中，"登录"按钮下方、form-links 之前插入：
  ```xml
      <view wx:if="{{bindErrorMsg}}" class="error-msg" style="margin-top: 20rpx;">
        <icon name="alert-circle" size="24rpx" color="#cd5852" />
        <text>{{bindErrorMsg}}</text>
      </view>
      <view class="divider-or"><view class="line"></view><text class="divider-text">或</text><view class="line"></view></view>
      <text class="bind-info-text">已有此刻校园账号？可以先输入邮箱密码后点下方按钮，将当前微信绑定到该账号，下次直接用微信登录</text>
      <view class="submit-btn submit-btn-secondary {{bindLoading ? 'disabled' : ''}}" bindtap="onBindExistingTap" hover-class="submit-btn-hover" hover-stay-time="120">
        <text>{{bindLoading ? '绑定中...' : '绑定该微信并登录'}}</text>
      </view>
  ```

- [ ] **Step 3: 改 login.wxss**
  末尾新增：
  ```css
  .submit-btn-secondary {
    background: transparent;
    color: var(--lake);
    border: 2rpx solid var(--lake);
    box-shadow: none;
    margin-top: 16rpx;
  }
  .bind-info-text {
    display: block;
    color: var(--muted);
    font-size: 24rpx;
    line-height: 1.6;
    margin: 32rpx 10rpx 20rpx;
  }
  .divider-or {
    display: flex;
    align-items: center;
    gap: 20rpx;
    margin: 40rpx 0 10rpx;
  }
  .divider-or .line {
    flex: 1;
    height: 2rpx;
    background: var(--line);
  }
  .divider-or .divider-text {
    color: var(--muted);
    font-size: 22rpx;
    padding: 0 6rpx;
  }
  ```

- [ ] **Step 4: 提交 git**
  ```bash
  git add miniprogram/pages/login/login.ts miniprogram/pages/login/login.wxml miniprogram/pages/login/login.wxss
  git commit -m "feat(login): 微信登录/邮箱登录完成后跳个人中心；邮箱Tab新增绑定并登录双按钮"
  ```

---

## Task 5: 前端 register 页成功后统一跳 profile，409 冲突做友好提示

**Files:**
- Modify: `miniprogram/pages/register/register.ts`（onSubmit 成功分支 + catch 分支）

- [ ] **Step 1: 改成功后的 switchTab**
  L119-120 中两处成功后的 `wx.switchTab({ url: '/pages/home/home' })` 统一改为：
  ```ts
  setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 500)
  ```

- [ ] **Step 2: 409 错误加前缀**
  catch 里（L121-123）：
  ```ts
    } catch (e: any) {
      const msg = e?.message || '操作失败'
      const status = e?.status || e?.statusCode
      const prefix = (status === 409 || /已绑定|已被注册/.test(msg)) ? '绑定失败：' : ''
      this.setData({ errorMsg: prefix + msg })
    } finally {
  ```

- [ ] **Step 3: 提交 git**
  ```bash
  git add miniprogram/pages/register/register.ts
  git commit -m "fix(register): 注册/绑定完成后跳个人中心页展示邮箱未验证的登录态"
  ```

---

## Task 6: 后端全量 wechat_auth 测试通过

**Files:**
- Run only, no modify

- [ ] **Step 1: 运行全量 tests/test_wechat_auth.py**
  ```powershell
  cd backend; .venv\Scripts\python.exe -m pytest tests/test_wechat_auth.py -v --asyncio-mode=auto 2>&1
  ```
  Expected: 18 tests passed（新增 1 个，原 17 个总共 18 全通过）

- [ ] **Step 2: 顺手跑 tests/test_auth.py 确保 email login/register 没回退**
  ```powershell
  cd backend; .venv\Scripts\python.exe -m pytest tests/test_auth.py -v --asyncio-mode=auto 2>&1
  ```

---

## Task 7: 微信开发者工具端到端 3 条链路验证

**Files:**
- No modify, only simulator operations

- [ ] **Step 1: 启动开发者工具并编译**
  ```powershell
  wechatide -c CodeBuddy simulator_refresh --project e:\Project\moment-campus\miniprogram
  ```
  预期：success=true，编译无报错

- [ ] **Step 2: 链路 A - 微信首次登录走注册→自动绑微信→个人中心未验证态**
  ```powershell
  wechatide -c CodeBuddy simulator_open_page --project e:\Project\moment-campus\miniprogram --page pages/login/login
  # 截图一次
  wechatide -c CodeBuddy simulator_screenshot --project e:\Project\moment-campus\miniprogram
  ```
  然后：使用 simulator_click 点「使用微信登录」→ 应跳到注册页（含 binding_ticket 参数）
  填表单：昵称"微信链路测试001"+ 学校选江南大学 + 教育邮箱 `wechat_test_001@example.jiangnan.edu.cn` + 密码 pass123 + 确认密码 pass123 → 点「注册并登录」
  预期：Toast "成功"；switchTab 到个人中心；页面显示：该昵称 + 顶部湖蓝卡片不是"点击登录"卡片（说明已登录），校园身份认证部分未点亮（未验证态 ✅）。
  模拟器截图一次保存。

- [ ] **Step 3: 链路 B - 同一 code（模拟同一微信）再次点击微信登录直接登录**
  先手动退出：点个人中心"退出登录" → 回到个人中心空态
  再进入登录页 → 点「使用微信登录」
  预期：不弹注册页，直接 Toast "登录成功" → 个人中心显示同一用户（邮箱未验证但身份正确）。截图。

- [ ] **Step 4: 链路 C - 绑定并登录：账号已有微信时拒绝冲突**
  先退出登录 → 进登录页 → 切邮箱 Tab
  填已有账号邮箱：`fudan_admin@momentcampus.com` / 密码 `pass123`
  点「绑定该微信并登录」（= 当前模拟器微信）
  第一次（该账号无微信身份）：成功 → 个人中心显示 fudan_admin。截图。
  退出登录 → 再次切邮箱 Tab → 填 `user1@example.jiangnan.edu.cn` / `pass123`（= 另一个账号），同一个微信再点绑定 → 预期：Toast 绑定失败 "该微信已绑定其他账号" 或 "该账号已绑定其他微信"。截图并记录错误文案到任务报告。

---

## Task 8: 更新文档（TODO、CHANGELOG、AIwork 报告）并 Git 总提交

**Files:**
- Modify: `TODO.md`、`CHANGELOG.md`
- Create: `AIwork/微信登录绑定链路规范化_任务报告.md`

- [ ] **Step 1: 更新 TODO.md**
  顶部新增一节 `## 2026-08-08 执行任务：微信登录/绑定链路规范化`（10+ 条 `[x]`，覆盖后端补 user 字段、冲突检查、前端跳转、绑定并登录按钮、store 兜底、后端测试、模拟器 3 链路验证）。

- [ ] **Step 2: 更新 CHANGELOG.md**
  顶部新增 `[2.2.15] - 2026-08-08`（修复）。

- [ ] **Step 3: 新增 AIwork 报告**
  严格按 8 节模板（任务概述 / 已完成 / 未完成 / 实现思路 / 修改文件 / 影响范围 / 测试与验证 / 后续建议），附上模拟器截图路径说明。

- [ ] **Step 4: 总提交**
  ```bash
  git add TODO.md CHANGELOG.md AIwork/微信登录绑定链路规范化_任务报告.md
  git commit -m "docs: 微信登录绑定链路规范化 TODO/CHANGELOG/任务报告"
  ```

---

## Plan Self-Review（执行前自查，固定在计划文档里）

**1. Spec coverage:**
| 用户需求点 | 对应任务 |
|---|---|
| 微信登录时先查当前微信有无绑定账号 | Task 2 已确保 exchange 返回 status，login.ts L46-62 已判断 ✅ |
| 微信未绑定时进入注册页填表单 | Task 4 login.ts onWechatLogin binding_required navigateTo register?ticket ✅ |
| 注册完毕后自动绑定账号与当前微信 | Task 1-2 后端 /auth/wechat/register 会消费 binding_ticket 创建 wechat_miniprogram 身份 ✅ |
| 注册后自动登录并显示"未邮箱验证"登录态 | Task 2 register 返回 user，campus_verified=false（断言）；Task 5 跳 profile ✅ |
| 选择"绑定并登录"时，先判断当前账号是否已有绑定微信 | Task 1 后端 bind-existing 加账号已有 wechat_identity 冲突检查 409 ✅ |
| 账号没有绑定微信时绑定并登录 | Task 4 邮箱 Tab 加「绑定并登录」按钮，调 /bind-existing ✅ |
| 账号已有绑定微信时报错 | Task 1 冲突返回"该账号已绑定其他微信，不能重复绑定"；前端 Task 4 toast ✅ |

**2. Placeholder scan:** 无 TBD / TODO / "实现 later"，各步骤代码完整。

**3. Type consistency:**
- 后端 `user` 字段统一是 `UserResponse.model_validate(user).model_dump()` dict；
- 前端 `setAuth` 参数的 user 字段类型兼容现有 `User` type；
- 跳转 URL 统一 `/pages/profile/profile`（switchTab Tab4）。

计划通过自查。
