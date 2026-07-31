import { authStore } from '../../store/auth'

Page({
  data: {
    bindingTicket: '',
    mode: 'bind' as 'bind' | 'register',
    email: '',
    password: '',
    nickname: '',
    schoolId: 0,
    schoolName: '',
    loading: false,
    errorMsg: '',
    schools: [] as Array<{ id: number; name: string; code: string }>,
  },

  onLoad(options: { ticket?: string; mode?: string }) {
    if (options.ticket) {
      this.setData({ bindingTicket: options.ticket, mode: options.mode === 'register' ? 'register' : 'bind' })
    }
    this.loadSchools()
  },

  async loadSchools() {
    try {
      const { http } = await import('../../services/request')
      const res = await http.get<any>('/schools')
      this.setData({ schools: res.schools || [] })
    } catch (e) {
      console.error('加载学校列表失败', e)
    }
  },

  onEmailInput(e: any) { this.setData({ email: e.detail.value }) },
  onPasswordInput(e: any) { this.setData({ password: e.detail.value }) },
  onNicknameInput(e: any) { this.setData({ nickname: e.detail.value }) },
  onSchoolSelect(e: any) {
    const index = Number(e.detail.value)
    const school = this.data.schools[index]
    if (school) {
      this.setData({ schoolId: school.id, schoolName: school.name })
    }
  },

  async onSubmit() {
    if (this.data.loading) return
    this.setData({ loading: true, errorMsg: '' })

    try {
      const { wechatBindExisting, wechatRegister } = await import('../../services/auth')

      if (this.data.mode === 'bind') {
        const res = await wechatBindExisting(
          this.data.bindingTicket,
          this.data.email,
          this.data.password
        )
        authStore.setAuth(res)
      } else {
        if (!this.data.nickname || !this.data.schoolId) {
          this.setData({ errorMsg: '请填写昵称和选择学校' })
          return
        }
        const res = await wechatRegister({
          binding_ticket: this.data.bindingTicket,
          nickname: this.data.nickname,
          school_id: this.data.schoolId,
          password: this.data.password,
          email: this.data.email || undefined,
        })
        authStore.setAuth(res)
      }

      wx.showToast({ title: '成功', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/home/home' }), 500)
    } catch (e: any) {
      this.setData({ errorMsg: e.message || '操作失败' })
    } finally {
      this.setData({ loading: false })
    }
  },
})
