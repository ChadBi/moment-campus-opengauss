import { listSchools, switchSchool } from '../../services/schools'
import { campusStore } from '../../store/campus'
import { resolveImageUrl } from '../../services/request'

interface SchoolView {
  id: number
  code: string
  name: string
  short_name: string
  logo_url?: string
  description?: string
  location?: string
  latitude?: number
  longitude?: number
  map_zoom?: number
  is_active: boolean
  logoUrl: string
  selected: boolean
}

Page({
  data: {
    mode: '' as string,
    schools: [] as SchoolView[],
    selectedId: 0 as number,
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
      const schools: SchoolView[] = (res.schools || []).map(s => ({
        ...s,
        logoUrl: resolveImageUrl(s.logo_url),
        selected: s.id === currentId,
      }))
      this.setData({
        schools,
        selectedId: currentId,
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
    })
  },

  async onConfirm() {
    const id = this.data.selectedId
    if (!id) {
      wx.showToast({ title: '请先选择学校', icon: 'none' })
      return
    }
    if (this.data.submitting) return
    this.setData({ submitting: true })
    try {
      const res = await switchSchool(id)
      campusStore.setSchool(res.school)
      wx.showToast({ title: '切换成功', icon: 'success' })
      setTimeout(() => {
        if (this.data.mode === 'register') {
          wx.reLaunch({ url: '/pages/home/home' })
        } else {
          wx.navigateBack({ delta: 1 })
        }
      }, 600)
    } catch (e: any) {
      wx.showToast({ title: e.message || '切换失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },
})
