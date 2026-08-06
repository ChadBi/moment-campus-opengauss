import { authStore } from '../store/auth'

/**
 * 游客模式登录引导（Task 6）
 * 未登录用户点击写操作时调用，弹出引导而非直接 reLaunch 打断浏览。
 * @param hint 引导文案
 * @returns 是否已登录（true 表示可直接继续操作）
 */
export function requireLogin(hint = '该操作需要登录后才能使用'): boolean {
  if (authStore.getState().isLoggedIn) return true
  wx.showModal({
    title: '提示',
    content: hint,
    confirmText: '去登录',
    cancelText: '再看看',
    success: r => {
      if (r.confirm) {
        wx.navigateTo({ url: '/pages/login/login' })
      }
    },
  })
  return false
}

/**
 * 游客浏览入口守卫（Task 6）
 * 需要登录的页面（我的/通知/订阅/反馈/通知偏好等）在 onShow 中调用。
 * 未登录时提示并用 navigateTo 跳登录，保留返回上下文。
 */
export function guardPageLogin(hint = '请先登录后使用'): boolean {
  if (authStore.getState().isLoggedIn) return true
  wx.showModal({
    title: '提示',
    content: hint,
    confirmText: '去登录',
    cancelText: '取消',
    success: r => {
      if (r.confirm) {
        wx.navigateTo({ url: '/pages/login/login' })
      }
    },
  })
  return false
}