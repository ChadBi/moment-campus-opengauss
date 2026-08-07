import { formatDate, formatCount } from '../../utils/format'
import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { cachedFetch } from '../../utils/cache'
import { getRecommendations } from '../../services/schools'
import { listCategories, listHotPosts, listPosts } from '../../services/posts'
import type { Category, Post } from '../../types'

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
  },

  onLoad() {
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

  async onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
    }
    await this.refreshHome()
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
    this.setData({ page: 1, hasMore: true, posts: [] })
    await Promise.all([this.loadRecommendations(), this.loadHotPosts(), this.loadFeed()])
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

  async loadFeed() {
    if (this.data.loading || this.data.loadingMore) return
    const isFirstPage = this.data.page === 1
    this.setData({ loading: isFirstPage, loadingMore: !isFirstPage })
    try {
      const { activeCategoryId, page, pageSize } = this.data
      const result = await listPosts({
        page,
        page_size: pageSize,
        category_id: activeCategoryId > 0 ? activeCategoryId : undefined,
        status: 'published',
        sort: 'latest',
      })
      const total = result.total || (this.data.posts.length + result.items.length)
      this.setData({
        posts: [...this.data.posts, ...result.items],
        hasMore: result.has_more,
        page: page + 1,
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
    const id = e.detail.id
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
    wx.navigateTo({ url: '/subpackages/pages/hot-ranking/hot-ranking' })
  },

  goToSearch() {
    wx.switchTab({ url: '/pages/search/search' })
  },

  goToMap() {
    wx.switchTab({ url: '/pages/map/map' })
  },

  goToLocations() {
    wx.navigateTo({ url: '/subpackages/pages/locations/locations' })
  },

  goToPublish() {
    wx.switchTab({ url: '/pages/publish/publish' })
  },

  goToProfile() {
    wx.switchTab({ url: '/pages/profile/profile' })
  },
})
