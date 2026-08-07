import { authStore } from '../../store/auth'
import { wechatExchange, emailLogin } from '../../services/auth'

Page({
  data: {
    mode: 'wechat' as 'wechat' | 'email',
    loading: false,
    email: '',
    password: '',
    errorMsg: '',
  },

  switchMode(e: any) {
    this.setData({
      mode: e.currentTarget.dataset.mode,
      errorMsg: '',
    })
  },

  onEmailInput(e: any) {
    this.setData({ email: e.detail.value })
  },

  onPasswordInput(e: any) {
    this.setData({ password: e.detail.value })
  },

  async onWechatLogin() {
    if (this.data.loading) return
    this.setData({ loading: true, errorMsg: '' })

    try {
      const loginRes = await new Promise<WechatLoginResult>((resolve, reject) => {
        wx.login({
          success: res => {
            if (res.code) {
              resolve({ code: res.code })
            } else {
              reject(new Error('微信登录失败'))
            }
          },
          fail: () => reject(new Error('微信登录失败')),
        })
      })

      const exchangeRes = await wechatExchange(loginRes.code)

      if (exchangeRes.status === 'authenticated') {
        authStore.setAuth({
          access_token: exchangeRes.access_token,
          refresh_token: exchangeRes.refresh_token,
          user: exchangeRes.user,
        })
        wx.showToast({ title: '登录成功', icon: 'success' })
        setTimeout(() => wx.switchTab({ url: '/pages/home/home' }), 500)
      } else if (exchangeRes.status === 'binding_required') {
        // 首次微信登录直接进入与普通注册一致的邮箱注册表单，
        // 不再默认落到“绑定已有账号”的密码表单。
        wx.navigateTo({
          url: `/pages/register/register?ticket=${exchangeRes.binding_ticket}`,
        })
      }
    } catch (e: any) {
      this.setData({ errorMsg: e.message || '登录失败' })
    } finally {
      this.setData({ loading: false })
    }
  },

  async onEmailLogin() {
    if (this.data.loading) return
    if (!this.data.email || !this.data.password) {
      this.setData({ errorMsg: '请填写邮箱和密码' })
      return
    }
    this.setData({ loading: true, errorMsg: '' })

    try {
      const res = await emailLogin(this.data.email, this.data.password)
      authStore.setAuth(res)
      wx.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/home/home' }), 500)
    } catch (e: any) {
      this.setData({ errorMsg: e.message || '登录失败' })
    } finally {
      this.setData({ loading: false })
    }
  },

  goToRegister() {
    if (this.data.loading) return
    this.setData({ loading: true, errorMsg: '' })
    new Promise<string>((resolve, reject) => {
      wx.login({
        success: res => res.code ? resolve(res.code) : reject(new Error('微信登录失败')),
        fail: () => reject(new Error('微信登录失败')),
      })
    }).then(code => wechatExchange(code)).then(res => {
      if (res.status !== 'binding_required') throw new Error('该微信已绑定账号，请直接登录')
      wx.navigateTo({
        url: `/pages/register/register?ticket=${res.binding_ticket}`,
      })
    }).catch((e: any) => {
      this.setData({ errorMsg: e.message || '注册入口打开失败' })
    }).finally(() => this.setData({ loading: false }))
  },

  goToHome() {
    const url = '/pages/home/home'
    // 登录页可能是通过 reLaunch/navigateTo 打开的，部分开发者工具版本
    // 对此时的 switchTab 不回调；失败时用 reLaunch 保证游客入口可用。
    wx.switchTab({
      url,
      fail: err => {
        console.warn('游客入口切换首页失败，改用重启导航', err)
        wx.reLaunch({
          url,
          fail: relaunchError => {
            console.error('游客入口导航失败', relaunchError)
            wx.showToast({ title: '首页打开失败，请重试', icon: 'none' })
          },
        })
      },
    })
  },

  goToForgotPassword() {
    wx.navigateTo({ url: '/subpackages/pages/forgot-password/forgot-password' })
  },
})

interface WechatLoginResult {
  code: string
}
