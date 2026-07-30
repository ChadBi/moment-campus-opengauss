import { authStore } from './store/auth'
import { campusStore } from './store/campus'

App({
  globalData: {
    userInfo: null,
    version: '1.0.0',
    baseUrl: 'http://localhost:8000/api/v1',
  },

  onLaunch() {
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
