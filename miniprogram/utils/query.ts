/**
 * 小程序 JSCore 不保证提供 URLSearchParams；所有接口查询参数统一在 service 层编码。
 */
export function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  return Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
}
