import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { postsApi } from '../services/posts';
import { commentsApi } from '../services/comments';
import { interactionsApi } from '../services/interactions';
import { governanceApi } from '../services/governance';
import type {
  Post,
  Comment,
  ReportType,
  ValidationType,
  ChangeReportType,
  ChangeReportStatus,
  GovernanceSummary,
  ChangeReport,
} from '../types';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Loading } from '../components/ui/Loading';
import { Toast } from '../components/ui/Toast';
import { useAuthStore } from '../store/useAuthStore';
import { useCampusStore } from '../store/useCampusStore';
import {
  Heart,
  MessageCircle,
  Eye,
  MapPin,
  Clock,
  Flag,
  CheckCircle2,
  XCircle,
  X,
  AlertTriangle,
  RefreshCw,
  FileWarning,
  Image as ImageIcon,
  Phone,
  ChevronLeft,
  ChevronRight,
  CornerDownRight,
  Share2,
  Link2,
  Navigation,
  Copy,
  Check,
} from 'lucide-react';
import { logger } from '../utils/logger';
import { formatDateTime, formatRelativeTime as formatDate } from '../utils/date';

// FND-01.1: 举报类型与后端 ReportType 枚举对齐（spam/abuse/harassment/false_info/other）
const REPORT_OPTIONS: Array<{ value: ReportType; label: string }> = [
  { value: 'spam', label: '垃圾信息' },
  { value: 'abuse', label: '滥用' },
  { value: 'harassment', label: '骚扰' },
  { value: 'false_info', label: '虚假信息' },
  { value: 'other', label: '其他' },
];

const STATUS_BADGE_CONFIG: Record<string, { variant: 'default' | 'success' | 'warning' | 'danger' | 'info'; label: string }> = {
  draft: { variant: 'default', label: '草稿' },
  pending: { variant: 'warning', label: '待审核' },
  published: { variant: 'success', label: '已发布' },
  expired: { variant: 'default', label: '已过期' },
  conflict: { variant: 'danger', label: '冲突中' },
  archived: { variant: 'default', label: '已归档' },
};

const VALIDATION_OPTIONS: Array<{
  type: ValidationType;
  label: string;
  activeLabel: string;
  icon: React.ReactNode;
  color: string;
  activeClass: string;
}> = [
  {
    type: 'confirmation',
    label: '证实',
    activeLabel: '已证实',
    icon: <CheckCircle2 size={14} />,
    color: 'text-grass',
    activeClass: 'bg-grass text-white border-grass',
  },
  {
    type: 'refutation',
    label: '证伪',
    activeLabel: '已证伪',
    icon: <XCircle size={14} />,
    color: 'text-danger',
    activeClass: 'bg-danger text-white border-danger',
  },
];

// GOV-01: 3 类问题报告（update/expiration_report/conflict_report）
const CHANGE_REPORT_OPTIONS: Array<{ value: ChangeReportType; label: string; hint: string }> = [
  { value: 'update', label: '更新建议', hint: '提供更新的信息' },
  { value: 'expiration_report', label: '过期报告', hint: '报告信息已过期' },
  { value: 'conflict_report', label: '冲突报告', hint: '报告与其他信息冲突' },
];

const CHANGE_REPORT_STATUS_CONFIG: Record<ChangeReportStatus, { variant: 'default' | 'success' | 'warning' | 'danger' | 'info'; label: string }> = {
  open: { variant: 'warning', label: '待处理' },
  in_review: { variant: 'info', label: '处理中' },
  resolved: { variant: 'success', label: '已解决' },
  dismissed: { variant: 'default', label: '已驳回' },
};

const LOST_TYPE_LABELS: Record<string, string> = {
  lost: '丢失',
  found: '招领',
};

// 计算距离过期还剩多久（用于有效期倒计时展示）
function formatExpireCountdown(expireAt?: string): { text: string; expired: boolean } | null {
  if (!expireAt) return null;
  const target = new Date(expireAt);
  if (Number.isNaN(target.getTime())) return null;
  const now = new Date();
  const diff = target.getTime() - now.getTime();
  if (diff <= 0) return { text: '已过期', expired: true };
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  if (days > 0) return { text: `${days}天 ${hours}小时后过期`, expired: false };
  if (hours > 0) return { text: `${hours}小时 ${minutes}分钟后过期`, expired: false };
  return { text: `${minutes}分钟后过期`, expired: false };
}

const PostDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { isAuthenticated, user } = useAuthStore();
  const [post, setPost] = useState<Post | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [commentText, setCommentText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);
  const [showReportForm, setShowReportForm] = useState(false);
  const [reportType, setReportType] = useState<ReportType>('spam');
  const [reportDescription, setReportDescription] = useState('');
  const [reporting, setReporting] = useState(false);
  // GOV-01: 3 类问题报告状态
  const [showChangeReportForm, setShowChangeReportForm] = useState(false);
  const [changeReportType, setChangeReportType] = useState<ChangeReportType>('update');
  const [changeReportDescription, setChangeReportDescription] = useState('');
  const [changeReportEvidence, setChangeReportEvidence] = useState('');
  const [submittingChangeReport, setSubmittingChangeReport] = useState(false);
  const [handlingReportId, setHandlingReportId] = useState<number | null>(null);
  // DSC-02.1: 图片轮播
  const [activeImageIndex, setActiveImageIndex] = useState(0);
  // DSC-02.1: 评论回复表单（按 comment.id 维护一个输入框；为 null 表示未在回复任何评论）
  const [replyTarget, setReplyTarget] = useState<{ comment: Comment } | null>(null);
  const [replyText, setReplyText] = useState('');
  // UX-01.2 / UX-01.3: 复制成功反馈态
  const [copiedField, setCopiedField] = useState<'address' | 'link' | null>(null);
  // UX-01.3: 是否支持原生分享
  const [canNativeShare, setCanNativeShare] = useState(false);
  // UX-01.2: 外部地图导航菜单展开
  const [showNavMenu, setShowNavMenu] = useState(false);
  // 当前学校 code（用于构造分享 URL 含 school_code）
  const currentSchoolCode = useCampusStore((s) => s.currentSchoolCode);

  const loadPost = async () => {
    try {
      const response = await postsApi.getPost(Number(id));
      setPost(response as Post);
    } catch (error) {
      logger.error('加载帖子失败:', error);
      setToast({ message: '加载帖子失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const loadComments = async () => {
    try {
      const response = await commentsApi.getComments(Number(id));
      setComments(response.items || []);
    } catch (error) {
      logger.error('加载评论失败:', error);
    }
  };

  // DSC-02.1: 评论接口本身不要求登录（公开可见），游客也可调用
  // 验证统计 / 问题报告列表 已聚合在 post.governance 中（postsApi.getPost 返回），无需单独请求
  useEffect(() => {
    if (id) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void loadPost();
      void loadComments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // DSC-02.1: 从 post.governance 取聚合数据（游客/登录用户均可读，无需额外请求）
  const governance: GovernanceSummary | null = post?.governance ?? null;
  const changeReports: ChangeReport[] = governance?.recent_change_reports ?? [];
  const changeReportsOpen = governance?.change_reports_open ?? 0;
  const userValidationType = governance?.user_validation_type ?? null;
  const totalValidations = governance?.total_validation_count ?? 0;
  const confirmCount = governance?.confirmation_count ?? 0;
  const refuteCount = governance?.refutation_count ?? 0;
  const confirmPercent = totalValidations > 0 ? Math.round((confirmCount / totalValidations) * 100) : 0;
  const refutePercent = totalValidations > 0 ? Math.round((refuteCount / totalValidations) * 100) : 0;

  const expireCountdown = useMemo(() => formatExpireCountdown(post?.expire_at), [post?.expire_at]);

  const handleValidate = async (type: ValidationType) => {
    if (!isAuthenticated) {
      setToast({ message: '请先登录后再进行验证', type: 'warning' });
      return;
    }
    const current = userValidationType;
    try {
      await interactionsApi.validatePost(Number(id), type);
      if (current === type) {
        setToast({ message: '已取消验证', type: 'info' });
      } else if (current) {
        setToast({ message: '已切换验证', type: 'success' });
      } else {
        setToast({ message: '验证已提交', type: 'success' });
      }
      void loadPost();
    } catch {
      setToast({ message: '验证失败', type: 'error' });
    }
  };

  const handleLike = async () => {
    if (!isAuthenticated) {
      setToast({ message: '请先登录', type: 'warning' });
      return;
    }
    try {
      await interactionsApi.likePost(Number(id));
      void loadPost();
    } catch {
      setToast({ message: '操作失败', type: 'error' });
    }
  };

  const handleComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      setToast({ message: '请先登录', type: 'warning' });
      return;
    }
    if (!commentText.trim()) {
      setToast({ message: '请输入评论内容', type: 'warning' });
      return;
    }
    try {
      setSubmitting(true);
      await commentsApi.createComment(Number(id), commentText);
      setCommentText('');
      void loadComments();
      void loadPost();
      setToast({ message: '评论成功', type: 'success' });
    } catch {
      setToast({ message: '评论失败', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  // DSC-02.1: 回复评论（嵌套回复，统一挂在父评论下）
  const handleReply = async (parent: Comment) => {
    if (!isAuthenticated) {
      setToast({ message: '请先登录', type: 'warning' });
      return;
    }
    if (!replyText.trim()) {
      setToast({ message: '请输入回复内容', type: 'warning' });
      return;
    }
    try {
      setSubmitting(true);
      await commentsApi.createComment(
        Number(id),
        replyText,
        parent.parent_id ?? parent.id, // 已是子评论时仍挂在同一顶级父评论下
        parent.user_id // 被回复者：当前所点评论的作者
      );
      setReplyText('');
      setReplyTarget(null);
      void loadComments();
      void loadPost();
      setToast({ message: '回复成功', type: 'success' });
    } catch {
      setToast({ message: '回复失败', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleReport = async () => {
    if (!isAuthenticated) {
      setToast({ message: '请先登录后再举报', type: 'warning' });
      return;
    }
    if (!reportDescription.trim()) {
      setToast({ message: '请填写举报描述', type: 'warning' });
      return;
    }
    try {
      setReporting(true);
      await interactionsApi.reportPost(Number(id), reportType, reportDescription.trim());
      setToast({ message: '举报已提交，管理员将尽快处理', type: 'success' });
      setShowReportForm(false);
      setReportDescription('');
      setReportType('spam');
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      const msg = err?.response?.data?.detail || '举报失败，请稍后重试';
      setToast({ message: msg, type: 'error' });
    } finally {
      setReporting(false);
    }
  };

  // GOV-01: 提交问题报告（update/expiration_report/conflict_report）
  const handleSubmitChangeReport = async () => {
    if (!isAuthenticated) {
      setToast({ message: '请先登录后再提交报告', type: 'warning' });
      return;
    }
    if (!changeReportDescription.trim()) {
      setToast({ message: '请填写报告说明', type: 'warning' });
      return;
    }
    try {
      setSubmittingChangeReport(true);
      await governanceApi.createChangeReport(
        Number(id),
        changeReportType,
        changeReportDescription.trim(),
        changeReportEvidence.trim() || undefined
      );
      setToast({ message: '问题报告已提交', type: 'success' });
      setShowChangeReportForm(false);
      setChangeReportDescription('');
      setChangeReportEvidence('');
      setChangeReportType('update');
      void loadPost();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      const msg = err?.response?.data?.detail || '提交报告失败，请稍后重试';
      setToast({ message: msg, type: 'error' });
    } finally {
      setSubmittingChangeReport(false);
    }
  };

  // GOV-01: 处理问题报告（作者：仅 resolved；管理员：全部状态）
  const handleChangeReportStatus = async (
    reportId: number,
    targetStatus: ChangeReportStatus,
    reason?: string
  ) => {
    try {
      setHandlingReportId(reportId);
      await governanceApi.handleChangeReport(reportId, targetStatus, reason);
      setToast({ message: '报告状态已更新', type: 'success' });
      void loadPost();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      const msg = err?.response?.data?.detail || '处理报告失败，请稍后重试';
      setToast({ message: msg, type: 'error' });
    } finally {
      setHandlingReportId(null);
    }
  };

  // ============ UX-01.2 / UX-01.3: 复制地址 / 深链接 / 外部地图导航 / 原生分享 ============

  // UX-01.3: 挂载时检测 navigator.canShare() 与 navigator.share 是否可用
  useEffect(() => {
    if (typeof navigator !== 'undefined' && typeof (navigator as Navigator & { canShare?: (data?: ShareData) => boolean }).canShare === 'function') {
      setCanNativeShare(true);
    } else {
      setCanNativeShare(false);
    }
  }, []);

  // UX-01.2: 复制地点名称（带建筑物/楼层信息）到剪贴板
  const handleCopyAddress = async () => {
    if (!post?.location) {
      setToast({ message: '该帖子未关联地点', type: 'warning' });
      return;
    }
    const parts: string[] = [post.location.name];
    if (post.location.building) parts.push(post.location.building);
    if (post.location.floor) parts.push(`${post.location.floor} 层`);
    const text = parts.join(' · ');
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField('address');
      setToast({ message: '地点已复制到剪贴板', type: 'success' });
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      setToast({ message: '复制失败，请手动选择文本复制', type: 'error' });
    }
  };

  // UX-01.2 / UX-01.3: 构造含 school_code + post_id 的深链接（用于分享与复制）
  const buildShareUrl = () => {
    if (!post) return '';
    const schoolCode = currentSchoolCode ?? 'default';
    const base = window.location.origin;
    return `${base}/posts/${post.id}?school=${encodeURIComponent(schoolCode)}`;
  };

  // UX-01.2: 复制深链接
  const handleCopyLink = async () => {
    const url = buildShareUrl();
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopiedField('link');
      setToast({ message: '深链接已复制，可粘贴到其他应用', type: 'success' });
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      setToast({ message: '复制失败，请手动复制地址栏', type: 'error' });
    }
  };

  // UX-01.2: 调用外部地图导航（高德/百度/Google），未提供坐标时回退文字路径
  const handleOpenExternalMap = (provider: 'amap' | 'baidu' | 'google') => {
    if (!post?.location) {
      setToast({ message: '该帖子未关联地点，无法导航', type: 'warning' });
      return;
    }
    const loc = post.location;
    // 地图不可用回退：仅复制地点名 + 提示用户手动搜索
    if (loc.latitude == null || loc.longitude == null) {
      const text = `${loc.name}${loc.building ? ` · ${loc.building}` : ''}${loc.floor ? ` · ${loc.floor}层` : ''}`;
      void navigator.clipboard?.writeText(text).catch(() => undefined);
      setToast({
        message: `该地点无坐标，已复制名称：「${text}」，请到地图 App 搜索`,
        type: 'info',
      });
      setShowNavMenu(false);
      return;
    }
    const { latitude, longitude } = loc;
    let url = '';
    switch (provider) {
      case 'amap':
        url = `https://uri.amap.com/marker?position=${longitude},${latitude}&name=${encodeURIComponent(loc.name)}`;
        break;
      case 'baidu':
        url = `https://api.map.baidu.com/marker?location=${latitude},${longitude}&title=${encodeURIComponent(loc.name)}&output=html`;
        break;
      case 'google':
        url = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
        break;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
    setShowNavMenu(false);
  };

  // UX-01.3: 系统原生分享（canShare 检测通过后调用），失败回退复制链接
  const handleNativeShare = async () => {
    const url = buildShareUrl();
    if (!url || !post) return;
    const shareData: ShareData = {
      title: post.title,
      text: post.content.slice(0, 80) + (post.content.length > 80 ? '…' : ''),
      url,
    };
    try {
      if (canNativeShare && typeof navigator.share === 'function') {
        const canShareResult = (navigator as Navigator & { canShare?: (data?: ShareData) => boolean }).canShare?.(shareData);
        if (canShareResult === false) {
          // 浏览器判定不可分享此数据：回退复制链接
          await handleCopyLink();
          return;
        }
        await navigator.share(shareData);
        setToast({ message: '已通过系统分享', type: 'success' });
      } else {
        // 不支持原生分享：回退复制链接
        await handleCopyLink();
      }
    } catch (err: unknown) {
      const e = err as { name?: string };
      // 用户主动取消分享不提示错误
      if (e?.name === 'AbortError') return;
      // 其他错误回退复制链接
      await handleCopyLink();
    }
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto py-16">
        <Loading text="加载中..." />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center">
        <div className="text-5xl mb-4">⌖</div>
        <p className="font-medium text-ink mb-1.5">这条信息不存在或已失效</p>
        <p className="text-sm text-ink-muted">可能已被发布者删除，或链接有误。</p>
      </div>
    );
  }

  // DSC-02.1: 图片轮播
  const images = post.images ?? [];
  const activeImage = images[activeImageIndex];

  return (
    <div className="max-w-2xl mx-auto py-4">
      {/* 长卷主容器 */}
      <article className="bg-paper rounded-[16px] border border-line/60 shadow-md overflow-hidden">
        {/* 标题区 */}
        <header className="px-6 pt-6 pb-5">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <Badge>{post.category?.name || '未分类'}</Badge>
            {post.status && STATUS_BADGE_CONFIG[post.status] && (
              <Badge variant={STATUS_BADGE_CONFIG[post.status].variant}>
                {STATUS_BADGE_CONFIG[post.status].label}
              </Badge>
            )}
            {post.lost_type && LOST_TYPE_LABELS[post.lost_type] && (
              <Badge variant="warning">{LOST_TYPE_LABELS[post.lost_type]}</Badge>
            )}
            <span className="text-xs text-ink-muted flex items-center gap-1 ml-auto">
              <Clock size={12} />
              {formatDate(post.created_at)}
            </span>
          </div>

          <h1 className="font-display font-bold text-[24px] md:text-[28px] leading-[1.3] text-ink mb-4">
            {post.title}
          </h1>

          <div className="flex items-center gap-3">
            <Avatar
              src={post.author?.avatar_url}
              fallback={post.author?.nickname?.[0] || '?'}
              size="sm"
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-ink">
                {post.author?.nickname || '匿名用户'}
              </div>
              <div className="text-xs text-ink-muted flex items-center gap-1">
                <MapPin size={11} />
                {post.location?.name || '未知地点'}
              </div>
            </div>
          </div>
        </header>

        {/* 墨线分隔 */}
        <div className="mx-6 border-t border-ink-divider" />

        {/* DSC-02.1: 图片轮播 */}
        {images.length > 0 && (
          <>
            <div className="px-6 py-4">
              <div className="relative rounded-[12px] overflow-hidden border border-line/60 bg-paper-hover">
                <div className="aspect-[4/3] bg-mist flex items-center justify-center">
                  {activeImage ? (
                    <img
                      src={activeImage.image_url}
                      alt={`${post.title} 图片 ${activeImageIndex + 1}`}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <ImageIcon size={40} className="text-ink-muted" />
                  )}
                </div>
                {images.length > 1 && (
                  <>
                    <button
                      type="button"
                      onClick={() => setActiveImageIndex((idx) => (idx - 1 + images.length) % images.length)}
                      className="absolute left-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-paper/80 border border-line/60 text-ink hover:bg-paper transition-colors"
                      aria-label="上一张"
                    >
                      <ChevronLeft size={16} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveImageIndex((idx) => (idx + 1) % images.length)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-full bg-paper/80 border border-line/60 text-ink hover:bg-paper transition-colors"
                      aria-label="下一张"
                    >
                      <ChevronRight size={16} />
                    </button>
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 px-2.5 py-1 rounded-full bg-ink/60 text-paper text-xs font-data">
                      {activeImageIndex + 1} / {images.length}
                    </div>
                  </>
                )}
              </div>
              {images.length > 1 && (
                <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
                  {images.map((img, idx) => (
                    <button
                      key={img.id}
                      type="button"
                      onClick={() => setActiveImageIndex(idx)}
                      className={`flex-shrink-0 w-16 h-16 rounded-[8px] overflow-hidden border-2 transition-all ${
                        idx === activeImageIndex ? 'border-lake' : 'border-line/40 hover:border-line'
                      }`}
                      aria-label={`查看第 ${idx + 1} 张图片`}
                    >
                      <img src={img.image_url} alt="" className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="mx-6 border-t border-ink-divider" />
          </>
        )}

        {/* DSC-02.1: 元信息条：有效期倒计时 + 活动时间 + 联系方式 */}
        <div className="px-6 py-4 space-y-2.5">
          {expireCountdown && (
            <div className="flex items-center gap-2 text-sm">
              <Clock size={14} className={expireCountdown.expired ? 'text-ink-muted' : 'text-[#b89230]'} />
              <span className="text-ink-muted">有效期：</span>
              <span className={`font-medium ${expireCountdown.expired ? 'text-ink-muted' : 'text-[#b89230]'}`}>
                {expireCountdown.text}
              </span>
              {post.expire_at && (
                <span className="text-xs text-ink-muted font-data">
                  （{formatDateTime(post.expire_at)}）
                </span>
              )}
            </div>
          )}
          {/* DSC-02.1: 联系方式仅登录用户可见（后端对游客返回 null） */}
          {post.contact_info && (
            <div className="flex items-center gap-2 text-sm">
              <Phone size={14} className="text-grass" />
              <span className="text-ink-muted">联系方式：</span>
              <span className="font-data text-ink break-all">{post.contact_info}</span>
            </div>
          )}
          {!isAuthenticated && (
            <div className="text-xs text-ink-muted/80 bg-paper-hover rounded-[8px] px-3 py-2 inline-block">
              登录后可查看联系方式、参与投票与评论
            </div>
          )}
        </div>

        <div className="mx-6 border-t border-ink-divider" />

        {/* 统计与验证条 */}
        <div className="px-6 py-4">
          <div className="flex items-center gap-5 text-sm text-ink-muted">
            <span className="flex items-center gap-1.5">
              <Eye size={15} />
              <span className="font-data font-bold text-ink">{post.view_count || 0}</span>
              <span className="hidden sm:inline">浏览</span>
            </span>
            <span className="flex items-center gap-1.5">
              <Heart size={15} />
              <span className="font-data font-bold text-ink">{post.like_count || 0}</span>
              <span className="hidden sm:inline">赞</span>
            </span>
            <span className="flex items-center gap-1.5">
              <MessageCircle size={15} />
              <span className="font-data font-bold text-ink">{post.comment_count || 0}</span>
              <span className="hidden sm:inline">评论</span>
            </span>
          </div>

          {totalValidations > 0 && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-ink-muted flex items-center gap-1">
                  <CheckCircle2 size={12} className="text-grass" />
                  协同验证
                </span>
                <span className="text-ink-muted">
                  {totalValidations} 人参与
                  {governance?.validity_status === 'valid' && <span className="text-grass ml-1">· 有效</span>}
                  {governance?.validity_status === 'invalid' && <span className="text-danger ml-1">· 无效</span>}
                  {governance?.validity_status === 'uncertain' && <span className="text-[#b89230] ml-1">· 待定</span>}
                </span>
              </div>
              <div className="h-2 bg-mist rounded-full overflow-hidden flex gap-0">
                <div
                  className="bg-grass h-full transition-all duration-500"
                  style={{ width: `${confirmPercent}%` }}
                />
                <div
                  className="bg-danger h-full transition-all duration-500"
                  style={{ width: `${refutePercent}%` }}
                />
              </div>
              <div className="flex justify-between text-xs mt-1">
                <span className="text-grass font-medium font-data">{confirmCount} 证实</span>
                <span className="text-danger font-medium font-data">{refuteCount} 证伪</span>
              </div>
            </div>
          )}

          {/* DSC-02.1: 投票按钮仅登录用户可见，且作者不可给自己投票（后端会返回 403） */}
          {isAuthenticated && (
            <div className="flex flex-wrap gap-2 mt-4">
              {VALIDATION_OPTIONS.map(opt => {
                const isActive = userValidationType === opt.type;
                return (
                  <button
                    key={opt.type}
                    onClick={() => handleValidate(opt.type)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[10px] text-xs font-medium border transition-all ${
                      isActive
                        ? opt.activeClass
                        : `bg-paper border-line ${opt.color} hover:bg-paper-hover`
                    }`}
                  >
                    {opt.icon}
                    {isActive ? opt.activeLabel : opt.label}
                  </button>
                );
              })}
              {userValidationType && (
                <span className="text-xs text-ink-muted self-center ml-1">
                  · 再点一次取消
                </span>
              )}
            </div>
          )}
        </div>

        {/* 墨线分隔 */}
        <div className="mx-6 border-t border-ink-divider" />

        {/* 正文内容 */}
        <div className="px-6 py-5">
          <div className="content-paper rounded-[10px] px-5 py-4 -mx-0.5">
            <p className="text-[15px] text-ink leading-[1.8] whitespace-pre-wrap">{post.content}</p>
          </div>
        </div>

        {/* 底部操作栏 */}
        <div className="px-6 py-4 border-t border-ink-divider flex flex-wrap gap-2 items-center">
          {isAuthenticated && (
            <Button
              variant={post.is_liked ? 'danger' : 'primary'}
              size="sm"
              onClick={handleLike}
              icon={<Heart size={14} fill={post.is_liked ? 'currentColor' : 'none'} />}
            >
              {post.is_liked ? '已点赞' : '点赞'}
            </Button>
          )}

          {/* UX-01.2: 复制地点地址 */}
          <Button
            variant="secondary"
            size="sm"
            onClick={handleCopyAddress}
            icon={copiedField === 'address' ? <Check size={14} /> : <Copy size={14} />}
            disabled={!post.location}
          >
            {copiedField === 'address' ? '已复制' : '复制地址'}
          </Button>

          {/* UX-01.2: 复制深链接（含 school_code + post_id） */}
          <Button
            variant="secondary"
            size="sm"
            onClick={handleCopyLink}
            icon={copiedField === 'link' ? <Check size={14} /> : <Link2 size={14} />}
          >
            {copiedField === 'link' ? '已复制' : '复制链接'}
          </Button>

          {/* UX-01.2: 外部地图导航（含菜单） */}
          <div className="relative">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowNavMenu((v) => !v)}
              icon={<Navigation size={14} />}
              disabled={!post.location}
              aria-haspopup="menu"
              aria-expanded={showNavMenu}
            >
              导航
            </Button>
            {showNavMenu && (
              <>
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setShowNavMenu(false)}
                  aria-hidden="true"
                />
                <div
                  className="absolute right-0 mt-1 z-40 bg-paper rounded-[10px] border border-line shadow-lg py-1 min-w-[140px]"
                  role="menu"
                >
                  <button
                    type="button"
                    onClick={() => handleOpenExternalMap('amap')}
                    className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-paper-hover transition-colors"
                    role="menuitem"
                  >
                    高德地图
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenExternalMap('baidu')}
                    className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-paper-hover transition-colors"
                    role="menuitem"
                  >
                    百度地图
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenExternalMap('google')}
                    className="w-full text-left px-3 py-2 text-sm text-ink hover:bg-paper-hover transition-colors"
                    role="menuitem"
                  >
                    Google 地图
                  </button>
                </div>
              </>
            )}
          </div>

          {/* UX-01.3: 系统原生分享（不支持时回退复制链接） */}
          <Button
            variant="secondary"
            size="sm"
            onClick={handleNativeShare}
            icon={<Share2 size={14} />}
          >
            {canNativeShare ? '分享' : '复制链接'}
          </Button>

          {isAuthenticated && (
            <Button
              variant="text"
              size="sm"
              icon={<Flag size={14} />}
              onClick={() => setShowReportForm(!showReportForm)}
            >
              举报
            </Button>
          )}
        </div>

        {/* 举报表单 */}
        {showReportForm && isAuthenticated && (
          <div className="mx-6 mb-4 p-4 bg-paper-hover rounded-[10px] border border-line/80">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-display font-bold text-sm text-lake">举报这条信息</h3>
              <button
                onClick={() => setShowReportForm(false)}
                className="text-ink-muted hover:text-ink transition-colors"
                aria-label="关闭举报表单"
              >
                <X size={16} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-ink-muted mb-1.5">举报类型</label>
                <div className="flex flex-wrap gap-2">
                  {REPORT_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setReportType(opt.value)}
                      className={`px-3 py-1.5 rounded-[10px] text-xs font-medium border transition-all ${
                        reportType === opt.value
                          ? 'bg-lake text-white border-lake'
                          : 'bg-paper border-line text-ink-sub hover:bg-paper-hover'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs text-ink-muted mb-1.5">举报描述</label>
                <textarea
                  value={reportDescription}
                  onChange={(e) => setReportDescription(e.target.value)}
                  placeholder="请详细描述举报原因..."
                  className="w-full px-3 py-2 text-sm bg-paper border border-line rounded-[10px] resize-none focus:outline-none focus:border-lake transition-colors"
                  rows={3}
                  maxLength={500}
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="text"
                  size="sm"
                  onClick={() => setShowReportForm(false)}
                >
                  取消
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleReport}
                  loading={reporting}
                  disabled={!reportDescription.trim()}
                >
                  提交举报
                </Button>
              </div>
            </div>
          </div>
        )}
      </article>

      {/* GOV-01: 协同治理 — 3 类问题报告（update/expiration_report/conflict_report） */}
      <section className="bg-paper rounded-[16px] border border-line/60 shadow-md mt-4 overflow-hidden">
        <div className="px-6 pt-5 pb-3 flex items-center justify-between">
          <h2 className="font-display font-bold text-lg text-lake flex items-center gap-2">
            <FileWarning size={18} />
            问题报告
            <span className="font-data text-ink-muted text-sm">
              ({changeReports.length}{changeReportsOpen > 0 && ` · ${changeReportsOpen} 待处理`})
            </span>
          </h2>
          {isAuthenticated && (
            <Button
              variant="text"
              size="sm"
              icon={<AlertTriangle size={14} />}
              onClick={() => setShowChangeReportForm(!showChangeReportForm)}
            >
              提交报告
            </Button>
          )}
        </div>

        {/* 提交问题报告表单 */}
        {showChangeReportForm && isAuthenticated && (
          <div className="mx-6 mb-4 p-4 bg-paper-hover rounded-[10px] border border-line/80">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-display font-bold text-sm text-lake">提交问题报告</h3>
              <button
                onClick={() => setShowChangeReportForm(false)}
                className="text-ink-muted hover:text-ink transition-colors"
                aria-label="关闭问题报告表单"
              >
                <X size={16} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-ink-muted mb-1.5">报告类型</label>
                <div className="flex flex-wrap gap-2">
                  {CHANGE_REPORT_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setChangeReportType(opt.value)}
                      title={opt.hint}
                      className={`px-3 py-1.5 rounded-[10px] text-xs font-medium border transition-all ${
                        changeReportType === opt.value
                          ? 'bg-lake text-white border-lake'
                          : 'bg-paper border-line text-ink-sub hover:bg-paper-hover'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs text-ink-muted mb-1.5">报告说明</label>
                <textarea
                  value={changeReportDescription}
                  onChange={(e) => setChangeReportDescription(e.target.value)}
                  placeholder="请详细描述需要更新/过期/冲突的内容..."
                  className="w-full px-3 py-2 text-sm bg-paper border border-line rounded-[10px] resize-none focus:outline-none focus:border-lake transition-colors"
                  rows={3}
                  maxLength={2000}
                />
              </div>
              <div>
                <label className="block text-xs text-ink-muted mb-1.5">证据链接（可选）</label>
                <input
                  type="url"
                  value={changeReportEvidence}
                  onChange={(e) => setChangeReportEvidence(e.target.value)}
                  placeholder="https://..."
                  className="w-full h-10 px-3.5 bg-paper border border-line rounded-[10px] text-[14px] text-ink placeholder:text-ink-muted/60 transition-colors focus:outline-none focus:border-lake"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="text"
                  size="sm"
                  onClick={() => setShowChangeReportForm(false)}
                >
                  取消
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSubmitChangeReport}
                  loading={submittingChangeReport}
                  disabled={!changeReportDescription.trim()}
                >
                  提交报告
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* 报告列表（来自 post.governance.recent_change_reports，游客可见） */}
        <div className="border-t border-ink-divider">
          {changeReports.length === 0 ? (
            <div className="text-center py-10">
              <div className="text-3xl mb-2">✓</div>
              <p className="text-ink-muted text-sm">暂无问题报告</p>
            </div>
          ) : (
            <div>
              {changeReports.map((report, idx) => {
                const isAuthor = !!user && user.id === post.user_id;
                const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
                const canHandle = (isAuthor || isAdmin) && report.status !== 'resolved' && report.status !== 'dismissed';
                const statusConfig = CHANGE_REPORT_STATUS_CONFIG[report.status];
                const typeOption = CHANGE_REPORT_OPTIONS.find(o => o.value === report.report_type);
                return (
                  <div
                    key={report.id}
                    className={`px-6 py-4 ${idx > 0 ? 'border-t border-ink-divider/60' : ''}`}
                  >
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <Badge variant="info">{typeOption?.label || report.report_type}</Badge>
                      <Badge variant={statusConfig.variant}>{statusConfig.label}</Badge>
                      <span className="text-xs text-ink-muted font-data ml-auto">
                        {formatDate(report.created_at)}
                      </span>
                    </div>
                    {report.description && (
                      <p className="text-sm text-ink leading-[1.7] mb-2">{report.description}</p>
                    )}
                    {report.evidence_url && (
                      <a
                        href={report.evidence_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-lake hover:underline mb-2"
                      >
                        <RefreshCw size={11} />
                        查看证据
                      </a>
                    )}
                    <div className="flex items-center gap-3 text-xs text-ink-muted">
                      <span>报告人：{report.reporter?.nickname || '匿名'}</span>
                      {report.handler && (
                        <span>处理人：{report.handler.nickname}</span>
                      )}
                      {report.handler_note && (
                        <span className="truncate">说明：{report.handler_note}</span>
                      )}
                    </div>
                    {canHandle && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {isAuthor && (
                          <Button
                            variant="success"
                            size="sm"
                            icon={<CheckCircle2 size={12} />}
                            onClick={() => handleChangeReportStatus(report.id, 'resolved', '作者标记已处理')}
                            loading={handlingReportId === report.id}
                          >
                            标记已处理
                          </Button>
                        )}
                        {isAdmin && (
                          <>
                            {report.status === 'open' && (
                              <Button
                                variant="info"
                                size="sm"
                                onClick={() => handleChangeReportStatus(report.id, 'in_review', '管理员受理')}
                                loading={handlingReportId === report.id}
                              >
                                受理
                              </Button>
                            )}
                            <Button
                              variant="success"
                              size="sm"
                              icon={<CheckCircle2 size={12} />}
                              onClick={() => handleChangeReportStatus(report.id, 'resolved', '已解决')}
                              loading={handlingReportId === report.id}
                            >
                              解决
                            </Button>
                            <Button
                              variant="text"
                              size="sm"
                              icon={<XCircle size={12} />}
                              onClick={() => handleChangeReportStatus(report.id, 'dismissed', '驳回')}
                              loading={handlingReportId === report.id}
                            >
                              驳回
                            </Button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* 评论区长卷 */}
      <section className="bg-paper rounded-[16px] border border-line/60 shadow-md mt-4 overflow-hidden">
        <div className="px-6 pt-5 pb-3">
          <h2 className="font-display font-bold text-lg text-lake">
            评论 <span className="font-data text-ink-muted">({comments.length})</span>
          </h2>
        </div>

        <div className="px-6 pb-4">
          {isAuthenticated ? (
            <form onSubmit={handleComment} className="mb-5">
              <div className="flex gap-2">
                <input
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  placeholder="写下你的评论..."
                  className="flex-1 h-10 px-3.5 bg-paper border border-line rounded-[10px] text-[14px] text-ink placeholder:text-ink-muted/60 transition-colors focus:outline-none focus:border-lake"
                />
                <Button type="submit" loading={submitting} size="sm">
                  发布
                </Button>
              </div>
            </form>
          ) : (
            <div className="text-center py-3 text-ink-muted text-sm mb-5 bg-paper-hover rounded-[10px]">
              请先登录后再评论
            </div>
          )}
        </div>

        <div className="border-t border-ink-divider">
          {comments.length === 0 ? (
            <div className="text-center py-10">
              <div className="text-3xl mb-2">✎</div>
              <p className="text-ink-muted text-sm">暂无评论，快来抢沙发吧！</p>
            </div>
          ) : (
            <div>
              {comments.map((comment, idx) => (
                <div
                  key={comment.id}
                  className={`px-6 py-4 ${idx > 0 ? 'border-t border-ink-divider/60' : ''}`}
                >
                  {/* 顶级评论 */}
                  <div className="flex gap-3">
                    <Avatar
                      src={comment.author?.avatar_url}
                      fallback={comment.author?.nickname?.[0] || '?'}
                      size="sm"
                      className="flex-shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-ink text-sm">
                          {comment.author?.nickname || '匿名用户'}
                        </span>
                        <span className="text-xs text-ink-muted font-data">
                          {formatDate(comment.created_at)}
                        </span>
                      </div>
                      <p className="text-ink text-[14px] leading-[1.7]">{comment.content}</p>
                      {isAuthenticated && (
                        <button
                          type="button"
                          onClick={() => {
                            setReplyTarget({ comment });
                            setReplyText('');
                          }}
                          className="mt-2 inline-flex items-center gap-1 text-xs text-ink-muted hover:text-lake transition-colors"
                        >
                          <CornerDownRight size={11} />
                          回复
                        </button>
                      )}

                      {/* 回复输入框：当前顶级评论被点击回复时展示 */}
                      {replyTarget?.comment.id === comment.id && (
                        <div className="mt-3 flex gap-2">
                          <input
                            value={replyText}
                            onChange={(e) => setReplyText(e.target.value)}
                            placeholder={`回复 ${comment.author?.nickname || '匿名用户'}...`}
                            className="flex-1 h-9 px-3 bg-paper border border-line rounded-[8px] text-[13px] text-ink placeholder:text-ink-muted/60 transition-colors focus:outline-none focus:border-lake"
                          />
                          <Button
                            size="sm"
                            variant="primary"
                            loading={submitting}
                            onClick={() => handleReply(comment)}
                            disabled={!replyText.trim()}
                          >
                            回复
                          </Button>
                          <Button
                            size="sm"
                            variant="text"
                            onClick={() => {
                              setReplyTarget(null);
                              setReplyText('');
                            }}
                          >
                            取消
                          </Button>
                        </div>
                      )}

                      {/* 嵌套回复列表 */}
                      {comment.replies && comment.replies.length > 0 && (
                        <div className="mt-3 space-y-3 pl-3 border-l-2 border-line/40">
                          {comment.replies.map(reply => (
                            <div key={reply.id} className="flex gap-2.5">
                              <Avatar
                                src={reply.author?.avatar_url}
                                fallback={reply.author?.nickname?.[0] || '?'}
                                size="sm"
                                className="flex-shrink-0"
                              />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                                  <span className="font-medium text-ink text-[13px]">
                                    {reply.author?.nickname || '匿名用户'}
                                  </span>
                                  {reply.reply_to_user && reply.reply_to_user.id !== reply.user_id && (
                                    <span className="text-xs text-ink-muted">
                                      回复 <span className="text-lake">@{reply.reply_to_user.nickname}</span>
                                    </span>
                                  )}
                                  <span className="text-xs text-ink-muted font-data ml-auto">
                                    {formatDate(reply.created_at)}
                                  </span>
                                </div>
                                <p className="text-ink text-[13px] leading-[1.6]">{reply.content}</p>
                                {isAuthenticated && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setReplyTarget({ comment });
                                      setReplyText('');
                                    }}
                                    className="mt-1 inline-flex items-center gap-1 text-xs text-ink-muted hover:text-lake transition-colors"
                                  >
                                    <CornerDownRight size={10} />
                                    回复
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

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

export default PostDetailPage;
