import { http } from '../../services/request'
import { formatDate } from '../../utils/format'
import { normalizeTopic } from '../../services/normalize'

Page({
  data: {
    topics: [] as any[],
    loading: false,
    loadingMore: false,
    page: 1,
    pageSize: 20,
    hasMore: true,
    total: 0,
  },

  onLoad() {
    this.refreshTopics()
  },

  async onShow() {
    // 进入页面时轻量刷新
  },

  async refreshTopics() {
    this.setData({ page: 1, hasMore: true, topics: [] })
    await this.loadTopics()
  },

  async loadTopics() {
    if (this.data.loading || this.data.loadingMore) return
    const isFirstPage = this.data.page === 1
    this.setData({ loading: isFirstPage, loadingMore: !isFirstPage })
    try {
      const { page, pageSize } = this.data
      const res: any = await http.get(`/topics?page=${page}&page_size=${pageSize}`)
      const items = res.items || []
      const processed = items.map((t: any) => ({
        ...normalizeTopic(t),
        cover_image: normalizeTopic(t).cover_url || '',
        created_at_text: formatDate(t.published_at || t.created_at),
        post_count_text: normalizeTopic(t).post_count || 0,
      }))
      const total = res.total !== undefined
        ? res.total
        : (this.data.topics.length + processed.length)
      this.setData({
        topics: [...this.data.topics, ...processed],
        hasMore: res.has_more !== undefined ? res.has_more : (processed.length >= pageSize),
        page: page + 1,
        total,
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false, loadingMore: false })
    }
  },

  onPullDownRefresh() {
    this.refreshTopics().finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading && !this.data.loadingMore) {
      this.loadTopics()
    }
  },

  onTopicTap(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/subpackages/pages/topic-detail/topic-detail?id=${id}` })
  },

  onShareAppMessage() {
    return {
      title: '专题 - 此刻校园',
      path: '/pages/topics/topics',
    }
  },
})
