import { searchPosts, aiSearch, getHotTags } from '../../services/search'
import { resolveImageUrl } from '../../services/request'
import { formatDate, formatCount, truncateText } from '../../utils/format'

const HISTORY_KEY = 'search_history'
const MAX_HISTORY = 20

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

  // ============== 历史与热门标签 ==============
  loadHistory() {
    try {
      const list = wx.getStorageSync(HISTORY_KEY)
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
      wx.setStorageSync(HISTORY_KEY, list)
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
            wx.removeStorageSync(HISTORY_KEY)
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
    // 后端 PaginatedResponse 返回 items；兼容旧字段 posts
    const items = (res && (res.items || res.posts)) || []
    const list = items.map((p: any) => this.normalizePost(p))
    this.setData({
      results: page === 1 ? list : [...this.data.results, ...list],
      total: (res && (res.total ?? res.total_count)) || list.length,
      hasMore: !!(res && res.has_more),
      page,
    })
  },

  // ============== AI 搜索 ==============
  async runAiSearch(query: string, page: number) {
    const res: any = await aiSearch({ query, page, page_size: 20 })
    const items = (res && (res.items || res.posts)) || []
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

  // 归一化帖子字段 + 处理图片 URL + 时间/文本格式化
  normalizePost(p: any): any {
    if (!p) return p
    const images = Array.isArray(p.images) ? p.images.map((u: string) => resolveImageUrl(u)) : []
    return {
      ...p,
      images,
      cover: images[0] || '',
      author_avatar: resolveImageUrl(p.author_avatar),
      created_at_text: formatDate(p.created_at),
      content_brief: truncateText(p.content || '', 80),
      likes_count_text: formatCount(p.likes_count || 0),
      comments_count_text: formatCount(p.comments_count || 0),
      validations_count_text: formatCount(p.validations_count || 0),
      views_count_text: formatCount(p.views_count || 0),
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
