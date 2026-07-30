import { http, resolveImageUrl } from '../../services/request'
import { formatDate, formatCount, getRemainingTime } from '../../utils/format'
import {
  likePost,
  createComment,
  validatePost,
  getValidationStats,
  reportPost,
  listComments,
} from '../../services/interactions'

const REPORT_REASONS = [
  '垃圾信息',
  '虚假内容',
  '不当言论',
  '侵权内容',
  '其他',
]

Page({
  data: {
    postId: 0,
    loading: true,
    post: null as any,
    images: [] as string[],
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
    reportType: '其他',
    reportReasons: REPORT_REASONS,
    submittingReport: false,
  },

  onLoad(options: any) {
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
    if (this.data.countdownTimer) {
      clearInterval(this.data.countdownTimer)
    }
  },

  async loadAll() {
    this.setData({ loading: true })
    try {
      await Promise.all([
        this.loadPost(),
        this.loadInteractions(),
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
    const res: any = await http.get(`/posts/${this.data.postId}`)
    const post = res || {}
    const images = Array.isArray(post.images)
      ? post.images.map((u: string) => resolveImageUrl(u))
      : []
    const normalized = {
      ...post,
      images,
      author_avatar: resolveImageUrl(post.author_avatar),
      created_at_text: formatDate(post.created_at),
      likes_count_text: formatCount(post.likes_count || 0),
      comments_count_text: formatCount(post.comments_count || 0),
      validations_count_text: formatCount(post.validations_count || 0),
      views_count_text: formatCount(post.views_count || 0),
    }
    this.setData({ post: normalized, images })
    this.startCountdown(post.expires_at)
  },

  // ============== 互动状态 ==============
  async loadInteractions() {
    try {
      const res: any = await http.get(`/posts/${this.data.postId}/interactions`)
      this.setData({
        isLiked: !!res.is_liked,
        likesCount: res.likes_count ?? (this.data.post && this.data.post.likes_count) ?? 0,
        commentsCount: res.comments_count ?? (this.data.post && this.data.post.comments_count) ?? 0,
      })
    } catch {
      // 游客或失败时静默
    }
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
      const items = (res && (res.items || res.comments || res.data)) || []
      const list = items.map((c: any) => ({
        ...c,
        author_avatar: resolveImageUrl(c.author_avatar),
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
    this.setData({
      replyingTo: { id, nickname },
      commentInput: `@${nickname} `,
    })
  },

  cancelReply() {
    this.setData({ replyingTo: null, commentInput: '' })
  },

  async onSubmitComment() {
    const content = (this.data.commentInput || '').trim()
    if (!content) {
      wx.showToast({ title: '请输入评论内容', icon: 'none' })
      return
    }
    if (this.data.submittingComment) return
    this.setData({ submittingComment: true })
    try {
      const parentId = this.data.replyingTo ? this.data.replyingTo.id : undefined
      const res: any = await createComment(this.data.postId, content, parentId)
      const newComment = {
        ...(res || {}),
        author_avatar: resolveImageUrl(res && res.author_avatar),
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
            comments_count: (this.data.post.comments_count || 0) + 1,
            comments_count_text: formatCount((this.data.post.comments_count || 0) + 1),
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
    if (!this.data.post) return
    try {
      const res: any = await likePost(this.data.postId)
      const liked = !!(res && res.liked !== undefined ? res.liked : !this.data.isLiked)
      const count = (res && res.likes_count !== undefined)
        ? res.likes_count
        : (this.data.likesCount + (liked ? 1 : -1))
      this.setData({
        isLiked: liked,
        likesCount: count,
      })
      if (this.data.post) {
        this.setData({
          post: {
            ...this.data.post,
            likes_count: count,
            likes_count_text: formatCount(count),
          },
        })
      }
    } catch (e: any) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    }
  },

  // ============== 协同验证 ==============
  async onValidate(e: any) {
    const type: 'confirmation' | 'refutation' = e.currentTarget.dataset.type
    if (!type) return
    // 已投过同类型 → 提示
    if (this.data.userValidationType === type) {
      wx.showToast({ title: '你已经投过此票', icon: 'none' })
      return
    }
    try {
      await validatePost(this.data.postId, type)
      wx.showToast({
        title: type === 'confirmation' ? '已证实' : '已证伪',
        icon: 'success',
      })
      this.setData({ userValidationType: type })
      await this.loadValidationStats()
    } catch (e: any) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    }
  },

  // ============== 举报 ==============
  openReport() {
    this.setData({ reportVisible: true, reportReason: '', reportType: '其他' })
  },

  closeReport() {
    this.setData({ reportVisible: false })
  },

  onReportReasonInput(e: any) {
    this.setData({ reportReason: e.detail.value || '' })
  },

  onPickReportType(e: any) {
    const type = e.currentTarget.dataset.type
    this.setData({ reportType: type })
  },

  async onSubmitReport() {
    if (this.data.submittingReport) return
    if (!this.data.reportReason.trim()) {
      wx.showToast({ title: '请填写举报理由', icon: 'none' })
      return
    }
    this.setData({ submittingReport: true })
    try {
      await reportPost(this.data.postId, this.data.reportReason.trim(), this.data.reportType)
      wx.showToast({ title: '举报已提交', icon: 'success' })
      this.setData({ reportVisible: false, reportReason: '', reportType: '其他' })
    } catch (e: any) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' })
    } finally {
      this.setData({ submittingReport: false })
    }
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
    wx.previewImage({ current: url, urls: this.data.images })
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
