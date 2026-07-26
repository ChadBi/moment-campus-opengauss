import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { topicsApi, type TopicDetail as TopicDetailData } from '../services/topics';
import { Loading } from '../components/ui/Loading';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { SubscribeButton } from '../components/SubscribeButton';
import { ArrowLeft, Eye, Heart, MessageCircle, FileText } from 'lucide-react';
import { logger } from '../utils/logger';
import { formatRelativeTime, formatDate as formatDateAbs } from '../utils/date';

const TopicDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [topic, setTopic] = useState<TopicDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const topicId = Number(id);
    if (!topicId || isNaN(topicId)) {
      setError('专题 ID 无效');
      setLoading(false);
      return;
    }

    const loadTopic = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await topicsApi.getTopic(topicId);
        setTopic(data);
      } catch (err: unknown) {
        logger.error('加载专题详情失败:', err);
        const e = err as { response?: { status?: number; data?: { detail?: string } } };
        if (e?.response?.status === 404) {
          setError('专题不存在或已下线');
        } else {
          setError(e?.response?.data?.detail || '加载专题详情失败');
        }
      } finally {
        setLoading(false);
      }
    };

    void loadTopic();
  }, [id]);

  const formatDate = (dateString?: string | null) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return '';
    const now = new Date();
    const days = Math.floor((now.getTime() - date.getTime()) / 86400000);
    if (days >= 30) return formatDateAbs(dateString);
    return formatRelativeTime(dateString);
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <Loading fullScreen />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <div className="bg-danger/10 border border-danger/30 rounded-lg p-6 text-center">
          <p className="text-ink text-sm mb-4">{error}</p>
          <Button size="sm" variant="primary" onClick={() => navigate('/topics')}>
            返回专题列表
          </Button>
        </div>
      </div>
    );
  }

  if (!topic) return null;

  return (
    <div className="max-w-2xl mx-auto py-4">
      {/* 返回按钮 */}
      <button
        onClick={() => navigate('/topics')}
        className="flex items-center gap-1 text-ink-sub hover:text-ink text-sm mb-4 transition-colors"
      >
        <ArrowLeft size={16} />
        返回专题列表
      </button>

      {/* 专题头部 */}
      <header className="mb-6">
        {topic.cover_url && (
          <div className="w-full h-40 bg-mist rounded-[16px] overflow-hidden mb-4">
            <img
              src={topic.cover_url}
              alt={topic.title}
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
          </div>
        )}
        <div className="flex items-start justify-between gap-3 mb-2">
          <h1 className="font-display font-bold text-[26px] tracking-wide text-lake leading-tight">
            {topic.title}
          </h1>
          {/* SUB-01: 订阅本专题按钮（有新内容/更新/过期/冲突时通知） */}
          <SubscribeButton target_type="topic" target_id={topic.id} size="sm" />
        </div>
        {topic.description && (
          <p className="text-ink-sub text-sm leading-relaxed mb-3">
            {topic.description}
          </p>
        )}
        <div className="flex items-center gap-4 text-xs text-ink-muted">
          <span className="flex items-center gap-1">
            <FileText size={12} />
            {topic.post_count} 篇内容
          </span>
          <span className="flex items-center gap-1">
            <Eye size={12} />
            {topic.view_count} 次浏览
          </span>
          {topic.published_at && (
            <span>发布于 {formatDate(topic.published_at)}</span>
          )}
        </div>
      </header>

      {/* 关联帖子列表 */}
      <section>
        <h2 className="text-base font-bold text-ink mb-3 px-1">
          专题内容
        </h2>

        {topic.posts.length === 0 ? (
          <div className="text-center py-12 bg-paper border border-line/60 rounded-[16px]">
            <FileText size={40} className="mx-auto text-ink-disabled mb-3" />
            <p className="text-ink-sub text-sm">暂无内容</p>
          </div>
        ) : (
          <div className="space-y-3">
            {topic.posts.map((post, index) => (
              <article
                key={post.id}
                className="bg-paper border border-line/60 rounded-[16px] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] cursor-pointer overflow-hidden stagger-card"
                style={{ animationDelay: `${index * 40}ms` }}
                onClick={() => navigate(`/posts/${post.id}`)}
              >
                <div className="px-5 py-4">
                  <div className="flex items-start gap-3">
                    {/* 帖子首图 */}
                    {post.cover_image_url && (
                      <div className="flex-shrink-0 w-20 h-20 bg-mist rounded-lg overflow-hidden">
                        <img
                          src={post.cover_image_url}
                          alt={post.title}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                      </div>
                    )}

                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-ink text-sm mb-1 line-clamp-2">
                        {post.title}
                      </h3>
                      <p className="text-ink-sub text-xs line-clamp-2 mb-2">
                        {post.content}
                      </p>

                      {/* 元信息 */}
                      <div className="flex items-center gap-3 text-[11px] text-ink-muted">
                        {post.category_name && (
                          <Badge variant="info" className="text-[10px]">
                            {post.category_name}
                          </Badge>
                        )}
                        {post.author_name && (
                          <span>{post.author_name}</span>
                        )}
                        <span className="flex items-center gap-0.5">
                          <Heart size={10} />
                          {post.like_count}
                        </span>
                        <span className="flex items-center gap-0.5">
                          <MessageCircle size={10} />
                          {post.comment_count}
                        </span>
                        <span className="flex items-center gap-0.5">
                          <Eye size={10} />
                          {post.view_count}
                        </span>
                        <span className="ml-auto">{formatDate(post.created_at)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default TopicDetailPage;
