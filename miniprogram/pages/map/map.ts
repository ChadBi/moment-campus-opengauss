import { campusStore } from '../../store/campus'
import { getLocations, getDetail } from '../../services/locations'
import type { LocationItem } from '../../types'

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

const DEFAULT_LAT = 31.483652
const DEFAULT_LNG = 120.27116

function formatStars(score: number): string {
  const full = Math.max(0, Math.min(5, Math.round(score || 0)))
  return '★'.repeat(full) + '☆'.repeat(5 - full)
}

Page({
  data: {
    latitude: DEFAULT_LAT,
    longitude: DEFAULT_LNG,
    scale: 16,
    markers: [] as WxMarker[],
    rawLocations: [] as LocationItem[],
    schoolName: '加载中...',
    selectedLocation: null as any,
  },

  onLoad() {
    ;(this as any)._locationRequestVersion = 0
    ;(this as any)._hasLoadedLocations = false
    ;(this as any)._unsubscribeCampus = campusStore.subscribe(state => {
      const school = state.currentSchool
      const schoolName = (school && school.name) || state.schoolCode
      const update: any = { schoolName }
      if (school) {
        update.latitude = school.center_lat
        update.longitude = school.center_lng
        update.scale = school.map_zoom || 16
      }
      this.setData(update)
      ;(this as any)._locationRequestVersion += 1
      this.loadLocations((this as any)._locationRequestVersion)
    })
  },

  onUnload() {
    const unsubscribe = (this as any)._unsubscribeCampus
    if (unsubscribe) unsubscribe()
  },

  async onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    if (!(this as any)._hasLoadedLocations) this.loadLocations((this as any)._locationRequestVersion || 0)
  },

  async loadLocations(version?: number) {
    const requestVersion = version ?? ((this as any)._locationRequestVersion || 0)
    const schoolCode = campusStore.getState().schoolCode
    try {
      const locs = await getLocations()
      if (schoolCode !== campusStore.getState().schoolCode || requestVersion !== ((this as any)._locationRequestVersion || 0)) return
      const wxMarkers: WxMarker[] = locs.map((loc: LocationItem) => ({
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
      this.setData({ markers: wxMarkers, rawLocations: locs, selectedLocation: null })
      ;(this as any)._hasLoadedLocations = true
    } catch (e: any) {
      console.error('加载地点标记失败', e)
      wx.showToast({ title: e.message || '加载地点标记失败', icon: 'none' })
    }
  },

  async onMarkerTap(e: any) {
    const markerId = e.detail.markerId
    const loc = this.data.rawLocations.find(m => m.id === markerId)
    if (!loc) return
    this.setData({
      selectedLocation: {
        id: loc.id,
        name: loc.name,
        isVerified: loc.is_verified,
        postCount: loc.post_count || 0,
        starsText: formatStars(loc.avg_score || 0),
        avgScoreText: (loc.avg_score || 0).toFixed(1),
        rating_count: loc.rating_count || 0,
        review_count: loc.review_count || 0,
        summaryPreview: '',
        summaryStatus: 'loading',
      },
    })
    try {
      const detail = await getDetail(loc.id)
      if (this.data.selectedLocation && this.data.selectedLocation.id === loc.id) {
        this.setData({
          selectedLocation: {
            ...this.data.selectedLocation,
            summaryPreview: detail.summary?.summary_text || '',
            summaryStatus: detail.summary?.status || 'insufficient',
          },
        })
      }
    } catch {
      if (this.data.selectedLocation && this.data.selectedLocation.id === loc.id) {
        this.setData({ 'selectedLocation.summaryStatus': 'insufficient' })
      }
    }
  },

  closeLocationCard() {
    this.setData({ selectedLocation: null })
  },

  goToLocationsPage() {
    wx.navigateTo({ url: '/subpackages/pages/locations/locations' })
  },

  goToLocationDetail() {
    const loc = this.data.selectedLocation
    if (!loc) return
    wx.navigateTo({ url: `/subpackages/pages/locations/locations?id=${loc.id}` })
  },

})
