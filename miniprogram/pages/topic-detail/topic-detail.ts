import { http, resolveImageUrl } from '../../services/request'
import { formatDate, formatCount } from '../../utils/format'

Page({
  data: {
    topicId: 0,
    loading: true,
    topic: null as any,
    coverImage: '',
    createdAtText: '',
    postCountText: '0',
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
      const topic = res || {}
      // 预处理关联帖子：归一化字段以适配 post-card 组件
      // 后端 TopicPostItem: cover_image_url/author_name/like_count/comment_count/view_count
      // post-card 期望: images/author_nickname/likes_count/comments_count/views_count
      const posts = Array.isArray(topic.posts)
        ? topic.posts.map((p: any) => {
            const cover = resolveImageUrl(p.cover_image_url || p.cover_image)
            return {
              ...p,
              images: cover ? [cover] : (Array.isArray(p.images) ? p.images.map((u: string) => resolveImageUrl(u)) : []),
              author_avatar: resolveImageUrl(p.author_avatar),
              author_nickname: p.author_name || p.author_nickname,
              likes_count: p.like_count !== undefined ? p.like_count : (p.likes_count || 0),
              comments_count: p.comment_count !== undefined ? p.comment_count : (p.comments_count || 0),
              views_count: p.view_count !== undefined ? p.view_count : (p.views_count || 0),
              created_at_text: formatDate(p.created_at),
            }
          })
        : []
      this.setData({
        topic,
        // 后端字段为 cover_url；兼容 cover_image 写法
        coverImage: resolveImageUrl(topic.cover_url || topic.cover_image),
        createdAtText: formatDate(topic.published_at || topic.created_at),
        postCountText: formatCount(topic.post_count || 0),
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
      path: `/pages/topic-detail/topic-detail?id=${this.data.topicId}`,
    }
  },
})
