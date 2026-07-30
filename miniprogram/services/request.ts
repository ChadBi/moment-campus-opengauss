const BASE_URL = 'http://localhost:8000/api/v1'
const REQUEST_TIMEOUT = 15000

let isRefreshing = false
let pendingRequests: Array<(token: string) => void> = []

function getAccessToken(): string {
  return wx.getStorageSync('access_token') || ''
}

function getRefreshToken(): string {
  return wx.getStorageSync('refresh_token') || ''
}

function setTokens(accessToken: string, refreshToken: string): void {
  wx.setStorageSync('access_token', accessToken)
  wx.setStorageSync('refresh_token', refreshToken)
}

function clearTokens(): void {
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
    return url.replace('/uploads/', 'http://localhost:8000/uploads/')
  }
  return url
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
        method,
        data,
        header: headers,
        timeout: REQUEST_TIMEOUT,
        success: r => resolve({ statusCode: r.statusCode, data: r.data }),
        fail: err => reject(err),
      })
    })

    if (res.statusCode === 401 && !authUrl) {
      const newToken = await refreshToken()
      if (newToken) {
        headers['Authorization'] = `Bearer ${newToken}`
        const retryRes = await new Promise<{ statusCode: number; data: any }>((resolve, reject) => {
          wx.request({
            url: fullUrl,
            method,
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
    clearTokens()
    wx.reLaunch({ url: '/pages/login/login' })
    throw new Error(data?.detail || '未登录或登录已过期')
  }

  if (statusCode === 403) {
    throw new Error(data?.detail || '权限不足')
  }

  if (statusCode === 404) {
    throw new Error(data?.detail || '资源不存在')
  }

  if (statusCode >= 400 && statusCode < 500) {
    throw new Error(data?.detail || data?.message || '请求参数错误')
  }

  throw new Error(data?.detail || '服务器错误')
}

export const http = {
  get: <T>(url: string, data?: any) => request<T>({ url, method: 'GET', data }),
  post: <T>(url: string, data?: any) => request<T>({ url, method: 'POST', data }),
  put: <T>(url: string, data?: any) => request<T>({ url, method: 'PUT', data }),
  delete: <T>(url: string, data?: any) => request<T>({ url, method: 'DELETE', data }),
  patch: <T>(url: string, data?: any) => request<T>({ url, method: 'PATCH', data }),
}
