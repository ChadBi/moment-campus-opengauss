import { listHotPosts } from '../../../services/posts'
import { campusStore } from '../../../store/campus'
import { formatCount, formatDate, truncateText } from '../../../utils/format'
import type { Post } from '../../../types'

interface HotPostView extends Post {
  rank: number
  rankLabel: string
  contentPreview: string
  viewText: string
  likeText: string
  commentText: string
  timeText: string
}

function toHotPostView(post: Post, index: number): HotPostView {
  return {
    ...post,
    rank: index + 1,
    rankLabel: String(index + 1).padStart(2, '0'),
    contentPreview: truncateText(post.content || '这条校园动态暂无正文摘要', 86),
    viewText: formatCount(post.view_count || 0),
    likeText: formatCount(post.like_count || 0),
    commentText: formatCount(post.comment_count || 0),
    timeText: formatDate(post.created_at),
  }
}

Page({
  data: {
    schoolName: '此刻校园',
    hotPosts: [] as HotPostView[],
    loading: false,
    error: '',
    days: 7,
  },

  onLoad() {
    ;(this as any)._requestVersion = 0
    ;(this as any)._unsubscribeCampus = campusStore.subscribe(state => {
      this.setData({
        schoolName: state.currentSchool?.name || state.schoolCode || '此刻校园',
      })
    })
  },

  onShow() {
    void this.loadHotPosts()
  },

  onUnload() {
    const unsubscribe = (this as any)._unsubscribeCampus
    if (unsubscribe) unsubscribe()
  },

  async loadHotPosts() {
    const version = ((this as any)._requestVersion || 0) + 1
    ;(this as any)._requestVersion = version
    const schoolCode = campusStore.getState().schoolCode
    this.setData({ loading: true, error: '' })
    try {
      const result = await listHotPosts(this.data.days, 10)
      if (schoolCode !== campusStore.getState().schoolCode || version !== ((this as any)._requestVersion || 0)) return
      this.setData({
        hotPosts: result.items.map(toHotPostView),
        loading: false,
      })
    } catch (e: any) {
      if (schoolCode === campusStore.getState().schoolCode && version === ((this as any)._requestVersion || 0)) {
        this.setData({ loading: false, error: e.message || '校园热榜加载失败' })
      }
    }
  },

  retry() {
    void this.loadHotPosts()
  },

  onPostTap(e: any) {
    const id = Number(e.currentTarget.dataset.id)
    if (id) wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  goBack() {
    wx.navigateBack({ delta: 1 })
  },
})

