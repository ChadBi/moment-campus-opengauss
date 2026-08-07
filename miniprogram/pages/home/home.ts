import { http } from '../../services/request'
import { formatDate, formatCount } from '../../utils/format'
import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { cachedFetch } from '../../utils/cache'
import { normalizePost, normalizePostList } from '../../services/normalize'

Page({
  data: {
    isLoggedIn: false,
    schoolName: '加载中...',
    categories: [{ id: 0, name: '推荐' }] as any[],
    activeCategoryId: 0,
    posts: [] as any[],
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
        schoolName: (state.currentSchool && state.currentSchool.name) || state.schoolCode || '此刻校园'
      })
    })
    this.loadCategories()
  },

  async onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
    }
    await this.refreshPosts()
  },

  async loadCategories() {
    try {
      // 分类为低频数据，走本地缓存 + 过期刷新（Task 10）
      const schoolCode = campusStore.getState().schoolCode
      const res = await cachedFetch<any>('categories', () => http.get('/categories'), { schoolCode })
      const cats = Array.isArray(res) ? res : (res.items || [])
      this.setData({
        categories: [{ id: 0, name: '推荐' }, ...cats]
      })
    } catch (e: any) {
      console.error('加载分类失败', e)
    }
  },

  async refreshPosts() {
    this.setData({ page: 1, hasMore: true, posts: [] })
    await this.loadPosts()
  },

  async loadPosts() {
    if (this.data.loading || this.data.loadingMore) return
    const isFirstPage = this.data.page === 1
    this.setData({ loading: isFirstPage, loadingMore: !isFirstPage })
    try {
      const { activeCategoryId, page, pageSize } = this.data
      let res: any
      if (activeCategoryId === 0) {
        res = await http.get(`/recommendations?page=${page}&page_size=${pageSize}`)
      } else {
        res = await http.get(`/posts?category_id=${activeCategoryId}&page=${page}&page_size=${pageSize}`)
      }
      const list = normalizePostList(res)
      const isRecommend = activeCategoryId === 0
      const processedPosts = list.items.map((post: any) => {
        const normalized: any = { ...post }
        if (isRecommend && (post.reason || post.reason_code)) {
          normalized.recommend_reason = post.reason || post.reason_code
        }
        return normalized
      })

      const total = list.total !== undefined
        ? list.total
        : (this.data.posts.length + processedPosts.length)
      this.setData({
        posts: [...this.data.posts, ...processedPosts],
        hasMore: list.has_more !== undefined ? list.has_more : (processedPosts.length >= pageSize),
        page: page + 1,
        totalPosts: total,
        formattedTotal: formatCount(total),
        formattedRefreshTime: formatDate(new Date()),
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false, loadingMore: false })
    }
  },

  onCategoryTap(e: any) {
    const id = e.currentTarget.dataset.id
    if (id === this.data.activeCategoryId) return
    this.setData({ activeCategoryId: id, page: 1, hasMore: true, posts: [] })
    this.loadPosts()
  },

  onPullDownRefresh() {
    this.refreshPosts().finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading && !this.data.loadingMore) {
      this.loadPosts()
    }
  },

  onPostTap(e: any) {
    const id = e.detail.id
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
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
