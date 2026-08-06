import { authStore } from '../../../store/auth'
import { submitFeedback, getMyFeedbacks } from '../../../services/feedback'
import { formatDate } from '../../../utils/format'

const TYPE_OPTIONS = [
  { key: 'suggestion', label: '建议' },
  { key: 'bug', label: 'Bug' },
  { key: 'complaint', label: '投诉' },
  { key: 'other', label: '其他' },
]

const TYPE_LABELS: Record<string, string> = {
  suggestion: '建议',
  bug: 'Bug',
  complaint: '投诉',
  other: '其他',
}

const STATUS_LABELS: Record<string, string> = {
  open: '待处理',
  in_review: '处理中',
  resolved: '已解决',
}

Page({
  data: {
    isLoggedIn: false,
    loading: false,

    // 表单
    typeOptions: TYPE_OPTIONS,
    selectedType: 'suggestion',
    content: '',
    contact: '',
    submitting: false,

    // 我的反馈历史
    feedbacks: [] as any[],
    page: 1,
    pageSize: 10,
    hasMore: true,
    loadingList: false,
    loadingMore: false,
  },

  goLogin() {
    wx.reLaunch({ url: '/pages/login/login' })
  },

  onShow() {
    const isLoggedIn = authStore.getState().isLoggedIn
    if (!isLoggedIn) {
      this.setData({ isLoggedIn: false, loading: false })
      wx.showModal({
        title: '提示',
        content: '请先登录后再提交反馈',
        confirmText: '去登录',
        success: r => {
          if (r.confirm) wx.reLaunch({ url: '/pages/login/login' })
        },
      })
      return
    }
    this.setData({ isLoggedIn: true })
    this.loadFeedbacks(true)
  },

  onTypeTap(e: any) {
    const key = e.currentTarget.dataset.key
    if (!key) return
    this.setData({ selectedType: key })
  },

  onContentInput(e: any) {
    this.setData({ content: e.detail.value || '' })
  },

  onContactInput(e: any) {
    this.setData({ contact: e.detail.value || '' })
  },

  async onSubmit() {
    if (this.data.submitting) return
    const content = (this.data.content || '').trim()
    if (!content) {
      wx.showToast({ title: '请输入反馈内容', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    try {
      await submitFeedback({
        feedback_type: this.data.selectedType,
        content,
        contact: (this.data.contact || '').trim(),
      })
      wx.showToast({ title: '提交成功', icon: 'success' })
      this.setData({ content: '', contact: '' })
      this.loadFeedbacks(true)
    } catch (e: any) {
      wx.showToast({ title: e.message || '提交失败，请重试', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  async loadFeedbacks(reset: boolean) {
    if (this.data.loadingList || this.data.loadingMore) return
    const page = reset ? 1 : this.data.page
    this.setData({ loadingList: reset, loadingMore: !reset })
    try {
      const res: any = await getMyFeedbacks(page, this.data.pageSize)
      const items = (res.items || []) as any[]
      const list = items.map((f: any) => this.normalize(f))
      this.setData({
        feedbacks: reset ? list : [...this.data.feedbacks, ...list],
        hasMore: res.has_more !== undefined ? !!res.has_more : list.length >= this.data.pageSize,
        page: page + 1,
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载反馈失败', icon: 'none' })
    } finally {
      this.setData({ loadingList: false, loadingMore: false })
    }
  },

  normalize(f: any): any {
    if (!f) return f
    return {
      ...f,
      type_label: TYPE_LABELS[f.feedback_type] || f.feedback_type,
      status_label: STATUS_LABELS[f.status] || f.status,
      created_at_text: f.created_at ? formatDate(f.created_at, 'datetime') : '',
    }
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loadingList && !this.data.loadingMore) {
      this.loadFeedbacks(false)
    }
  },
})