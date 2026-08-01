import React, { useEffect, useEffectEvent, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../store/useAuthStore';
import { useCampusStore } from '../store/useCampusStore';
import { usersApi, type UserStats, type ViewHistoryItem } from '../services/users';
import { postsApi } from '../services/posts';
import { notificationsApi } from '../services/notifications';
import { schoolsApi } from '../services/schools';
import { recommendationsApi } from '../services/recommendations';
import { authApi } from '../services/auth';
import { useSwitchSchool } from '../hooks/useSchoolSync';
import type { User, Post, PostStatus, PaginatedResponse, RecommendationPreference } from '../types';
import { Card } from '../components/ui/Card';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Loading } from '../components/ui/Loading';
import { Toast } from '../components/ui/Toast';
import { NotificationPreferencesCard } from '../components/NotificationPreferencesCard';
import { SubscriptionsCard } from '../components/SubscriptionsCard';
import { logger } from '../utils/logger';
import {
  Edit,
  LogOut,
  FileText,
  LogIn,
  UserCircle,
  CheckCircle,
  X,
  Camera,
  Send,
  Trash2,
  Clock,
  AlertCircle,
  Eye,
  School as SchoolIcon,
  Star,
  RefreshCw,
  Sparkles,
  Shield,
} from 'lucide-react';

// PUB-02: 状态中文名与 Badge 样式映射（6 态状态机）
const STATUS_LABEL: Record<PostStatus, string> = {
  draft: '草稿',
  pending: '待审核',
  published: '已发布',
  expired: '已过期',
  conflict: '冲突中',
  archived: '已归档',
};

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';
const STATUS_BADGE_VARIANT: Record<PostStatus, BadgeVariant> = {
  draft: 'default',
  pending: 'warning',
  published: 'success',
  expired: 'info',
  conflict: 'danger',
  archived: 'default',
};

// PUB-02: 状态下一步动作提示
const STATUS_HINT: Record<PostStatus, string> = {
  draft: '可继续编辑或提交审核',
  pending: '管理员审核中，请耐心等待',
  published: '已公开展示',
  expired: '已过有效期，保留展示供历史回溯',
  conflict: '存在信息冲突，待管理员处理',
  archived: '已归档，不可再编辑',
};

// PUB-02: 状态分组标签页（全部 + 6 态）
type StatusFilter = PostStatus | 'all';
const STATUS_TABS: Array<{ key: StatusFilter; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'draft', label: '草稿' },
  { key: 'pending', label: '待审核' },
  { key: 'published', label: '已发布' },
  { key: 'expired', label: '已过期' },
  { key: 'conflict', label: '冲突中' },
  { key: 'archived', label: '已归档' },
];

const PAGE_SIZE = 10;
const HISTORY_PAGE_SIZE = 10;

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // PRF-01.1: 资料更新后同步刷新 useAuthStore（setUser）
  const { isAuthenticated, logout, setUser } = useAuthStore();
  // PRF-01.3: 学校/角色/默认学校来自 useCampusStore（useSchoolSync 已加载）
  const {
    memberships,
    currentSchoolId,
    currentSchoolName,
    setMemberships,
  } = useCampusStore();
  const switchSchool = useSwitchSchool();
  const [userInfo, setUserInfo] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ nickname: '', bio: '' });
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // PUB-02: 我的发布（按状态分组分页）
  const [activeStatus, setActiveStatus] = useState<StatusFilter>('all');
  const [postsPage, setPostsPage] = useState<PaginatedResponse<Post> | null>(null);
  const [postsLoading, setPostsLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  // PRF-01.2: 真实统计（来自 /users/me/stats，按当前学校过滤）
  const [stats, setStats] = useState<UserStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  // PUB-02: 审核通知（驳回原因）映射：post_id → 最新一条 audit 通知内容
  const [auditNoticeByPostId, setAuditNoticeByPostId] = useState<Record<number, string>>({});
  // PUB-02: 行内操作 loading（提交审核 / 删除）
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  // PRF-01.3: 浏览历史（按当前学校过滤）
  const [historyPage, setHistoryPage] = useState<PaginatedResponse<ViewHistoryItem> | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyCurrentPage, setHistoryCurrentPage] = useState(1);
  const [historyActionLoading, setHistoryActionLoading] = useState(false);

  // PRF-01.3: 切换默认学校 loading
  const [switchingDefaultId, setSwitchingDefaultId] = useState<number | null>(null);

  // REC-01.2: 推荐隐私偏好（个性化开关 + 清除画像历史）
  const [recPref, setRecPref] = useState<RecommendationPreference | null>(null);
  const [recPrefLoading, setRecPrefLoading] = useState(false);
  const [recToggleLoading, setRecToggleLoading] = useState(false);
  const [recClearLoading, setRecClearLoading] = useState(false);

  // FND-01.4: 函数声明移到 useEffect 之前，避免 access-before-declaration
  const loadUserInfo = async () => {
    try {
      const response = await usersApi.getCurrentUser();
      setUserInfo(response.data);
      // PRF-01.1: 同步刷新全局 auth store，避免其他页面显示旧昵称/头像
      setUser(response.data);
    } catch (error) {
      logger.error('加载用户信息失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // PRF-01.2: 拉取我的发布（按状态筛选 + 分页）
  const loadMyPosts = async (status: StatusFilter, page: number) => {
    setPostsLoading(true);
    try {
      const data = await postsApi.getMyPosts(
        page,
        PAGE_SIZE,
        status === 'all' ? undefined : status
      );
      setPostsPage(data);
    } catch (error) {
      logger.error('加载我的帖子失败:', error);
      setToast({ message: '加载我的发布失败', type: 'error' });
    } finally {
      setPostsLoading(false);
    }
  };

  // PRF-01.2: 拉取真实统计（替换原 6 次拉取计数拼凑）
  const loadStats = async () => {
    setStatsLoading(true);
    try {
      const data = await usersApi.getMyStats();
      setStats(data);
    } catch (error) {
      logger.error('加载统计失败:', error);
    } finally {
      setStatsLoading(false);
    }
  };

  // PRF-01.3: 拉取浏览历史（按当前学校过滤）
  const loadViewHistory = async (page: number) => {
    setHistoryLoading(true);
    try {
      const data = await usersApi.getMyViewHistory(page, HISTORY_PAGE_SIZE);
      setHistoryPage(data);
    } catch (error) {
      logger.error('加载浏览历史失败:', error);
    } finally {
      setHistoryLoading(false);
    }
  };

  // PUB-02: 拉取审核通知（驳回原因）
  const loadAuditNotices = async () => {
    try {
      const auditResp = await notificationsApi.getNotifications(1, 50, 'audit');
      // 审核通知：每条 target_id 只保留最新一条（接口已按 created_at desc 排序）
      const map: Record<number, string> = {};
      for (const n of auditResp.items) {
        if (n.target_type === 'post' && n.target_id != null && !(n.target_id in map)) {
          map[n.target_id] = n.content;
        }
      }
      setAuditNoticeByPostId(map);
    } catch (error) {
      logger.error('加载审核通知失败:', error);
    }
  };

  // PRF-01.3: 重新拉取 memberships（设为默认学校后立即更新 UI）
  const reloadMemberships = async () => {
    try {
      const list = await schoolsApi.listMyMemberships();
      setMemberships(list);
    } catch (error) {
      logger.error('刷新学校列表失败:', error);
    }
  };

  // REC-01.2: 加载推荐隐私偏好
  const loadRecPref = async () => {
    setRecPrefLoading(true);
    try {
      const pref = await recommendationsApi.getMyPreferences();
      setRecPref(pref);
    } catch (error) {
      logger.error('加载推荐隐私偏好失败:', error);
    } finally {
      setRecPrefLoading(false);
    }
  };

  // REC-01.2: 切换个性化推荐开关
  const handleTogglePersonalization = async (enabled: boolean) => {
    if (recToggleLoading) return;
    // 关闭前二次确认（关闭会清除浏览历史）
    if (
      !enabled &&
      !window.confirm(
        '关闭个性化推荐将清除你在所有学校的浏览历史，确定关闭吗？\n关闭后仍可使用本校热门/最新/管理员推荐。'
      )
    ) {
      return;
    }
    setRecToggleLoading(true);
    try {
      const pref = await recommendationsApi.updateMyPreferences(enabled);
      setRecPref(pref);
      setToast({
        message: enabled
          ? '已开启个性化推荐'
          : '已关闭个性化推荐，浏览历史已清除',
        type: 'success',
      });
      // 刷新首页推荐缓存与浏览历史，使新设置立即生效
      queryClient.invalidateQueries({ queryKey: ['school'] });
      await loadViewHistory(historyCurrentPage);
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({
        message: e?.response?.data?.detail || '更新失败，请重试',
        type: 'error',
      });
    } finally {
      setRecToggleLoading(false);
    }
  };

  // REC-01.2: 清除推荐画像历史（浏览 + 搜索）
  const handleClearRecHistory = async () => {
    if (recClearLoading) return;
    if (
      !window.confirm(
        `确定清除在「${currentSchoolName ?? '当前学校'}」的推荐画像历史吗？\n将清除当前学校的浏览历史与全部搜索历史，下次推荐改用冷启动。`
      )
    ) {
      return;
    }
    setRecClearLoading(true);
    try {
      const result = await recommendationsApi.clearMyHistory();
      setToast({ message: result.message || '已清除推荐画像历史', type: 'success' });
      // 刷新首页推荐缓存与浏览历史
      queryClient.invalidateQueries({ queryKey: ['school'] });
      setHistoryCurrentPage(1);
      await loadViewHistory(1);
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({
        message: e?.response?.data?.detail || '清除失败，请重试',
        type: 'error',
      });
    } finally {
      setRecClearLoading(false);
    }
  };

  const loadProfileOverview = useEffectEvent(() => {
    void loadUserInfo();
    void loadAuditNotices();
    void loadViewHistory(1);
    void loadRecPref();
  });

  useEffect(() => {
    if (!isAuthenticated) return;
    void Promise.resolve().then(loadProfileOverview);
  }, [isAuthenticated, currentSchoolId]);

  // PRF-01.2: 切换学校时重新拉取统计（统计按学校过滤）
  useEffect(() => {
    if (!isAuthenticated) return;
    void Promise.resolve().then(loadStats);
  }, [isAuthenticated, currentSchoolId]);

  // PUB-02: 状态/页码变化时重新拉取列表
  useEffect(() => {
    if (!isAuthenticated) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMyPosts(activeStatus, currentPage);
  }, [isAuthenticated, activeStatus, currentPage, currentSchoolId]);

  // PRF-01.3: 浏览历史分页变化时重新拉取
  useEffect(() => {
    if (!isAuthenticated) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadViewHistory(historyCurrentPage);
  }, [isAuthenticated, historyCurrentPage, currentSchoolId]);

  // PUB-02: 切换状态时重置到第 1 页
  const handleStatusChange = (status: StatusFilter) => {
    setActiveStatus(status);
    setCurrentPage(1);
  };

  // PUB-02: 继续编辑草稿 → 跳发布页编辑模式
  const handleContinueEdit = (postId: number) => {
    navigate(`/publish?edit=${postId}`);
  };

  // PUB-02: 提交审核（draft → pending）
  const handleSubmitReview = async (postId: number) => {
    setActionLoadingId(postId);
    try {
      await postsApi.transitionPost(postId, 'pending');
      setToast({ message: '已提交审核，可在"待审核"标签查看进度', type: 'success' });
      await loadMyPosts(activeStatus, currentPage);
      await loadStats();
      await loadAuditNotices();
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '提交审核失败', type: 'error' });
    } finally {
      setActionLoadingId(null);
    }
  };

  // PUB-02: 删除草稿（软删除，后端走 is_deleted + archived）
  const handleDeleteDraft = async (postId: number, title: string) => {
    if (!window.confirm(`确定删除草稿《${title}》吗？删除后不可恢复。`)) return;
    setActionLoadingId(postId);
    try {
      await postsApi.deletePost(postId);
      setToast({ message: '草稿已删除', type: 'success' });
      await loadMyPosts(activeStatus, currentPage);
      await loadStats();
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '删除失败', type: 'error' });
    } finally {
      setActionLoadingId(null);
    }
  };

  // PRF-01.3: 清除当前学校下的全部浏览历史
  const handleClearHistory = async () => {
    if (!window.confirm(`确定清除在「${currentSchoolName ?? '当前学校'}」的全部浏览历史吗？`)) return;
    setHistoryActionLoading(true);
    try {
      const result = await usersApi.clearMyViewHistory();
      setToast({ message: result.message || '已清除浏览历史', type: 'success' });
      setHistoryCurrentPage(1);
      await loadViewHistory(1);
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '清除失败', type: 'error' });
    } finally {
      setHistoryActionLoading(false);
    }
  };

  // PRF-01.3: 删除单条浏览历史
  const handleDeleteHistoryItem = async (postId: number) => {
    setHistoryActionLoading(true);
    try {
      await usersApi.deleteViewHistoryItem(postId);
      setToast({ message: '已删除该条浏览历史', type: 'success' });
      await loadViewHistory(historyCurrentPage);
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '删除失败', type: 'error' });
    } finally {
      setHistoryActionLoading(false);
    }
  };

  // PRF-01.3: 设为默认学校
  const handleSetDefault = async (schoolId: number, schoolName: string) => {
    setSwitchingDefaultId(schoolId);
    try {
      await schoolsApi.setDefaultSchool(schoolId);
      setToast({ message: `已将「${schoolName}」设为默认学校`, type: 'success' });
      await reloadMemberships();
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '设置默认学校失败', type: 'error' });
    } finally {
      setSwitchingDefaultId(null);
    }
  };

  // PRF-01.3: 切换到该校（不设为默认）
  const handleSwitchSchool = async (code: string) => {
    await switchSchool(code, false);
  };

  // PUB-02: 从审核通知内容中提取驳回原因（"备注：xxx" 之后的部分）
  const extractRejectReason = (postId: number): string | null => {
    const content = auditNoticeByPostId[postId];
    if (!content) return null;
    if (!content.includes('未通过审核')) return null;
    const idx = content.indexOf('备注：');
    if (idx === -1) return null;
    return content.slice(idx + 3).trim() || null;
  };

  const myPosts = useMemo(() => postsPage?.items ?? [], [postsPage]);
  const historyItems = useMemo(() => historyPage?.items ?? [], [historyPage]);

  // PRF-01.3: 按学校分组的 memberships（同校可能多条记录通常不会发生，但兜底）
  const activeMemberships = useMemo(
    () => memberships.filter((m) => m.status === 'active'),
    [memberships]
  );

  if (!isAuthenticated) {
    return (
      <div className="max-w-2xl mx-auto py-4">
        <header className="mb-5 px-1">
          <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">我的</h1>
          <p className="text-ink-muted text-sm mt-1">登录后查看个人信息</p>
        </header>
        <Card variant="elevated" padding="lg" className="text-center py-16">
          <div className="w-20 h-20 mx-auto rounded-[16px] bg-mist grid place-items-center mb-5">
            <UserCircle size={40} className="text-lake" />
          </div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">登录后查看个人信息</h3>
          <p className="text-ink-sub text-sm mb-6">登录账号，记录你的发布与足迹</p>
          <Button
            variant="primary"
            icon={<LogIn size={16} />}
            onClick={() => navigate('/login')}
          >
            去登录
          </Button>
        </Card>
      </div>
    );
  }

  // P2-005: 登出先调后端 /auth/logout（让后端有机会失效 refresh token / 写黑名单），
  // 再清本地 state；后端调用失败不阻塞前端登出（网络异常/后端宕机时仍能本地登出）
  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // 后端登出失败不阻塞本地登出（refresh token 后续自然过期）
    }
    logout();
    setToast({ message: '已退出登录', type: 'success' });
    setTimeout(() => navigate('/login'), 1000);
  };

  const handleStartEdit = () => {
    if (userInfo) {
      setEditForm({ nickname: userInfo.nickname, bio: userInfo.bio || '' });
    }
    setEditing(true);
  };

  const handleCancelEdit = () => {
    setEditing(false);
  };

  // PRF-01.1: 资料更新后同步刷新 useAuthStore（setUser）
  const handleSaveEdit = async () => {
    if (!editForm.nickname.trim()) {
      setToast({ message: '昵称不能为空', type: 'error' });
      return;
    }
    setSaving(true);
    try {
      await usersApi.updateUser({
        nickname: editForm.nickname.trim(),
        bio: editForm.bio.trim(),
      });
      await loadUserInfo();
      setEditing(false);
      setToast({ message: '资料已更新', type: 'success' });
    } catch (error) {
      logger.error('更新资料失败:', error);
      setToast({ message: '更新失败，请重试', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  // PRF-01.1: 头像更新后同步刷新 useAuthStore
  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setToast({ message: '图片大小不能超过 5MB', type: 'error' });
      return;
    }
    setAvatarUploading(true);
    try {
      await usersApi.uploadAvatar(file);
      await loadUserInfo();
      setToast({ message: '头像已更新', type: 'success' });
    } catch (error) {
      logger.error('上传头像失败:', error);
      setToast({ message: '头像上传失败', type: 'error' });
    } finally {
      setAvatarUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto py-16">
        <Loading text="加载中..." />
      </div>
    );
  }

  if (!userInfo) {
    return (
      <div className="max-w-2xl mx-auto py-6 text-center text-ink-sub">
        <p>用户信息加载失败</p>
      </div>
    );
  }

  // PRF-01.2: 真实统计来自后端（按当前学校过滤），未加载完成时显示 0
  const publishedCount = stats?.published_count ?? 0;
  const draftCount = stats?.draft_count ?? 0;
  const pendingCount = stats?.pending_count ?? 0;
  const confirmationCount = stats?.confirmation_count ?? 0;
  const totalAll = stats?.total_count ?? 0;

  const statsCards = [
    { label: '已发布', value: publishedCount, icon: <FileText size={16} />, color: 'text-lake' },
    { label: '草稿', value: draftCount, icon: <Edit size={16} />, color: 'text-ink-sub' },
    { label: '待审核', value: pendingCount, icon: <Clock size={16} />, color: 'text-sun' },
    { label: '贡献验证', value: confirmationCount, icon: <CheckCircle size={16} />, color: 'text-grass' },
  ];

  // PUB-02: 状态分组标签页徽标计数使用真实统计
  const statusCountMap: Partial<Record<PostStatus, number>> = stats
    ? {
        draft: stats.draft_count,
        pending: stats.pending_count,
        published: stats.published_count,
        expired: stats.expired_count,
        conflict: stats.conflict_count,
        archived: stats.archived_count,
      }
    : {};

  const formatHistoryDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    if (diff < 60000) return '刚刚';
    const minutes = Math.floor(diff / 60000);
    if (minutes < 60) return `${minutes} 分钟前`;
    const hours = Math.floor(diff / 3600000);
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(diff / 86400000);
    if (days < 30) return `${days} 天前`;
    return date.toLocaleDateString('zh-CN');
  };

  return (
    <div className="max-w-2xl mx-auto py-4">
      <Card variant="elevated" padding="none" className="mb-4 overflow-hidden">
        <div className="relative px-6 pt-6 pb-5 bg-gradient-to-br from-lake to-lake-light text-white overflow-hidden">
          <div className="relative flex items-center gap-4">
            <div className="relative group">
              <Avatar
                src={userInfo.avatar_url}
                fallback={userInfo.nickname?.[0] || '?'}
                size="xl"
                className="!ring-3 !ring-white/30"
              />
              {editing && (
                <button
                  type="button"
                  onClick={handleAvatarClick}
                  disabled={avatarUploading}
                  className="absolute inset-0 rounded-full bg-black/50 grid place-items-center text-white hover:bg-black/60 transition-colors disabled:opacity-50"
                  aria-label="更换头像"
                >
                  {avatarUploading ? (
                    <Loading text="" />
                  ) : (
                    <Camera size={22} />
                  )}
                </button>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleAvatarChange}
                className="hidden"
              />
            </div>
            <div className="flex-1 min-w-0">
              {editing ? (
                <input
                  type="text"
                  value={editForm.nickname}
                  onChange={e => setEditForm({ ...editForm, nickname: e.target.value })}
                  maxLength={32}
                  className="w-full mt-1 px-2 py-1 rounded-[10px] bg-white/20 text-white placeholder-white/50 border border-white/30 focus:bg-white/30 focus:outline-none font-display font-bold text-xl"
                  placeholder="昵称"
                />
              ) : (
                <h1 className="text-xl font-display font-bold mt-1 truncate">{userInfo.nickname}</h1>
              )}
              <p className="text-white/75 text-xs mt-0.5 truncate">{userInfo.email}</p>
              {editing ? (
                <textarea
                  value={editForm.bio}
                  onChange={e => setEditForm({ ...editForm, bio: e.target.value })}
                  maxLength={200}
                  rows={2}
                  className="w-full mt-2 px-2 py-1 rounded-[10px] bg-white/20 text-white placeholder-white/50 border border-white/30 focus:bg-white/30 focus:outline-none text-sm resize-none"
                  placeholder="一句话介绍自己"
                />
              ) : (
                userInfo.bio && (
                  <p className="text-white/85 text-sm mt-2 line-clamp-2">{userInfo.bio}</p>
                )
              )}
            </div>
          </div>
        </div>
        <div className="px-6 py-4 flex gap-2 bg-paper">
          {editing ? (
            <>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveEdit}
                disabled={saving}
                icon={<CheckCircle size={14} />}
              >
                {saving ? '保存中...' : '保存'}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleCancelEdit}
                icon={<X size={14} />}
              >
                取消
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleStartEdit}
                icon={<Edit size={14} />}
              >
                编辑资料
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleLogout}
                icon={<LogOut size={14} />}
              >
                退出登录
              </Button>
            </>
          )}
        </div>
      </Card>

      {/* PRF-01.2: 真实统计（按当前学校过滤） */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        {statsCards.map((stat) => (
          <div
            key={stat.label}
            className="bg-paper rounded-[14px] border border-line/60 p-3 text-center shadow-sm"
          >
            <div className={`mx-auto w-7 h-7 rounded-[8px] bg-mist grid place-items-center mb-1.5 ${stat.color}`}>
              {stat.icon}
            </div>
            <div className="font-data font-bold text-lg text-ink leading-none">
              {statsLoading ? '-' : stat.value}
            </div>
            <div className="text-[10px] text-ink-muted mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* PRF-01.3: 加入学校 / 各校角色 / 默认学校 / 切换入口 */}
      <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display font-semibold text-ink flex items-center gap-2">
            <SchoolIcon size={18} className="text-lake" />
            加入的学校
          </h2>
          <span className="text-xs text-ink-muted bg-mist px-2 py-0.5 rounded-[6px]">
            {activeMemberships.length} 所
          </span>
        </div>
        {activeMemberships.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-ink-sub text-sm mb-2">尚未加入任何学校</p>
            <p className="text-ink-muted text-xs">可在页头切换器选择学校并自动加入</p>
          </div>
        ) : (
          <div className="space-y-2">
            {activeMemberships.map((m) => {
              const isCurrent = m.school_id === currentSchoolId;
              const isDefault = m.is_default;
              const isSwitching = switchingDefaultId === m.school_id;
              return (
                <div
                  key={m.id}
                  className={`flex items-center gap-3 p-3 rounded-[10px] border transition-colors ${
                    isCurrent
                      ? 'border-lake/40 bg-lake/[0.04]'
                      : 'border-line/60 bg-paper hover:bg-paper-hover'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium text-ink text-sm truncate">
                        {m.school.name}
                      </span>
                      {isDefault && (
                        <span className="inline-flex items-center gap-0.5 text-[10px] text-sun bg-sun/10 px-1 py-0.5 rounded-[4px]">
                          <Star size={9} /> 默认
                        </span>
                      )}
                      {isCurrent && (
                        <span className="inline-flex items-center gap-0.5 text-[10px] text-lake bg-lake/10 px-1 py-0.5 rounded-[4px]">
                          当前
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-ink-muted mt-0.5 flex items-center gap-2">
                      <span>角色：{m.role === 'admin' ? '管理员' : '成员'}</span>
                      <span>·</span>
                      <span>{m.school.code}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {!isCurrent && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleSwitchSchool(m.school.code)}
                      >
                        切换
                      </Button>
                    )}
                    {!isDefault && (
                      <Button
                        variant="text"
                        size="sm"
                        disabled={isSwitching}
                        onClick={() => handleSetDefault(m.school_id, m.school.name)}
                        icon={isSwitching ? <RefreshCw size={12} className="animate-spin" /> : <Star size={12} />}
                      >
                        设为默认
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {currentSchoolName && (
          <p className="mt-3 text-[11px] text-ink-muted">
            当前学校：{currentSchoolName}（统计/帖子/浏览历史均按当前学校过滤）
          </p>
        )}
      </div>

      {/* UX-01.5: 通知偏好（7 类开关 + 每日摘要时间 + 邮件同步） */}
      <NotificationPreferencesCard />

      {/* SUB-01: 我的订阅（分类/地点/专题，按当前学校过滤） */}
      <SubscriptionsCard />

      {/* REC-01.2: 推荐隐私偏好（个性化开关 + 清除画像历史） */}
      <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display font-semibold text-ink flex items-center gap-2">
            <Sparkles size={18} className="text-lake" />
            推荐隐私
          </h2>
          {recPref && (
            <span className="text-xs text-ink-muted bg-mist px-2 py-0.5 rounded-[6px]">
              {recPref.personalization_enabled ? '已开启个性化' : '已关闭个性化'}
            </span>
          )}
        </div>

        {recPrefLoading ? (
          <div className="py-6">
            <Loading text="加载中..." />
          </div>
        ) : (
          <>
            <div className="flex items-start gap-3 p-3 rounded-[10px] bg-mist/40 border border-line/60 mb-3">
              <Shield size={16} className="text-lake flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-ink font-medium">个性化推荐</p>
                <p className="text-[11px] text-ink-muted mt-1 leading-relaxed">
                  开启后，首页"为你推荐"将基于你的浏览、搜索与订阅偏好做确定性排序；
                  关闭后将清除所有学校的浏览历史，并改用本校热门/最新/管理员推荐。
                </p>
              </div>
              {/* 开关按钮 */}
              <button
                type="button"
                role="switch"
                aria-checked={recPref?.personalization_enabled ?? true}
                disabled={recToggleLoading}
                onClick={() =>
                  handleTogglePersonalization(
                    !(recPref?.personalization_enabled ?? true)
                  )
                }
                className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors duration-200 focus:outline-none disabled:opacity-60 ${
                  recPref?.personalization_enabled
                    ? 'bg-lake'
                    : 'bg-ink-muted/40'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-200 ${
                    recPref?.personalization_enabled
                      ? 'translate-x-5'
                      : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-[10px] border border-line/60">
              <Trash2 size={16} className="text-ink-sub flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-ink font-medium">清除推荐画像历史</p>
                <p className="text-[11px] text-ink-muted mt-1 leading-relaxed">
                  清除当前学校的浏览历史与全部搜索历史，下次推荐改用冷启动。
                  个性化开关不受影响。
                </p>
              </div>
              <Button
                variant="text"
                size="sm"
                disabled={recClearLoading}
                onClick={handleClearRecHistory}
                icon={<Trash2 size={12} />}
              >
                清除
              </Button>
            </div>
          </>
        )}
      </div>

      {/* PRF-01.3: 浏览历史（按当前学校过滤） */}
      <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display font-semibold text-ink flex items-center gap-2">
            <Eye size={18} className="text-lake" />
            浏览历史
          </h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-muted bg-mist px-2 py-0.5 rounded-[6px]">
              {historyPage?.total ?? 0} 条
            </span>
            {historyItems.length > 0 && (
              <Button
                variant="text"
                size="sm"
                disabled={historyActionLoading}
                onClick={handleClearHistory}
                icon={<Trash2 size={12} />}
              >
                清除
              </Button>
            )}
          </div>
        </div>
        {historyLoading ? (
          <div className="py-8">
            <Loading text="加载中..." />
          </div>
        ) : historyItems.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-[36px] leading-none mb-2">👁</div>
            <p className="text-ink-sub text-sm">暂无浏览历史</p>
            <p className="text-ink-muted text-xs mt-1">浏览帖子详情后将在此显示</p>
          </div>
        ) : (
          <>
            <div className="space-y-0">
              {historyItems.map((item, idx) => (
                <div
                  key={item.id}
                  className={`py-2.5 -mx-2 px-2 rounded-[10px] hover:bg-paper-hover transition-colors ${
                    idx > 0 ? 'border-t border-ink-divider/60' : ''
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <h3
                      className="font-medium text-ink text-sm line-clamp-1 flex-1 min-w-0 cursor-pointer hover:text-lake"
                      onClick={() => navigate(`/posts/${item.post_id}`)}
                    >
                      {item.title}
                    </h3>
                    <Badge variant={STATUS_BADGE_VARIANT[item.status as PostStatus] ?? 'default'}>
                      {STATUS_LABEL[item.status as PostStatus] ?? item.status}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-ink-muted flex items-center gap-1.5">
                      <Clock size={11} />
                      {formatHistoryDate(item.viewed_at)}
                      {item.category_name && <span>· {item.category_name}</span>}
                      {item.location_name && <span>· {item.location_name}</span>}
                    </span>
                    <Button
                      variant="text"
                      size="sm"
                      disabled={historyActionLoading}
                      onClick={() => handleDeleteHistoryItem(item.post_id)}
                      icon={<X size={11} />}
                    >
                      删除
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            {historyPage && historyPage.total_pages > 1 && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={historyCurrentPage <= 1 || historyLoading}
                  onClick={() => setHistoryCurrentPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </Button>
                <span className="text-xs text-ink-muted">
                  {historyCurrentPage} / {historyPage.total_pages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!historyPage.has_more || historyLoading}
                  onClick={() => setHistoryCurrentPage((p) => p + 1)}
                >
                  下一页
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display font-semibold text-ink flex items-center gap-2">
            <FileText size={18} className="text-lake" />
            我的发布
          </h2>
          <span className="text-xs text-ink-muted bg-mist px-2 py-0.5 rounded-[6px]">{totalAll} 篇</span>
        </div>

        {/* PUB-02: 状态分组标签页 */}
        <div className="flex gap-1 overflow-x-auto pb-2 mb-3 -mx-1 px-1 border-b border-line/60">
          {STATUS_TABS.map((tab) => {
            const count = tab.key === 'all' ? totalAll : (statusCountMap[tab.key] ?? 0);
            const isActive = activeStatus === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => handleStatusChange(tab.key)}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-[8px] text-xs font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-lake text-white'
                    : 'text-ink-sub hover:bg-paper-hover'
                }`}
              >
                {tab.label}
                {count > 0 && (
                  <span
                    className={`text-[10px] px-1 rounded-[4px] ${
                      isActive ? 'bg-white/25' : 'bg-mist text-ink-muted'
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="space-y-0">
          {postsLoading ? (
            <div className="py-10">
              <Loading text="加载中..." />
            </div>
          ) : myPosts.length === 0 ? (
            <div className="text-center py-10">
              <div className="text-[40px] leading-none mb-3">📝</div>
              <p className="text-ink-sub text-sm">
                {activeStatus === 'all'
                  ? '还没有发布过帖子'
                  : `暂无「${STATUS_TABS.find((t) => t.key === activeStatus)?.label}」状态的帖子`}
              </p>
              <Button
                variant="text"
                size="sm"
                className="mt-3"
                onClick={() => navigate('/publish')}
              >
                去发布第一条
              </Button>
            </div>
          ) : (
            myPosts.map((post, idx) => {
              const status = post.status as PostStatus;
              const rejectReason = status === 'draft' ? extractRejectReason(post.id) : null;
              const isActioning = actionLoadingId === post.id;
              return (
                <div
                  key={post.id}
                  className={`py-3 -mx-2 px-2 rounded-[10px] transition-colors ${idx > 0 ? 'border-t border-ink-divider/60' : ''}`}
                >
                  <div className="flex items-center justify-between mb-1 gap-2">
                    <h3
                      className="font-medium text-ink text-sm line-clamp-1 flex-1 min-w-0 cursor-pointer hover:text-lake"
                      onClick={() => {
                        // 草稿/待审核对公众不可见，作者点标题进编辑或详情
                        if (status === 'draft') {
                          handleContinueEdit(post.id);
                        } else {
                          navigate(`/posts/${post.id}`);
                        }
                      }}
                    >
                      {post.title}
                    </h3>
                    <Badge variant={STATUS_BADGE_VARIANT[status] ?? 'default'}>
                      {STATUS_LABEL[status] ?? post.status}
                    </Badge>
                  </div>
                  <p className="text-ink-sub text-xs line-clamp-2">{post.content}</p>

                  {/* PUB-02: 驳回原因（草稿状态下展示最近一次审核驳回备注） */}
                  {rejectReason && (
                    <div className="mt-2 flex items-start gap-1.5 text-[11px] text-danger bg-danger/5 border border-danger/15 rounded-[8px] px-2 py-1.5">
                      <AlertCircle size={12} className="flex-shrink-0 mt-[1px]" />
                      <span className="line-clamp-2">审核未通过：{rejectReason}</span>
                    </div>
                  )}

                  {/* PUB-02: 状态提示与下一步动作 */}
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className="text-[11px] text-ink-muted flex items-center gap-1">
                      <Clock size={11} />
                      {STATUS_HINT[status]}
                    </span>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {status === 'draft' && (
                        <>
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={isActioning}
                            onClick={() => handleContinueEdit(post.id)}
                            icon={<Edit size={12} />}
                          >
                            继续编辑
                          </Button>
                          <Button
                            variant="primary"
                            size="sm"
                            disabled={isActioning}
                            onClick={() => handleSubmitReview(post.id)}
                            icon={<Send size={12} />}
                          >
                            提交审核
                          </Button>
                          <Button
                            variant="text"
                            size="sm"
                            disabled={isActioning}
                            onClick={() => handleDeleteDraft(post.id, post.title)}
                            icon={<Trash2 size={12} />}
                          >
                            删除
                          </Button>
                        </>
                      )}
                      {status === 'pending' && (
                        <span className="text-[11px] text-sun">审核中…</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* PUB-02: 分页 */}
        {postsPage && postsPage.total_pages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={currentPage <= 1 || postsLoading}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            >
              上一页
            </Button>
            <span className="text-xs text-ink-muted">
              {currentPage} / {postsPage.total_pages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={!postsPage.has_more || postsLoading}
              onClick={() => setCurrentPage((p) => p + 1)}
            >
              下一页
            </Button>
          </div>
        )}
      </div>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};

export default ProfilePage;
