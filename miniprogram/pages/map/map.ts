import { http } from '../../services/request'
import { campusStore } from '../../store/campus'
import { getMapMarkers } from '../../services/map'

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

Page({
  data: {
    latitude: DEFAULT_LAT,
    longitude: DEFAULT_LNG,
    scale: 16,
    markers: [] as WxMarker[],
    rawMarkers: [] as RawMarker[],
    schoolName: '加载中...',
    locationDenied: false,
    selectedMarker: null as SelectedMarker | null,
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
    await this.loadMarkers()
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
