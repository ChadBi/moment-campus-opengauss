import { getLocations, getDetail, getReviews, submitReview, withdrawReview, submitFactProposal } from '../../../services/locations'
import { formatDate } from '../../../utils/format'
import { authStore } from '../../../store/auth'
import { campusStore } from '../../../store/campus'
import { requireLogin } from '../../../utils/auth-guard'
import type {
  LocationItem,
  LocationReview,
} from '../../../types'

function formatStars(score: number): string {
  const full = Math.max(0, Math.min(5, Math.round(score || 0)))
  return '★'.repeat(full) + '☆'.repeat(5 - full)
}

Page({
  data: {
    isLoggedIn: false,
    campusVerified: false,
    schoolName: '',
    // 列表
    locations: [] as any[],
    loading: false,
    error: '',
    // 详情弹层
    detailVisible: false,
    activeDetailId: 0,
    detail: null as any,
    detailLoading: false,
    detailError: '',
    myReview: null as LocationReview | null,
    // 评价表单
    score: 5,
    content: '',
    submitting: false,
    factKey: 'normal_hours',
    factLabel: '营业时间',
    factValue: '',
    factReason: '',
    proposalSubmitting: false,
    factKeyOptions: ['normal_hours', 'services', 'price_note', 'contact', 'access', 'booking', 'other'],
    starOptions: [1, 2, 3, 4, 5],
  },

  onLoad(options: Record<string, string | undefined>) {
    authStore.subscribe(state => {
      this.setData({ isLoggedIn: state.isLoggedIn, campusVerified: !!state.user?.campus_verified })
    })
    campusStore.subscribe(state => {
      this.setData({
        schoolName: (state.currentSchool && state.currentSchool.name) || state.schoolCode || '校园中心',
      })
    })
    if (options && options.id) {
      this.openDetail(Number(options.id))
    }
  },

  async onShow() {
    this.loadLocations()
  },

  noop() {},

  // ============== 全部地点列表 ==============
  async loadLocations() {
    this.setData({ loading: true, error: '' })
    try {
      const items = (await getLocations()).map(loc => this.normalizeLocation(loc))
      this.setData({ locations: items, loading: false })
    } catch (e: any) {
      this.setData({ loading: false, error: e.message || '加载地点失败' })
    }
  },

  retryList() {
    this.loadLocations()
  },

  normalizeLocation(loc: LocationItem): any {
    return {
      ...loc,
      starsText: formatStars(loc.avg_score || 0),
      avgScoreText: (loc.avg_score || 0).toFixed(1),
    }
  },

  normalizeReview(review: LocationReview): any {
    return {
      ...review,
      starsText: formatStars(review.score),
      created_at_text: formatDate(review.created_at),
    }
  },

  // ============== 详情弹层 ==============
  onCardTap(e: any) {
    const id = Number(e.currentTarget.dataset.id)
    if (id) this.openDetail(id)
  },

  async openDetail(id: number) {
    this.setData({
      detailVisible: true,
      activeDetailId: id,
      detailLoading: true,
      detailError: '',
      detail: null,
      myReview: null,
      score: 5,
      content: '',
      factValue: '',
      factReason: '',
    })
    await this.reloadDetail(id, true)
  },

  async reloadDetail(id: number, keepLoading = false) {
    try {
      const [detailRes, reviewsRes] = await Promise.all([
        getDetail(id),
        getReviews(id, { page: 1, page_size: 20 }),
      ])
      const myReview = detailRes.my_review
      this.setData({
        detail: {
          location: this.normalizeLocation(detailRes.location),
          facts: detailRes.facts || [],
          summary: detailRes.summary || { status: 'insufficient', confidence_level: 'insufficient', claims: [], conflicts: [], source_count: 0, sources: [] },
          reviews: (reviewsRes.items || []).map(r => this.normalizeReview(r)),
        },
        myReview,
        score: myReview ? myReview.score : (keepLoading ? this.data.score : 5),
        content: myReview ? (myReview.content || '') : (keepLoading ? this.data.content : ''),
        detailLoading: false,
        detailError: '',
      })
    } catch (e: any) {
      this.setData({ detailLoading: false, detailError: e.message || '加载详情失败' })
    }
  },

  closeDetail() {
    this.setData({ detailVisible: false, detail: null, myReview: null, activeDetailId: 0 })
  },

  retryDetail() {
    if (this.data.activeDetailId) {
      this.setData({ detailLoading: true, detailError: '' })
      this.reloadDetail(this.data.activeDetailId)
    }
  },

  // ============== 评价表单 ==============
  onScoreTap(e: any) {
    const score = Number(e.currentTarget.dataset.score)
    this.setData({ score })
  },

  onContentInput(e: any) {
    this.setData({ content: e.detail.value || '' })
  },

  onFactKeyChange(e: any) {
    const options = this.data.factKeyOptions as string[]
    this.setData({ factKey: options[Number(e.detail.value)] || 'other' })
  },

  onFactLabelInput(e: any) {
    this.setData({ factLabel: e.detail.value || '' })
  },

  onFactValueInput(e: any) {
    this.setData({ factValue: e.detail.value || '' })
  },

  onFactReasonInput(e: any) {
    this.setData({ factReason: e.detail.value || '' })
  },

  async submitFactProposal() {
    if (!requireLogin('登录后即可补充地点资料')) return
    if (!this.data.campusVerified) {
      wx.showToast({ title: '请先完成校园认证', icon: 'none' })
      return
    }
    const id = this.data.activeDetailId
    const value = (this.data.factValue || '').trim()
    if (!id || !value) {
      wx.showToast({ title: '请填写资料内容', icon: 'none' })
      return
    }
    this.setData({ proposalSubmitting: true })
    try {
      await submitFactProposal(id, {
        upserts: [{ fact_key: this.data.factKey, label: this.data.factLabel || undefined, value }],
        reason: (this.data.factReason || '').trim() || undefined,
      })
      wx.showToast({ title: '已提交，等待管理员审核', icon: 'success' })
      this.setData({ factValue: '', factReason: '' })
    } catch (e: any) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' })
    } finally {
      this.setData({ proposalSubmitting: false })
    }
  },

  async submitReview() {
    if (!requireLogin('登录后即可评价地点')) return
    const id = this.data.activeDetailId
    if (!id) return
    if (!this.data.score) {
      wx.showToast({ title: '请选择评分', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    try {
      await submitReview(id, {
        score: this.data.score,
        content: (this.data.content || '').trim() || undefined,
      })
      wx.showToast({ title: this.data.myReview ? '评价已更新' : '评价已提交', icon: 'success' })
      await this.reloadDetail(id)
    } catch (e: any) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  withdrawReview() {
    const id = this.data.activeDetailId
    if (!id) return
    wx.showModal({
      title: '提示',
      content: '确定撤回这条评价？',
      success: async res => {
        if (!res.confirm) return
        this.setData({ submitting: true })
        try {
          await withdrawReview(id)
          wx.showToast({ title: '评价已撤回', icon: 'success' })
          await this.reloadDetail(id)
          this.setData({ score: 5, content: '' })
        } catch (e: any) {
          wx.showToast({ title: e.message || '撤回失败', icon: 'none' })
        } finally {
          this.setData({ submitting: false })
        }
      },
    })
  },

  goToLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },
})
