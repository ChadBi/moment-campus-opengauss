import { http } from '../../services/request'
import { campusStore } from '../../store/campus'
import { getMapMarkers } from '../../services/map'
import { getNearby } from '../../services/locations'

interface RawMarker {
  id: number
  latitude: number
  longitude: number
  title: string
  content_snippet?: string
  category_name?: string
  status: string
  post_id: number
}

interface WxMarker {
  id: number
  latitude: number
  longitude: number
  title: string
  width: number
  height: number
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

interface SelectedMarker extends RawMarker {
  statusLabel: string
}

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  pending: '待审核',
  published: '已发布',
  expired: '已失效',
  conflict: '冲突',
  archived: '已归档',
}

const DEFAULT_LAT = 31.4882
const DEFAULT_LNG = 120.588

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
    latitude: DEFAULT_LAT,
    longitude: DEFAULT_LNG,
    scale: 16,
    markers: [] as WxMarker[],
    rawMarkers: [] as RawMarker[],
    locationMarkers: [] as WxMarker[],
    rawLocations: [] as any[],
    mapMode: 'posts' as 'posts' | 'locations',
    schoolName: '加载中...',
    locationDenied: false,
    selectedMarker: null as SelectedMarker | null,
    selectedLocation: null as any,
  },

  onLoad() {
    campusStore.subscribe(state => {
      const school = state.currentSchool
      const schoolName = (school && school.name) || state.schoolCode
      const update: any = { schoolName }
      if (school && school.latitude && school.longitude) {
        update.latitude = school.latitude
        update.longitude = school.longitude
        update.scale = school.map_zoom || 16
      }
      this.setData(update)
    })
  },

  async onShow() {
    if (this.data.mapMode === 'posts') {
      await this.loadMarkers()
    } else {
      await this.loadLocations()
    }
    this.requestLocation()
  },

  requestLocation() {
    wx.getLocation({
      type: 'gcj02',
      success: res => {
        this.setData({
          latitude: res.latitude,
          longitude: res.longitude,
          locationDenied: false,
        })
        campusStore.setLocation(res.latitude, res.longitude, res.accuracy)
      },
      fail: () => {
        campusStore.setLocationAuthorized(false)
        const school = campusStore.getState().currentSchool
        if (school && school.latitude && school.longitude) {
          this.setData({
            latitude: school.latitude,
            longitude: school.longitude,
          })
        }
        this.setData({ locationDenied: true })
      },
    })
  },

  async loadMarkers() {
    try {
      const res = await getMapMarkers()
      const rawMarkers: RawMarker[] = res.markers || []
      const wxMarkers: WxMarker[] = rawMarkers.map(m => ({
        id: m.id,
        latitude: m.latitude,
        longitude: m.longitude,
        title: m.title,
        width: 32,
        height: 32,
        callout: {
          content: m.title,
          color: '#152629',
          fontSize: 12,
          borderRadius: 8,
          bgColor: '#fafcfb',
          padding: 8,
          display: 'BYCLICK',
        },
      }))
      this.setData({ markers: wxMarkers, rawMarkers })
    } catch (e: any) {
      console.error('加载地图标记失败', e)
      wx.showToast({ title: e.message || '加载标记失败', icon: 'none' })
    }
  },

  onMarkerTap(e: any) {
    if (this.data.mapMode === 'locations') {
      this.onLocationMarkerTap(e)
      return
    }
    const markerId = e.detail.markerId
    const raw = this.data.rawMarkers.find(m => m.id === markerId)
    if (!raw) return
    const statusLabel = STATUS_LABEL[raw.status] || raw.status
    this.setData({ selectedMarker: { ...raw, statusLabel } })
  },

  closeInfoCard() {
    this.setData({ selectedMarker: null })
  },

  goToPostDetail() {
    const marker = this.data.selectedMarker
    if (!marker) return
    wx.navigateTo({
      url: `/pages/post-detail/post-detail?id=${marker.post_id}`,
    })
  },

  // ============== 附近地点模式 ==============
  switchMapMode(e: any) {
    const mode = e.currentTarget.dataset.mode as 'posts' | 'locations'
    if (mode === this.data.mapMode) return
    this.setData({
      mapMode: mode,
      selectedMarker: null,
      selectedLocation: null,
    })
    if (mode === 'posts') {
      this.loadMarkers()
    } else {
      this.loadLocations()
    }
  },

  async loadLocations() {
    try {
      const res = await getNearby({
        lat: this.data.latitude,
        lng: this.data.longitude,
        radius: 5000,
        page: 1,
        page_size: 50,
      })
      const locs = res.items || []
      const wxMarkers: WxMarker[] = locs.map(loc => ({
        id: loc.id,
        latitude: loc.latitude,
        longitude: loc.longitude,
        title: loc.name,
        width: 32,
        height: 32,
        callout: {
          content: `${loc.name} ${formatStars(loc.avg_score || 0)} ${(loc.avg_score || 0).toFixed(1)}`,
          color: '#152629',
          fontSize: 12,
          borderRadius: 8,
          bgColor: '#fafcfb',
          padding: 8,
          display: 'BYCLICK',
        },
      }))
      this.setData({ locationMarkers: wxMarkers, rawLocations: locs, markers: wxMarkers })
    } catch (e: any) {
      console.error('加载附近地点失败', e)
      wx.showToast({ title: e.message || '加载附近地点失败', icon: 'none' })
    }
  },

  onLocationMarkerTap(e: any) {
    const markerId = e.detail.markerId
    const loc = (this.data.rawLocations as any[]).find(m => m.id === markerId)
    if (!loc) return
    this.setData({
      selectedLocation: {
        id: loc.id,
        name: loc.name,
        starsText: formatStars(loc.avg_score || 0),
        avgScoreText: (loc.avg_score || 0).toFixed(1),
        distanceText: formatDistance(loc.distance),
        rating_count: loc.rating_count || 0,
        review_count: loc.review_count || 0,
      },
    })
  },

  closeLocationCard() {
    this.setData({ selectedLocation: null })
  },

  goToLocationsPage() {
    wx.navigateTo({ url: '/pages/locations/locations' })
  },

  goToLocationDetail() {
    const loc = this.data.selectedLocation
    if (!loc) return
    wx.navigateTo({ url: `/pages/locations/locations?id=${loc.id}` })
  },

  openSetting() {
    wx.openSetting({
      success: res => {
        if (res.authSetting && res.authSetting['scope.userLocation']) {
          this.requestLocation()
        }
      },
    })
  },
})
