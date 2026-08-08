import { authStore } from '../../store/auth'
import { wechatBindExisting, wechatRegister, emailRegister } from '../../services/auth'
import { listSchools, getCurrentSchool } from '../../services/schools'
import { campusStore } from '../../store/campus'
import { navigateToTab } from '../../utils/tab-navigation'
import type { School } from '../../types'

Page({
  data: {
    bindingTicket: '',
    mode: 'register' as 'bind' | 'register',
    email: '',
    password: '',
    showPassword: false,
    confirmPassword: '',
    showConfirmPassword: false,
    nickname: '',
    schoolId: 0,
    schoolName: '',
    loading: false,
    errorMsg: '',
    schools: [] as School[],
    schoolIndex: 0,
  },

  onLoad(options: { ticket?: string; mode?: string }) {
    const mode = options.mode === 'bind' ? 'bind' : 'register'
    this.setData({ bindingTicket: options.ticket || '', mode })
    wx.setNavigationBarTitle({ title: mode === 'bind' ? '绑定已有账号' : '注册账号' })
    this.loadSchools()
  },

  async loadSchools() {
    try {
      const schools = await listSchools()
      this.setData({ schools })
    } catch (e) {
      console.error('加载学校列表失败', e)
    }
  },

  onEmailInput(e: any) { this.setData({ email: e.detail.value }) },
  onPasswordInput(e: any) { this.setData({ password: e.detail.value }) },
  onConfirmPasswordInput(e: any) { this.setData({ confirmPassword: e.detail.value }) },
  onNicknameInput(e: any) { this.setData({ nickname: e.detail.value }) },
  toggleShowPassword() { this.setData({ showPassword: !this.data.showPassword }) },
  toggleShowConfirmPassword() { this.setData({ showConfirmPassword: !this.data.showConfirmPassword }) },
  switchMode(e: any) {
    const mode = e.currentTarget.dataset.mode === 'bind' ? 'bind' : 'register'
    this.setData({ mode, errorMsg: '', confirmPassword: '' })
    wx.setNavigationBarTitle({ title: mode === 'bind' ? '绑定已有账号' : '注册账号' })
  },
  onSchoolSelect(e: any) {
    const index = Number(e.detail.value)
    const school = this.data.schools[index]
    if (school) {
      this.setData({ schoolId: school.id, schoolName: school.name, schoolIndex: index })
    }
  },

  async onSubmit() {
    if (this.data.loading) return
    this.setData({ loading: true, errorMsg: '' })

    try {
      if (this.data.mode === 'bind') {
        if (!this.data.email || !this.data.password) {
          this.setData({ errorMsg: '请填写邮箱和密码' })
          return
        }
        const res = await wechatBindExisting(
          this.data.bindingTicket,
          this.data.email,
          this.data.password
        )
        authStore.setAuth(res)
      } else {
        if (!this.data.email || !this.data.nickname || !this.data.schoolId) {
          this.setData({ errorMsg: '请填写教育邮箱、昵称并选择学校' })
          return
        }
        if (this.data.nickname.trim().length < 2) {
          this.setData({ errorMsg: '昵称至少需要 2 个字符' })
          return
        }
        const emailDomain = this.data.email.trim().toLowerCase().split('@')[1]
        const selectedSchool = this.data.schools.find(s => s.id === this.data.schoolId)
        const allowedDomains = (selectedSchool?.domains || []).map(domain => domain.toLowerCase())
        const isQqEmail = emailDomain === 'qq.com'
        if (!emailDomain || !this.data.email.includes('@')) {
          this.setData({ errorMsg: '请输入有效的教育邮箱' })
          return
        }
        if (allowedDomains.length > 0 && !allowedDomains.includes(emailDomain) && !isQqEmail) {
          this.setData({ errorMsg: `请使用${selectedSchool?.name || '所选学校'}的官方邮箱，或使用 qq.com 邮箱` })
          return
        }
        if (!this.data.password || !this.data.confirmPassword) {
          this.setData({ errorMsg: '请设置并确认密码' })
          return
        }
        if (this.data.password.length < 6) {
          this.setData({ errorMsg: '密码长度至少为 6 位' })
          return
        }
        if (this.data.password !== this.data.confirmPassword) {
          this.setData({ errorMsg: '两次输入的密码不一致' })
          return
        }
        const res = await emailRegister({
          nickname: this.data.nickname,
          school_id: this.data.schoolId,
          password: this.data.password,
          email: this.data.email,
        })
        authStore.setAuth(res)
        const selected = this.data.schools.find(s => s.id === this.data.schoolId)
        if (selected) {
          const school = await getCurrentSchool(selected.code)
          campusStore.setSchool(school)
        }
      }

      wx.showToast({ title: '成功', icon: 'success' })
      setTimeout(() => navigateToTab('/pages/profile/profile'), 500)
    } catch (e: any) {
      const msg = e?.message || '操作失败'
      const status = e?.status || e?.statusCode
      const prefix = (status === 409 || /已绑定|已被注册/.test(msg)) ? '绑定失败：' : ''
      this.setData({ errorMsg: prefix + msg })
    } finally {
      this.setData({ loading: false })
    }
  },
})
