import { getCurrentPageTabBarIndex, getPreparedTabBarPath, getTabBarIndex, getTabBarPath, prepareTabBarSwitch, setPreparedTabBarPath, setTabBarIndex } from '../utils/tab-navigation'

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

  lifetimes: {
    attached() {
      const preparedPath = getPreparedTabBarPath()
      const currentPageSelected = getCurrentPageTabBarIndex()
      const selected = currentPageSelected ?? (preparedPath ? getTabBarIndex(preparedPath) : getTabBarIndex())
      if (currentPageSelected !== null) {
        setTabBarIndex(currentPageSelected)
        setPreparedTabBarPath(getTabBarPath(currentPageSelected))
      }
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
      if ((this as any)._switching || this.data.selected === index) return

      const previousSelected = this.data.selected
      const previousPath = getTabBarPath(previousSelected)
      // 源页面保持原高亮；目标页面显示后，由自己的 onShow 一次性同步高亮。
      ;(this as any)._switching = true
      prepareTabBarSwitch(path)
      wx.switchTab({
        url: path,
        success: () => undefined,
        fail: error => {
          setTabBarIndex(previousSelected)
          setPreparedTabBarPath(previousPath)
          console.error('切换底部页面失败', { path, index, error })
          wx.showToast({ title: '页面切换失败，请稍后再试', icon: 'none' })
        },
        complete: () => {
          ;(this as any)._switching = false
        },
      })
    }
  }
})
