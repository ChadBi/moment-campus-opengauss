import { http, resolveImageUrl } from '../../services/request'
import { formatDate, formatCount } from '../../utils/format'
import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'

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
    activeTab: 'home',
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
    await this.refreshPosts()
  },

  async loadCategories() {
    try {
      const res = await http.get('/categories') as any
      const cats = res.categories || res.items || []
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
      const items = res.items || res.posts || []
      // 预处理帖子数据：用 resolveImageUrl 处理图片 URL
      const processedPosts = items.map((post: any) => ({
        ...post,
        images: (post.images || []).map((img: string) => resolveImageUrl(img)),
        author_avatar: resolveImageUrl(post.author_avatar),
      }))

      const total = res.total !== undefined
        ? res.total
        : (this.data.posts.length + processedPosts.length)
      this.setData({
        posts: [...this.data.posts, ...processedPosts],
        hasMore: res.has_more !== undefined ? res.has_more : (processedPosts.length >= pageSize),
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

  goToHome() {
    wx.pageScrollTo({ scrollTop: 0, duration: 300 })
  },

  goToSearch() {
    wx.navigateTo({ url: '/pages/search/search' })
  },

  goToTopics() {
    wx.navigateTo({ url: '/pages/topics/topics' })
  },

  goToMap() {
    wx.navigateTo({ url: '/pages/map/map' })
  },

  goToPublish() {
    wx.navigateTo({ url: '/pages/publish/publish' })
  },

  goToProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' })
  },
})
