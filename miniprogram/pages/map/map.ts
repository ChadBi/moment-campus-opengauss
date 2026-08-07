import { campusStore } from '../../store/campus'
import { getLocations, getDetail, getReviews } from '../../services/locations'
import { listPosts } from '../../services/posts'
import type { LocationItem, MapLocationPanel, MapMarker } from '../../types'

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
    display: 'BYCLICK'
  }
}

const DEFAULT_LAT = 31.483652
const DEFAULT_LNG = 120.27116
const DEFAULT_ZOOM = 16
const VERIFIED_MARKER = '/assets/map-marker-verified.svg'
const UNVERIFIED_MARKER = '/assets/map-marker-unverified.svg'
const SELECTED_MARKER = '/assets/map-marker-selected.svg'

function formatCallout(location: LocationItem): string {
  const score = location.avg_score > 0 ? location.avg_score.toFixed(1) : '暂无评分'
  const verified = location.is_verified ? '已核验' : '待核验'
  return `${location.name} · ${score} · ${verified}`
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
      display: 'BYCLICK',
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
  },

  onLoad() {
    ;(this as any)._locationRequestVersion = 0
    ;(this as any)._selectedRequestVersion = 0
    ;(this as any)._hasLoadedLocations = false
    ;(this as any)._unsubscribeCampus = campusStore.subscribe(state => {
      const school = state.currentSchool
      const schoolName = (school && school.name) || state.schoolCode
      const version = ((this as any)._locationRequestVersion || 0) + 1
      ;(this as any)._locationRequestVersion = version
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
      })
      void this.loadLocations(version)
    })
  },

  onUnload() {
    const unsubscribe = (this as any)._unsubscribeCampus
    if (unsubscribe) unsubscribe()
    ;(this as any)._locationRequestVersion += 1
    ;(this as any)._selectedRequestVersion += 1
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    if (!(this as any)._hasLoadedLocations) {
      void this.loadLocations((this as any)._locationRequestVersion || 0)
    }
  },

  async loadLocations(version?: number) {
    const requestVersion = version ?? ((this as any)._locationRequestVersion || 0)
    const schoolCode = campusStore.getState().schoolCode
    this.setData({ locationsLoading: true, locationsError: false })
    try {
      const locations = await getLocations(schoolCode)
      if (schoolCode !== campusStore.getState().schoolCode || requestVersion !== ((this as any)._locationRequestVersion || 0)) return
      this.setData({
        markers: locations.map(location => buildMarker(location)),
        rawLocations: locations,
        selectedLocation: null,
        locationsLoading: false,
        locationsError: false,
      })
      ;(this as any)._hasLoadedLocations = true
    } catch (e: any) {
      if (schoolCode !== campusStore.getState().schoolCode || requestVersion !== ((this as any)._locationRequestVersion || 0)) return
      console.error('加载地点标记失败', e)
      this.setData({ locationsLoading: false, locationsError: true })
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
    const reviews = reviewsResult.status === 'fulfilled' ? reviewsResult.value : undefined
    const postsResponse = postsResult.status === 'fulfilled' ? postsResult.value : undefined
    const posts = postsResponse ? postsResponse.items : []
    const detailError = detailResult.status === 'rejected' ? '地点详情加载失败' : undefined
    const postsError = postsResult.status === 'rejected' ? '相关帖子加载失败' : undefined
    const normalizedLocation = detail?.location || location

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
    })
    if (reviews && reviews.total !== normalizedLocation.review_count) {
      this.setData({ 'selectedLocation.location.review_count': reviews.total })
    }
  },

  closeLocationCard() {
    ;(this as any)._selectedRequestVersion += 1
    this.setData({
      selectedLocation: null,
      sheetExpanded: false,
      sheetDragging: false,
      sheetDragOffset: 0,
      markers: this.data.rawLocations.map(location => buildMarker(location)),
    })
  },

  onSheetTouchStart(e: any) {
    if (this.data.sheetExpanded) return
    const touch = e.touches && e.touches[0]
    if (!touch) return
    ;(this as any)._sheetTouchStartY = touch.clientY ?? touch.pageY
    ;(this as any)._sheetTouchStartOffset = Number(this.data.sheetDragOffset || 0)
    this.setData({ sheetDragging: true })
  },

  onSheetTouchMove(e: any) {
    if (this.data.sheetExpanded) return
    const touch = e.touches && e.touches[0]
    const startY = (this as any)._sheetTouchStartY
    if (!touch || typeof startY !== 'number') return
    const currentY = touch.clientY ?? touch.pageY
    const deltaY = currentY - startY
    const startOffset = Number((this as any)._sheetTouchStartOffset || 0)
    const maxDrag = this.getSheetMaxDrag()
    // 半屏状态下整张卡片随手指移动；向下最多露出一小段，松手后关闭。
    const offset = Math.max(-maxDrag, Math.min(150, startOffset + deltaY))
    this.setData({ sheetDragOffset: offset })
  },

  onSheetTouchEnd(e: any) {
    if (this.data.sheetExpanded) return
    const touch = e.changedTouches && e.changedTouches[0]
    const startY = (this as any)._sheetTouchStartY
    if (!touch || typeof startY !== 'number') {
      this.setData({ sheetDragging: false, sheetDragOffset: 0 })
      return
    }
    const endY = touch.clientY ?? touch.pageY
    const deltaY = endY - startY
    ;(this as any)._sheetTouchStartY = undefined
    const offset = Number(this.data.sheetDragOffset || 0)
    const maxDrag = this.getSheetMaxDrag()
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

  goToLocationDetail() {
    const panel = this.data.selectedLocation
    if (!panel) return
    wx.navigateTo({ url: `/subpackages/pages/locations/locations?id=${panel.location.id}` })
  },

  onRelatedPostTap(e: any) {
    const id = Number(e.detail.id)
    if (!id) return
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },
})
