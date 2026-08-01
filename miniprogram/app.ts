import { authStore } from './store/auth'
import { campusStore } from './store/campus'

const handoffPayloads: Record<string, any> = {}

App({
  globalData: {
    userInfo: null,
    version: '1.0.0',
    baseUrl: 'http://localhost:8000/api/v1',
  },

  onLaunch() {
    // Register agent handoff handler for AI skill navigation
    if (typeof (wx as any).onAgentHandoff === 'function') {
      ;(wx as any).onAgentHandoff((payload: { pageId: string; path: string; query: string; payload?: any }) => {
        if (payload && payload.pageId) {
          handoffPayloads[payload.pageId] = payload
        }
      })
    }

    // Register before-app-route to inject handoff query
    if (typeof (wx as any).onBeforeAppRoute === 'function') {
      ;(wx as any).onBeforeAppRoute((route: { path: string; query: string }) => {
        // handoff query is automatically injected by platform into onLoad(query)
        return route
      })
    }

    authStore.initFromStorage()
    campusStore.initFromStorage()

    const authState = authStore.getState()
    if (!authState.isLoggedIn) {
      wx.reLaunch({ url: '/pages/login/login' })
    }
  },

  onShow() {
    const authState = authStore.getState()
    if (!authState.isLoggedIn) {
      wx.reLaunch({ url: '/pages/login/login' })
    }
  },
})
