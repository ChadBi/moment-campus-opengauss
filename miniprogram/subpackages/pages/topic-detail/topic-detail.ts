import { http } from '../../../services/request'
import { authStore } from '../../../store/auth'
import { formatDate, formatCount } from '../../../utils/format'
import { requireLogin } from '../../../utils/auth-guard'
import { normalizePost, normalizeTopic } from '../../../services/normalize'
import { createSubscription, removeSubscription, checkSubscription } from '../../../services/subscriptions'

Page({
  data: {
    topicId: 0,
    loading: true,
    topic: null as any,
    coverImage: '',
    createdAtText: '',
    postCountText: '0',
    viewCountText: '',
    isSubscribed: false,
    subscriptionId: 0,
    subscribedLoading: false,
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
    this.loadSubscriptionState()
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

  // 页面加载时读取当前订阅状态（登录用户）
  async loadSubscriptionState() {
    if (!authStore.getState().isLoggedIn) return
    try {
      const res = await checkSubscription('topic', this.data.topicId)
      if (res) {
        this.setData({
          isSubscribed: !!res.subscribed,
          subscriptionId: res.subscription_id || 0,
        })
      }
    } catch (e) {
      // 静默失败，不影响浏览
    }
  },

  // 订阅 / 取消订阅专题
  async toggleSubscribe() {
    if (this.data.subscribedLoading) return
    // 未登录引导登录（Task 6）
    if (!requireLogin('登录后即可订阅专题')) return
    this.setData({ subscribedLoading: true })
    try {
      if (this.data.isSubscribed) {
        // 已订阅 → 取消
        if (this.data.subscriptionId) {
          await removeSubscription(this.data.subscriptionId)
        }
        this.setData({ isSubscribed: false, subscriptionId: 0 })
        wx.showToast({ title: '已取消订阅', icon: 'none' })
      } else {
        // 未订阅 → 订阅
        const res: any = await createSubscription('topic', this.data.topicId)
        this.setData({ isSubscribed: true, subscriptionId: res.id || 0 })
        wx.showToast({ title: '已订阅', icon: 'success' })
      }
    } catch (e: any) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    } finally {
      this.setData({ subscribedLoading: false })
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
