import { http } from '../../services/request'
import { formatDate } from '../../utils/format'

const TYPE_ICONS: Record<string, string> = {
  category: '🏷️',
  user: '👤',
  tag: '🔖',
  location: '📍',
}

const TYPE_LABELS: Record<string, string> = {
  category: '分类',
  user: '用户',
  tag: '标签',
  location: '地点',
}

Page({
  data: {
    activeTab: 'subscribed',

    // 已订阅列表
    subscriptions: [] as any[],
    loadingSubscriptions: false,

    // 添加订阅（分类列表）
    categories: [] as any[],
    loadingCategories: false,
    subscribedCategoryIds: [] as number[],
    togglingId: 0,
  },

  onLoad() {
    this.loadSubscriptions()
  },

  onShow() {
    // 返回页面时刷新已订阅列表（首次进入由 onLoad 处理，避免重复加载）
    if (this.data.subscriptions.length > 0) {
      this.loadSubscriptions()
    }
  },

  // ============== Tab 切换 ==============
  onTabTap(e: any) {
    const key = e.currentTarget.dataset.key
    if (!key || key === this.data.activeTab) return
    this.setData({ activeTab: key })
    if (key === 'add' && this.data.categories.length === 0) {
      this.loadCategories()
    }
  },

  // ============== 已订阅列表 ==============
  async loadSubscriptions() {
    this.setData({ loadingSubscriptions: true })
    try {
      const res: any = await http.get('/subscriptions')
      const items = (res.items || res.subscriptions || res || []) as any[]
      const list = items.map((s: any) => this.normalizeSubscription(s))
      const categoryIds = list
        .filter((s: any) => s.subscription_type === 'category')
        .map((s: any) => Number(s.target_id))
      this.setData({
        subscriptions: list,
        subscribedCategoryIds: categoryIds,
      })
      this.applySubscribedToCategories()
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载订阅失败', icon: 'none' })
    } finally {
      this.setData({ loadingSubscriptions: false })
    }
  },

  // 将订阅状态同步到分类列表项上（供模板渲染）
  applySubscribedToCategories() {
    if (this.data.categories.length === 0) return
    const ids = this.data.subscribedCategoryIds
    const list = this.data.categories.map((c: any) => ({
      ...c,
      subscribed: ids.indexOf(c.id) !== -1,
    }))
    this.setData({ categories: list })
  },

  normalizeSubscription(s: any): any {
    if (!s) return s
    const type = s.subscription_type || s.type || 'category'
    return {
      ...s,
      subscription_type: type,
      type_icon: TYPE_ICONS[type] || '🔔',
      type_label: TYPE_LABELS[type] || type,
      target_name: s.target_name || s.name || '未知',
      created_at_text: s.created_at ? formatDate(s.created_at, 'datetime') : '',
    }
  },

  onCancelSubscription(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.showModal({
      title: '提示',
      content: '确定要取消该订阅吗？',
      success: async r => {
        if (!r.confirm) return
        try {
          await http.delete(`/subscriptions/${id}`)
          wx.showToast({ title: '已取消', icon: 'success' })
          const list = this.data.subscriptions.filter((s: any) => s.id !== id)
          const categoryIds = list
            .filter((s: any) => s.subscription_type === 'category')
            .map((s: any) => Number(s.target_id))
          this.setData({ subscriptions: list, subscribedCategoryIds: categoryIds })
          this.applySubscribedToCategories()
        } catch (err: any) {
          wx.showToast({ title: err.message || '取消失败', icon: 'none' })
        }
      },
    })
  },

  // ============== 添加订阅（分类列表） ==============
  async loadCategories() {
    this.setData({ loadingCategories: true })
    try {
      const res: any = await http.get('/categories')
      const items = (res.items || res.categories || res || []) as any[]
      const ids = this.data.subscribedCategoryIds
      const list = items.map((c: any) => ({
        ...c,
        id: Number(c.id),
        name: c.name || '未命名分类',
        description: c.description || '',
        icon: c.icon || '🏷️',
        subscribed: ids.indexOf(Number(c.id)) !== -1,
      }))
      this.setData({ categories: list })
      // 若已订阅列表未加载过，补一次以保证订阅态准确
      if (this.data.subscriptions.length === 0) {
        await this.loadSubscriptions()
      }
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载分类失败', icon: 'none' })
    } finally {
      this.setData({ loadingCategories: false })
    }
  },

  onToggleCategory(e: any) {
    const id = Number(e.currentTarget.dataset.id)
    if (!id || this.data.togglingId === id) return
    const category = this.data.categories.find((c: any) => c.id === id)
    if (!category) return
    const subscribed = !!category.subscribed
    this.setData({ togglingId: id })

    if (subscribed) {
      // 取消订阅：找到对应的订阅记录 id
      const sub = this.data.subscriptions.find(
        (s: any) => s.subscription_type === 'category' && Number(s.target_id) === id
      )
      if (!sub) {
        this.setData({ togglingId: 0 })
        return
      }
      http
        .delete(`/subscriptions/${sub.id}`)
        .then(() => {
          wx.showToast({ title: '已取消订阅', icon: 'success' })
          const list = this.data.subscriptions.filter((s: any) => s.id !== sub.id)
          const categoryIds = list
            .filter((s: any) => s.subscription_type === 'category')
            .map((s: any) => Number(s.target_id))
          this.setData({ subscriptions: list, subscribedCategoryIds: categoryIds })
          this.applySubscribedToCategories()
        })
        .catch((err: any) => {
          wx.showToast({ title: err.message || '取消失败', icon: 'none' })
        })
        .finally(() => {
          this.setData({ togglingId: 0 })
        })
    } else {
      // 添加订阅
      http
        .post('/subscriptions', { type: 'category', target_id: id })
        .then((res: any) => {
          wx.showToast({ title: '订阅成功', icon: 'success' })
          const newSub = this.normalizeSubscription(res.subscription || res || {
            id: res.id,
            subscription_type: 'category',
            target_id: id,
            target_name: category.name,
            created_at: new Date().toISOString(),
          })
          const list = [...this.data.subscriptions, newSub]
          const categoryIds = list
            .filter((s: any) => s.subscription_type === 'category')
            .map((s: any) => Number(s.target_id))
          this.setData({ subscriptions: list, subscribedCategoryIds: categoryIds })
          this.applySubscribedToCategories()
        })
        .catch((err: any) => {
          wx.showToast({ title: err.message || '订阅失败', icon: 'none' })
        })
        .finally(() => {
          this.setData({ togglingId: 0 })
        })
    }
  },

  onPullDownRefresh() {
    const tasks: Promise<any>[] = [this.loadSubscriptions()]
    if (this.data.activeTab === 'add') {
      tasks.push(this.loadCategories())
    }
    Promise.all(tasks).finally(() => wx.stopPullDownRefresh())
  },
})
