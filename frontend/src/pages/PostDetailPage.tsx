import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { postsApi } from '../services/posts';
import { commentsApi } from '../services/comments';
import { interactionsApi, type ValidationStats, type ValidationType } from '../services/interactions';
import type { Post, Comment } from '../types';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Loading } from '../components/ui/Loading';
import { Toast } from '../components/ui/Toast';
import { useAuthStore } from '../store/useAuthStore';
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
} from 'lucide-react';

const REPORT_OPTIONS = [
  { value: 'fake', label: '虚假信息' },
  { value: 'ad', label: '广告/spam' },
  { value: 'inappropriate', label: '内容不当' },
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

const PostDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { isAuthenticated } = useAuthStore();
  const [post, setPost] = useState<Post | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [commentText, setCommentText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);
  const [validationStats, setValidationStats] = useState<ValidationStats | null>(null);
  const [showReportForm, setShowReportForm] = useState(false);
  const [reportType, setReportType] = useState('fake');
  const [reportDescription, setReportDescription] = useState('');
  const [reporting, setReporting] = useState(false);

  useEffect(() => {
    if (id) {
      setLoading(true);
      loadPost();
      loadComments();
      loadValidationStats();
    }
  }, [id]);

  const loadPost = async () => {
    try {
      const response = await postsApi.getPost(Number(id));
      setPost(response as Post);
    } catch (error) {
      console.error('加载帖子失败:', error);
      setToast({ message: '加载帖子失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const loadValidationStats = async () => {
    try {
      const stats = await interactionsApi.getValidationStats(Number(id));
      setValidationStats(stats);
    } catch (error) {
      console.error('加载验证统计失败:', error);
    }
  };

  const handleValidate = async (type: ValidationType) => {
    if (!isAuthenticated) {
      setToast({ message: '请先登录后再进行验证', type: 'warning' });
      return;
    }
    const current = validationStats?.user_validation_type;
    try {
      await interactionsApi.validatePost(Number(id), type);
      if (current === type) {
        setToast({ message: '已取消验证', type: 'info' });
      } else if (current) {
        setToast({ message: '已切换验证', type: 'success' });
      } else {
        setToast({ message: '验证已提交', type: 'success' });
      }
      loadValidationStats();
      loadPost();
    } catch (error) {
      setToast({ message: '验证失败', type: 'error' });
    }
  };

  const loadComments = async () => {
    try {
      const response = await commentsApi.getComments(Number(id));
      setComments(response.items || []);
    } catch (error) {
      console.error('加载评论失败:', error);
    }
  };

  const handleLike = async () => {
    if (!isAuthenticated) {
      setToast({ message: '请先登录', type: 'warning' });
      return;
    }
    try {
      await interactionsApi.likePost(Number(id));
      loadPost();
    } catch (error) {
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
      loadComments();
      loadPost();
      setToast({ message: '评论成功', type: 'success' });
    } catch (error) {
      setToast({ message: '评论失败', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    if (diff < 60000) return '刚刚';
    const minutes = Math.floor(diff / 60000);
    if (minutes < 30) return `${minutes}分钟前`;
    const hours = Math.floor(diff / 3600000);
    if (hours < 24) return `${hours}小时前`;
    const days = Math.floor(diff / 86400000);
    return `${days}天前`;
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
      setReportType('fake');
    } catch (error: any) {
      const msg = error?.response?.data?.detail || '举报失败，请稍后重试';
      setToast({ message: msg, type: 'error' });
    } finally {
      setReporting(false);
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

  const totalValidations = validationStats?.total_count || 0;
  const confirmPercent = totalValidations > 0 ? Math.round((validationStats?.confirmation_count || 0) / totalValidations * 100) : 0;
  const refutePercent = totalValidations > 0 ? Math.round((validationStats?.refutation_count || 0) / totalValidations * 100) : 0;

  return (
    <div className="max-w-2xl mx-auto py-4">
      {/* 长卷主容器 */}
      <article className="bg-paper rounded-[16px] border border-line/60 shadow-md overflow-hidden">
        {/* 标题区 */}
        <header className="px-6 pt-6 pb-5">
          <div className="flex items-center gap-2 mb-3">
            <Badge>{post.category?.name || '未分类'}</Badge>
            {post.status && STATUS_BADGE_CONFIG[post.status] && (
              <Badge variant={STATUS_BADGE_CONFIG[post.status].variant}>
                {STATUS_BADGE_CONFIG[post.status].label}
              </Badge>
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
                  {validationStats?.validity_status === 'valid' && <span className="text-grass ml-1">· 有效</span>}
                  {validationStats?.validity_status === 'invalid' && <span className="text-danger ml-1">· 无效</span>}
                  {validationStats?.validity_status === 'uncertain' && <span className="text-[#b89230] ml-1">· 待定</span>}
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
                <span className="text-grass font-medium font-data">{validationStats?.confirmation_count || 0} 证实</span>
                <span className="text-danger font-medium font-data">{validationStats?.refutation_count || 0} 证伪</span>
              </div>
            </div>
          )}

          {isAuthenticated && (
            <div className="flex flex-wrap gap-2 mt-4">
              {VALIDATION_OPTIONS.map(opt => {
                const isActive = validationStats?.user_validation_type === opt.type;
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
              {validationStats?.user_validation_type && (
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
            {post.tags && post.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-ink-divider/60">
                {post.tags.map(tag => (
                  <span key={tag.id} className="hand-tag">#{tag.name}</span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 底部操作栏 */}
        <div className="px-6 py-4 border-t border-ink-divider flex flex-wrap gap-2">
          <Button
            variant={post.is_liked ? 'danger' : 'primary'}
            size="sm"
            onClick={handleLike}
            icon={<Heart size={14} fill={post.is_liked ? 'currentColor' : 'none'} />}
          >
            {post.is_liked ? '已点赞' : '点赞'}
          </Button>
          <Button
            variant="text"
            size="sm"
            icon={<Flag size={14} />}
            onClick={() => setShowReportForm(!showReportForm)}
          >
            举报
          </Button>
        </div>

        {/* 举报表单 */}
        {showReportForm && (
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
                  className={`px-6 py-4 flex gap-3 ${idx > 0 ? 'border-t border-ink-divider/60' : ''}`}
                >
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
