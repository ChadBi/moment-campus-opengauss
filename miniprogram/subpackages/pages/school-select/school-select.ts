import { getCurrentSchool, joinSchool, listSchools } from '../../../services/schools'
import { authStore } from '../../../store/auth'
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
    filteredSchools: [] as SchoolView[],
    searchQuery: '' as string,
    selectedId: 0 as number,
    selectedCode: '' as string,
    selectedName: '' as string,
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
        filteredSchools: schools,
        searchQuery: '',
        selectedId: currentId,
        selectedCode: (current && current.code) || '',
        selectedName: (current && current.name) || '',
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载学校失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onSearchInput(e: any) {
    const searchQuery = String(e?.detail?.value || '').trim().toLowerCase()
    const filteredSchools = this.filterSchools(searchQuery)
    this.setData({ searchQuery, filteredSchools })
  },

  filterSchools(searchQuery: string, schools = this.data.schools): SchoolView[] {
    if (!searchQuery) return schools
    return schools.filter(school => {
      const searchable = [school.name, school.code, school.province, school.city, school.description]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return searchable.includes(searchQuery)
    })
  },

  clearSearch() {
    this.setData({ searchQuery: '', filteredSchools: this.data.schools })
  },

  onSelectSchool(e: any) {
    const id = Number(e.currentTarget.dataset.id)
    const schools = this.data.schools.map(s => ({
      ...s,
      selected: s.id === id,
    }))
    const selected = schools.find(s => s.id === id)
    this.setData({
      schools,
      filteredSchools: this.filterSchools(this.data.searchQuery, schools),
      selectedId: id,
      selectedCode: selected?.code || '',
      selectedName: selected?.name || '',
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

      // 游客切换的是本地浏览租户，不创建/修改账号学校绑定。
      const authState = authStore.getState()
      if (!authState.isLoggedIn) {
        const school = this.data.schools.find(item => item.code === code)
        if (!school) throw new Error('学校信息不存在，请重新选择')
        clearSchoolCache(oldState.schoolCode)
        campusStore.setSchool(school)
        wx.showToast({ title: '浏览学校已切换', icon: 'success' })
        setTimeout(() => {
          wx.navigateBack({ delta: 1 })
        }, 500)
        return
      }

      await joinSchool(code)
      const school = await getCurrentSchool(code)
      clearSchoolCache(oldState.schoolCode)
      campusStore.setSchool(school)
      const user = authState.user
      if (user) authStore.setUser({ ...user, school_id: school.id })
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
