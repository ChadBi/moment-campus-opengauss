import { getNearby, getDetail, getReviews, submitReview, withdrawReview } from '../../services/locations'
import { formatDate } from '../../utils/format'
import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import type {
  LocationItem,
  LocationReview,
} from '../../types'

const RADIUS_OPTIONS = [
  { value: 1000, label: '1 公里内' },
  { value: 3000, label: '3 公里内' },
  { value: 5000, label: '5 公里内' },
  { value: 10000, label: '10 公里内' },
]

function formatStars(score: number): string {
  const full = Math.max(0, Math.min(5, Math.round(score || 0)))
  return '★'.repeat(full) + '☆'.repeat(5 - full)
}

function formatDistance(m?: number | null): string {
  if (m == null) return '未知距离'
  if (m < 1000) return `${Math.round(m)}米`
  return `${(m / 1000).toFixed(1)}公里`
}

Page({
  data: {
    isLoggedIn: false,
    schoolName: '',
    // 定位
    locating: false,
    centerLat: 0,
    centerLng: 0,
    centerLabel: '',
    centerSource: 'school' as 'gps' | 'school',
    // 半径
    radiusOptions: RADIUS_OPTIONS,
    radiusIndex: 1,
    radius: 3000,
    radiusLabel: RADIUS_OPTIONS[1].label,
    // 列表
    nearby: [] as any[],
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
    starOptions: [1, 2, 3, 4, 5],
  },

  onLoad(options: Record<string, string | undefined>) {
    authStore.subscribe(state => {
      this.setData({ isLoggedIn: state.isLoggedIn })
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

  onShow() {
    this.handleGeolocate()
  },

  noop() {},

  // ============== 定位与附近列表 ==============
  handleGeolocate() {
    this.setData({ locating: true })
    wx.getLocation({
      type: 'gcj02',
      success: res => {
        this.setData({ locating: false })
        this.loadNearby(res.latitude, res.longitude, 'gps', '我的位置')
      },
      fail: () => {
        this.setData({ locating: false })
        campusStore.setLocationAuthorized(false)
        const school = campusStore.getState().currentSchool
        if (school && school.latitude && school.longitude) {
          this.loadNearby(school.latitude, school.longitude, 'school', '校园中心')
        } else {
          this.setData({ loading: false, centerLat: 0, centerLng: 0, error: '无法定位，请点击重试' })
        }
      },
    })
  },

  async loadNearby(lat: number, lng: number, source: 'gps' | 'school', label: string) {
    this.setData({
      loading: true,
      error: '',
      centerLat: lat,
      centerLng: lng,
      centerSource: source,
      centerLabel: label,
      nearby: [],
    })
    try {
      const res = await getNearby({ lat, lng, radius: this.data.radius, page: 1, page_size: 20 })
      const items = (res.items || []).map(loc => this.normalizeLocation(loc))
      this.setData({ nearby: items, loading: false })
    } catch (e: any) {
      this.setData({ loading: false, error: e.message || '加载附近地点失败' })
    }
  },

  onRadiusChange(e: any) {
    const idx = Number(e.detail.value)
    const opt = RADIUS_OPTIONS[idx] || RADIUS_OPTIONS[1]
    this.setData({ radiusIndex: idx, radius: opt.value, radiusLabel: opt.label })
    if (this.data.centerLat && this.data.centerLng) {
      this.loadNearby(this.data.centerLat, this.data.centerLng, this.data.centerSource, this.data.centerLabel)
    }
  },

  retryList() {
    if (this.data.centerLat && this.data.centerLng) {
      this.loadNearby(this.data.centerLat, this.data.centerLng, this.data.centerSource, this.data.centerLabel)
    } else {
      this.handleGeolocate()
    }
  },

  normalizeLocation(loc: LocationItem): any {
    return {
      ...loc,
      starsText: formatStars(loc.avg_score || 0),
      avgScoreText: (loc.avg_score || 0).toFixed(1),
      distanceText: formatDistance(loc.distance),
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

  async submitReview() {
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