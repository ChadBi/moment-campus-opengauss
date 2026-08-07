import { getLocations, getDetail, getReviews, submitReview, withdrawReview, submitFactProposal } from '../../../services/locations'
import { formatDate } from '../../../utils/format'
import { authStore } from '../../../store/auth'
import { campusStore } from '../../../store/campus'
import { requireLogin } from '../../../utils/auth-guard'
import { createSubscription, removeSubscription, checkSubscription } from '../../../services/subscriptions'
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
    mode: '' as string,
    searchKeyword: '',
    allLocations: [] as any[],
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
    locationSubscribed: false,
    locationSubscriptionId: 0,
    locationSubscriptionLoading: false,
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
    ;(this as any)._locationRequestVersion = 0
    ;(this as any)._campusReady = false
    this.setData({ mode: options?.mode || '' })
    authStore.subscribe(state => {
      this.setData({ isLoggedIn: state.isLoggedIn, campusVerified: !!state.user?.campus_verified })
    })
    ;(this as any)._unsubscribeCampus = campusStore.subscribe(state => {
      this.setData({
        schoolName: (state.currentSchool && state.currentSchool.name) || state.schoolCode || '校园中心',
      })
      if ((this as any)._campusReady) {
        const version = ((this as any)._locationRequestVersion || 0) + 1
        ;(this as any)._locationRequestVersion = version
        this.loadLocations(version)
      }
    })
    ;(this as any)._campusReady = true
    if (options && options.id) {
      this.openDetail(Number(options.id))
    }
  },

  async onShow() {
    const version = ((this as any)._locationRequestVersion || 0) + 1
    ;(this as any)._locationRequestVersion = version
    this.loadLocations(version)
  },

  onUnload() {
    const unsubscribe = (this as any)._unsubscribeCampus
    if (unsubscribe) unsubscribe()
  },

  noop() {},

  // ============== 全部地点列表 ==============
  async loadLocations(version?: number) {
    const requestVersion = version ?? ((this as any)._locationRequestVersion || 0)
    const schoolCode = campusStore.getState().schoolCode
    this.setData({ loading: true, error: '' })
    try {
      const items = (await getLocations(schoolCode)).map(loc => this.normalizeLocation(loc))
      if (schoolCode !== campusStore.getState().schoolCode || requestVersion !== ((this as any)._locationRequestVersion || 0)) return
      this.setData({ locations: items, allLocations: items, loading: false })
    } catch (e: any) {
      if (schoolCode === campusStore.getState().schoolCode && requestVersion === ((this as any)._locationRequestVersion || 0)) {
        this.setData({ loading: false, error: e.message || '加载地点失败' })
      }
    }
  },

  retryList() {
    this.loadLocations()
  },

  onKeywordInput(e: any) {
    const keyword = String(e.detail.value || '').trim().toLowerCase()
    const all = this.data.allLocations || []
    const locations = !keyword ? all : all.filter((item: any) => [item.name, item.description, item.building, item.floor]
      .filter(Boolean).some((value: any) => String(value).toLowerCase().includes(keyword)))
    this.setData({ searchKeyword: e.detail.value || '', locations })
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
    if (this.data.mode === 'select') {
      const selected = (this.data.allLocations || []).find((item: any) => item.id === id)
      if (selected) {
        wx.setStorageSync('selected_location', selected)
        wx.navigateBack({ delta: 1 })
      }
      return
    }
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
      locationSubscribed: false,
      locationSubscriptionId: 0,
      locationSubscriptionLoading: false,
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
      this.loadLocationSubscription(id)
    } catch (e: any) {
      this.setData({ detailLoading: false, detailError: e.message || '加载详情失败' })
    }
  },

  async loadLocationSubscription(id: number) {
    if (!authStore.getState().isLoggedIn) return
    try {
      const result = await checkSubscription('location', id)
      if (this.data.activeDetailId !== id) return
      this.setData({
        locationSubscribed: !!result.subscribed,
        locationSubscriptionId: result.subscription_id || 0,
      })
    } catch {
      // 游客或登录态刷新期间检查失败不影响地点详情展示。
    }
  },

  async toggleLocationSubscription() {
    if (this.data.locationSubscriptionLoading) return
    if (!requireLogin('登录后即可订阅地点动态')) return
    const id = this.data.activeDetailId
    if (!id) return
    this.setData({ locationSubscriptionLoading: true })
    try {
      if (this.data.locationSubscribed) {
        if (this.data.locationSubscriptionId) {
          await removeSubscription(this.data.locationSubscriptionId)
        }
        this.setData({ locationSubscribed: false, locationSubscriptionId: 0 })
        wx.showToast({ title: '已取消订阅', icon: 'none' })
      } else {
        const result = await createSubscription('location', id)
        this.setData({ locationSubscribed: true, locationSubscriptionId: result.id || 0 })
        wx.showToast({ title: '已订阅地点', icon: 'success' })
      }
    } catch (e: any) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    } finally {
      this.setData({ locationSubscriptionLoading: false })
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
