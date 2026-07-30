import { http } from '../../services/request'
import { chooseAndUploadImage } from '../../services/upload'
import { resolveImageUrl } from '../../services/request'

const DRAFT_KEY = 'publish_draft'

Page({
  data: {
    categories: [] as any[],
    selectedCategoryId: 0,
    title: '',
    content: '',
    images: [] as string[],
    maxImages: 5,
    titleMaxLen: 50,
    contentMaxLen: 2000,

    // 位置
    locationName: '',
    latitude: 0,
    longitude: 0,
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

  onUnload() {
    // 离开页面时自动保存草稿（仅在表单有内容时）
    this.saveDraftSilent()
  },

  // ============== 分类 ==============
  async loadCategories() {
    this.setData({ loadingCategories: true })
    try {
      const res: any = await http.get('/categories')
      const list = (res && (res.categories || res.items || res.data)) || []
      const cats = list.filter((c: any) => c.is_active === undefined || c.is_active === true)
      let selectedCategoryId = this.data.selectedCategoryId
      if (!selectedCategoryId && cats.length > 0) {
        selectedCategoryId = cats[0].id
      }
      this.setData({ categories: cats, selectedCategoryId, loadingCategories: false })
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
        const normalized = urls.map((u: string) => resolveImageUrl(u))
        this.setData({ images: [...this.data.images, ...normalized] })
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
    wx.previewImage({ current: url, urls: this.data.images })
  },

  // ============== 位置 ==============
  onChooseLocation() {
    wx.chooseLocation({
      success: (res: any) => {
        this.setData({
          locationName: res.name || res.address || '已选位置',
          latitude: res.latitude,
          longitude: res.longitude,
          hasLocation: true,
        })
      },
      fail: (err: any) => {
        if (err && err.errMsg && err.errMsg.includes('cancel')) return
        wx.showToast({ title: '位置选择失败', icon: 'none' })
      },
    })
  },

  onClearLocation() {
    this.setData({
      locationName: '',
      latitude: 0,
      longitude: 0,
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
      latitude: this.data.latitude,
      longitude: this.data.longitude,
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
        images: Array.isArray(draft.images) ? draft.images : [],
        locationName: draft.locationName || '',
        latitude: draft.latitude || 0,
        longitude: draft.longitude || 0,
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
          latitude: 0,
          longitude: 0,
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
    if (!this.data.selectedCategoryId) return '请选择分类'
    if (this.data.isCustomExpiry) {
      const days = parseInt(this.data.customDays, 10)
      if (!days || days <= 0) return '请输入自定义有效天数'
    }
    return null
  },

  async onSubmit() {
    if (this.data.submitting) return
    const err = this.validate()
    if (err) {
      wx.showToast({ title: err, icon: 'none' })
      return
    }
    const expiresAt = this.computeExpiresAt()

    const payload: any = {
      title: this.data.title.trim(),
      content: this.data.content.trim(),
      category_id: this.data.selectedCategoryId,
    }
    if (this.data.images.length > 0) payload.images = this.data.images
    if (this.data.hasLocation) {
      payload.location_name = this.data.locationName
      payload.latitude = this.data.latitude
      payload.longitude = this.data.longitude
    }
    if (expiresAt) payload.expires_at = expiresAt

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
