import { authStore } from '../../store/auth'
import { wechatExchange, emailLogin, wechatBindExisting } from '../../services/auth'

Page({
  data: {
    mode: 'wechat' as 'wechat' | 'email',
    loading: false,
    email: '',
    password: '',
    errorMsg: '',
    bindLoading: false,
    bindErrorMsg: '',
  },

  switchMode(e: any) {
    this.setData({
      mode: e.currentTarget.dataset.mode,
      errorMsg: '',
      bindErrorMsg: '',
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
        await authStore.setAuth(exchangeRes as any)
        wx.showToast({ title: '登录成功', icon: 'success' })
        setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 500)
      } else if (exchangeRes.status === 'binding_required') {
        wx.navigateTo({
          url: `/pages/register/register?ticket=${exchangeRes.binding_ticket}&from=login`,
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
      await authStore.setAuth(res)
      wx.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 500)
    } catch (e: any) {
      this.setData({ errorMsg: e.message || '登录失败' })
    } finally {
      this.setData({ loading: false })
    }
  },

  async onBindExistingTap() {
    if (this.data.loading || this.data.bindLoading) return
    if (!this.data.email || !this.data.password) {
      this.setData({ errorMsg: '请先填写邮箱和密码' })
      return
    }
    this.setData({ bindLoading: true, bindErrorMsg: '', errorMsg: '' })
    try {
      const code = await new Promise<string>((resolve, reject) => {
        wx.login({
          success: res => (res.code ? resolve(res.code) : reject(new Error('微信登录失败'))),
          fail: () => reject(new Error('微信登录失败')),
        })
      })
      const exchangeRes = await wechatExchange(code)
      if (exchangeRes.status === 'authenticated') {
        await authStore.setAuth(exchangeRes as any)
        wx.showToast({ title: '该微信已直接登录', icon: 'success' })
        setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 500)
        return
      }
      if (exchangeRes.status !== 'binding_required') {
        throw new Error('微信状态异常，请重试')
      }
      const bindRes = await wechatBindExisting(
        exchangeRes.binding_ticket,
        this.data.email,
        this.data.password,
      )
      await authStore.setAuth(bindRes as any)
      wx.showToast({ title: '绑定并登录成功', icon: 'success' })
      setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 500)
    } catch (e: any) {
      const raw = e?.message || '绑定失败'
      const prefix = /已绑定|不能重复/.test(raw) ? '绑定失败：' : ''
      this.setData({ bindErrorMsg: prefix + raw })
    } finally {
      this.setData({ bindLoading: false })
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
        url: `/pages/register/register?ticket=${res.binding_ticket}&from=login`,
      })
    }).catch((e: any) => {
      this.setData({ errorMsg: e.message || '注册入口打开失败' })
    }).finally(() => this.setData({ loading: false }))
  },

  goToHome() {
    const url = '/pages/home/home'
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
