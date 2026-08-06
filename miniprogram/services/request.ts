import { API_HOST, BASE_URL, IMAGE_HOST } from '../config/env'

const REQUEST_TIMEOUT = 15000

let isRefreshing = false
let pendingRequests: Array<(token: string | null) => void> = []

// access_token 为短时效凭据，尽量保持在内存态，不落 storage，降低明文敏感信息驻留面。
// refresh_token 为长凭据，仍需持久化用于冷启动静默刷新。
let accessTokenCache = ''
let refreshTokenCache = ''

export function getAccessToken(): string {
  if (accessTokenCache) return accessTokenCache
  // 兜底：兼容旧版本残留的 access_token 缓存
  accessTokenCache = wx.getStorageSync('access_token') || ''
  return accessTokenCache
}

function getRefreshToken(): string {
  if (refreshTokenCache) return refreshTokenCache
  refreshTokenCache = wx.getStorageSync('refresh_token') || ''
  return refreshTokenCache
}

function setTokens(accessToken: string, refreshToken: string): void {
  accessTokenCache = accessToken
  refreshTokenCache = refreshToken
  // 只持久化 refresh_token；access_token 不落 storage
  if (refreshToken) wx.setStorageSync('refresh_token', refreshToken)
  wx.removeStorageSync('access_token')
}

function clearTokens(): void {
  accessTokenCache = ''
  refreshTokenCache = ''
  wx.removeStorageSync('access_token')
  wx.removeStorageSync('refresh_token')
}

function isAuthUrl(url: string): boolean {
  const authPaths = ['/auth/', '/auth/wechat/']
  return authPaths.some(p => url.includes(p))
}

function buildFullUrl(path: string): string {
  if (path.startsWith('http')) return path
  return `${BASE_URL}${path.startsWith('/') ? path : '/' + path}`
}

export function resolveImageUrl(url: string | undefined): string {
  if (!url) return ''
  if (url.startsWith('http')) return url
  if (url.startsWith('/uploads/')) {
    return url.replace('/uploads/', `${IMAGE_HOST}/uploads/`)
  }
  return url
}

// 水墨风默认头像（纯蓝灰SVG，兼容小程序 data:image 显示）
const DEFAULT_AVATAR_SVG = `data:image/svg+xml;utf8,` + encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#2d6270"/><stop offset="100%" stop-color="#174d5e"/></linearGradient></defs><rect width="64" height="64" rx="32" fill="url(#g)"/><circle cx="32" cy="26" r="10" fill="#fafcfb" opacity="0.9"/><path d="M12 54c4-10 14-16 20-16s16 6 20 16" fill="#fafcfb" opacity="0.9"/></svg>`
)

export function defaultAvatar(): string {
  return DEFAULT_AVATAR_SVG
}

export function resolveAvatar(url: string | undefined): string {
  const resolved = resolveImageUrl(url)
  if (resolved) return resolved
  return DEFAULT_AVATAR_SVG
}

function getSchoolCode(): string {
  return wx.getStorageSync('school_code') || 'jiangnan'
}

async function refreshToken(): Promise<string | null> {
  if (isRefreshing) {
    return new Promise(resolve => {
      pendingRequests.push(resolve)
    })
  }

  isRefreshing = true
  try {
    const rt = getRefreshToken()
    if (!rt) {
      clearTokens()
      return null
    }

    const res = await new Promise<{ statusCode: number; data: any }>((resolve, reject) => {
      wx.request({
        url: buildFullUrl('/auth/refresh'),
        method: 'POST',
        data: { refresh_token: rt },
        timeout: REQUEST_TIMEOUT,
        success: r => resolve({ statusCode: r.statusCode, data: r.data }),
        fail: reject,
      })
    })

    if (res.statusCode === 200) {
      const { access_token, refresh_token } = res.data
      setTokens(access_token, refresh_token)
      pendingRequests.forEach(cb => cb(access_token))
      pendingRequests = []
      return access_token
    } else {
      clearTokens()
      pendingRequests.forEach(cb => cb(null))
      pendingRequests = []
      wx.showToast({ title: '登录已过期', icon: 'none' })
      return null
    }
  } catch {
    clearTokens()
    pendingRequests.forEach(cb => cb(null))
    pendingRequests = []
    return null
  } finally {
    isRefreshing = false
  }
}

export interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  data?: any
  header?: Record<string, string>
  loading?: boolean
}

export async function request<T = any>(options: RequestOptions): Promise<T> {
  const { url, method = 'GET', data, header = {}, loading = false } = options
  const fullUrl = buildFullUrl(url)
  const authUrl = isAuthUrl(url)

  if (loading) {
    wx.showLoading({ title: '加载中...', mask: true })
  }

  const headers: Record<string, string> = { ...header }

  if (!authUrl) {
    const token = getAccessToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    headers['X-School-Code'] = getSchoolCode()
  }

  try {
    const res = await new Promise<{ statusCode: number; data: any }>((resolve, reject) => {
      wx.request({
        url: fullUrl,
        method: method as any,
        data,
        header: headers,
        timeout: REQUEST_TIMEOUT,
        success: r => resolve({ statusCode: r.statusCode, data: r.data }),
        fail: err => reject(err),
      })
    })

    if (res.statusCode === 401 && !authUrl) {
      // 游客模式（无 refresh_token 持久化）：401 仅代表该接口需要登录，不强制打断浏览跳转
      const isGuest = !getRefreshToken()
      if (isGuest) {
        throw new Error('该操作需要登录')
      }
      const newToken = await refreshToken()
      if (newToken) {
        headers['Authorization'] = `Bearer ${newToken}`
        const retryRes = await new Promise<{ statusCode: number; data: any }>((resolve, reject) => {
          wx.request({
            url: fullUrl,
            method: method as any,
            data,
            header: headers,
            timeout: REQUEST_TIMEOUT,
            success: r => resolve({ statusCode: r.statusCode, data: r.data }),
            fail: reject,
          })
        })
        return handleResponse<T>(retryRes.statusCode, retryRes.data)
      } else {
        wx.reLaunch({ url: '/pages/login/login' })
        throw new Error('登录已过期')
      }
    }

    return handleResponse<T>(res.statusCode, res.data)
  } catch (err: any) {
    if (err.errMsg && err.errMsg.includes('timeout')) {
      throw new Error('请求超时，请检查网络')
    }
    throw err
  } finally {
    if (loading) wx.hideLoading()
  }
}

function handleResponse<T>(statusCode: number, data: any): T {
  if (statusCode >= 200 && statusCode < 300) {
    return data as T
  }

  if (statusCode === 401) {
    // 游客模式：401 只抛异常，不跳登录打断浏览（写操作在交互层用 requireLogin 引导）
    const isGuest = !getRefreshToken()
    if (isGuest) {
      throw new Error((data && data.detail) || '该操作需要登录')
    }
    clearTokens()
    wx.reLaunch({ url: '/pages/login/login' })
    throw new Error((data && data.detail) || '未登录或登录已过期')
  }

  if (statusCode === 403) {
    throw new Error((data && data.detail) || '权限不足')
  }

  if (statusCode === 404) {
    throw new Error((data && data.detail) || '资源不存在')
  }

  if (statusCode >= 400 && statusCode < 500) {
    throw new Error((data && data.detail) || (data && data.message) || '请求参数错误')
  }

  throw new Error((data && data.detail) || '服务器错误')
}

export const http = {
  get: <T>(url: string, data?: any) => request<T>({ url, method: 'GET', data }),
  post: <T>(url: string, data?: any) => request<T>({ url, method: 'POST', data }),
  put: <T>(url: string, data?: any) => request<T>({ url, method: 'PUT', data }),
  delete: <T>(url: string, data?: any) => request<T>({ url, method: 'DELETE', data }),
  patch: <T>(url: string, data?: any) => request<T>({ url, method: 'PATCH', data }),
}
