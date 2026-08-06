import { forgotPassword, resetPassword } from '../../../services/auth'

Page({
  data: {
    step: 1 as 1 | 2,
    email: '',
    resetToken: '',
    newPassword: '',
    confirmPassword: '',
    loading: false,
    errorMsg: '',
    infoMsg: '',
  },

  onEmailInput(e: any) {
    this.setData({ email: e.detail.value })
  },

  onResetTokenInput(e: any) {
    this.setData({ resetToken: e.detail.value })
  },

  onPasswordInput(e: any) {
    this.setData({ newPassword: e.detail.value })
  },

  onConfirmPasswordInput(e: any) {
    this.setData({ confirmPassword: e.detail.value })
  },

  async onSendResetEmail() {
    if (this.data.loading) return
    const email = this.data.email.trim()
    if (!email) {
      this.setData({ errorMsg: '请输入邮箱' })
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      this.setData({ errorMsg: '邮箱格式不正确' })
      return
    }
    this.setData({ loading: true, errorMsg: '', infoMsg: '' })

    try {
      const res = await forgotPassword(email)
      if (res.reset_token) {
        this.setData({
          resetToken: res.reset_token,
          infoMsg: '本地开发环境已返回重置 Token（生产环境将通过邮件发送）',
        })
      } else {
        this.setData({
          infoMsg: res.message || '如该邮箱已注册，重置链接已发送',
        })
      }
      this.setData({ step: 2 })
    } catch (e: any) {
      this.setData({ errorMsg: e.message || '操作失败，请稍后重试' })
    } finally {
      this.setData({ loading: false })
    }
  },

  async onResetPassword() {
    if (this.data.loading) return
    const { resetToken, newPassword, confirmPassword } = this.data

    if (!resetToken) {
      this.setData({ errorMsg: '请输入重置 Token' })
      return
    }
    if (!newPassword) {
      this.setData({ errorMsg: '请输入新密码' })
      return
    }
    if (newPassword.length < 6) {
      this.setData({ errorMsg: '密码长度至少为 6 位' })
      return
    }
    if (newPassword !== confirmPassword) {
      this.setData({ errorMsg: '两次输入的密码不一致' })
      return
    }
    this.setData({ loading: true, errorMsg: '' })

    try {
      const res = await resetPassword({ token: resetToken, new_password: newPassword })
      wx.showToast({ title: res.message || '密码已重置', icon: 'success' })
      setTimeout(() => {
        wx.navigateBack({
          fail: () => wx.reLaunch({ url: '/pages/login/login' }),
        })
      }, 1500)
    } catch (e: any) {
      this.setData({ errorMsg: e.message || '重置失败，请稍后重试' })
    } finally {
      this.setData({ loading: false })
    }
  },

  goToLogin() {
    wx.navigateTo({ url: '/pages/login/login' })
  },

  backToStep1() {
    this.setData({ step: 1, errorMsg: '', resetToken: '' })
  },
})