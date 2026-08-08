import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { wechatPhoneLogin } from '../../services/auth'
import { navigateToTab } from '../../utils/tab-navigation'

Page({
  data: {
    loading: false,
    errorMsg: '',
  },

  async onGetPhoneNumber(e: any) {
    if (this.data.loading) return
    const phoneCode = e?.detail?.code
    if (!phoneCode) {
      this.setData({ errorMsg: '需要授权手机号才能登录此刻校园' })
      return
    }
    this.setData({ loading: true, errorMsg: '' })
    try {
      const wxCode = await new Promise<string>((resolve, reject) => {
        wx.login({
          success: res => res.code ? resolve(res.code) : reject(new Error('微信登录失败')),
          fail: () => reject(new Error('微信登录失败')),
        })
      })
      const response = await wechatPhoneLogin(wxCode, phoneCode, campusStore.getState().schoolCode || 'jiangnan')
      await authStore.setAuth(response)
      wx.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => navigateToTab('/pages/profile/profile'), 500)
    } catch (error: any) {
      this.setData({ errorMsg: error?.message || '微信手机号登录失败，请重试' })
    } finally {
      this.setData({ loading: false })
    }
  },

  goToHome() {
    navigateToTab('/pages/home/home')
  },
})
