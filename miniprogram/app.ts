import { authStore } from './store/auth'
import { campusStore } from './store/campus'
import { BASE_URL } from './config/env'
import { http } from './services/request'

const handoffPayloads: Record<string, any> = {}

App({
  globalData: {
    userInfo: null,
    version: '1.0.0',
    baseUrl: BASE_URL,
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

    // 启动时根据 school_code 从后端加载当前学校详情（name/lat/lng/zoom 等）
    this.loadCurrentSchool()

    // 游客模式（Task 6）：未登录也能浏览首页/地图/搜索/详情/专题。
    // 需要登录的页面（我的/通知/订阅/反馈等）在各自 onShow 中守卫，写操作统一引导登录。

    // 版本更新检查（Task 7）：启动时静默检查新版本
    this.registerUpdateManager()
  },

  async loadCurrentSchool() {
    try {
      const state = campusStore.getState()
      const code = state.schoolCode
      if (!code) return
      // 已有 currentSchool 且 code 匹配则跳过
      if (state.currentSchool && state.currentSchool.code === code) return
      // 用 schools/current 接口，自动带上 X-School-Code 头
      const res: any = await http.get('/schools/current')
      const school = (res && res.school) || res
      if (school) {
        campusStore.setSchool(school)
      }
    } catch (e) {
      // 启动时静默失败：页面后续通过 onShow 再加载
      console.warn('加载当前学校详情失败', e)
    }
  },

  registerUpdateManager() {
    try {
      if (typeof wx.getUpdateManager !== 'function') return
      const updateManager = wx.getUpdateManager()
      updateManager.onUpdateReady(() => {
        wx.showModal({
          title: '更新提示',
          content: '新版本已经准备好，是否重启应用？',
          confirmText: '立即重启',
          success: r => {
            if (r.confirm) {
              updateManager.applyUpdate()
            }
          },
        })
      })
    } catch (e) {
      // 静默：更新检查失败不影响启动
      console.warn('update manager init failed', e)
    }
  },

  onShow() {
    // 游客可浏览，无需强制跳登录
  },
})
