import { formatDate, formatCount } from '../../utils/format'
import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { cachedFetch } from '../../utils/cache'
import { getRecommendations } from '../../services/schools'
import { listCategories, listHotPosts, listPosts } from '../../services/posts'
import { navigateToTab, syncTabBarForPage } from '../../utils/tab-navigation'
import type { Category, Post } from '../../types'

const HOME_REFRESH_INTERVAL_MS = 60 * 1000

Page({
  data: {
    isLoggedIn: false,
    schoolName: '加载中...',
    categories: [{ id: 0, name: '全部' }] as Array<{ id: number; name: string }>,
    activeCategoryId: 0,
    recommendations: [] as Post[],
    featuredRecommendation: null as Post | null,
    recommendationMode: null as any,
    recommendationLoading: false,
    recommendationError: false,
    hotPosts: [] as Post[],
    hotLoading: false,
    hotError: false,
    posts: [] as Post[],
    loading: false,
    loadingMore: false,
    page: 1,
    pageSize: 20,
    hasMore: true,
    totalPosts: 0,
    formattedTotal: '0',
    formattedRefreshTime: '',
    homeLoaded: false,
    lastRefreshAt: 0,
  },

  onLoad() {
    syncTabBarForPage(0)
    authStore.subscribe(state => {
      this.setData({ isLoggedIn: state.isLoggedIn })
    })
    campusStore.subscribe(state => {
      this.setData({
        schoolName: (state.currentSchool && state.currentSchool.name) || state.schoolCode || '此刻校园',
      })
    })
    this.loadCategories()
  },

  onShow() {
    syncTabBarForPage(0)
    const now = Date.now()
    const needsRefresh =
      !this.data.homeLoaded || now - this.data.lastRefreshAt >= HOME_REFRESH_INTERVAL_MS
    if (needsRefresh && !this.data.loading && !this.data.loadingMore) {
      void this.refreshHome()
    }
  },

  async loadCategories() {
    try {
      const schoolCode = campusStore.getState().schoolCode
      const cats = await cachedFetch<Category[]>(
        'categories',
        () => listCategories(),
        { schoolCode },
      )
      this.setData({
        categories: [{ id: 0, name: '全部' }, ...cats.filter(item => item.is_active !== false)],
      })
    } catch (e) {
      console.error('加载分类失败', e)
    }
  },

  async refreshHome() {
    // 保留旧列表到新数据返回，避免从帖子详情返回时先白屏再重绘。
    this.setData({ page: 1, hasMore: true })
    await Promise.all([
      this.loadRecommendations(),
      this.loadHotPosts(),
      this.loadFeed(true),
    ])
    this.setData({ homeLoaded: true, lastRefreshAt: Date.now() })
  },

  async loadRecommendations() {
    this.setData({ recommendationLoading: true, recommendationError: false })
    try {
      const result = await getRecommendations({ page: 1, page_size: 5 })
      this.setData({
        recommendations: result.items,
        featuredRecommendation: result.items[0] || null,
        recommendationMode: result.mode || null,
      })
    } catch (e) {
      console.error('加载推荐失败', e)
      this.setData({ recommendations: [], featuredRecommendation: null, recommendationMode: null, recommendationError: true })
    } finally {
      this.setData({ recommendationLoading: false })
    }
  },

  async loadHotPosts() {
    this.setData({ hotLoading: true, hotError: false })
    try {
      const result = await listHotPosts(7, 10)
      this.setData({ hotPosts: result.items })
    } catch (e) {
      console.error('加载校园热榜失败', e)
      this.setData({ hotPosts: [], hotError: true })
    } finally {
      this.setData({ hotLoading: false })
    }
  },

  async loadFeed(reset = false) {
    if (this.data.loading || this.data.loadingMore) return
    const requestPage = reset ? 1 : this.data.page
    const isFirstPage = requestPage === 1
    this.setData({ loading: isFirstPage, loadingMore: !isFirstPage })
    try {
      const { activeCategoryId, pageSize } = this.data
      const result = await listPosts({
        page: requestPage,
        page_size: pageSize,
        category_id: activeCategoryId > 0 ? activeCategoryId : undefined,
        status: 'published',
        sort: 'latest',
      })
      const total = result.total || ((reset ? 0 : this.data.posts.length) + result.items.length)
      this.setData({
        posts: [...(reset ? [] : this.data.posts), ...result.items],
        hasMore: result.has_more,
        page: requestPage + 1,
        totalPosts: total,
        formattedTotal: formatCount(total),
        formattedRefreshTime: formatDate(new Date()),
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '信息流加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false, loadingMore: false })
    }
  },

  retryRecommendations() {
    void this.loadRecommendations()
  },

  retryHotPosts() {
    void this.loadHotPosts()
  },

  onCategoryTap(e: any) {
    const id = Number(e.currentTarget.dataset.id)
    if (id === this.data.activeCategoryId) return
    this.setData({ activeCategoryId: id, page: 1, hasMore: true, posts: [] })
    void this.loadFeed()
  },

  onPullDownRefresh() {
    this.refreshHome().finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading && !this.data.loadingMore) {
      void this.loadFeed()
    }
  },

  onPostTap(e: any) {
    const id = Number(e.detail && e.detail.id)
    if (!id) return
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  onRecommendationTap(e: any) {
    const id = Number(e.currentTarget.dataset.id)
    if (id) wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  onHotPostTap(e: any) {
    const id = Number(e.currentTarget.dataset.id)
    if (id) wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  goToHotRanking() {
    const url = '/pages/hot-ranking/hot-ranking'
    wx.navigateTo({
      url,
      fail: error => {
        console.error('打开校园热榜失败', error)
        // 页面栈已满时用 redirectTo 兜底，避免点击后完全没有反馈。
        wx.redirectTo({
          url,
          fail: redirectError => {
            console.error('重定向校园热榜失败', redirectError)
            wx.showToast({ title: '热榜页面暂时打不开', icon: 'none' })
          },
        })
      },
    })
  },

  goToMap() {
    navigateToTab('/pages/map/map')
  },

  goToLocations() {
    wx.navigateTo({ url: '/subpackages/pages/locations/locations' })
  },

  goToPublish() {
    navigateToTab('/pages/publish/publish')
  },

  goToProfile() {
    navigateToTab('/pages/profile/profile')
  },
})
