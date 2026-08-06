import { campusStore } from '../../store/campus'
import { getLocations } from '../../services/locations'
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

const DEFAULT_LAT = 31.4882
const DEFAULT_LNG = 120.588

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
      this.loadLocations()
    })
  },

  async onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    this.loadLocations()
  },

  async loadLocations() {
    try {
      const locs = await getLocations()
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
    } catch (e: any) {
      console.error('加载地点标记失败', e)
      wx.showToast({ title: e.message || '加载地点标记失败', icon: 'none' })
    }
  },

  onMarkerTap(e: any) {
    const markerId = e.detail.markerId
    const loc = this.data.rawLocations.find(m => m.id === markerId)
    if (!loc) return
    this.setData({
      selectedLocation: {
        id: loc.id,
        name: loc.name,
        starsText: formatStars(loc.avg_score || 0),
        avgScoreText: (loc.avg_score || 0).toFixed(1),
        rating_count: loc.rating_count || 0,
        review_count: loc.review_count || 0,
      },
    })
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

  goToSchoolSelect() {
    wx.navigateTo({ url: '/subpackages/pages/school-select/school-select' })
  },
})