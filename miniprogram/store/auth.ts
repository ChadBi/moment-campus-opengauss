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

  setAuth(data: { access_token: string; refresh_token: string; user: User } | WechatExchangeResponse) {
    if ('user' in data && 'access_token' in data) {
      state.accessToken = data.access_token
      state.refreshToken = data.refresh_token
      state.user = data.user
      state.isLoggedIn = true
      // 与请求层同步：避免登录/切换账号后继续复用旧用户的内存 token。
      syncAuthTokens(data.access_token, data.refresh_token)
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
