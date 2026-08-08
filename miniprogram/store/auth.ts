import type { User, WechatExchangeResponse } from '../types'
import { clearAuthTokens, syncAuthTokens } from '../services/request'

interface AuthState {
  isLoggedIn: boolean
  user: User | null
  accessToken: string
  refreshToken: string
}

type AuthListener = (state: AuthState) => void

const state: AuthState = {
  isLoggedIn: false,
  user: null,
  accessToken: '',
  refreshToken: '',
}

const listeners: Set<AuthListener> = new Set()

function notify() {
  listeners.forEach(fn => fn({ ...state }))
}

export const authStore = {
  subscribe(fn: AuthListener): () => void {
    listeners.add(fn)
    fn({ ...state })
    return () => listeners.delete(fn)
  },

  getState(): AuthState {
    return { ...state }
  },

  async setAuth(
    data:
      | { access_token: string; refresh_token: string; user: User }
      | WechatExchangeResponse
      | { access_token: string; refresh_token: string; user_id: number; user?: User }
  ): Promise<void> {
    if (!('access_token' in data) || !data.access_token) {
      console.warn('[authStore] setAuth 缺少 access_token', data)
      notify()
      return
    }
    state.accessToken = data.access_token
    state.refreshToken = data.refresh_token || ''
    syncAuthTokens(data.access_token, data.refresh_token || '')

    if ('user' in data && data.user && (data.user as User).id) {
      state.user = data.user as User
      state.isLoggedIn = true
      notify()
      return
    }
    if ('user_id' in data) {
      // 后端没返回 user：自己 /users/me 拉一次
      state.user = null
      state.isLoggedIn = false
      notify()
      try {
        const { getMe } = await import('../services/users')
        const user = await getMe()
        state.user = user
        state.isLoggedIn = true
      } catch (err) {
        console.warn('[authStore] setAuth 后拉取 user 失败', err)
        state.user = null
        state.isLoggedIn = false
      }
    } else {
      state.isLoggedIn = false
    }
    notify()
  },

  setTokens(accessToken: string, refreshToken: string) {
    state.accessToken = accessToken
    state.refreshToken = refreshToken
    syncAuthTokens(accessToken, refreshToken)
    notify()
  },

  setUser(user: User) {
    state.user = user
    notify()
  },

  clear() {
    state.isLoggedIn = false
    state.user = null
    state.accessToken = ''
    state.refreshToken = ''
    clearAuthTokens()
    notify()
  },

  initFromStorage() {
    // 以 refresh_token 是否持久化作为登录态依据；access_token 不落 storage
    const refreshToken = wx.getStorageSync('refresh_token') || ''
    const accessToken = wx.getStorageSync('access_token') || '' // 兼容旧版本残留
    if (refreshToken) {
      state.refreshToken = refreshToken
      state.accessToken = accessToken || ''
      state.isLoggedIn = true
    }
    notify()
  },
}
