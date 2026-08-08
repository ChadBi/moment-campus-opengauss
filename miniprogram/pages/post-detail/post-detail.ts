import { getPost } from '../../services/posts'
import { formatDate, formatCount, getRemainingTime } from '../../utils/format'
import {
  likePost,
  createComment,
  validatePost,
  getValidationStats,
  reportPost,
  listComments,
} from '../../services/interactions'
import { requireLogin } from '../../utils/auth-guard'
import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { canWriteInCurrentSchool } from '../../utils/campus-permission'
import { normalizeComment } from '../../services/normalize'
import type { PostImage } from '../../types'

// 举报类型与后端 ReportType 枚举对齐（backend/app/schemas/enums.py 六类）
const REPORT_REASONS = [
  { label: '垃圾信息', value: 'spam' },
  { label: '滥用信息', value: 'abuse' },
  { label: '骚扰言论', value: 'harassment' },
  { label: '虚假信息', value: 'false_info' },
  { label: '信息过期', value: 'expired_info' },
  { label: '其他', value: 'other' },
]

/**
 * 分类名映射到分类色板 CSS 类名（与 post-card 组件一致）
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
    post: null as any,
    images: [] as PostImage[],
    swiperCurrent: 0,

    // 互动
    isLiked: false,
    likesCount: 0,
    commentsCount: 0,

    // 验证统计
    confirmationCount: 0,
    refutationCount: 0,
    totalValidationCount: 0,
    validityStatus: 'valid',
    userValidationType: '' as string,

    // 评论
    comments: [] as any[],
    commentPage: 1,
    commentHasMore: false,
    commentLoading: false,
    commentInput: '',
    submittingComment: false,
    replyingTo: null as any,

    // 倒计时
    remainingTime: '',
    countdownTimer: null as any,

    // 举报
    reportVisible: false,
    reportReason: '',
    reportType: 'other',
    reportReasons: REPORT_REASONS,
    submittingReport: false,

    // 当前学校写权限（注册学校可写，其他学校只读）
    canWrite: false,

    // 分类色板类名
    categoryClass: 'default',
  },

  onLoad(options: any) {
    ;(this as any)._unsubscribeAuth = authStore.subscribe(state => {
      this.setData({
        canWrite: canWriteInCurrentSchool(state.user, campusStore.getState().currentSchool?.id),
      })
    })
    ;(this as any)._unsubscribeCampus = campusStore.subscribe(state => {
      this.setData({
        canWrite: canWriteInCurrentSchool(authStore.getState().user, state.currentSchool?.id),
      })
    })
    const id = Number(options && options.id)
    if (!id) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 800)
      return
    }
    this.setData({ postId: id })
    this.loadAll()
  },

  onUnload() {
    const unsubscribeAuth = (this as any)._unsubscribeAuth
    const unsubscribeCampus = (this as any)._unsubscribeCampus
    if (unsubscribeAuth) unsubscribeAuth()
    if (unsubscribeCampus) unsubscribeCampus()
    if (this.data.countdownTimer) {
      clearInterval(this.data.countdownTimer)
    }
  },

  requireWritable(message: string): boolean {
    if (!requireLogin(message)) return false
    if (!this.data.canWrite) {
      wx.showToast({ title: '当前学校仅支持浏览，请切回注册学校后再操作', icon: 'none' })
      return false
    }
    return true
  },

  async loadAll() {
    this.setData({ loading: true })
    try {
      await Promise.all([
        this.loadPost(),
        this.loadValidationStats(),
        this.loadComments(1),
      ])
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  // ============== 加载详情 ==============
  async loadPost() {
    const post = await getPost(this.data.postId)
    const images = post.images || []
    const location: any = post.location || {}
    const locationParts: string[] = []
    if (location.name) locationParts.push(location.name)
    if (location.building) locationParts.push(location.building)
    if (location.floor) locationParts.push(`${location.floor} 层`)
    const normalized = {
      ...post,
      location_name: post.location_name || location.name || '',
      location_address: locationParts.join(' · '),
      author_nickname: post.author?.nickname || '匿名用户',
      author_avatar: post.author?.avatar_url || '',
      created_at_text: formatDate(post.created_at),
      like_count_text: formatCount(post.like_count || 0),
      comment_count_text: formatCount(post.comment_count || 0),
      valid_count_text: formatCount(post.valid_count || 0),
      view_count_text: formatCount(post.view_count || 0),
    }
    const categoryName = post.category?.name || ''
    this.setData({
      post: normalized,
      images,
      isLiked: !!post.is_liked,
      likesCount: post.like_count || 0,
      commentsCount: post.comment_count || 0,
      categoryClass: mapCategoryToClass(categoryName),
    })
    this.startCountdown(post.expire_at || undefined)
  },

  // ============== 验证统计 ==============
  async loadValidationStats() {
    try {
      const res: any = await getValidationStats(this.data.postId)
      this.setData({
        confirmationCount: res.confirmation_count || res.valid_count || 0,
        refutationCount: res.refutation_count || res.invalid_count || 0,
        totalValidationCount: res.total_count || res.total_validation_count || 0,
        validityStatus: res.validity_status || 'valid',
        userValidationType: res.user_validation_type || res.my_validation_type || '',
      })
    } catch {
      // 静默
    }
  },

  // ============== 评论 ==============
  async loadComments(page: number) {
    if (this.data.commentLoading) return
    this.setData({ commentLoading: true })
    try {
      const res: any = await listComments(this.data.postId, page)
      const list = (res?.items || []).map((c: any) => ({
        ...normalizeComment(c),
        author_nickname: c.author?.nickname || '匿名',
        author_avatar: c.author?.avatar_url || '',
        is_verified: !!c.author?.is_verified,
        created_at_text: formatDate(c.created_at),
      }))
      this.setData({
        comments: page === 1 ? list : [...this.data.comments, ...list],
        commentPage: page,
        commentHasMore: !!(res && res.has_more),
      })
    } catch (e: any) {
      // 评论加载失败不阻断主流程
    } finally {
      this.setData({ commentLoading: false })
    }
  },

  onCommentInput(e: any) {
    this.setData({ commentInput: e.detail.value || '' })
  },

  // 点击回复某条评论
  onReplyComment(e: any) {
    const id = e.currentTarget.dataset.id
    const nickname = e.currentTarget.dataset.nickname
    const userId = Number(e.currentTarget.dataset.userId) || undefined
    this.setData({
      replyingTo: { id, nickname, userId },
      commentInput: `@${nickname} `,
    })
  },

  cancelReply() {
    this.setData({ replyingTo: null, commentInput: '' })
  },

  async onSubmitComment() {
    if (!this.requireWritable('登录后即可发表评论')) return
    const content = (this.data.commentInput || '').trim()
    if (!content) {
      wx.showToast({ title: '请输入评论内容', icon: 'none' })
      return
    }
    if (this.data.submittingComment) return
    this.setData({ submittingComment: true })
    try {
      const parentId = this.data.replyingTo ? this.data.replyingTo.id : undefined
      const replyToUserId = this.data.replyingTo ? this.data.replyingTo.userId : undefined
      const res: any = await createComment(this.data.postId, content, parentId, replyToUserId)
      const newComment = {
        ...(res || {}),
        author_nickname: res?.author?.nickname || '匿名',
        author_avatar: res?.author?.avatar_url || '',
        is_verified: !!res?.author?.is_verified,
        created_at_text: formatDate((res && res.created_at) || new Date()),
      }
      this.setData({
        comments: [newComment, ...this.data.comments],
        commentsCount: this.data.commentsCount + 1,
        commentInput: '',
        replyingTo: null,
      })
      // 同步帖子计数显示
      if (this.data.post) {
        this.setData({
          post: {
            ...this.data.post,
            comment_count: (this.data.post.comment_count || 0) + 1,
            comment_count_text: formatCount((this.data.post.comment_count || 0) + 1),
          },
        })
      }
      wx.showToast({ title: '评论成功', icon: 'success' })
    } catch (e: any) {
      wx.showToast({ title: e.message || '评论失败', icon: 'none' })
    } finally {
      this.setData({ submittingComment: false })
    }
  },

  onLoadMoreComments() {
    if (this.data.commentLoading || !this.data.commentHasMore) return
    this.loadComments(this.data.commentPage + 1)
  },

  // ============== 点赞 ==============
  async onLike() {
    if (!this.requireWritable('登录后即可点赞')) return
    if (!this.data.post) return
    try {
      const res: any = await likePost(this.data.postId)
      const liked = !!res.is_liked
      const count = Number(res.like_count || 0)
      this.setData({
        isLiked: liked,
        likesCount: count,
      })
      if (this.data.post) {
        this.setData({
          post: {
            ...this.data.post,
            like_count: count,
            like_count_text: formatCount(count),
          },
        })
      }
    } catch (e: any) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    }
  },

  // ============== 协同验证 ==============
  async onValidate(e: any) {
    if (!this.requireWritable('登录后即可参与协同验证')) return
    const type: 'confirmation' | 'refutation' = e.currentTarget.dataset.type
    if (!type) return
    try {
      const res = await validatePost(this.data.postId, type)
      // 后端自动处理：同类型=取消(removed)，不同类型=切换(switched)，首次=created
      const action = res && res.action
      const currentType = res && res.current_validation_type
      if (action === 'removed') {
        wx.showToast({ title: '已取消投票', icon: 'none' })
        this.setData({ userValidationType: '' })
      } else {
        wx.showToast({
          title: currentType === 'confirmation' ? '已证实' : '已证伪',
          icon: 'success',
        })
        this.setData({ userValidationType: currentType || type })
      }
      await this.loadValidationStats()
    } catch (e: any) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    }
  },

  // ============== 举报 ==============
  openReport() {
    if (!this.requireWritable('登录后即可举报')) return
    this.setData({ reportVisible: true, reportReason: '', reportType: 'other' })
  },

  closeReport() {
    this.setData({ reportVisible: false })
  },

  onReportReasonInput(e: any) {
    this.setData({ reportReason: e.detail.value || '' })
  },

  onPickReportType(e: any) {
    const value = e.currentTarget.dataset.type
    this.setData({ reportType: value })
  },

  async onSubmitReport() {
    if (!this.requireWritable('登录后即可举报')) return
    if (this.data.submittingReport) return
    if (!this.data.reportReason.trim()) {
      wx.showToast({ title: '请填写举报理由', icon: 'none' })
      return
    }
    this.setData({ submittingReport: true })
    try {
      await reportPost(this.data.postId, this.data.reportReason.trim(), this.data.reportType)
      wx.showToast({ title: '举报已提交', icon: 'success' })
      this.setData({ reportVisible: false, reportReason: '', reportType: 'other' })
    } catch (e: any) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' })
    } finally {
      this.setData({ submittingReport: false })
    }
  },

  // ============== 复制地址 / 链接 ==============
  copyAddress() {
    const post = this.data.post || {}
    const text = post.location_address || post.location_name || ''
    if (!text) {
      wx.showToast({ title: '暂无地点信息', icon: 'none' })
      return
    }
    wx.setClipboardData({
      data: text,
      success: () => wx.showToast({ title: '地址已复制', icon: 'success' }),
    })
  },

  copyLink() {
    const url = `https://campus.chaina1.com/posts/${this.data.postId}`
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: '链接已复制', icon: 'success' }),
    })
  },

  // ============== 倒计时 ==============
  startCountdown(expiresAt?: string) {
    if (this.data.countdownTimer) {
      clearInterval(this.data.countdownTimer)
      this.setData({ countdownTimer: null })
    }
    if (!expiresAt) {
      this.setData({ remainingTime: '' })
      return
    }
    const update = () => {
      this.setData({ remainingTime: getRemainingTime(expiresAt) })
    }
    update()
    const timer = setInterval(update, 60 * 1000)
    this.setData({ countdownTimer: timer })
  },

  // ============== 图片轮播 ==============
  onSwiperChange(e: any) {
    this.setData({ swiperCurrent: e.detail.current })
  },

  onPreviewImage(e: any) {
    const url = e.currentTarget.dataset.url
    if (!url || this.data.images.length === 0) return
    wx.previewImage({ current: url, urls: this.data.images.map((item: PostImage) => item.image_url) })
  },

  // ============== 其他 ==============
  onShareAppMessage() {
    const post = this.data.post || {}
    return {
      title: post.title || '此刻校园',
      path: `/pages/post-detail/post-detail?id=${this.data.postId}`,
    }
  },
})
