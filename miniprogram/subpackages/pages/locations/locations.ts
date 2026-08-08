import { getLocations, getDetail, getReviews, submitReview, withdrawReview, submitFactProposal, createLocation } from '../../../services/locations'
import { formatDate } from '../../../utils/format'
import { authStore } from '../../../store/auth'
import { campusStore } from '../../../store/campus'
import { requireLogin } from '../../../utils/auth-guard'
import { navigateToTab } from '../../../utils/tab-navigation'
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
    // 自定义导航栏
    statusBarHeight: 0,
    navBarHeight: 44,
    navBarTotalHeight: 44,
    backTitle: '返回',
    isLoggedIn: false,
    campusVerified: false,
    canCreateLocation: false,
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
    detailNotice: '',
    createVisible: false,
    createSubmitting: false,
    createName: '',
    createDescription: '',
    createBuilding: '',
    createFloor: '',
    createLatitude: '',
    createLongitude: '',
    proposalVisible: false,
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
    // ============ 自定义导航栏尺寸计算 ============
    try {
      const sysInfo = wx.getSystemInfoSync()
      const statusBarHeight = sysInfo.statusBarHeight || 20
      let navBarHeight = 44
      try {
        const rect = wx.getMenuButtonBoundingClientRect()
        // 胶囊按钮 top - 状态栏高度 = 胶囊与状态栏间隙；整体高度 = 间隙*2 + 胶囊高度
        const gap = rect.top - statusBarHeight
        navBarHeight = Math.max(44, gap * 2 + rect.height)
      } catch {
        navBarHeight = 44
      }
      this.setData({
        statusBarHeight,
        navBarHeight,
        navBarTotalHeight: statusBarHeight + navBarHeight,
      })
    } catch {
      this.setData({ statusBarHeight: 20, navBarHeight: 44, navBarTotalHeight: 64 })
    }
    ;(this as any)._locationRequestVersion = 0
    ;(this as any)._campusReady = false
    this.setData({ mode: options?.mode || '' })
    authStore.subscribe(state => {
      const role = state.user?.role || ''
      this.setData({
        isLoggedIn: state.isLoggedIn,
        campusVerified: !!state.user?.campus_verified,
        canCreateLocation: !!state.user?.campus_verified || role === 'admin' || role === 'super_admin',
      })
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
    if (options?.mode === 'create') {
      setTimeout(() => this.openCreateForm(), 0)
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

  // ============== 新增地点 ==============
  openCreateForm() {
    if (!requireLogin('登录后即可新增地点')) return
    if (!this.data.canCreateLocation) {
      wx.showToast({ title: '请先完成校园认证', icon: 'none' })
      return
    }
    const school = campusStore.getState().currentSchool
    this.setData({
      createVisible: true,
      createName: '',
      createDescription: '',
      createBuilding: '',
      createFloor: '',
      createLatitude: school?.center_lat ? String(school.center_lat) : '',
      createLongitude: school?.center_lng ? String(school.center_lng) : '',
    })
  },

  closeCreateForm() {
    if (this.data.createSubmitting) return
    this.setData({ createVisible: false })
  },

  onCreateInput(e: any) {
    const field = e.currentTarget.dataset.field
    if (!field) return
    this.setData({ [field]: e.detail.value || '' })
  },

  async submitCreateLocation() {
    if (this.data.createSubmitting) return
    if (!this.data.canCreateLocation) {
      wx.showToast({ title: '请先完成校园认证', icon: 'none' })
      return
    }
    const name = String(this.data.createName || '').trim()
    const latitude = Number(this.data.createLatitude)
    const longitude = Number(this.data.createLongitude)
    if (!name) {
      wx.showToast({ title: '请填写地点名称', icon: 'none' })
      return
    }
    if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90 || !Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
      wx.showToast({ title: '请填写正确的经纬度', icon: 'none' })
      return
    }
    this.setData({ createSubmitting: true })
    try {
      const created = await createLocation({
        name,
        latitude,
        longitude,
        description: String(this.data.createDescription || '').trim() || undefined,
        building: String(this.data.createBuilding || '').trim() || undefined,
        floor: String(this.data.createFloor || '').trim() || undefined,
      })
      wx.showToast({ title: '地点已提交，等待核验', icon: 'success' })
      this.setData({ createVisible: false })
      await this.loadLocations()
      if (created?.id) this.openDetail(created.id)
    } catch (e: any) {
      wx.showToast({ title: e.message || '新增地点失败', icon: 'none' })
    } finally {
      this.setData({ createSubmitting: false })
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
      detailNotice: '',
      detail: null,
      myReview: null,
      proposalVisible: false,
      score: 5,
      content: '',
      factValue: '',
      factReason: '',
    })
    await this.reloadDetail(id, true)
  },

  async reloadDetail(id: number, keepLoading = false) {
    let baseLocation = (this.data.allLocations || []).find((item: any) => item.id === id)
    let detailRes: any = null
    let reviews: LocationReview[] = []
    let detailNotice = ''

    try {
      detailRes = await getDetail(id)
    } catch (e: any) {
      // 体验环境可能先部署了地点列表、尚未部署详情路由。列表中的基础资料仍然可信，
      // 先让用户能打开地点，再明确提示详情能力待后端更新，而不是显示整块 Not Found。
      if (!baseLocation) {
        try {
          const schoolCode = campusStore.getState().schoolCode
          const list = await getLocations(schoolCode)
          const found = list.find(item => item.id === id)
          if (found) baseLocation = this.normalizeLocation(found)
        } catch {
          // 详情回退仍以原始错误为准。
        }
      }
      if (!baseLocation) {
        this.setData({ detailLoading: false, detailError: e.message || '加载详情失败' })
        return
      }
      detailRes = {
        location: baseLocation,
        my_review: null,
        facts: [],
        summary: { status: 'insufficient', confidence_level: 'insufficient', claims: [], conflicts: [], source_count: 0, sources: [] },
      }
      detailNotice = '地点详细信息暂时不可用，当前展示基础资料。请稍后再试。'
    }

    try {
      const reviewsRes = await getReviews(id, { page: 1, page_size: 20 })
      reviews = reviewsRes.items || []
    } catch {
      detailNotice = detailNotice || '评价明细暂时不可用，基础资料仍可查看。'
    }

    if (this.data.activeDetailId !== id) return
    const myReview = detailRes.my_review
    this.setData({
      detail: {
        location: this.normalizeLocation(detailRes.location),
        facts: detailRes.facts || [],
        summary: detailRes.summary || { status: 'insufficient', confidence_level: 'insufficient', claims: [], conflicts: [], source_count: 0, sources: [] },
        reviews: reviews.map(r => this.normalizeReview(r)),
      },
      myReview,
      score: myReview ? myReview.score : (keepLoading ? this.data.score : 5),
      content: myReview ? (myReview.content || '') : (keepLoading ? this.data.content : ''),
      detailLoading: false,
      detailError: '',
      detailNotice,
    })
  },

  closeDetail() {
    this.setData({ detailVisible: false, detail: null, myReview: null, activeDetailId: 0, detailNotice: '', proposalVisible: false })
  },

  retryDetail() {
    if (this.data.activeDetailId) {
      this.setData({ detailLoading: true, detailError: '', detailNotice: '' })
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

  openFactProposal() {
    this.setData({ proposalVisible: true })
  },

  closeFactProposal() {
    if (this.data.proposalSubmitting) return
    this.setData({ proposalVisible: false })
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
      this.setData({ proposalVisible: false, factValue: '', factReason: '' })
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

  // ============== 自定义导航栏返回 ==============
  onBackTap() {
    const pages = getCurrentPages()
    if (pages && pages.length > 1) {
      wx.navigateBack({ delta: 1 })
    } else {
      // 栈空（分享/扫码/从系统入口进入）：降级回到首页，与🏠原行为等价但视觉是返回箭头
      navigateToTab('/pages/home/home')
    }
  },

  goToLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },
})
