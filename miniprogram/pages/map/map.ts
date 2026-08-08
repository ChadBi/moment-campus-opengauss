import { campusStore } from '../../store/campus'
import { getLocations, getDetail, getReviews, submitReview, withdrawReview } from '../../services/locations'
import { listPosts } from '../../services/posts'
import { authStore } from '../../store/auth'
import { requireLogin } from '../../utils/auth-guard'
import { syncTabBarForPage } from '../../utils/tab-navigation'
import type { LocationItem, LocationReview, MapLocationPanel, MapMarker } from '../../types'

interface WxMarker extends MapMarker {
  width: number
  height: number
  anchor?: { x: number; y: number }
  callout: {
    content: string
    color: string
    fontSize: number
    borderRadius: number
    bgColor: string
    padding: number
    display: 'ALWAYS'
  }
}

const DEFAULT_LAT = 31.483652
const DEFAULT_LNG = 120.27116
const DEFAULT_ZOOM = 16
const VERIFIED_MARKER = '/assets/map-marker-verified.svg'
const UNVERIFIED_MARKER = '/assets/map-marker-unverified.svg'
const SELECTED_MARKER = '/assets/map-marker-selected.svg'

function formatStars(score: number): string {
  const full = Math.max(0, Math.min(5, Math.round(score || 0)))
  return '★'.repeat(full) + '☆'.repeat(5 - full)
}

function formatCallout(location: LocationItem): string {
  const score = location.avg_score > 0 ? `★${location.avg_score.toFixed(1)}` : '暂无评分'
  return `${location.name} · ${score}`
}

function buildMarker(location: LocationItem, selected = false): WxMarker {
  return {
    id: location.id,
    location_id: location.id,
    latitude: location.latitude,
    longitude: location.longitude,
    title: location.name,
    width: selected ? 36 : 30,
    height: selected ? 42 : 36,
    iconPath: selected ? SELECTED_MARKER : (location.is_verified ? VERIFIED_MARKER : UNVERIFIED_MARKER),
    selectedIconPath: SELECTED_MARKER,
    anchor: { x: 0.5, y: 1 },
    callout: {
      content: formatCallout(location),
      color: '#152629',
      fontSize: 12,
      borderRadius: 14,
      bgColor: '#fafcfb',
      padding: 8,
      display: 'ALWAYS',
    },
  }
}

Page({
  data: {
    latitude: DEFAULT_LAT,
    longitude: DEFAULT_LNG,
    scale: DEFAULT_ZOOM,
    markers: [] as WxMarker[],
    rawLocations: [] as LocationItem[],
    schoolName: '加载中...',
    locationsLoading: false,
    locationsError: false,
    selectedLocation: null as MapLocationPanel | null,
    sheetExpanded: false,
    sheetDragging: false,
    sheetDragOffset: 0,
    isLoggedIn: false,
    campusVerified: false,
    myReview: null as LocationReview | null,
    score: 5,
    content: '',
    submitting: false,
    editingReview: false,
    starOptions: [1, 2, 3, 4, 5],
    averageStarsText: '☆☆☆☆☆',
  },

  onLoad() {
    syncTabBarForPage(1)
    ;(this as any)._locationRequestVersion = 0
    ;(this as any)._locationsLoadingVersion = null
    ;(this as any)._locationSchoolCode = ''
    ;(this as any)._selectedRequestVersion = 0
    ;(this as any)._hasLoadedLocations = false
    ;(this as any)._sheetScrollTop = 0
    authStore.subscribe(state => {
      this.setData({ isLoggedIn: state.isLoggedIn, campusVerified: !!state.user?.campus_verified })
    })
    ;(this as any)._unsubscribeCampus = campusStore.subscribe(state => {
      const school = state.currentSchool
      const schoolName = (school && school.name) || state.schoolCode
      const schoolChanged = (this as any)._locationSchoolCode !== state.schoolCode
      ;(this as any)._locationSchoolCode = state.schoolCode

      if (!schoolChanged) {
        this.setData({
          schoolName,
          latitude: school?.center_lat || DEFAULT_LAT,
          longitude: school?.center_lng || DEFAULT_LNG,
          scale: school?.map_zoom || DEFAULT_ZOOM,
        })
        return
      }

      const version = ((this as any)._locationRequestVersion || 0) + 1
      ;(this as any)._locationRequestVersion = version
      ;(this as any)._hasLoadedLocations = false
      ;(this as any)._sheetScrollTop = 0
      this.setData({
        schoolName,
        latitude: school?.center_lat || DEFAULT_LAT,
        longitude: school?.center_lng || DEFAULT_LNG,
        scale: school?.map_zoom || DEFAULT_ZOOM,
        selectedLocation: null,
        sheetExpanded: false,
        sheetDragging: false,
        sheetDragOffset: 0,
        markers: [],
        rawLocations: [],
      })
      void this.loadLocations(version)
    })
  },

  onUnload() {
    const unsubscribe = (this as any)._unsubscribeCampus
    if (unsubscribe) unsubscribe()
    ;(this as any)._locationRequestVersion += 1
    ;(this as any)._locationsLoadingVersion = null
    ;(this as any)._selectedRequestVersion += 1
  },

  onShow() {
    syncTabBarForPage(1)
    if (!(this as any)._hasLoadedLocations && (this as any)._locationsLoadingVersion === null) {
      void this.loadLocations((this as any)._locationRequestVersion || 0)
    }
  },

  async loadLocations(version?: number) {
    const requestVersion = version ?? ((this as any)._locationRequestVersion || 0)
    if ((this as any)._locationsLoadingVersion === requestVersion) return

    const schoolCode = campusStore.getState().schoolCode
    ;(this as any)._locationsLoadingVersion = requestVersion
    this.setData({ locationsLoading: true, locationsError: false })
    try {
      const locations = await getLocations(schoolCode)
      if (schoolCode !== campusStore.getState().schoolCode || requestVersion !== ((this as any)._locationRequestVersion || 0)) return
      this.setData({
        markers: locations.map(location => buildMarker(location)),
        rawLocations: locations,
        selectedLocation: null,
        locationsError: false,
      })
      ;(this as any)._hasLoadedLocations = true
    } catch (e: any) {
      if (schoolCode !== campusStore.getState().schoolCode || requestVersion !== ((this as any)._locationRequestVersion || 0)) return
      console.error('加载地点标记失败', e)
      this.setData({ locationsError: true })
    } finally {
      if ((this as any)._locationsLoadingVersion !== requestVersion) return
      ;(this as any)._locationsLoadingVersion = null
      if (schoolCode === campusStore.getState().schoolCode && requestVersion === ((this as any)._locationRequestVersion || 0)) {
        this.setData({ locationsLoading: false })
      }
    }
  },

  selectMarker(locationId: number) {
    this.setData({
      markers: this.data.rawLocations.map(location => buildMarker(location, location.id === locationId)),
    })
  },

  async onMarkerTap(e: any) {
    const markerId = Number(e.detail.markerId)
    const location = this.data.rawLocations.find(item => item.id === markerId)
    if (!location) return

    const requestVersion = ((this as any)._selectedRequestVersion || 0) + 1
    ;(this as any)._selectedRequestVersion = requestVersion
    ;(this as any)._sheetScrollTop = 0
    this.selectMarker(location.id)
    this.setData({
      selectedLocation: {
        location,
        scoreText: location.avg_score > 0 ? location.avg_score.toFixed(1) : '暂无',
        relatedPostCount: Number(location.post_count || 0),
        relatedPosts: [],
        loading: true,
        postsLoading: true,
      },
      averageStarsText: formatStars(location.avg_score || 0),
      myReview: null,
      score: 5,
      content: '',
      submitting: false,
      editingReview: false,
      sheetExpanded: false,
      sheetDragging: false,
      sheetDragOffset: 0,
    })

    const schoolCode = campusStore.getState().schoolCode
    const [detailResult, reviewsResult, postsResult] = await Promise.allSettled([
      getDetail(location.id, schoolCode),
      getReviews(location.id, { page: 1, page_size: 20 }),
      listPosts({ location_id: location.id, status: 'published', sort: 'latest', page: 1, page_size: 5 }),
    ])

    if (
      schoolCode !== campusStore.getState().schoolCode ||
      requestVersion !== ((this as any)._selectedRequestVersion || 0) ||
      !this.data.selectedLocation ||
      this.data.selectedLocation.location.id !== location.id
    ) return

    const detail = detailResult.status === 'fulfilled' ? detailResult.value : undefined
    const postsResponse = postsResult.status === 'fulfilled' ? postsResult.value : undefined
    const posts = postsResponse ? postsResponse.items : []
    const detailError = detailResult.status === 'rejected' ? '地点详情加载失败' : undefined
    const postsError = postsResult.status === 'rejected' ? '相关帖子加载失败' : undefined
    const normalizedLocation = detail?.location || location
    const myReview = detail?.my_review ?? null

    this.setData({
      selectedLocation: {
        location: normalizedLocation,
        scoreText: normalizedLocation.avg_score > 0 ? normalizedLocation.avg_score.toFixed(1) : '暂无',
        relatedPostCount: postsResponse ? postsResponse.total : Number(normalizedLocation.post_count || 0),
        detail,
        relatedPosts: posts,
        loading: false,
        postsLoading: false,
        reviewsLoading: false,
        error: detailError,
        postsError,
      },
      averageStarsText: formatStars(normalizedLocation.avg_score || 0),
      myReview,
      score: myReview ? myReview.score : 5,
      content: myReview ? (myReview.content || '') : '',
      editingReview: false,
    })
  },

  closeLocationCard() {
    ;(this as any)._selectedRequestVersion += 1
    ;(this as any)._sheetScrollTop = 0
    this.setData({
      selectedLocation: null,
      sheetExpanded: false,
      sheetDragging: false,
      sheetDragOffset: 0,
      markers: this.data.rawLocations.map(location => buildMarker(location)),
    })
  },

  onSheetScroll(e: any) {
    ;(this as any)._sheetScrollTop = Math.max(0, Number(e.detail?.scrollTop || 0))
  },

  onSheetTouchStart(e: any) {
    const touch = e.touches && e.touches[0]
    if (!touch) return
    const startY = touch.clientY ?? touch.pageY
    const expanded = this.data.sheetExpanded
    ;(this as any)._sheetTouchStartY = startY
    ;(this as any)._sheetTouchLastY = startY
    ;(this as any)._sheetTouchStartOffset = Number(this.data.sheetDragOffset || 0)
    ;(this as any)._sheetTouchMode = expanded ? 'expanded' : 'half'
    ;(this as any)._sheetPullFromExpanded = expanded && Number((this as any)._sheetScrollTop || 0) <= 1
    ;(this as any)._sheetGestureBlocked = false
    if (!expanded) this.setData({ sheetDragging: true })
  },

  onSheetTouchMove(e: any) {
    const touch = e.touches && e.touches[0]
    const startY = (this as any)._sheetTouchStartY
    if (!touch || typeof startY !== 'number') return
    const currentY = touch.clientY ?? touch.pageY
    const lastY = Number((this as any)._sheetTouchLastY ?? startY)
    ;(this as any)._sheetTouchLastY = currentY

    if ((this as any)._sheetTouchMode === 'expanded') {
      const scrollTop = Number((this as any)._sheetScrollTop || 0)
      const movingDown = currentY > lastY

      if (scrollTop > 1) {
        ;(this as any)._sheetPullFromExpanded = false
        ;(this as any)._sheetGestureBlocked = true
        return
      }
      if (!(this as any)._sheetPullFromExpanded) {
        if (!movingDown) {
          ;(this as any)._sheetGestureBlocked = true
          return
        }
        ;(this as any)._sheetPullFromExpanded = true
        ;(this as any)._sheetTouchStartY = currentY
        ;(this as any)._sheetGestureBlocked = false
        return
      }

      const pullDelta = currentY - Number((this as any)._sheetTouchStartY)
      const maxDrag = this.getSheetMaxDrag()
      const offset = Math.max(0, Math.min(maxDrag, pullDelta))
      if (offset === 0 && !this.data.sheetDragging) {
        ;(this as any)._sheetGestureBlocked = true
        return
      }
      ;(this as any)._sheetGestureBlocked = false
      this.setData({
        sheetDragging: true,
        sheetDragOffset: offset,
      })
      return
    }

    const deltaY = currentY - startY
    const startOffset = Number((this as any)._sheetTouchStartOffset || 0)
    const maxDrag = this.getSheetMaxDrag()
    const offset = Math.max(-maxDrag, Math.min(150, startOffset + deltaY))
    ;(this as any)._sheetGestureBlocked = startOffset === 0 && offset === 0 && Math.abs(deltaY) < 2
    this.setData({ sheetDragOffset: offset })
  },

  onSheetTouchEnd(e: any) {
    const touch = e.changedTouches && e.changedTouches[0]
    const startY = (this as any)._sheetTouchStartY
    const touchMode = (this as any)._sheetTouchMode
    const blocked = !!(this as any)._sheetGestureBlocked
    if (typeof startY !== 'number') {
      this.setData({ sheetDragging: false, sheetDragOffset: 0 })
      return
    }
    const offset = Number(this.data.sheetDragOffset || 0)
    const endY = touch ? (touch.clientY ?? touch.pageY) : startY + offset
    const deltaY = endY - startY
    ;(this as any)._sheetTouchStartY = undefined
    ;(this as any)._sheetTouchLastY = undefined
    ;(this as any)._sheetTouchMode = undefined
    ;(this as any)._sheetPullFromExpanded = false
    ;(this as any)._sheetGestureBlocked = false
    const maxDrag = this.getSheetMaxDrag()

    if (blocked) {
      this.setData({ sheetDragging: false, sheetDragOffset: 0 })
      return
    }

    if (touchMode === 'expanded') {
      if (!this.data.sheetDragging) return
      this.setData({ sheetDragging: false })
      if (offset >= Math.max(72, maxDrag * 0.18) || deltaY >= 72) {
        ;(this as any)._sheetScrollTop = 0
        this.setData({ sheetExpanded: false, sheetDragOffset: 0 })
        return
      }
      this.setData({ sheetDragOffset: 0 })
      return
    }

    this.setData({ sheetDragging: false })

    if (offset <= -Math.max(72, maxDrag * 0.22) || deltaY <= -72) {
      this.setData({ sheetExpanded: true, sheetDragOffset: 0 })
      return
    }
    if (offset >= 100 || deltaY >= 100) {
      this.closeLocationCard()
      return
    }
    this.setData({ sheetDragOffset: 0 })
  },

  getSheetMaxDrag() {
    try {
      const info = wx.getSystemInfoSync()
      return Math.max(220, Math.round(info.windowHeight * 0.42))
    } catch (e) {
      return 320
    }
  },

  onZoomIn() {
    this.setData({ scale: Math.min(19, this.data.scale + 1) })
  },

  onZoomOut() {
    this.setData({ scale: Math.max(12, this.data.scale - 1) })
  },

  goToLocationsPage() {
    wx.navigateTo({ url: '/subpackages/pages/locations/locations' })
  },

  goToCreateLocation() {
    wx.navigateTo({ url: '/subpackages/pages/locations/locations?mode=create' })
  },

  goToLocationDetail() {
    const panel = this.data.selectedLocation
    if (!panel) return
    wx.navigateTo({ url: `/subpackages/pages/locations/locations?id=${panel.location.id}` })
  },

  goToFactProposal() {
    const panel = this.data.selectedLocation
    if (!panel) return
    wx.navigateTo({ url: `/subpackages/pages/locations/locations?id=${panel.location.id}` })
  },

  onRelatedPostTap(e: any) {
    const id = Number(e.detail.id)
    if (!id) return
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  // ============== 评分表单 ==============
  onScoreTap(e: any) {
    const score = Number(e.currentTarget.dataset.score)
    this.setData({ score })
  },

  onContentInput(e: any) {
    this.setData({ content: e.detail.value || '' })
  },

  onStartEditReview() {
    const review = this.data.myReview
    if (review) {
      this.setData({ score: review.score, content: review.content || '', editingReview: true })
    }
  },

  onCancelEditReview() {
    this.setData({ editingReview: false })
  },

  async submitReview() {
    if (!requireLogin('登录后即可评价地点')) return
    if (!this.data.campusVerified) {
      wx.showToast({ title: '请先完成校园认证', icon: 'none' })
      return
    }
    const panel = this.data.selectedLocation
    const id = panel?.location.id
    if (!id) return
    if (!this.data.score) {
      wx.showToast({ title: '请选择评分', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    try {
      const review = await submitReview(id, {
        score: this.data.score,
        content: (this.data.content || '').trim() || undefined,
      })
      wx.showToast({ title: this.data.myReview ? '评价已更新' : '评价已提交', icon: 'success' })
      const schoolCode = campusStore.getState().schoolCode
      const [detailRes, reviewsRes] = await Promise.all([
        getDetail(id, schoolCode),
        getReviews(id, { page: 1, page_size: 20 }),
      ])
      const normalizedLocation = detailRes.location || panel.location
      const totalReviews = reviewsRes.total ?? normalizedLocation.review_count
      this.setData({
        myReview: review,
        editingReview: false,
        'selectedLocation.location': normalizedLocation,
        'selectedLocation.location.review_count': totalReviews,
        'selectedLocation.scoreText': normalizedLocation.avg_score > 0 ? normalizedLocation.avg_score.toFixed(1) : '暂无',
        averageStarsText: formatStars(normalizedLocation.avg_score || 0),
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  withdrawReview() {
    const panel = this.data.selectedLocation
    const id = panel?.location.id
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
          const schoolCode = campusStore.getState().schoolCode
          const [detailRes, reviewsRes] = await Promise.all([
            getDetail(id, schoolCode),
            getReviews(id, { page: 1, page_size: 20 }),
          ])
          const normalizedLocation = detailRes.location || panel.location
          const totalReviews = reviewsRes.total ?? normalizedLocation.review_count
          this.setData({
            myReview: null,
            editingReview: false,
            score: 5,
            content: '',
            'selectedLocation.location': normalizedLocation,
            'selectedLocation.location.review_count': totalReviews,
            'selectedLocation.scoreText': normalizedLocation.avg_score > 0 ? normalizedLocation.avg_score.toFixed(1) : '暂无',
            averageStarsText: formatStars(normalizedLocation.avg_score || 0),
          })
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
