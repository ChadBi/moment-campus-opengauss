import type { User, WechatExchangeResponse } from '../types'

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
      // 仅持久化长凭据 refresh_token；access_token 保持内存态，不落 storage
      if (data.refresh_token) wx.setStorageSync('refresh_token', data.refresh_token)
      wx.removeStorageSync('access_token')
    }
    notify()
  },

  setTokens(accessToken: string, refreshToken: string) {
    state.accessToken = accessToken
    state.refreshToken = refreshToken
    if (refreshToken) wx.setStorageSync('refresh_token', refreshToken)
    wx.removeStorageSync('access_token')
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
    wx.removeStorageSync('access_token')
    wx.removeStorageSync('refresh_token')
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
