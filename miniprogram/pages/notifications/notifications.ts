import { http } from '../../services/request'
import { formatDate } from '../../utils/format'
import { listNotifications, markAsRead, markAllAsRead, deleteNotification, getUnreadCount } from '../../services/notifications'

const TYPE_TABS = [
  { key: 'all', label: '全部' },
  { key: 'comment', label: '评论' },
  { key: 'like', label: '点赞' },
  { key: 'validation', label: '验证' },
  { key: 'report', label: '举报' },
  { key: 'system', label: '系统' },
]

const TYPE_LABELS: Record<string, string> = {
  comment: '评论',
  like: '点赞',
  validation: '验证',
  report: '举报',
  system: '系统',
}

const TYPE_ICONS: Record<string, string> = {
  comment: '💬',
  like: '👍',
  validation: '✅',
  report: '⚠️',
  system: '📢',
}

Page({
  data: {
    typeTabs: TYPE_TABS,
    activeType: 'all',

    notifications: [] as any[],
    page: 1,
    pageSize: 20,
    hasMore: true,
    loading: false,
    loadingMore: false,

    unreadCount: 0,
    markingAllRead: false,
  },

  onLoad() {
    this.refreshNotifications()
  },

  onShow() {
    this.loadUnreadCount()
  },

  // ============== 通知列表 ==============
  async refreshNotifications() {
    this.setData({ page: 1, hasMore: true, notifications: [] })
    await this.loadNotifications()
  },

  async loadNotifications() {
    if (this.data.loading || this.data.loadingMore) return
    const isFirstPage = this.data.page === 1
    this.setData({ loading: isFirstPage, loadingMore: !isFirstPage })
    try {
      const { activeType, page, pageSize } = this.data
      const params: any = { page, page_size: pageSize }
      if (activeType && activeType !== 'all') {
        params.type = activeType
      }
      const res: any = await listNotifications(params)
      const items = (res.items || res.notifications || []) as any[]
      const list = items.map((n: any) => this.normalizeNotification(n))
      this.setData({
        notifications: [...this.data.notifications, ...list],
        hasMore: res.has_more !== undefined ? !!res.has_more : list.length >= pageSize,
        page: page + 1,
        unreadCount: res.unread_count !== undefined ? Number(res.unread_count) : this.data.unreadCount,
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载通知失败', icon: 'none' })
    } finally {
      this.setData({ loading: false, loadingMore: false })
    }
  },

  normalizeNotification(n: any): any {
    if (!n) return n
    return {
      ...n,
      type_label: TYPE_LABELS[n.type] || n.type,
      type_icon: TYPE_ICONS[n.type] || '🔔',
      created_at_text: formatDate(n.created_at),
    }
  },

  async loadUnreadCount() {
    try {
      const res: any = await getUnreadCount()
      this.setData({ unreadCount: Number(res.count || 0) })
    } catch (e) {
      // 静默
    }
  },

  // ============== 类型筛选 ==============
  onTypeTabTap(e: any) {
    const key = e.currentTarget.dataset.key
    if (!key || key === this.data.activeType) return
    this.setData({ activeType: key, page: 1, hasMore: true, notifications: [] })
    this.loadNotifications()
  },

  // ============== 单条标记已读 ==============
  async onNotificationTap(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    const item = this.data.notifications.find((n: any) => n.id === id)
    if (item && !item.is_read) {
      // 先乐观更新
      this.updateItemInList(id, { is_read: true })
      this.setData({ unreadCount: Math.max(0, this.data.unreadCount - 1) })
      try {
        await markAsRead(Number(id))
      } catch (err: any) {
        // 失败回滚
        this.updateItemInList(id, { is_read: false })
        this.setData({ unreadCount: this.data.unreadCount + 1 })
      }
    }

    // 跳转相关帖子
    if (item && item.related_post_id) {
      wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${item.related_post_id}` })
    }
  },

  // ============== 全部标记已读 ==============
  async onMarkAllRead() {
    if (this.data.markingAllRead) return
    if (this.data.notifications.length === 0) {
      wx.showToast({ title: '暂无通知', icon: 'none' })
      return
    }
    this.setData({ markingAllRead: true })
    try {
      await markAllAsRead()
      const list = this.data.notifications.map((n: any) => ({ ...n, is_read: true }))
      this.setData({ notifications: list, unreadCount: 0 })
      wx.showToast({ title: '已全部标记为已读', icon: 'success' })
    } catch (e: any) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    } finally {
      this.setData({ markingAllRead: false })
    }
  },

  // ============== 删除通知 ==============
  onDeleteNotification(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.showModal({
      title: '提示',
      content: '确定要删除该通知吗？',
      success: async r => {
        if (!r.confirm) return
        try {
          await deleteNotification(Number(id))
          const list = this.data.notifications.filter((n: any) => n.id !== id)
          this.setData({ notifications: list })
          wx.showToast({ title: '已删除', icon: 'success' })
        } catch (err: any) {
          wx.showToast({ title: err.message || '删除失败', icon: 'none' })
        }
      },
    })
  },

  // ============== 工具方法 ==============
  updateItemInList(id: number, patch: any) {
    const list = this.data.notifications.map((n: any) =>
      n.id === id ? { ...n, ...patch } : n
    )
    this.setData({ notifications: list })
  },

  onPullDownRefresh() {
    this.refreshNotifications().finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading && !this.data.loadingMore) {
      this.loadNotifications()
    }
  },
})
