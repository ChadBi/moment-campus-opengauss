/**
 * 低频接口本地缓存（Task 10）
 * 对学校目录、分类、专题等低频变化数据做本地缓存 + 过期刷新，减少重复请求。
 * 默认按学校 code 隔离，避免切换学校后使用他校缓存。
 */

const DEFAULT_TTL = 10 * 60 * 1000 // 10 分钟

export interface CacheOptions {
  ttl?: number
  schoolCode?: string
}

function buildKey(name: string, schoolCode?: string): string {
  return schoolCode ? `cache_${name}_${schoolCode}` : `cache_${name}`
}

/**
 * 读取缓存；命中且未过期则返回数据，否则返回 null。
 */
export function getCache<T>(name: string, opts: CacheOptions = {}): T | null {
  try {
    const raw = wx.getStorageSync(buildKey(name, opts.schoolCode))
    if (!raw) return null
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!parsed || typeof parsed !== 'object' || !('ts' in parsed)) return null
    const ttl = opts.ttl || DEFAULT_TTL
    if (Date.now() - parsed.ts > ttl) return null
    return parsed.data as T
  } catch {
    return null
  }
}

/**
 * 写入缓存。
 */
export function setCache<T>(name: string, data: T, opts: CacheOptions = {}): void {
  try {
    wx.setStorageSync(buildKey(name, opts.schoolCode), JSON.stringify({ ts: Date.now(), data }))
  } catch {
    // 存储满等异常静默，不影响主流程
  }
}

/**
 * 清除指定缓存。
 */
export function clearCache(name: string, schoolCode?: string): void {
  try {
    wx.removeStorageSync(buildKey(name, schoolCode))
  } catch {
    // ignore
  }
}

/**
 * 带缓存的取数：优先读缓存，未命中或过期则调用 fetch 并回写。
 */
export async function cachedFetch<T>(
  name: string,
  fetch: () => Promise<T>,
  opts: CacheOptions = {},
): Promise<T> {
  const cached = getCache<T>(name, opts)
  if (cached !== null) return cached
  const data = await fetch()
  setCache(name, data, opts)
  return data
}