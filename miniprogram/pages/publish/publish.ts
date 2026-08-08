import { chooseAndUploadImage } from '../../services/upload'
import { requireLogin, guardPageLogin } from '../../utils/auth-guard'
import { cachedFetch } from '../../utils/cache'
import { campusStore } from '../../store/campus'
import { authStore } from '../../store/auth'
import { createPost, listCategories, suggestPost } from '../../services/posts'
import { getSchoolSettings } from '../../services/schools'
import { navigateToTab, syncTabBarForPage } from '../../utils/tab-navigation'
import type { Category, PostImage } from '../../types'

const DRAFT_KEY_PREFIX = 'publish_draft'

function getDraftKey(): string {
  const schoolCode = campusStore.getState().schoolCode || 'jiangnan'
  const userId = authStore.getState().user?.id || 'guest'
  return `${DRAFT_KEY_PREFIX}:${schoolCode}:${userId}`
}

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
    categories: [] as Array<Category & { cls: string }>,
    selectedCategoryId: 0,
    title: '',
    content: '',
    images: [] as PostImage[],
    maxImages: 9,
    titleMaxLen: 100,
    contentMaxLen: 5000,
    isAnonymous: false,
    allowAnonymous: true,
    contactInfo: '',
    lostType: '' as '' | 'lost' | 'found',
    lostTypeVisible: false,
    lostTypeOptions: ['请选择', '丢失', '拾获'],
    lostTypeIndex: 0,

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
    syncTabBarForPage(3)
    this.loadCategories()
    this.restoreDraft()
  },

  onShow() {
    syncTabBarForPage(3)
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
      const list = await cachedFetch<Category[]>('categories', () => listCategories(), { schoolCode })
      const cats = list
        .filter(c => c.is_active !== false)
        .map(c => ({ ...c, cls: mapCategoryToClass(c.name) }))
      let selectedCategoryId = this.data.selectedCategoryId
      if (!selectedCategoryId && cats.length > 0) {
        selectedCategoryId = cats[0].id
      }
      this.setData({ categories: cats, selectedCategoryId, loadingCategories: false })
      this.updateLostTypeVisibility(selectedCategoryId, cats)
      try {
        const settings = await cachedFetch<any>('school-settings', () => getSchoolSettings(), { schoolCode })
        const limit = Number(settings?.image_limit)
        this.setData({
          allowAnonymous: settings?.allow_anonymous !== false,
          maxImages: Number.isFinite(limit) && limit > 0 ? Math.min(limit, 9) : 9,
        })
      } catch {
        // 学校设置不可用时沿用安全默认值。
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
    this.updateLostTypeVisibility(id)
  },

  updateLostTypeVisibility(categoryId: number, categories = this.data.categories) {
    const category = categories.find(item => item.id === categoryId)
    const visible = category?.code === 'lost_found' || /失物/.test(category?.name || '')
    this.setData({ lostTypeVisible: visible })
    if (!visible && this.data.lostType) this.setData({ lostType: '' })
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

  onContactInput(e: any) {
    this.setData({ contactInfo: String(e.detail.value || '').slice(0, 255) })
  },

  onAnonymousChange(e: any) {
    if (!this.data.allowAnonymous) return
    this.setData({ isAnonymous: !!e.detail.value })
  },

  onLostTypeChange(e: any) {
    const index = Number(e.detail.value)
    this.setData({
      lostTypeIndex: index,
      lostType: index === 1 ? 'lost' : (index === 2 ? 'found' : ''),
    })
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
      isAnonymous: this.data.isAnonymous,
      contactInfo: this.data.contactInfo,
      lostType: this.data.lostType,
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
      wx.setStorageSync(getDraftKey(), this.buildDraftData())
    } catch (e) {
      // 静默
    }
  },

  restoreDraft() {
    try {
      const draft: any = wx.getStorageSync(getDraftKey())
      if (!draft) return
      // 草稿超过 7 天则丢弃
      if (draft.savedAt && Date.now() - draft.savedAt > 7 * 86400000) {
        wx.removeStorageSync(getDraftKey())
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
        isAnonymous: this.data.allowAnonymous && !!draft.isAnonymous,
        contactInfo: draft.contactInfo || '',
        lostType: draft.lostType || '',
        lostTypeIndex: draft.lostType === 'lost' ? 1 : (draft.lostType === 'found' ? 2 : 0),
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
        try { wx.removeStorageSync(getDraftKey()) } catch (e) {}
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
          isAnonymous: false,
          contactInfo: '',
          lostType: '',
          lostTypeIndex: 0,
          draftRestored: false,
        })
        wx.showToast({ title: '已清空', icon: 'success' })
      },
    })
  },

  // ============== 提交 ==============
  validate(): string | null {
    const title = this.data.title.trim()
    const content = this.data.content.trim()
    if (!title) return '请输入标题'
    if (title.length < 5 || title.length > this.data.titleMaxLen) return '标题长度必须在 5-100 字符之间'
    if (!content) return '请输入正文'
    if (content.length < 10 || content.length > this.data.contentMaxLen) return '正文长度必须在 10-5000 字符之间'
    if (!this.data.selectedCategoryId) return '请选择分类'
    if (this.data.isCustomExpiry) {
      const days = parseInt(this.data.customDays, 10)
      if (!days || days <= 0) return '请输入自定义有效天数'
    }
    if (this.isLostFoundCategory() && !this.data.lostType) return '请选择失物类型'
    return null
  },

  isLostFoundCategory(): boolean {
    const category = this.data.categories.find(item => item.id === this.data.selectedCategoryId)
    return category?.code === 'lost_found' || /失物/.test(category?.name || '')
  },

  buildPostPayload(status: 'draft' | 'pending') {
    const payload: any = {
      title: this.data.title.trim(),
      content: this.data.content.trim(),
      category_id: this.data.selectedCategoryId,
      is_anonymous: this.data.allowAnonymous && this.data.isAnonymous,
      contact_info: this.data.contactInfo.trim() || undefined,
      lost_type: this.isLostFoundCategory() ? (this.data.lostType || undefined) : undefined,
      images: this.data.images.length > 0 ? this.data.images : undefined,
      expire_at: this.computeExpiresAt(),
      status,
    }
    if (this.data.hasLocation && this.data.locationId) {
      payload.location_id = this.data.locationId
    } else if (this.data.hasLocation) {
      payload.location_name = this.data.locationName
      payload.location_lat = this.data.locationLat
      payload.location_lng = this.data.locationLng
    }
    return payload
  },

  async onSaveDraft() {
    await this.submitPost('draft')
  },

  async onSubmit() {
    await this.submitPost('pending')
  },

  async submitPost(status: 'draft' | 'pending') {
    if (!requireLogin(status === 'draft' ? '登录后即可保存草稿' : '登录后即可提交审核')) return
    if (this.data.submitting) return
    const err = this.validate()
    if (err) {
      wx.showToast({ title: err, icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    try {
      await createPost(this.buildPostPayload(status))
      try { wx.removeStorageSync(getDraftKey()) } catch (e) {}
      wx.showToast({
        title: status === 'draft' ? '草稿已保存' : '已提交审核',
        icon: 'success',
        duration: 1200,
      })
      setTimeout(() => {
        wx.navigateBack({
          fail: () => navigateToTab('/pages/home/home'),
        })
      }, 1000)
    } catch (e: any) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
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
      const res = await suggestPost(title, content)
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
    const optimizedTitle = sug.optimized_title || sug.title
    if (optimizedTitle && optimizedTitle.trim()) {
      updates.title = optimizedTitle.trim().slice(0, this.data.titleMaxLen)
    }
    if (sug.optimized_content && sug.optimized_content.trim()) {
      updates.content = sug.optimized_content.trim().slice(0, this.data.contentMaxLen)
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
    if (updates.selectedCategoryId) this.updateLostTypeVisibility(updates.selectedCategoryId)
    wx.showToast({ title: '已应用标题/正文建议', icon: 'success' })
  },

  onCloseAiSuggestion() {
    this.setData({ showAiSuggestion: false })
  },
})
