import { http } from '../../services/request'
import { chooseAndUploadImage } from '../../services/upload'
import { requireLogin, guardPageLogin } from '../../utils/auth-guard'
import { cachedFetch } from '../../utils/cache'
import { campusStore } from '../../store/campus'
import type { PostImage } from '../../types'

const DRAFT_KEY = 'publish_draft'

/**
 * 分类名映射到分类色板 CSS 类名（与 post-card 组件保持一致）
 * 美食/食物/餐饮→food, 活动/事件→event, 服务→service,
 * 学习/学术→study, 失物招领/失物→lostFound, 社团→club, 其他→default
 */
function mapCategoryToClass(name: string): string {
  if (!name) return 'default'
  const n = String(name).trim()
  if (/(美食|食物|餐饮|食品|吃饭)/.test(n)) return 'food'
  if (/(活动|事件)/.test(n)) return 'event'
  if (/(服务)/.test(n)) return 'service'
  if (/(学习|学术|学习交流|课程|考研)/.test(n)) return 'study'
  if (/(失物招领|失物)/.test(n)) return 'lostFound'
  if (/(社团)/.test(n)) return 'club'
  return 'default'
}

Page({
  data: {
    categories: [] as any[],
    selectedCategoryId: 0,
    title: '',
    content: '',
    images: [] as PostImage[],
    maxImages: 9,
    titleMaxLen: 50,
    contentMaxLen: 2000,

    // 位置
    locationId: null as number | null,
    locationName: '',
    locationLat: 0,
    locationLng: 0,
    hasLocation: false,

    // 有效期
    expiryOptions: ['1天', '3天', '7天', '30天', '自定义'],
    expiryIndex: 0,
    isCustomExpiry: false,
    customDays: '',

    // 状态
    submitting: false,
    loadingCategories: true,
    uploadingImage: false,
    draftRestored: false,

    // AI 助手
    aiLoading: false,
    aiSuggestion: null as any,
    showAiSuggestion: false,
  },

  onLoad() {
    this.loadCategories()
    this.restoreDraft()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 3 })
    }
    // 发布页是纯写操作，进入前就提醒登录（避免填半天表单才发现不能提交）
    guardPageLogin('请先登录后再发布帖子')
    this.consumeSelectedLocation()
  },

  onUnload() {
    // 离开页面时自动保存草稿（仅在表单有内容时）
    this.saveDraftSilent()
  },

  // ============== 分类 ==============
  async loadCategories() {
    this.setData({ loadingCategories: true })
    try {
      // 分类为低频数据，走本地缓存 + 过期刷新（Task 10）
      const schoolCode = campusStore.getState().schoolCode
      const res: any = await cachedFetch<any>('categories', () => http.get('/categories'), { schoolCode })
      const list = Array.isArray(res) ? res : ((res && (res.items || res.data)) || [])
      const cats = list
        .filter((c: any) => c.is_active === undefined || c.is_active === true)
        .map((c: any) => ({ ...c, cls: mapCategoryToClass(c.name) }))
      let selectedCategoryId = this.data.selectedCategoryId
      if (!selectedCategoryId && cats.length > 0) {
        selectedCategoryId = cats[0].id
      }
      this.setData({ categories: cats, selectedCategoryId, loadingCategories: false })
      try {
        const settings: any = await http.get('/schools/current/settings')
        const limit = Number(settings?.image_limit)
        if (Number.isFinite(limit) && limit > 0) this.setData({ maxImages: Math.min(limit, 9) })
      } catch {
        // 学校设置不可用时沿用后端默认 9 张。
      }
    } catch (e: any) {
      this.setData({ loadingCategories: false })
      wx.showToast({ title: e.message || '分类加载失败', icon: 'none' })
    }
  },

  onCategoryTap(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id || id === this.data.selectedCategoryId) return
    this.setData({ selectedCategoryId: id })
  },

  // ============== 表单输入 ==============
  onTitleInput(e: any) {
    let value: string = (e.detail.value || '').slice(0, this.data.titleMaxLen)
    this.setData({ title: value })
  },

  onContentInput(e: any) {
    let value: string = (e.detail.value || '').slice(0, this.data.contentMaxLen)
    this.setData({ content: value })
  },

  // ============== 图片 ==============
  async onChooseImage() {
    if (this.data.uploadingImage) return
    const remain = this.data.maxImages - this.data.images.length
    if (remain <= 0) {
      wx.showToast({ title: `最多${this.data.maxImages}张图片`, icon: 'none' })
      return
    }
    this.setData({ uploadingImage: true })
    try {
      const urls = await chooseAndUploadImage(remain)
      if (urls && urls.length > 0) {
        this.setData({ images: [...this.data.images, ...urls] })
      }
    } catch (e: any) {
      const msg = (e && e.errMsg && e.errMsg.includes('cancel')) ? '' : (e.message || '图片上传失败')
      if (msg) wx.showToast({ title: msg, icon: 'none' })
    } finally {
      this.setData({ uploadingImage: false })
    }
  },

  onRemoveImage(e: any) {
    const index = Number(e.currentTarget.dataset.index)
    if (isNaN(index)) return
    const images = this.data.images.slice()
    images.splice(index, 1)
    this.setData({ images })
  },

  onPreviewImage(e: any) {
    const url = e.currentTarget.dataset.url
    if (!url || this.data.images.length === 0) return
    wx.previewImage({ current: url, urls: this.data.images.map((item: PostImage) => item.image_url) })
  },

  // ============== 位置 ==============
  onChooseLocation() {
    wx.navigateTo({ url: '/subpackages/pages/locations/locations?mode=select' })
  },

  consumeSelectedLocation() {
    try {
      const selected: any = wx.getStorageSync('selected_location')
      if (!selected) return
      wx.removeStorageSync('selected_location')
      this.setData({
        locationId: selected.id || null,
        locationName: selected.name || '',
        locationLat: Number(selected.latitude || 0),
        locationLng: Number(selected.longitude || 0),
        hasLocation: !!selected.id,
      })
    } catch {
      // ignore malformed selection
    }
  },

  onClearLocation() {
    this.setData({
      locationName: '',
      locationId: null,
      locationLat: 0,
      locationLng: 0,
      hasLocation: false,
    })
  },

  // ============== 有效期 ==============
  onExpiryChange(e: any) {
    const index = Number(e.detail.value)
    const isCustom = index === this.data.expiryOptions.length - 1
    this.setData({
      expiryIndex: index,
      isCustomExpiry: isCustom,
      customDays: isCustom ? this.data.customDays : '',
    })
  },

  onCustomDaysInput(e: any) {
    let value: string = (e.detail.value || '').replace(/[^\d]/g, '').slice(0, 4)
    this.setData({ customDays: value })
  },

  computeExpiresAt(): string | undefined {
    const DAY_MS = 86400000
    const presetDays = [1, 3, 7, 30]
    let days = 0
    if (this.data.isCustomExpiry) {
      days = parseInt(this.data.customDays, 10)
      if (!days || days <= 0) return undefined
    } else {
      days = presetDays[this.data.expiryIndex] || 1
    }
    const expires = new Date(Date.now() + days * DAY_MS)
    return expires.toISOString()
  },

  // ============== 草稿 ==============
  buildDraftData() {
    return {
      title: this.data.title,
      content: this.data.content,
      selectedCategoryId: this.data.selectedCategoryId,
      images: this.data.images,
      locationName: this.data.locationName,
      locationId: this.data.locationId,
      locationLat: this.data.locationLat,
      locationLng: this.data.locationLng,
      hasLocation: this.data.hasLocation,
      expiryIndex: this.data.expiryIndex,
      isCustomExpiry: this.data.isCustomExpiry,
      customDays: this.data.customDays,
      savedAt: Date.now(),
    }
  },

  hasFormContent(): boolean {
    return !!(
      this.data.title.trim() ||
      this.data.content.trim() ||
      this.data.images.length > 0 ||
      this.data.hasLocation
    )
  },

  saveDraftSilent() {
    if (!this.hasFormContent()) return
    try {
      wx.setStorageSync(DRAFT_KEY, this.buildDraftData())
    } catch (e) {
      // 静默
    }
  },

  restoreDraft() {
    try {
      const draft: any = wx.getStorageSync(DRAFT_KEY)
      if (!draft) return
      // 草稿超过 7 天则丢弃
      if (draft.savedAt && Date.now() - draft.savedAt > 7 * 86400000) {
        wx.removeStorageSync(DRAFT_KEY)
        return
      }
      this.setData({
        title: draft.title || '',
        content: draft.content || '',
        selectedCategoryId: draft.selectedCategoryId || this.data.selectedCategoryId,
        images: Array.isArray(draft.images)
          ? draft.images.map((item: any) => typeof item === 'string' ? { image_url: item } : item)
          : [],
        locationName: draft.locationName || '',
        locationId: draft.locationId || null,
        locationLat: draft.locationLat || draft.latitude || 0,
        locationLng: draft.locationLng || draft.longitude || 0,
        hasLocation: !!draft.hasLocation,
        expiryIndex: draft.expiryIndex || 0,
        isCustomExpiry: !!draft.isCustomExpiry,
        customDays: draft.customDays || '',
        draftRestored: true,
      })
      if (this.hasFormContent()) {
        wx.showToast({ title: '已恢复草稿', icon: 'none', duration: 1200 })
      }
    } catch (e) {
      // 静默
    }
  },

  onClearDraft() {
    wx.showModal({
      title: '清空草稿',
      content: '确定清空当前表单内容吗？',
      confirmColor: '#e53935',
      success: (res: any) => {
        if (!res.confirm) return
        try { wx.removeStorageSync(DRAFT_KEY) } catch (e) {}
        this.setData({
          title: '',
          content: '',
          images: [],
          locationName: '',
          locationId: null,
          locationLat: 0,
          locationLng: 0,
          hasLocation: false,
          expiryIndex: 0,
          isCustomExpiry: false,
          customDays: '',
          draftRestored: false,
        })
        wx.showToast({ title: '已清空', icon: 'success' })
      },
    })
  },

  // ============== 提交 ==============
  validate(): string | null {
    const title = this.data.title.trim()
    if (!title) return '请输入标题'
    if (this.data.content.trim().length < 10) return '正文至少需要 10 个字'
    if (!this.data.selectedCategoryId) return '请选择分类'
    if (this.data.isCustomExpiry) {
      const days = parseInt(this.data.customDays, 10)
      if (!days || days <= 0) return '请输入自定义有效天数'
    }
    return null
  },

  async onSubmit() {
    if (!requireLogin('登录后即可发布帖子')) return
    if (this.data.submitting) return
    const err = this.validate()
    if (err) {
      wx.showToast({ title: err, icon: 'none' })
      return
    }

    // 敏感操作二次确认
    const confirmed = await new Promise<boolean>(resolve => {
      wx.showModal({
        title: '确认发布',
        content: '确定要发布这条帖子吗？',
        confirmText: '发布',
        cancelText: '取消',
        success: (r: any) => resolve(!!r.confirm),
        fail: () => resolve(false),
      })
    })
    if (!confirmed) return

    const expiresAt = this.computeExpiresAt()

    const payload: any = {
      title: this.data.title.trim(),
      content: this.data.content.trim(),
      category_id: this.data.selectedCategoryId,
    }
    if (this.data.images.length > 0) payload.images = this.data.images
    if (this.data.hasLocation && this.data.locationId) {
      payload.location_id = this.data.locationId
    } else if (this.data.hasLocation) {
      payload.location_name = this.data.locationName
      payload.location_lat = this.data.locationLat
      payload.location_lng = this.data.locationLng
    }
    if (expiresAt) payload.expire_at = expiresAt

    this.setData({ submitting: true })
    try {
      await http.post('/posts', payload)
      // 清除草稿
      try { wx.removeStorageSync(DRAFT_KEY) } catch (e) {}
      wx.showToast({ title: '发布成功', icon: 'success', duration: 1200 })
      setTimeout(() => {
        wx.navigateBack({
          fail: () => {
            wx.switchTab({
              url: '/pages/home/home',
              fail: () => {
                wx.reLaunch({ url: '/pages/home/home' })
              },
            } as any)
          },
        })
      }, 1000)
    } catch (e: any) {
      wx.showToast({ title: e.message || '发布失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  // ============== AI 助手 ==============
  async onAiSuggest() {
    if (this.data.aiLoading) return
    const title = this.data.title.trim()
    const content = this.data.content.trim()
    if (!title && !content) {
      wx.showToast({ title: '请先输入标题或内容', icon: 'none' })
      return
    }
    this.setData({ aiLoading: true, showAiSuggestion: true, aiSuggestion: null })
    try {
      const res: any = await http.post('/posts/ai-suggest', { title, content })
      this.setData({ aiSuggestion: res || {}, aiLoading: false })
    } catch (e: any) {
      this.setData({ aiLoading: false, showAiSuggestion: false })
      wx.showToast({ title: e.message || 'AI建议获取失败', icon: 'none' })
    }
  },

  onApplyAiSuggestion() {
    const s = this.data.aiSuggestion
    if (!s || !s.suggestions) {
      wx.showToast({ title: '暂无可应用的建议', icon: 'none' })
      return
    }
    const sug = s.suggestions
    const updates: any = {}
    if (sug.title && sug.title.trim()) {
      updates.title = sug.title.trim().slice(0, this.data.titleMaxLen)
    }
    if (sug.category_id) {
      const exists = this.data.categories.find((c: any) => c.id === sug.category_id)
      if (exists) updates.selectedCategoryId = sug.category_id
    }
    if (Object.keys(updates).length === 0) {
      wx.showToast({ title: '暂无可应用的建议', icon: 'none' })
      return
    }
    this.setData(updates)
    wx.showToast({ title: '已应用建议', icon: 'success' })
  },

  onCloseAiSuggestion() {
    this.setData({ showAiSuggestion: false })
  },
})
