/** 切校时清理学校作用域缓存；认证令牌、草稿等全局状态不会被触碰。 */
export function clearSchoolCache(schoolCode?: string): void {
  if (!schoolCode) return
  try {
    const info = wx.getStorageInfoSync()
    const prefix = `cache_`
    const keys = (info.keys || []).filter(key => key.startsWith(prefix) && key.endsWith(`_${schoolCode}`))
    keys.forEach(key => wx.removeStorageSync(key))
    wx.removeStorageSync(`search_history_${schoolCode}`)
  } catch {
    // 清理失败不阻塞切校；网络请求仍会使用新的 X-School-Code。
  }
}
