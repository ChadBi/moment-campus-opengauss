Component({
  data: {
    selected: 0,
    switching: false,
    color: 'rgba(255,255,255,0.75)',
    list: [
      { pagePath: '/pages/home/home' },
      { pagePath: '/pages/map/map' },
      { pagePath: '/pages/search/search' },
      { pagePath: '/pages/publish/publish' },
      { pagePath: '/pages/profile/profile' },
    ]
  },

  methods: {
    switchTab(e: any) {
      const path = String(e.currentTarget.dataset.path || '')
      const index = Number(e.currentTarget.dataset.index)
      if (!path || !Number.isInteger(index) || index < 0 || index > 4) return
      if (this.data.switching || this.data.selected === index) return

      // 等真实路由成功后再更新高亮，避免点击时先闪到目标页又被旧页面覆盖。
      this.setData({ switching: true })
      wx.switchTab({
        url: path,
        success: () => {
          this.setData({ selected: index })
        },
        fail: error => {
          console.error('切换底部页面失败', { path, index, error })
          wx.showToast({ title: '页面切换失败，请稍后再试', icon: 'none' })
        },
        complete: () => {
          this.setData({ switching: false })
        },
      })
    }
  }
})
