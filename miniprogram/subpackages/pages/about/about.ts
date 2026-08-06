const VERSION = '1.0.0'

Page({
  data: {
    version: '',
    checking: false,
  },

  onLoad() {
    const app = getApp() as any
    const globalVersion = app && app.globalData && app.globalData.version
    this.setData({ version: globalVersion || VERSION })
  },

  // 检查更新（Task 7）：调用 wx.getUpdateManager 检查是否有新版本
  checkUpdate() {
    if (this.data.checking) return
    this.setData({ checking: true })
    try {
      // 能力检测：基础库过低时降级提示
      if (typeof wx.getUpdateManager !== 'function') {
        wx.showToast({ title: '当前微信版本不支持自动更新', icon: 'none' })
        this.setData({ checking: false })
        return
      }
      const updateManager = wx.getUpdateManager()
      updateManager.onCheckForUpdate((res: any) => {
        this.setData({ checking: false })
        if (!res.hasUpdate) {
          wx.showToast({ title: '已是最新版本', icon: 'success' })
        }
      })
      updateManager.onUpdateReady(() => {
        wx.showModal({
          title: '更新提示',
          content: '新版本已经准备好，是否重启应用？',
          success: r => {
            if (r.confirm) {
              updateManager.applyUpdate()
            }
          },
        })
      })
      updateManager.onUpdateFailed(() => {
        this.setData({ checking: false })
        wx.showToast({ title: '更新失败，请稍后重试', icon: 'none' })
      })
    } catch (e) {
      this.setData({ checking: false })
      wx.showToast({ title: '检查更新失败', icon: 'none' })
    }
  },

  goToAgreement() {
    wx.navigateTo({ url: '/subpackages/pages/agreement/agreement' })
  },

  goToPrivacy() {
    wx.navigateTo({ url: '/subpackages/pages/privacy/privacy' })
  },

  goToFeedback() {
    wx.navigateTo({ url: '/subpackages/pages/feedback/feedback' })
  },
})