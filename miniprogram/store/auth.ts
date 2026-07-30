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
    }
    notify()
  },

  setTokens(accessToken: string, refreshToken: string) {
    state.accessToken = accessToken
    state.refreshToken = refreshToken
    wx.setStorageSync('access_token', accessToken)
    wx.setStorageSync('refresh_token', refreshToken)
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
    const accessToken = wx.getStorageSync('access_token') || ''
    const refreshToken = wx.getStorageSync('refresh_token') || ''
    if (accessToken && refreshToken) {
      state.accessToken = accessToken
      state.refreshToken = refreshToken
      state.isLoggedIn = true
    }
    notify()
  },
}
