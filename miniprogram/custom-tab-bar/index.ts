Component({
  data: {
    selected: 0,
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
      const path = e.currentTarget.dataset.path
      const index = Number(e.currentTarget.dataset.index)
      this.setData({ selected: index })
      wx.switchTab({
        url: path,
        fail: () => {
          wx.switchTab({ url: '/pages/home/home' })
        }
      })
    }
  }
})
