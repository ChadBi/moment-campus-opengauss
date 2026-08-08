import { getCurrentPageTabBarIndex, getPreparedTabBarPath, getTabBarIndex, getTabBarPath, prepareTabBarSwitch, setPreparedTabBarPath, setTabBarIndex } from '../utils/tab-navigation'

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

  lifetimes: {
    attached() {
      const preparedPath = getPreparedTabBarPath()
      const currentPageSelected = getCurrentPageTabBarIndex()
      const selected = preparedPath ? getTabBarIndex(preparedPath) : (currentPageSelected ?? getTabBarIndex())
      if (!preparedPath && currentPageSelected !== null) setTabBarIndex(currentPageSelected)
      if (selected !== null && selected !== this.data.selected) {
        this.setData({ selected })
      }
    },
  },

  methods: {
    switchTab(e: any) {
      const path = String(e.currentTarget.dataset.path || '')
      const index = Number(e.currentTarget.dataset.index)
      if (!path || !Number.isInteger(index) || index < 0 || index > 4) return
      if (this.data.switching || this.data.selected === index) return

      const previousSelected = this.data.selected
      const previousPath = getTabBarPath(previousSelected)
      // 先同步唯一导航状态，再发起路由；页面 onShow 不再反向覆盖高亮。
      prepareTabBarSwitch(path)
      this.setData({ selected: index, switching: true })
      wx.switchTab({
        url: path,
        success: () => undefined,
        fail: error => {
          setTabBarIndex(previousSelected)
          setPreparedTabBarPath(previousPath)
          this.setData({ selected: previousSelected })
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
