import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { postsApi } from '../services/posts';
import { commentsApi } from '../services/comments';
import { interactionsApi, type ValidationStats, type ValidationType } from '../services/interactions';
import type { Post, Comment } from '../types';
import { Card } from '../components/ui/Card';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
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
} from 'lucide-react';

// T-B-05: 6 态状态徽章配置
const STATUS_BADGE_CONFIG: Record<string, { variant: 'default' | 'success' | 'warning' | 'danger' | 'info'; label: string }> = {
  draft: { variant: 'default', label: '草稿' },
  pending: { variant: 'warning', label: '待审核' },
  published: { variant: 'success', label: '已发布' },
  expired: { variant: 'default', label: '已过期' },
  conflict: { variant: 'danger', label: '冲突中' },
  archived: { variant: 'default', label: '已归档' },
};

// T-B-05: 2 类协同验证选项（证实/证伪 互斥可切换）
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
    activeClass: 'bg-grass text-paper border-grass',
  },
  {
    type: 'refutation',
    label: '证伪',
    activeLabel: '已证伪',
    icon: <XCircle size={14} />,
    color: 'text-danger',
    activeClass: 'bg-danger text-paper border-danger',
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

  useEffect(() => {
    if (id) {
      // loading 仅用于初始加载，避免后续刷新时整个组件树被 Loading 占位符替换导致滚动位置丢失
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

  // T-B-05: 加载协同验证统计
  const loadValidationStats = async () => {
    try {
      const stats = await interactionsApi.getValidationStats(Number(id));
      setValidationStats(stats);
    } catch (error) {
      console.error('加载验证统计失败:', error);
    }
  };

  // T-B-05: 提交协同验证（互斥可切换）
  // - 当前未验证 → 新建
  // - 当前已选同类型 → 取消
  // - 当前已选不同类型 → 切换
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
    return date.toLocaleString('zh-CN');
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-1 py-16">
        <Loading text="加载中..." />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="max-w-2xl mx-auto px-1 py-16 text-center">
        <div className="text-5xl mb-4">⌖</div>
        <p className="font-medium text-ink mb-1.5">这条信息不存在或已失效</p>
        <p className="text-sm text-ink-muted">可能已被发布者删除，或链接有误。</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-1 py-2">
      {/* 顶部 hero 区域：渐变背景 + 大标题(楷体) + 位置信息 */}
      <section className="relative rounded-[22px] bg-gradient-to-br from-[#cfe3e6] to-[#e9f0d8] p-6 overflow-hidden mb-4">
        <div className="absolute -top-[100px] -right-[60px] w-[230px] h-[230px] rounded-full border-[42px] border-white/35 pointer-events-none" />
        <div className="relative z-10 max-w-[80%]">
          <span className="eyebrow">{post.category?.name || '未分类'} · {formatDate(post.created_at)}</span>
          <h1 className="font-display font-extrabold text-[26px] md:text-[30px] leading-tight text-ink mt-2.5 mb-2">
            {post.title}
          </h1>
          <p className="text-ink-sub text-sm flex items-center gap-1.5">
            <MapPin size={13} />
            {post.location?.name || '未知地点'}
          </p>
        </div>
      </section>

      {/* 信息卡片网格：2列布局 */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-white border border-line rounded-lg p-4">
          <small className="block text-ink-muted text-xs mb-1.5">现在状态</small>
          <strong className="text-sm text-ink font-medium flex items-center gap-2">
            {post.status && STATUS_BADGE_CONFIG[post.status] ? (
              <Badge variant={STATUS_BADGE_CONFIG[post.status].variant}>
                {STATUS_BADGE_CONFIG[post.status].label}
              </Badge>
            ) : (
              <span>{post.status || '未标注'}</span>
            )}
          </strong>
        </div>
        <div className="bg-white border border-line rounded-lg p-4">
          <small className="block text-ink-muted text-xs mb-1.5">信息分类</small>
          <strong className="text-sm text-ink font-medium">{post.category?.name || '未分类'}</strong>
        </div>
        <div className="bg-white border border-line rounded-lg p-4">
          <small className="block text-ink-muted text-xs mb-1.5">协同验证</small>
          <strong className="text-sm text-ink font-medium">
            <span className="font-data">{validationStats?.total_count || 0}</span> 条验证 ·
            综合状态：
            {validationStats?.validity_status === 'valid' && <span className="text-grass"> 有效</span>}
            {validationStats?.validity_status === 'invalid' && <span className="text-danger"> 无效</span>}
            {validationStats?.validity_status === 'uncertain' && <span className="text-sun"> 待定</span>}
          </strong>
        </div>
        <div className="bg-white border border-line rounded-lg p-4">
          <small className="block text-ink-muted text-xs mb-1.5">贡献者</small>
          <strong className="text-sm text-ink font-medium">{post.author?.nickname || '匿名用户'}</strong>
        </div>
      </div>

      {/* T-B-05: 协同验证统计面板（2 类） */}
      {validationStats && validationStats.total_count > 0 && (
        <Card variant="elevated" padding="md" className="mb-4">
          <h3 className="font-display font-bold text-sm text-lake mb-3 flex items-center gap-2">
            <CheckCircle2 size={16} />
            协同验证统计
          </h3>
          <div className="grid grid-cols-2 gap-3 text-center">
            <div className="p-3 rounded-md bg-grass/8">
              <div className="text-2xl font-data font-bold text-grass">{validationStats.confirmation_count}</div>
              <div className="text-xs text-ink-muted mt-1">证实</div>
            </div>
            <div className="p-3 rounded-md bg-danger/8">
              <div className="text-2xl font-data font-bold text-danger">{validationStats.refutation_count}</div>
              <div className="text-xs text-ink-muted mt-1">证伪</div>
            </div>
          </div>
        </Card>
      )}

      {/* T-B-05: 2 类协同验证操作按钮（互斥可切换） */}
      {isAuthenticated && (
        <div className="flex flex-wrap gap-2 mb-4">
          {VALIDATION_OPTIONS.map(opt => {
            const isActive = validationStats?.user_validation_type === opt.type;
            return (
              <button
                key={opt.type}
                onClick={() => handleValidate(opt.type)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium border transition-all ${
                  isActive
                    ? opt.activeClass
                    : `bg-paper border-line ${opt.color} hover:bg-mist`
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

      {/* 作者信息 + 统计 */}
      <Card variant="elevated" padding="md" className="mb-4">
        <div className="flex items-center gap-3 mb-4">
          <Avatar
            src={post.author?.avatar_url}
            fallback={post.author?.nickname?.[0] || '?'}
            size="md"
          />
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-medium text-ink">
                {post.author?.nickname || '匿名用户'}
              </span>
              <Badge variant="default">{post.category?.name || '未分类'}</Badge>
            </div>
            <div className="flex items-center gap-3 text-xs text-ink-muted">
              <span className="flex items-center gap-1">
                <Clock size={12} />
                {formatDate(post.created_at)}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4 pt-3 border-t border-line/70 text-sm text-ink-muted">
          <span className="flex items-center gap-1.5">
            <Eye size={15} />
            <span className="font-data font-bold">{post.view_count || 0}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <Heart size={15} />
            <span className="font-data font-bold">{post.like_count || 0}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <MessageCircle size={15} />
            <span className="font-data font-bold">{post.comment_count || 0}</span>
          </span>
        </div>
      </Card>

      {/* 内容区域：暖色背景(#fff6ec)的笔记卡片 */}
      <div className="bg-[#fff6ec] border border-[#f5dfc8] rounded-lg p-4 mb-4">
        <p className="text-[13px] text-[#70523b] leading-relaxed whitespace-pre-wrap">{post.content}</p>
        {post.tags && post.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {post.tags.map(tag => (
              <span key={tag.id} className="hand-tag">#{tag.name}</span>
            ))}
          </div>
        )}
      </div>

      {/* 底部操作按钮 */}
      <div className="flex flex-wrap gap-2 mb-6">
        <Button
          variant={post.is_liked ? 'danger' : 'primary'}
          size="sm"
          onClick={handleLike}
          icon={<Heart size={16} />}
        >
          {post.is_liked ? '已点赞' : '点赞'}
        </Button>
        <Button variant="text" size="sm" icon={<Flag size={16} />}>
          举报
        </Button>
      </div>

      {/* 评论区：Card 组件 */}
      <Card variant="elevated" padding="md">
        <h2 className="font-display font-bold text-lg text-lake mb-4">
          评论 <span className="font-data text-ink-muted">({comments.length})</span>
        </h2>

        {isAuthenticated ? (
          <form onSubmit={handleComment} className="mb-6">
            <div className="flex gap-2">
              <Input
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="写下你的评论..."
                className="flex-1"
              />
              <Button type="submit" loading={submitting}>
                发布
              </Button>
            </div>
          </form>
        ) : (
          <div className="text-center py-4 text-ink-muted text-sm mb-6 bg-mist/60 rounded-md">
            请先登录后再评论
          </div>
        )}

        <div className="space-y-4">
          {comments.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-3xl mb-2">✎</div>
              <p className="text-ink-muted text-sm">暂无评论，快来抢沙发吧！</p>
            </div>
          ) : (
            comments.map(comment => (
              <div key={comment.id} className="flex gap-3">
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
                  <p className="text-ink text-sm leading-relaxed">{comment.content}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

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
