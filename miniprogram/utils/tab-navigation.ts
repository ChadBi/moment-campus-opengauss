const TAB_BAR_PATHS = [
  '/pages/home/home',
  '/pages/map/map',
  '/pages/search/search',
  '/pages/publish/publish',
  '/pages/profile/profile',
]

const TAB_BAR_INDEX: Record<string, number> = TAB_BAR_PATHS.reduce(
  (result, path, index) => ({ ...result, [path]: index }),
  {} as Record<string, number>,
)

function normalizePath(url: string): string {
  return String(url || '').split('?')[0]
}

export function getTabBarIndex(url?: string): number | null {
  if (url) {
    const index = TAB_BAR_INDEX[normalizePath(url)]
    return index === undefined ? null : index
  }

  const app = getApp<any>()
  const stored = Number(app?.globalData?.tabBarSelected)
  return Number.isInteger(stored) && stored >= 0 && stored <= 4 ? stored : 0
}

export function getTabBarPath(index: number): string {
  return TAB_BAR_PATHS[index] || TAB_BAR_PATHS[0]
}

export function getPreparedTabBarPath(): string {
  const app = getApp<any>()
  const path = normalizePath(app?.globalData?.tabBarSelectedPath || '')
  return TAB_BAR_INDEX[path] === undefined ? '' : path
}

export function getCurrentPageTabBarIndex(): number | null {
  try {
    const pages = getCurrentPages()
    const current = pages[pages.length - 1] as any
    const route = current?.route ? `/${current.route}` : ''
    return route ? getTabBarIndex(route) : null
  } catch {
    return null
  }
}

export function setTabBarIndex(index: number): void {
  if (!Number.isInteger(index) || index < 0 || index > 4) return
  const app = getApp<any>()
  if (app?.globalData) app.globalData.tabBarSelected = index
}

export function setPreparedTabBarPath(url: string): void {
  const app = getApp<any>()
  if (app?.globalData) app.globalData.tabBarSelectedPath = normalizePath(url)
}

/**
 * 在发起 switchTab 前只记录目标路由。
 *
 * 每个 Tab 页都有独立且会被缓存的自定义 TabBar 实例。这里不能提前修改
 * 当前页的组件，否则会形成“源页先高亮目标项 -> 目标页显示自己的旧状态 ->
 * onShow 再修正”的可见闪烁。
 */
export function prepareTabBarSwitch(url: string): number | null {
  const index = getTabBarIndex(url)
  if (index === null) return null

  setTabBarIndex(index)
  setPreparedTabBarPath(url)
  return index
}

export function navigateToTab(url: string, options: Record<string, any> = {}): void {
  prepareTabBarSwitch(url)
  wx.switchTab({ ...options, url } as any)
}

/**
 * 同步当前页面自己的 TabBar 实例，兼容已缓存 Tab 页和直达页面。
 * 所有页面都通过这里写入，避免各页面各自维护高亮状态。
 */
export function syncTabBarForPage(index: number): void {
  const path = getTabBarPath(index)
  setTabBarIndex(index)
  setPreparedTabBarPath(path)
  try {
    const pages = getCurrentPages()
    const current = pages[pages.length - 1] as any
    const tabBar = current && typeof current.getTabBar === 'function' ? current.getTabBar() : null
    if (tabBar) tabBar.setData({ selected: index })
  } catch {
    // 非 TabBar 页面或组件尚未挂载时，保留全局状态供组件 attached 使用。
  }
}
