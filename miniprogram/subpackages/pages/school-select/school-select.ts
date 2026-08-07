import { getCurrentSchool, joinSchool, listSchools } from '../../../services/schools'
import { campusStore } from '../../../store/campus'
import { resolveImageUrl } from '../../../services/request'
import { clearSchoolCache } from '../../../utils/school-cache'

interface SchoolView {
  id: number
  code: string
  name: string
  logo_url?: string
  description?: string
  province?: string
  city?: string
  center_lat: number
  center_lng: number
  map_zoom: number
  is_active: boolean
  logoUrl: string
  logoText: string
  selected: boolean
}

function getSchoolLogoText(name: string, code: string): string {
  const compactName = String(name || '').replace(/大学|学院|学校/g, '')
  if (compactName) return compactName.slice(0, 2)
  return String(code || '校').slice(0, 3).toUpperCase()
}

Page({
  data: {
    mode: '' as string,
    schools: [] as SchoolView[],
    selectedId: 0 as number,
    selectedCode: '' as string,
    loading: false,
    submitting: false,
  },

  async onLoad(options: any) {
    const mode = options && options.mode ? options.mode : ''
    this.setData({ mode })
    await this.loadSchools()
  },

  async loadSchools() {
    this.setData({ loading: true })
    try {
      const res = await listSchools()
      const current = campusStore.getState().currentSchool
      const currentId = (current && current.id) || 0
      const schools: SchoolView[] = res.map(s => ({
        ...s,
        logoUrl: resolveImageUrl(s.logo_url),
        logoText: getSchoolLogoText(s.name, s.code),
        selected: s.id === currentId,
      }))
      this.setData({
        schools,
        selectedId: currentId,
        selectedCode: (current && current.code) || '',
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载学校失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onSelectSchool(e: any) {
    const id = Number(e.currentTarget.dataset.id)
    const schools = this.data.schools.map(s => ({
      ...s,
      selected: s.id === id,
    }))
    this.setData({
      schools,
      selectedId: id,
      selectedCode: (this.data.schools.find(s => s.id === id) || {}).code || '',
    })
  },

  async onConfirm() {
    const code = this.data.selectedCode
    if (!code) {
      wx.showToast({ title: '请先选择学校', icon: 'none' })
      return
    }
    if (this.data.submitting) return
    this.setData({ submitting: true })
    try {
      const oldState = campusStore.getState()
      await joinSchool(code)
      const school = await getCurrentSchool(code)
      clearSchoolCache(oldState.schoolCode)
      campusStore.setSchool(school)
      wx.showToast({ title: '切换成功', icon: 'success' })
      setTimeout(() => {
        wx.navigateBack({ delta: 1 })
      }, 600)
    } catch (e: any) {
      wx.showToast({ title: e.message || '切换失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },
})
