import { http } from '../../../services/request'
import { formatDate, formatCount } from '../../../utils/format'
import { normalizePost, normalizeTopic } from '../../../services/normalize'

Page({
  data: {
    topicId: 0,
    loading: true,
    topic: null as any,
    coverImage: '',
    createdAtText: '',
    postCountText: '0',
    viewCountText: '',
    posts: [] as any[],
  },

  onLoad(options: any) {
    const id = Number(options && options.id)
    if (!id) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 800)
      return
    }
    this.setData({ topicId: id })
    this.loadTopic()
  },

  async loadTopic() {
    this.setData({ loading: true })
    try {
      const res: any = await http.get(`/topics/${this.data.topicId}`)
      const topic = normalizeTopic(res || {})
      const posts = Array.isArray(res?.posts) ? res.posts.map((p: any) => normalizePost(p)) : []
      this.setData({
        topic,
        coverImage: topic.cover_url || '',
        createdAtText: formatDate(res?.published_at || res?.created_at),
        postCountText: formatCount(topic.post_count || 0),
        viewCountText: formatCount(topic.view_count || 0),
        posts,
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onPostTap(e: any) {
    // 兼容 post-card 组件的 bind:tap 事件（e.detail.id）与简单列表的 dataset.id
    const id = (e.detail && e.detail.id) || e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  onShareAppMessage() {
    const topic = this.data.topic || {}
    return {
      title: topic.title || '专题详情',
      path: `/subpackages/pages/topic-detail/topic-detail?id=${this.data.topicId}`,
    }
  },
})
