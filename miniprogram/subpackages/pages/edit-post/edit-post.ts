import { http } from '../../../services/request'
import { chooseAndUploadImage } from '../../../services/upload'
import type { PostImage } from '../../../types'

const DAY_MS = 86400000
const PRESET_DAYS = [1, 3, 7, 30]

/**
 * 分类名映射到分类色板 CSS 类名（与 publish/post-card 保持一致）
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
    postId: 0,
    loading: true,
    loadError: '',

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
    uploadingImage: false,
    loadingCategories: true,

    // 原帖状态（用于展示回审提示）
    originalStatus: '',
  },

  onLoad(options: any) {
    const id = Number(options && options.id)
    if (!id) {
      this.setData({ loading: false, loadError: '参数错误' })
      wx.showToast({ title: '参数错误', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 800)
      return
    }
    this.setData({ postId: id })
    this.loadCategories()
    this.loadPost()
  },

  // ============== 加载分类 ==============
  async loadCategories() {
    this.setData({ loadingCategories: true })
    try {
      const res: any = await http.get('/categories')
      const list = Array.isArray(res) ? res : ((res && (res.items || res.data)) || [])
      const cats = Array.isArray(list)
        ? list
            .filter((c: any) => c.is_active === undefined || c.is_active === true)
            .map((c: any) => ({ ...c, cls: mapCategoryToClass(c.name) }))
        : []
      this.setData({ categories: cats, loadingCategories: false })
    } catch (e: any) {
      this.setData({ loadingCategories: false })
      wx.showToast({ title: e.message || '分类加载失败', icon: 'none' })
    }
  },

  // ============== 加载帖子详情 ==============
  async loadPost() {
    this.setData({ loading: true, loadError: '' })
    try {
      const res: any = await http.get(`/posts/${this.data.postId}`)
      this.prefillForm(res || {})
    } catch (e: any) {
      this.setData({ loading: false, loadError: e.message || '加载失败' })
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  prefillForm(post: any) {
    const title: string = post.title || ''
    const content: string = post.content || ''
    const selectedCategoryId: number = post.category_id || 0

    // 图片：PostResponse.images 为 [{image_url, thumbnail_url, sort_order}]
    const rawImages = Array.isArray(post.images) ? post.images : []
    const images: PostImage[] = rawImages
      .map((img: any) => typeof img === 'string' ? { image_url: img } : {
        image_url: img.image_url || img.url || '',
        thumbnail_url: img.thumbnail_url,
      })
      .filter((item: PostImage) => !!item.image_url)

    // 位置：PostResponse.location 为 {id, name, latitude, longitude, ...}
    const loc = post.location
    const hasLocation = !!(loc && loc.id)
    const locationId = hasLocation ? loc.id : null
    const locationName = hasLocation ? (loc.name || '已选位置') : ''
    const locationLat = hasLocation ? (loc.latitude || 0) : 0
    const locationLng = hasLocation ? (loc.longitude || 0) : 0

    // 有效期：根据 created_at → expire_at 推算原始天数
    const { expiryIndex, isCustomExpiry, customDays } = this.computeExpiryFromPost(post)

    this.setData({
      title,
      content,
      selectedCategoryId,
      images,
      locationId,
      locationName,
      locationLat,
      locationLng,
      hasLocation,
      expiryIndex,
      isCustomExpiry,
      customDays,
      originalStatus: post.status || '',
      loading: false,
    })
  },

  computeExpiryFromPost(post: any) {
    if (!post.expire_at) {
      return { expiryIndex: 0, isCustomExpiry: false, customDays: '' }
    }
    const start = post.created_at ? new Date(post.created_at).getTime() : Date.now()
    const end = new Date(post.expire_at).getTime()
    let days = Math.round((end - start) / DAY_MS)
    if (!days || days <= 0) days = 1
    const presetIdx = PRESET_DAYS.indexOf(days)
    if (presetIdx >= 0) {
      return { expiryIndex: presetIdx, isCustomExpiry: false, customDays: '' }
    }
    return { expiryIndex: this.data.expiryOptions.length - 1, isCustomExpiry: true, customDays: String(days) }
  },

  // ============== 分类 ==============
  onCategoryTap(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id || id === this.data.selectedCategoryId) return
    this.setData({ selectedCategoryId: id })
  },

  // ============== 表单输入 ==============
  onTitleInput(e: any) {
    const value: string = (e.detail.value || '').slice(0, this.data.titleMaxLen)
    this.setData({ title: value })
  },

  onContentInput(e: any) {
    const value: string = (e.detail.value || '').slice(0, this.data.contentMaxLen)
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

  onShow() {
    try {
      const selected: any = wx.getStorageSync('selected_location')
      if (!selected) return
      wx.removeStorageSync('selected_location')
      this.setData({ locationId: selected.id || null, locationName: selected.name || '', locationLat: Number(selected.latitude || 0), locationLng: Number(selected.longitude || 0), hasLocation: !!selected.id })
    } catch {
      // ignore malformed selection
    }
  },

  onClearLocation() {
    this.setData({
      locationName: '',
      locationLat: 0,
      locationLng: 0,
      hasLocation: false,
      locationId: null,
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
    const value: string = (e.detail.value || '').replace(/[^\d]/g, '').slice(0, 4)
    this.setData({ customDays: value })
  },

  computeExpiresAt(): string | undefined {
    let days = 0
    if (this.data.isCustomExpiry) {
      days = parseInt(this.data.customDays, 10)
      if (!days || days <= 0) return undefined
    } else {
      days = PRESET_DAYS[this.data.expiryIndex] || 1
    }
    const expires = new Date(Date.now() + days * DAY_MS)
    return expires.toISOString()
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

    // 已发布帖子实质修改会触发回审，提示用户
    if (this.data.originalStatus === 'published') {
      const confirmed = await new Promise<boolean>(resolve => {
        wx.showModal({
          title: '修改提示',
          content: '修改已发布帖子后将重新进入审核，确认继续？',
          confirmText: '继续',
          cancelText: '取消',
          success: (r: any) => resolve(!!r.confirm),
          fail: () => resolve(false),
        })
      })
      if (!confirmed) return
    }

    this.setData({ submitting: true })
    try {
      let locationId = this.data.locationId

      const expiresAt = this.computeExpiresAt()
      const payload: any = {
        title: this.data.title.trim(),
        content: this.data.content.trim(),
        category_id: this.data.selectedCategoryId,
      }
      payload.images = this.data.images
      if (this.data.hasLocation && locationId) {
        payload.location_id = locationId
      } else if (this.data.hasLocation) {
        payload.location_name = this.data.locationName
        payload.location_lat = this.data.locationLat
        payload.location_lng = this.data.locationLng
      } else if (!this.data.hasLocation) {
        payload.location_id = null
      }
      if (expiresAt) payload.expire_at = expiresAt

      await http.put(`/posts/${this.data.postId}`, payload)
      wx.showToast({ title: '修改成功', icon: 'success', duration: 1200 })
      setTimeout(() => {
        wx.navigateBack({
          fail: () => {
            wx.switchTab({ url: '/pages/home/home' } as any)
          },
        })
      }, 1000)
    } catch (e: any) {
      wx.showToast({ title: e.message || '修改失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },
})
