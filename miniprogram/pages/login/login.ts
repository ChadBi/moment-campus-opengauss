import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { sendSms, wechatLogin, wechatSmsLogin } from '../../services/auth'
import { listSchools } from '../../services/schools'
import type { LoginResponse, School } from '../../types'
import { clearSchoolCache } from '../../utils/school-cache'
import { navigateToTab } from '../../utils/tab-navigation'

let countdownTimer: number | null = null

function getWxLoginCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    wx.login({
      success: res => res.code ? resolve(res.code) : reject(new Error('微信登录失败，请重试')),
      fail: () => reject(new Error('微信登录失败，请重试')),
    })
  })
}

Page({
  data: {
    step: 'wechat',
    phone: '',
    smsCode: '',
    schools: [] as School[],
    schoolNames: [] as string[],
    schoolIndex: -1,
    selectedSchoolCode: '',
    selectedSchoolName: '',
    schoolLoading: false,
    wechatLoading: false,
    sendingCode: false,
    countdown: 0,
    loading: false,
    errorMsg: '',
  },

  async onWechatLogin() {
    if (this.data.wechatLoading) return
    this.setData({ wechatLoading: true, errorMsg: '' })
    try {
      const wxCode = await getWxLoginCode()
      const response = await wechatLogin(wxCode)
      if (response.status === 'authenticated' && response.access_token && response.refresh_token && response.user) {
        await this.loadSchools()
        await this.completeLogin(response as LoginResponse)
        return
      }
      this.setData({ step: 'phone', errorMsg: response.message || '首次登录需要绑定手机号' })
      await this.loadSchools()
    } catch (error: any) {
      this.setData({ errorMsg: error?.message || '微信登录失败，请重试' })
    } finally {
      this.setData({ wechatLoading: false })
    }
  },

  async loadSchools() {
    if (this.data.schoolLoading) return
    this.setData({ schoolLoading: true, errorMsg: '' })
    try {
      const schools = (await listSchools()).filter(school => school.is_active !== false)
      if (schools.length === 0) throw new Error('暂无可选学校，请稍后重试')
      const currentCode = campusStore.getState().schoolCode
      const matchedIndex = schools.findIndex(school => school.code === currentCode)
      const schoolIndex = matchedIndex >= 0 ? matchedIndex : 0
      const selected = schools[schoolIndex]
      this.setData({
        schools,
        schoolNames: schools.map(school => school.name),
        schoolIndex,
        selectedSchoolCode: selected.code,
        selectedSchoolName: selected.name,
      })
    } catch (error: any) {
      this.setData({
        schools: [],
        schoolNames: [],
        schoolIndex: -1,
        selectedSchoolCode: '',
        selectedSchoolName: '',
        errorMsg: error?.message || '学校列表加载失败，请重试',
      })
    } finally {
      this.setData({ schoolLoading: false })
    }
  },

  onSchoolChange(e: any) {
    const schoolIndex = Number(e?.detail?.value)
    const selected = this.data.schools[schoolIndex]
    if (!selected) return
    this.setData({
      schoolIndex,
      selectedSchoolCode: selected.code,
      selectedSchoolName: selected.name,
      errorMsg: '',
    })
  },

  onPhoneInput(e: any) {
    const phone = String(e?.detail?.value || '').replace(/\D/g, '').slice(0, 11)
    this.setData({ phone, errorMsg: '' })
  },

  onSmsCodeInput(e: any) {
    const smsCode = String(e?.detail?.value || '').replace(/\D/g, '').slice(0, 6)
    this.setData({ smsCode, errorMsg: '' })
  },

  startCountdown() {
    if (countdownTimer !== null) clearInterval(countdownTimer)
    this.setData({ countdown: 60 })
    countdownTimer = setInterval(() => {
      const next = this.data.countdown - 1
      if (next <= 0) {
        if (countdownTimer !== null) clearInterval(countdownTimer)
        countdownTimer = null
        this.setData({ countdown: 0 })
        return
      }
      this.setData({ countdown: next })
    }, 1000) as unknown as number
  },

  async onSendSms() {
    if (this.data.sendingCode || this.data.countdown > 0) return
    if (!/^1\d{10}$/.test(this.data.phone)) {
      this.setData({ errorMsg: '请输入有效的国内 11 位手机号' })
      return
    }
    this.setData({ sendingCode: true, errorMsg: '' })
    try {
      await sendSms(this.data.phone, 'login')
      this.startCountdown()
      wx.showToast({ title: '验证码已发送', icon: 'success' })
    } catch (error: any) {
      this.setData({ errorMsg: error?.message || '验证码发送失败，请重试' })
    } finally {
      this.setData({ sendingCode: false })
    }
  },

  async onSubmitWechatSmsLogin() {
    if (this.data.loading) return
    if (!this.data.selectedSchoolCode) {
      this.setData({ errorMsg: '请先选择学校' })
      return
    }
    if (!/^1\d{10}$/.test(this.data.phone)) {
      this.setData({ errorMsg: '请输入有效的国内 11 位手机号' })
      return
    }
    if (!/^\d{6}$/.test(this.data.smsCode)) {
      this.setData({ errorMsg: '请输入 6 位短信验证码' })
      return
    }
    this.setData({ loading: true, errorMsg: '' })
    try {
      // wx.login code 只能使用一次；每次提交（包括失败重试）都必须重新获取。
      const wxCode = await getWxLoginCode()
      const response = await wechatSmsLogin(
        wxCode,
        this.data.phone,
        this.data.smsCode,
        this.data.selectedSchoolCode,
      )
      await this.completeLogin(response)
    } catch (error: any) {
      this.setData({ errorMsg: error?.message || '绑定登录失败，请重试' })
    } finally {
      this.setData({ loading: false })
    }
  },

  async completeLogin(response: LoginResponse) {
    const boundSchool = this.data.schools.find(school => school.id === response.user.school_id)
    if (!boundSchool) throw new Error('账号绑定学校不可用，请联系管理员')
    await authStore.setAuth(response)
    const previousSchoolCode = campusStore.getState().schoolCode
    if (previousSchoolCode !== boundSchool.code) clearSchoolCache(previousSchoolCode)
    campusStore.setSchool(boundSchool)
    wx.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => navigateToTab('/pages/profile/profile'), 500)
  },

  onUnload() {
    if (countdownTimer !== null) clearInterval(countdownTimer)
    countdownTimer = null
  },

  goToHome() {
    navigateToTab('/pages/home/home')
  },
})
