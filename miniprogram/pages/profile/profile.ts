import { http, resolveImageUrl } from '../../services/request'
import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { formatDate, formatCount } from '../../utils/format'
import { listIdentities, deleteIdentity, listSessions, revokeSession, logoutAll } from '../../services/auth'
import { logout } from '../../services/auth'

const STATUS_TABS = [
  { key: 'all', label: '全部' },
  { key: 'published', label: '已发布' },
  { key: 'draft', label: '草稿' },
  { key: 'pending', label: '待审' },
  { key: 'expired', label: '已过期' },
  { key: 'conflict', label: '冲突' },
  { key: 'archived', label: '已归档' },
]

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  pending: '待审',
  published: '已发布',
  expired: '已过期',
  conflict: '冲突',
  archived: '已归档',
}

Page({
  data: {
    activeTab: 'profile',
    schoolName: '',
    isLoggedIn: false,

    // 用户信息
    user: null as any,
    avatarUrl: '',
    nickname: '',
    bio: '',
    email: '',
    createdAtText: '',

    // 统计
    postsCount: 0,
    validationsCount: 0,
    commentsCount: 0,
    postsCountText: '0',
    validationsCountText: '0',
    commentsCountText: '0',

    // 我的帖子
    statusTabs: STATUS_TABS,
    activeStatus: 'all',
    posts: [] as any[],
    page: 1,
    pageSize: 10,
    hasMore: true,
    loadingPosts: false,
    loadingMorePosts: false,

    // 编辑资料弹出层
    editVisible: false,
    editNickname: '',
    editBio: '',
    savingProfile: false,

    // 身份管理弹出层
    identityVisible: false,
    identities: [] as any[],
    loadingIdentities: false,

    // 设备管理弹出层
    sessionVisible: false,
    sessions: [] as any[],
    loadingSessions: false,

    loadingUser: false,
  },

  onLoad() {
    authStore.subscribe(state => {
      this.setData({ isLoggedIn: state.isLoggedIn })
      if (state.isLoggedIn && state.user) {
        this.applyUser(state.user)
      }
    })
    campusStore.subscribe(state => {
      this.setData({
        schoolName: state.currentSchool?.name || state.schoolCode || '此刻校园',
      })
    })
  },

  async onShow() {
    if (authStore.getState().isLoggedIn) {
      await Promise.all([this.loadUser(), this.loadStats(), this.refreshPosts()])
    }
  },

  // ============== 用户信息 ==============
  applyUser(user: any) {
    if (!user) return
    this.setData({
      user,
      avatarUrl: resolveImageUrl(user.avatar_url),
      nickname: user.nickname || '',
      bio: user.bio || '',
      email: user.email || '',
      createdAtText: user.created_at ? formatDate(user.created_at, 'datetime') : '',
    })
  },

  async loadUser() {
    this.setData({ loadingUser: true })
    try {
      const res: any = await http.get('/users/me')
      const user = res.user || res
      this.applyUser(user)
      authStore.setUser(user)
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载用户信息失败', icon: 'none' })
    } finally {
      this.setData({ loadingUser: false })
    }
  },

  async loadStats() {
    try {
      const res: any = await http.get('/users/me/stats')
      const stats = res.stats || res
      const postsCount = Number(stats.posts_count || 0)
      const validationsCount = Number(stats.validations_count || 0)
      const commentsCount = Number(stats.comments_count || 0)
      this.setData({
        postsCount,
        validationsCount,
        commentsCount,
        postsCountText: formatCount(postsCount),
        validationsCountText: formatCount(validationsCount),
        commentsCountText: formatCount(commentsCount),
      })
    } catch (e: any) {
      console.error('加载统计失败', e)
    }
  },

  // ============== 我的帖子 ==============
  async refreshPosts() {
    this.setData({ page: 1, hasMore: true, posts: [] })
    await this.loadPosts()
  },

  async loadPosts() {
    if (this.data.loadingPosts || this.data.loadingMorePosts) return
    const isFirstPage = this.data.page === 1
    this.setData({ loadingPosts: isFirstPage, loadingMorePosts: !isFirstPage })
    try {
      const { activeStatus, page, pageSize } = this.data
      let url = `/users/me/posts?page=${page}&page_size=${pageSize}`
      if (activeStatus && activeStatus !== 'all') {
        url += `&status=${activeStatus}`
      }
      const res: any = await http.get(url)
      const items = (res.items || res.posts || []) as any[]
      const list = items.map((p: any) => this.normalizePost(p))
      this.setData({
        posts: [...this.data.posts, ...list],
        hasMore: res.has_more !== undefined ? !!res.has_more : list.length >= pageSize,
        page: page + 1,
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载帖子失败', icon: 'none' })
    } finally {
      this.setData({ loadingPosts: false, loadingMorePosts: false })
    }
  },

  normalizePost(p: any): any {
    if (!p) return p
    const images = Array.isArray(p.images) ? p.images.map((u: string) => resolveImageUrl(u)) : []
    return {
      ...p,
      images,
      cover: images[0] || '',
      status_label: STATUS_LABELS[p.status] || p.status,
      created_at_text: formatDate(p.created_at),
      likes_count_text: formatCount(p.likes_count || 0),
      comments_count_text: formatCount(p.comments_count || 0),
      validations_count_text: formatCount(p.validations_count || 0),
      views_count_text: formatCount(p.views_count || 0),
    }
  },

  onStatusTabTap(e: any) {
    const key = e.currentTarget.dataset.key
    if (!key || key === this.data.activeStatus) return
    this.setData({ activeStatus: key, page: 1, hasMore: true, posts: [] })
    this.loadPosts()
  },

  onPostTap(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  onPullDownRefresh() {
    Promise.all([this.loadUser(), this.loadStats(), this.refreshPosts()])
      .finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loadingPosts && !this.data.loadingMorePosts) {
      this.loadPosts()
    }
  },

  // ============== 编辑资料 ==============
  showEditPopup() {
    this.setData({
      editVisible: true,
      editNickname: this.data.nickname || '',
      editBio: this.data.bio || '',
    })
  },

  hideEditPopup() {
    this.setData({ editVisible: false })
  },

  onEditNicknameInput(e: any) {
    this.setData({ editNickname: e.detail.value || '' })
  },

  onEditBioInput(e: any) {
    this.setData({ editBio: e.detail.value || '' })
  },

  async saveEdit() {
    if (this.data.savingProfile) return
    const nickname = (this.data.editNickname || '').trim()
    if (!nickname) {
      wx.showToast({ title: '请填写昵称', icon: 'none' })
      return
    }
    this.setData({ savingProfile: true })
    try {
      const payload: any = { nickname, bio: this.data.editBio || '' }
      const res: any = await http.put('/users/me', payload)
      const user = res.user || res
      this.applyUser(user)
      authStore.setUser(user)
      this.setData({ editVisible: false })
      wx.showToast({ title: '已保存', icon: 'success' })
    } catch (e: any) {
      wx.showToast({ title: e.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ savingProfile: false })
    }
  },

  // 阻止弹出层冒泡
  noop() {},

  // ============== 身份管理 ==============
  async showIdentityPopup() {
    this.setData({ identityVisible: true })
    await this.loadIdentities()
  },

  hideIdentityPopup() {
    this.setData({ identityVisible: false })
  },

  async loadIdentities() {
    this.setData({ loadingIdentities: true })
    try {
      const res: any = await listIdentities()
      const list = (res.identities || []) as any[]
      const formatted = list.map((it: any) => ({
        ...it,
        type_label: this.identityTypeLabel(it.identity_type),
        created_at_text: formatDate(it.created_at, 'datetime'),
        last_used_at_text: it.last_used_at ? formatDate(it.last_used_at, 'datetime') : '—',
      }))
      this.setData({ identities: formatted })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载身份失败', icon: 'none' })
    } finally {
      this.setData({ loadingIdentities: false })
    }
  },

  identityTypeLabel(t: string): string {
    if (!t) return '未知'
    if (t === 'email' || t === 'password') return '邮箱'
    if (t === 'wechat' || t === 'wechat_miniprogram') return '微信'
    if (t === 'wechat_mp') return '公众号'
    return t
  },

  onDeleteIdentity(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.showModal({
      title: '提示',
      content: '确定要删除该登录身份吗？删除后将无法使用该方式登录。',
      success: async r => {
        if (!r.confirm) return
        try {
          await deleteIdentity(Number(id))
          wx.showToast({ title: '已删除', icon: 'success' })
          await this.loadIdentities()
        } catch (err: any) {
          wx.showToast({ title: err.message || '删除失败', icon: 'none' })
        }
      },
    })
  },

  // ============== 设备会话管理 ==============
  async showSessionPopup() {
    this.setData({ sessionVisible: true })
    await this.loadSessions()
  },

  hideSessionPopup() {
    this.setData({ sessionVisible: false })
  },

  async loadSessions() {
    this.setData({ loadingSessions: true })
    try {
      const res: any = await listSessions()
      const list = (res.sessions || []) as any[]
      const formatted = list.map((s: any) => ({
        ...s,
        type_label: this.sessionTypeLabel(s.session_type),
        device_brief: s.device_info || s.user_agent || '未知设备',
        ip_text: s.client_ip || '—',
        created_at_text: formatDate(s.created_at, 'datetime'),
        last_active_text: s.last_active_at ? formatDate(s.last_active_at) : '—',
        expires_text: s.expires_at ? formatDate(s.expires_at, 'datetime') : '—',
      }))
      this.setData({ sessions: formatted })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载会话失败', icon: 'none' })
    } finally {
      this.setData({ loadingSessions: false })
    }
  },

  sessionTypeLabel(t: string): string {
    if (!t) return '会话'
    if (t === 'web') return '网页'
    if (t === 'miniprogram') return '小程序'
    if (t === 'wechat') return '微信'
    return t
  },

  onRevokeSession(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.showModal({
      title: '提示',
      content: '确定要退出该设备？',
      success: async r => {
        if (!r.confirm) return
        try {
          await revokeSession(Number(id))
          wx.showToast({ title: '已退出', icon: 'success' })
          await this.loadSessions()
        } catch (err: any) {
          wx.showToast({ title: err.message || '操作失败', icon: 'none' })
        }
      },
    })
  },

  onLogoutAll() {
    wx.showModal({
      title: '提示',
      content: '将退出全部设备（含当前设备），确定继续？',
      success: async r => {
        if (!r.confirm) return
        try {
          await logoutAll()
          wx.showToast({ title: '已退出全部设备', icon: 'success' })
          this.performLogoutRedirect()
        } catch (err: any) {
          wx.showToast({ title: err.message || '操作失败', icon: 'none' })
        }
      },
    })
  },

  // ============== 退出登录 ==============
  onLogout() {
    wx.showModal({
      title: '提示',
      content: '确定要退出登录吗？',
      success: async r => {
        if (!r.confirm) return
        try {
          await logout()
        } catch (e) {
          // 忽略服务端错误，仍清除本地状态
        }
        this.performLogoutRedirect()
      },
    })
  },

  performLogoutRedirect() {
    authStore.clear()
    try {
      wx.removeStorageSync('access_token')
      wx.removeStorageSync('refresh_token')
    } catch {
      // ignore
    }
    this.setData({
      editVisible: false,
      identityVisible: false,
      sessionVisible: false,
    })
    wx.reLaunch({ url: '/pages/login/login' })
  },

  // ============== tab bar 跳转 ==============
  goToHome() {
    wx.switchTab({ url: '/pages/home/home' })
  },

  goToMap() {
    wx.switchTab({ url: '/pages/map/map' })
  },

  goToPublish() {
    wx.navigateTo({ url: '/pages/publish/publish' })
  },

  goToSearch() {
    wx.switchTab({ url: '/pages/search/search' })
  },

  goToNotifications() {
    wx.navigateTo({ url: '/pages/notifications/notifications' })
  },
})
