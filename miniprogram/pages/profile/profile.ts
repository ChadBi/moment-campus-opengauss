import { http, resolveAvatar, defaultAvatar } from '../../services/request'
import { authStore } from '../../store/auth'
import { campusStore } from '../../store/campus'
import { formatDate, formatCount } from '../../utils/format'
import { normalizePost, normalizeMembership, normalizeUser } from '../../services/normalize'
import { listMemberships } from '../../services/schools'
import { getMe } from '../../services/users'
import { logout } from '../../services/auth'
import {
  sendEducationEmail,
  confirmEducationEmail,
  sendEducationEmailUnbindCode,
  unbindEducationEmail,
  setPassword,
} from '../../services/auth'
import { navigateToTab, syncTabBarForPage } from '../../utils/tab-navigation'
import { isRegistrationSchool } from '../../utils/campus-permission'

const STATUS_TABS = [
  { key: 'all', label: '全部' },
  { key: 'draft', label: '草稿' },
  { key: 'pending', label: '待审核' },
  { key: 'published', label: '已发布' },
  { key: 'expired', label: '已过期' },
  { key: 'conflict', label: '冲突中' },
  { key: 'archived', label: '已归档' },
]

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  pending: '待审核',
  published: '已发布',
  expired: '已过期',
  conflict: '冲突中',
  archived: '已归档',
}

const PROFILE_REFRESH_INTERVAL_MS = 60 * 1000

Page({
  data: {
    schoolName: '',
    isLoggedIn: false,

    // 用户信息
    user: null as any,
    avatarUrl: defaultAvatar(),
    nickname: '',
    bio: '',
    phone: '',
    educationEmail: '',
    createdAtText: '',

    // 统计（对齐 Web ProfilePage: 已发布/草稿/待审核/贡献验证）
    publishedCount: 0,
    draftCount: 0,
    pendingCount: 0,
    confirmationCount: 0,
    publishedCountText: '0',
    draftCountText: '0',
    pendingCountText: '0',
    confirmationCountText: '0',
    statsLoading: false,

    // 加入的学校（D2）
    memberships: [] as any[],
    currentSchoolId: 0,

    // 我的帖子
    statusTabs: STATUS_TABS,
    activeStatus: 'all',
    posts: [] as any[],
    page: 1,
    pageSize: 10,
    hasMore: true,
    loadingPosts: false,
    loadingMorePosts: false,

    // 顶部分区切换：我的帖子 / 浏览历史
    activeSection: 'posts',

    // 浏览历史
    history: [] as any[],
    historyPage: 1,
    historyPageSize: 10,
    historyHasMore: true,
    loadingHistory: false,
    loadingMoreHistory: false,

    // 编辑资料弹出层
    editVisible: false,
    editNickname: '',
    editBio: '',
    savingProfile: false,

    // 校园身份认证（B-06）
    campusVerified: false,
    isRegistrationSchool: false,
    verifyStep: 'form', // 'form' | 'code'
    verifyCode: '',
    devCode: '',
    verifySending: false,
    verifyConfirming: false,

    loadingUser: false,

    // 推荐隐私（Task 4b）
    recEnabled: false,
    recLoading: false,
  },

  onLoad() {
    syncTabBarForPage(4)
    ;(this as any)._profileLoaded = false
    ;(this as any)._lastProfileRefreshAt = 0
    ;(this as any)._profileRefreshPromise = null
    ;(this as any)._lastSchoolId = 0
    authStore.subscribe(state => {
      this.setData({ isLoggedIn: state.isLoggedIn })
      if (state.isLoggedIn && state.user) {
        this.applyUser(state.user)
      }
    })
    campusStore.subscribe(state => {
      const nextSchoolId = state.currentSchool?.id || 0
      const prevSchoolId = (this as any)._lastSchoolId || 0
      const schoolChanged = prevSchoolId !== 0 && nextSchoolId !== prevSchoolId
      this.setData({
        schoolName: (state.currentSchool && state.currentSchool.name) || state.schoolCode || '此刻校园',
        currentSchoolId: nextSchoolId,
      })
      ;(this as any)._lastSchoolId = nextSchoolId
      if (this.data.user) this.applyUser(this.data.user)
      // 切换学校后强制刷新个人主页数据（清空旧学校帖子/历史，加载新学校数据）
      if (schoolChanged && authStore.getState().isLoggedIn) {
        ;(this as any)._profileLoaded = false
        ;(this as any)._lastProfileRefreshAt = 0
        this.setData({
          posts: [],
          history: [],
          page: 1,
          hasMore: true,
          historyPage: 1,
          historyHasMore: true,
          publishedCount: 0,
          draftCount: 0,
          pendingCount: 0,
          confirmationCount: 0,
          publishedCountText: '0',
          draftCountText: '0',
          pendingCountText: '0',
          confirmationCountText: '0',
        })
        this.refreshProfile(true)
      }
    })
  },

  async onShow() {
    syncTabBarForPage(4)
    // 未登录时不再弹 Modal 打断，直接渲染「点击登录」空态卡片引导用户主动点击
    if (!authStore.getState().isLoggedIn) {
      // 清空旧登录态残留数据，避免页面切换时闪烁展示假数据
      this.setData({
        user: null,
        avatarUrl: defaultAvatar(),
        nickname: '',
        bio: '',
        phone: '',
        educationEmail: '',
        createdAtText: '',
        campusVerified: false,
        isRegistrationSchool: false,
        publishedCount: 0,
        draftCount: 0,
        pendingCount: 0,
        confirmationCount: 0,
        publishedCountText: '0',
        draftCountText: '0',
        pendingCountText: '0',
        confirmationCountText: '0',
        memberships: [],
        posts: [],
        history: [],
        verifyStep: 'form',
        verifyCode: '',
        devCode: '',
        recEnabled: false,
      })
      ;(this as any)._profileLoaded = false
      ;(this as any)._lastProfileRefreshAt = 0
      return
    }
    await this.refreshProfile()
  },

  async refreshProfile(force = false) {
    const now = Date.now()
    if (
      !force &&
      (this as any)._profileLoaded &&
      now - Number((this as any)._lastProfileRefreshAt || 0) < PROFILE_REFRESH_INTERVAL_MS
    ) return

    if ((this as any)._profileRefreshPromise) {
      await (this as any)._profileRefreshPromise
      return
    }

    const tasks: Promise<any>[] = [this.loadUser(), this.loadStats(), this.refreshPosts(false), this.loadMemberships(), this.loadRecPreference()]
    if (this.data.activeSection === 'history') {
      tasks.push(this.refreshHistory(false))
    }
    const refreshPromise = Promise.all(tasks)
    ;(this as any)._profileRefreshPromise = refreshPromise
    try {
      await refreshPromise
      ;(this as any)._profileLoaded = true
      ;(this as any)._lastProfileRefreshAt = Date.now()
    } finally {
      if ((this as any)._profileRefreshPromise === refreshPromise) {
        ;(this as any)._profileRefreshPromise = null
      }
    }
  },

  // ============== 用户信息 ==============
  applyUser(user: any) {
    if (!user) return
    const registrationSchool = isRegistrationSchool(user, campusStore.getState().currentSchool?.id)
    this.setData({
      user,
      avatarUrl: resolveAvatar(user.avatar_url),
      nickname: user.nickname || '',
      bio: user.bio || '',
      phone: user.phone ? `${String(user.phone).slice(0, 3)}****${String(user.phone).slice(-4)}` : '',
      educationEmail: user.education_email || '',
      campusVerified: registrationSchool && !!user.campus_verified,
      isRegistrationSchool: registrationSchool,
      createdAtText: user.created_at ? formatDate(user.created_at, 'datetime') : '',
    })
  },

  async loadUser() {
    this.setData({ loadingUser: true })
    try {
      const user = await getMe()
      this.applyUser(user)
      authStore.setUser(user)
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载用户信息失败', icon: 'none' })
    } finally {
      this.setData({ loadingUser: false })
    }
  },

  async loadStats() {
    this.setData({ statsLoading: true })
    try {
      const res: any = await http.get('/users/me/stats')
      const stats = res.stats || res
      const publishedCount = Number(stats.published_count || 0)
      const draftCount = Number(stats.draft_count || 0)
      const pendingCount = Number(stats.pending_count || 0)
      const confirmationCount = Number(stats.confirmation_count || 0)
      this.setData({
        publishedCount,
        draftCount,
        pendingCount,
        confirmationCount,
        publishedCountText: formatCount(publishedCount),
        draftCountText: formatCount(draftCount),
        pendingCountText: formatCount(pendingCount),
        confirmationCountText: formatCount(confirmationCount),
        statsLoading: false,
      })
    } catch (e: any) {
      console.error('加载统计失败', e)
      this.setData({ statsLoading: false })
    }
  },

  // ============== 加入的学校（D2） ==============
  async loadMemberships() {
    try {
      const list = await listMemberships()
      const campusState = campusStore.getState()
      this.setData({
        memberships: list.map(normalizeMembership),
        currentSchoolId: (campusState.currentSchool && campusState.currentSchool.id) || 0,
      })
      if (this.data.user) this.applyUser(this.data.user)
    } catch (e: any) {
      console.error('加载学校成员关系失败', e)
    }
  },

  goToSchoolSelect() {
    wx.navigateTo({ url: '/subpackages/pages/school-select/school-select?mode=switch' })
  },

  // ============== 校园身份认证（B-06） ==============
  onEducationEmailInput(e: any) {
    this.setData({ educationEmail: e.detail.value || '' })
  },

  onVerifyCodeInput(e: any) {
    this.setData({ verifyCode: e.detail.value || '' })
  },

  onBackVerifyForm() {
    this.setData({ verifyStep: 'form', verifyCode: '', devCode: '' })
  },

  async onSendVerifyCode() {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    if (!this.data.isRegistrationSchool) {
      wx.showToast({ title: '校园身份认证仅适用于注册时选择的学校', icon: 'none' })
      return
    }
    if (this.data.verifySending) return
    this.setData({ verifySending: true })
    try {
      const educationEmail = (this.data.educationEmail || '').trim().toLowerCase()
      if (!educationEmail || !educationEmail.includes('@')) {
        wx.showToast({ title: '请填写教育邮箱', icon: 'none' })
        return
      }
      const res: any = await sendEducationEmail(educationEmail)
      this.setData({
        devCode: res && res.code ? String(res.code) : '',
        verifyStep: 'code',
      })
      const msg = (res && res.message) || '验证码已发送至邮箱，请查收'
      if (res && res.code) {
        // 兜底场景：邮件发送失败，直接弹窗显示验证码
        wx.showModal({
          title: '验证码',
          content: `您的验证码是：${res.code}\n\n（邮件发送失败，可直接输入此验证码完成认证）`,
          showCancel: false,
          confirmText: '我知道了',
        })
      } else {
        wx.showToast({ title: msg, icon: 'none', duration: 3000 })
      }
    } catch (e: any) {
      wx.showToast({ title: e.message || '发送失败，请重试', icon: 'none' })
    } finally {
      this.setData({ verifySending: false })
    }
  },

  async onConfirmVerify() {
    if (!this.data.isLoggedIn) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    if (!this.data.isRegistrationSchool) {
      wx.showToast({ title: '校园身份认证仅适用于注册时选择的学校', icon: 'none' })
      return
    }
    const code = (this.data.verifyCode || '').trim()
    if (!/^\d{6}$/.test(code)) {
      wx.showToast({ title: '请输入6位数字验证码', icon: 'none' })
      return
    }
    if (this.data.verifyConfirming) return
    this.setData({ verifyConfirming: true })
    try {
      const res: any = await confirmEducationEmail(code)
      // 同步更新本地用户状态
      const user = this.data.user ? { ...this.data.user, education_email: this.data.educationEmail, campus_verified: true } : null
      if (user) {
        authStore.setUser(user)
        this.applyUser(user)
      }
      this.setData({ verifyStep: 'form', verifyCode: '', devCode: '' })
      wx.showToast({ title: (res && res.message) || '校园身份认证成功', icon: 'success' })
    } catch (e: any) {
      wx.showToast({ title: e.message || '认证失败，请重试', icon: 'none' })
    } finally {
      this.setData({ verifyConfirming: false })
    }
  },

  // ============== 我的帖子 ==============
  async refreshPosts(clearExisting = false) {
    this.setData({
      page: 1,
      hasMore: true,
      ...(clearExisting ? { posts: [] } : {}),
    })
    await this.loadPosts()
  },

  async loadPosts() {
    if (this.data.loadingPosts || this.data.loadingMorePosts) return
    const isFirstPage = this.data.page === 1
    const showInitialLoading = isFirstPage && this.data.posts.length === 0
    this.setData({ loadingPosts: showInitialLoading, loadingMorePosts: !isFirstPage })
    try {
      const { activeStatus, page, pageSize } = this.data
      let url = `/users/me/posts?page=${page}&page_size=${pageSize}`
      if (activeStatus && activeStatus !== 'all') {
        url += `&status=${activeStatus}`
      }
      const res: any = await http.get(url)
      const items = (res.items || []) as any[]
      const list = items.map((p: any) => this.normalizePost(p))
      this.setData({
        posts: isFirstPage ? list : [...this.data.posts, ...list],
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
    const normalized = normalizePost(p)
    const images = normalized.images || []
    return {
      ...normalized,
      images,
      cover: images[0]?.thumbnail_url || images[0]?.image_url || '',
      status_label: STATUS_LABELS[normalized.status] || normalized.status,
      created_at_text: formatDate(normalized.created_at),
      like_count_text: formatCount(normalized.like_count || 0),
      comment_count_text: formatCount(normalized.comment_count || 0),
      valid_count_text: formatCount(normalized.valid_count || 0),
      view_count_text: formatCount(normalized.view_count || 0),
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
    this.refreshProfile(true)
      .finally(() => wx.stopPullDownRefresh())
  },

  onReachBottom() {
    if (this.data.activeSection === 'history') {
      if (this.data.historyHasMore && !this.data.loadingHistory && !this.data.loadingMoreHistory) {
        this.loadHistory()
      }
      return
    }
    if (this.data.hasMore && !this.data.loadingPosts && !this.data.loadingMorePosts) {
      this.loadPosts()
    }
  },

  // ============== 分区切换 ==============
  onSectionTabTap(e: any) {
    const key = e.currentTarget.dataset.key
    if (!key || key === this.data.activeSection) return
    this.setData({ activeSection: key })
    if (key === 'history' && this.data.history.length === 0) {
      this.refreshHistory()
    }
  },

  // ============== 浏览历史 ==============
  async refreshHistory(clearExisting = false) {
    this.setData({
      historyPage: 1,
      historyHasMore: true,
      ...(clearExisting ? { history: [] } : {}),
    })
    await this.loadHistory()
  },

  async loadHistory() {
    if (this.data.loadingHistory || this.data.loadingMoreHistory) return
    const isFirstPage = this.data.historyPage === 1
    const showInitialLoading = isFirstPage && this.data.history.length === 0
    this.setData({ loadingHistory: showInitialLoading, loadingMoreHistory: !isFirstPage })
    try {
      const { historyPage, historyPageSize } = this.data
      const res: any = await http.get(`/users/me/view-history?page=${historyPage}&page_size=${historyPageSize}`)
      const items = (res.items || res.history || res || []) as any[]
      const list = items.map((h: any) => this.normalizeHistory(h))
      this.setData({
        history: isFirstPage ? list : [...this.data.history, ...list],
        historyHasMore: res.has_more !== undefined ? !!res.has_more : list.length >= historyPageSize,
        historyPage: historyPage + 1,
      })
    } catch (e: any) {
      wx.showToast({ title: e.message || '加载浏览历史失败', icon: 'none' })
    } finally {
      this.setData({ loadingHistory: false, loadingMoreHistory: false })
    }
  },

  normalizeHistory(h: any): any {
    if (!h) return h
    return {
      ...h,
      post_id: h.post_id || h.id,
      post_title: h.post_title || h.title || '未命名帖子',
      category_name: h.category_name || h.category || '未分类',
      viewed_at_text: h.viewed_at ? formatDate(h.viewed_at, 'datetime') : '',
    }
  },

  onHistoryTap(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: `/pages/post-detail/post-detail?id=${id}` })
  },

  onDeleteHistoryItem(e: any) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.showModal({
      title: '提示',
      content: '确定要删除该条浏览历史吗？',
      success: async r => {
        if (!r.confirm) return
        try {
          await http.delete(`/users/me/view-history/${id}`)
          wx.showToast({ title: '已删除', icon: 'success' })
          const list = this.data.history.filter((h: any) => h.post_id !== id)
          this.setData({ history: list })
        } catch (err: any) {
          wx.showToast({ title: err.message || '删除失败', icon: 'none' })
        }
      },
    })
  },

  onClearHistory() {
    if (this.data.history.length === 0) {
      wx.showToast({ title: '暂无浏览历史', icon: 'none' })
      return
    }
    wx.showModal({
      title: '提示',
      content: '确定要清空全部浏览历史吗？此操作不可恢复。',
      success: async r => {
        if (!r.confirm) return
        try {
          await http.delete('/users/me/view-history')
          wx.showToast({ title: '已清空', icon: 'success' })
          this.setData({ history: [], historyHasMore: false })
        } catch (err: any) {
          wx.showToast({ title: err.message || '清空失败', icon: 'none' })
        }
      },
    })
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

  // ============== 账号安全 ==============
  onSetPasswordTap() {
    if (this.data.user?.has_password) return
    wx.showModal({
      title: '设置密码',
      editable: true,
      placeholderText: '请输入至少 6 位密码',
      success: first => {
        if (!first.confirm || !first.content || first.content.length < 6) {
          if (first.confirm) wx.showToast({ title: '密码至少 6 位', icon: 'none' })
          return
        }
        wx.showModal({
          title: '确认密码',
          editable: true,
          placeholderText: '请再次输入密码',
          success: async second => {
            if (!second.confirm) return
            if (second.content !== first.content) {
              wx.showToast({ title: '两次密码不一致', icon: 'none' })
              return
            }
            try {
              await setPassword(first.content, second.content)
              const user = this.data.user ? { ...this.data.user, has_password: true } : null
              if (user) { authStore.setUser(user); this.applyUser(user) }
              wx.showToast({ title: '密码设置成功', icon: 'success' })
            } catch (e: any) {
              wx.showToast({ title: e.message || '设置失败', icon: 'none' })
            }
          },
        })
      },
    })
  },

  onUnbindEducationEmailTap() {
    if (!this.data.educationEmail) return
    wx.showModal({
      title: '解除教育邮箱绑定',
      content: '将向当前手机号发送验证码，确认后会恢复未认证状态。',
      success: async first => {
        if (!first.confirm) return
        try {
          const sent = await sendEducationEmailUnbindCode()
          if (sent.code) wx.showToast({ title: `演示验证码：${sent.code}`, icon: 'none', duration: 3000 })
          wx.showModal({
            title: '输入短信验证码',
            editable: true,
            placeholderText: '请输入 6 位验证码',
            success: async second => {
              if (!second.confirm) return
              await unbindEducationEmail(second.content || '')
              const user = this.data.user ? { ...this.data.user, education_email: null, campus_verified: false } : null
              if (user) { authStore.setUser(user); this.applyUser(user) }
              wx.showToast({ title: '已解除绑定', icon: 'success' })
            },
          })
        } catch (e: any) {
          wx.showToast({ title: e.message || '发送失败', icon: 'none' })
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
    })
    wx.reLaunch({ url: '/pages/login/login' })
  },

  // ============== 推荐隐私（Task 4b） ==============
  async loadRecPreference() {
    try {
      const res: any = await http.get('/users/me/recommendation-preferences')
      const prefs = res.preferences || res
      this.setData({ recEnabled: !!prefs.personalization_enabled })
    } catch (e: any) {
      console.error('加载推荐偏好失败', e)
    }
  },

  async onRecToggle(e: any) {
    const next = !!e.detail.value
    if (this.data.recLoading) return
    if (!next) {
      // 关闭前提示将清除浏览/搜索画像历史
      wx.showModal({
        title: '关闭个性化推荐',
        content: '关闭后将清除你的浏览与搜索画像历史，推荐将转为热门/最新内容。确定关闭？',
        success: async r => {
          if (r.confirm) {
            await this.updateRecPreference(false)
          }
        },
      })
      return
    }
    await this.updateRecPreference(true)
  },

  async updateRecPreference(next: boolean) {
    this.setData({ recLoading: true })
    try {
      await http.put('/users/me/recommendation-preferences', { personalization_enabled: next })
      this.setData({ recEnabled: next })
      wx.showToast({ title: next ? '已开启个性化推荐' : '已关闭个性化推荐', icon: 'success' })
    } catch (e: any) {
      wx.showToast({ title: e.message || '设置失败', icon: 'none' })
      await this.loadRecPreference()
    } finally {
      this.setData({ recLoading: false })
    }
  },

  onClearRecHistory() {
    wx.showModal({
      title: '清除推荐画像历史',
      content: '将清除全部浏览与搜索画像历史，此操作不可恢复。确定清除？',
      success: async r => {
        if (!r.confirm) return
        try {
          await http.delete('/users/me/recommendation-history')
          wx.showToast({ title: '已清除推荐画像历史', icon: 'success' })
        } catch (err: any) {
          wx.showToast({ title: err.message || '清除失败', icon: 'none' })
        }
      },
    })
  },

  // ============== tab bar 跳转 ==============
  goToHome() {
    navigateToTab('/pages/home/home')
  },

  goToMap() {
    navigateToTab('/pages/map/map')
  },

  goToPublish() {
    navigateToTab('/pages/publish/publish')
  },

  goToSearch() {
    navigateToTab('/pages/search/search')
  },

  goToNotifications() {
    wx.navigateTo({ url: '/pages/notifications/notifications' })
  },

  goToNotificationPreferences() {
    if (!this.data.isLoggedIn) {
      wx.showModal({
        title: '提示',
        content: '请先登录后再设置通知偏好',
        confirmText: '去登录',
        success: r => {
          if (r.confirm) wx.reLaunch({ url: '/pages/login/login' })
        },
      })
      return
    }
    wx.navigateTo({ url: '/pages/notification-preferences/notification-preferences' })
  },

  goToAgreement() {
    wx.navigateTo({ url: '/pages/agreement/agreement' })
  },

  goToPrivacy() {
    wx.navigateTo({ url: '/pages/privacy/privacy' })
  },

  goToAbout() {
    wx.navigateTo({ url: '/pages/about/about' })
  },

  // ============== 未登录态登录引导 ==============
  onGoLoginTap() {
    wx.navigateTo({ url: '/pages/login/login' })
  },
})
