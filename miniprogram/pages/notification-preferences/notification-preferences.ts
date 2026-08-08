import { authStore } from '../../store/auth'
import { getPreferences, updatePreferences } from '../../services/notification-preferences'

const PREF_ITEMS = [
  { key: 'instant_enabled', label: '站内即时', desc: '实时接收重要动态的站内提醒' },
  { key: 'interaction_enabled', label: '互动', desc: '点赞、评论、关注等互动通知' },
  { key: 'audit_enabled', label: '审核', desc: '内容审核状态与结果通知' },
  { key: 'governance_enabled', label: '治理', desc: '内容治理与举报处理结果通知' },
  { key: 'system_enabled', label: '系统', desc: '系统公告与账号安全提醒' },
]

Page({
  data: {
    isLoggedIn: false,
    loading: true,
    saving: false,
    items: PREF_ITEMS.map(it => ({ ...it, value: false })),
  },

  goLogin() {
    wx.reLaunch({ url: '/pages/login/login' })
  },

  onShow() {
    const isLoggedIn = authStore.getState().isLoggedIn
    if (!isLoggedIn) {
      this.setData({ isLoggedIn: false, loading: false })
      wx.showModal({
        title: '提示',
        content: '请先登录后再设置通知偏好',
        confirmText: '去登录',
        success: r => {
          if (r.confirm) wx.reLaunch({ url: '/pages/login/login' })
        },
      })
      return
    }
    this.setData({ isLoggedIn: true })
    this.load()
  },

  async load() {
    this.setData({ loading: true })
    try {
      const prefs: any = await getPreferences()
      const items = this.data.items.map((it: any) => ({ ...it, value: !!prefs[it.key] }))
      this.setData({ items })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载通知偏好失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  onToggle(e: any) {
    if (this.data.saving) {
      // 保存中禁止再次切换，防止并发请求
      this.load()
      return
    }
    const key = e.currentTarget.dataset.key
    const next = !!e.detail.value
    const items = this.data.items.map((it: any) =>
      it.key === key ? { ...it, value: next } : it
    )
    this.setData({ items })
    this.save(items)
  },

  async save(items: any[]) {
    this.setData({ saving: true })
    const payload: any = {}
    items.forEach((it: any) => {
      payload[it.key] = !!it.value
    })

    // 客户端预校验：安全通知通道（系统 / 审核 / 站内即时）不可全部关闭
    if (!payload.system_enabled && !payload.audit_enabled && !payload.instant_enabled) {
      this.setData({ saving: false })
      wx.showModal({
        title: '无法全部关闭',
        content: '安全账号通知不可全部关闭，至少需保留一个安全通道（站内即时 / 审核 / 系统）。',
        showCancel: false,
        success: () => this.load(),
      })
      return
    }

    try {
      await updatePreferences(payload)
      wx.showToast({ title: '已保存', icon: 'success' })
    } catch (e: any) {
      // 后端 422 拒绝（安全通道全关）时回滚并提示
      wx.showModal({
        title: '保存失败',
        content: e.message || '安全账号通知不可全部关闭，至少需保留一个安全通道。',
        showCancel: false,
        success: () => this.load(),
      })
    } finally {
      this.setData({ saving: false })
    }
  },
})
