import { searchPosts, aiSearch, getHotTags } from '../../services/search'
import { formatDate, formatCount, truncateText, getRemainingTime } from '../../utils/format'
import { campusStore } from '../../store/campus'
import { normalizePost } from '../../services/normalize'

const HISTORY_PREFIX = 'search_history_'
const MAX_HISTORY = 20

// 按学校 code 分键：切换学校后历史互不干扰（对齐 Web `moment_search_recent::<schoolCode>`）
function historyKey(): string {
  const schoolCode = campusStore.getState().schoolCode || 'jiangnan'
  return `${HISTORY_PREFIX}${schoolCode}`
}

Page({
  data: {
    // 模式：normal | ai
    mode: 'normal',
    keyword: '',
    searching: false,
    hasSearched: false,
    // 搜索历史
    history: [] as string[],
    // 热门标签
    hotTags: [] as string[],
    // 结果列表（统一为 Post[]）
    results: [] as any[],
    total: 0,
    page: 1,
    hasMore: false,
    loadingMore: false,
    // AI 分析
    aiIntent: '' as string,
    aiReasons: [] as string[],
    aiMatchReasons: {} as Record<string, string[]>,
    aiFallback: false,
    aiFallbackReason: '',
    // 当前 AI 查询（用于分页时带上的 query）
    aiQuery: '',
  },

  onLoad() {
    this.loadHistory()
    this.loadHotTags()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
    }
  },

  // ============== 历史与热门标签 ==============
  loadHistory() {
    try {
      const list = wx.getStorageSync(historyKey())
      this.setData({ history: Array.isArray(list) ? list : [] })
    } catch {
      this.setData({ history: [] })
    }
  },

  saveHistory(keyword: string) {
    const kw = keyword.trim()
    if (!kw) return
    let list = (this.data.history || []).slice()
    list = list.filter(k => k !== kw)
    list.unshift(kw)
    if (list.length > MAX_HISTORY) list = list.slice(0, MAX_HISTORY)
    this.setData({ history: list })
    try {
      wx.setStorageSync(historyKey(), list)
    } catch {
      // ignore
    }
  },

  async loadHotTags() {
    try {
      const res: any = await getHotTags()
      const tags = (res && (res.tags || res.data)) || []
      this.setData({ hotTags: Array.isArray(tags) ? tags : [] })
    } catch {
      // 热门标签为可选项，失败时静默
    }
  },

  // ============== 输入与模式切换 ==============
  onInput(e: any) {
    this.setData({ keyword: e.detail.value || '' })
  },

  onModeSwitch(e: any) {
    const mode = e.currentTarget.dataset.mode
    if (mode === this.data.mode) return
    this.setData({
      mode,
      hasSearched: false,
      results: [],
      total: 0,
      aiIntent: '',
      aiReasons: [],
      aiMatchReasons: {},
      aiFallback: false,
      aiFallbackReason: '',
    })
  },

  onClearInput() {
    this.setData({
      keyword: '',
      hasSearched: false,
      results: [],
      total: 0,
      aiIntent: '',
      aiReasons: [],
      aiMatchReasons: {},
    })
  },

  // 点击历史/热门标签
  onTagTap(e: any) {
    const keyword = e.currentTarget.dataset.keyword
    if (!keyword) return
    this.setData({ keyword }, () => {
      this.doSearch()
    })
  },

  onClearHistory() {
    wx.showModal({
      title: '提示',
      content: '确定清空搜索历史？',
      success: res => {
        if (res.confirm) {
          this.setData({ history: [] })
          try {
            wx.removeStorageSync(historyKey())
          } catch {
            // ignore
          }
        }
      },
    })
  },

  // ============== 搜索触发 ==============
  onSearch() {
    this.doSearch()
  },

  onConfirmSearch(e: any) {
    const value = e.detail && e.detail.value
    if (value !== undefined) {
      this.setData({ keyword: value })
    }
    this.doSearch()
  },

  async doSearch() {
    const keyword = (this.data.keyword || '').trim()
    if (!keyword) {
      wx.showToast({ title: '请输入搜索内容', icon: 'none' })
      return
    }

    this.saveHistory(keyword)
    this.setData({
      searching: true,
      hasSearched: true,
      results: [],
      page: 1,
      aiIntent: '',
      aiReasons: [],
      aiMatchReasons: {},
      aiFallback: false,
      aiFallbackReason: '',
      aiQuery: keyword,
    })

    try {
      if (this.data.mode === 'ai') {
        await this.runAiSearch(keyword, 1)
      } else {
        await this.runNormalSearch(keyword, 1)
      }
    } catch (e: any) {
      wx.showToast({ title: e.message || '搜索失败', icon: 'none' })
    } finally {
      this.setData({ searching: false })
    }
  },

  // ============== 普通搜索 ==============
  async runNormalSearch(keyword: string, page: number) {
    const res: any = await searchPosts({ keyword, page, page_size: 20 })
    const list = (res.items || []).map((p: any) => this.normalizePost(p))
    this.setData({
      results: page === 1 ? list : [...this.data.results, ...list],
      total: (res && (res.total !== undefined ? res.total : res.total_count)) || list.length,
      hasMore: !!(res && res.has_more),
      page,
    })
  },

  // ============== AI 搜索 ==============
  async runAiSearch(query: string, page: number) {
    const res: any = await aiSearch({ query, page, page_size: 20 })
    const items = res.items || []
    const matchReasons = (res && res.match_reasons) || {}

    // 将匹配理由直接嵌入到每条结果中，便于 WXML 直接访问
    const list = items.map((p: any) => {
      const np = this.normalizePost(p)
      const pid = p && p.id
      const reasons = (pid !== undefined && (matchReasons[String(pid)] || matchReasons[pid])) || []
      return { ...np, match_reasons: reasons }
    })

    // 意图与匹配理由
    const intent = res && res.intent
    const intentText = intent && (intent.intent || '') || ''
    const intentReasons = (intent && intent.reasons) || []
    const fallback = !!(res && res.fallback)
    const fallbackReason = (res && res.fallback_reason) || ''

    this.setData({
      results: page === 1 ? list : [...this.data.results, ...list],
      total: (res && res.total) || list.length,
      hasMore: !!(res && res.has_more),
      page,
      aiIntent: intentText,
      aiReasons: intentReasons,
      aiMatchReasons: matchReasons,
      aiFallback: fallback,
      aiFallbackReason: fallbackReason,
    })
  },

  // service 层已完成契约归一化，这里只添加页面展示字段
  normalizePost(p: any): any {
    if (!p) return p
    const post = normalizePost(p)
    const images = post.images || []
    return {
      ...post,
      cover: images[0]?.thumbnail_url || images[0]?.image_url || '',
      created_at_text: formatDate(post.created_at),
      remaining_text: post.expire_at ? getRemainingTime(post.expire_at) : '',
      content_brief: truncateText(post.content || '', 80),
      like_count_text: formatCount(post.like_count || 0),
      comment_count_text: formatCount(post.comment_count || 0),
      valid_count_text: formatCount(post.valid_count || 0),
      view_count_text: formatCount(post.view_count || 0),
    }
  },

  // ============== 分页加载更多 ==============
  async onLoadMore() {
    if (this.data.loadingMore || !this.data.hasMore || this.data.searching) return
    const nextPage = this.data.page + 1
    this.setData({ loadingMore: true })
    try {
      if (this.data.mode === 'ai') {
        await this.runAiSearch(this.data.aiQuery, nextPage)
      } else {
        await this.runNormalSearch(this.data.keyword, nextPage)
      }
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loadingMore: false })
    }
  },

  onReachBottom() {
    this.onLoadMore()
  },

  // ============== 跳转详情 ==============
  goToDetail(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  // AI 卡片中展示该帖子的匹配理由
  getMatchReasons(postId: number | string): string[] {
    const map = this.data.aiMatchReasons || {}
    return map[String(postId)] || map[postId] || []
  },
})
