import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { sendSms, wechatSmsLogin } from '../../services/auth'
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
    wxCode: '',
    wxCodeAt: 0,
    phone: '',
    smsCode: '',
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
      this.setData({
        step: 'phone',
        wxCode,
        wxCodeAt: Date.now(),
      })
    } catch (error: any) {
      this.setData({ errorMsg: error?.message || '微信登录失败，请重试' })
    } finally {
      this.setData({ wechatLoading: false })
    }
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
      let wxCode = this.data.wxCode
      if (!wxCode || Date.now() - this.data.wxCodeAt > 4 * 60 * 1000) {
        wxCode = await getWxLoginCode()
      }
      const response = await wechatSmsLogin(
        wxCode,
        this.data.phone,
        this.data.smsCode,
        campusStore.getState().schoolCode || 'jiangnan',
      )
      await authStore.setAuth(response)
      wx.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => navigateToTab('/pages/profile/profile'), 500)
    } catch (error: any) {
      this.setData({ errorMsg: error?.message || '绑定登录失败，请重试' })
    } finally {
      this.setData({ loading: false })
    }
  },

  resetWechatStep() {
    this.setData({ step: 'wechat', wxCode: '', wxCodeAt: 0, smsCode: '', errorMsg: '' })
  },

  onUnload() {
    if (countdownTimer !== null) clearInterval(countdownTimer)
    countdownTimer = null
  },

  goToHome() {
    navigateToTab('/pages/home/home')
  },
})
