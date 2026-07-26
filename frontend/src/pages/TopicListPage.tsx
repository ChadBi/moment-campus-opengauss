import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { topicsApi, type TopicListItem } from '../services/topics';
import { Loading } from '../components/ui/Loading';
import { useSchoolQueryKey } from '../hooks/useSchoolQueryKey';
import { BookOpen, Eye, FileText } from 'lucide-react';
import { logger } from '../utils/logger';
import { formatDate } from '../utils/date';

const PAGE_SIZE = 20;

const TopicListPage: React.FC = () => {
  const navigate = useNavigate();
  const schoolKey = useSchoolQueryKey();
  const [topics, setTopics] = useState<TopicListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const loadTopics = useCallback(async (p: number) => {
    try {
      setLoading(true);
      setError(null);
      const data = await topicsApi.listTopics({ page: p, page_size: PAGE_SIZE });
      setTopics(data.items);
      setTotalPages(data.total_pages);
    } catch (err: unknown) {
      logger.error('加载专题列表失败:', err);
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      if (e?.response?.status === 404) {
        setError('当前学校暂未开放专题');
      } else {
        setError(e?.response?.data?.detail || '加载专题列表失败');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTopics(page);
  }, [page, loadTopics, schoolKey]);

  const handleTopicClick = (id: number) => {
    navigate(`/topics/${id}`);
  };

  if (loading && topics.length === 0) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <Loading fullScreen />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-4">
      {/* 页面标题 */}
      <header className="mb-6 px-1">
        <div className="flex items-center gap-2 mb-1">
          <BookOpen size={22} className="text-lake" />
          <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">
            校园专题
          </h1>
        </div>
        <p className="text-ink-muted text-sm">精选校园里的故事与线索</p>
      </header>

      {/* 错误提示 */}
      {error && (
        <div className="bg-sun/10 border border-sun/30 rounded-lg p-4 mb-4 text-center">
          <p className="text-ink text-sm">{error}</p>
        </div>
      )}

      {/* 空状态 */}
      {!loading && !error && topics.length === 0 && (
        <div className="text-center py-16">
          <BookOpen size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub text-sm">暂无专题内容</p>
        </div>
      )}

      {/* 专题卡片列表 */}
      <div className="space-y-3">
        {topics.map((topic, index) => (
          <article
            key={topic.id}
            className="bg-paper border border-line/60 rounded-[16px] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] cursor-pointer overflow-hidden stagger-card"
            style={{ animationDelay: `${index * 40}ms` }}
            onClick={() => handleTopicClick(topic.id)}
          >
            {/* 封面图（可选） */}
            {topic.cover_url && (
              <div className="w-full h-32 bg-mist overflow-hidden">
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

            <div className="px-5 py-4">
              <h2 className="font-bold text-ink text-base mb-1.5 line-clamp-2">
                {topic.title}
              </h2>
              {topic.description && (
                <p className="text-ink-sub text-sm mb-3 line-clamp-2">
                  {topic.description}
                </p>
              )}

              {/* 元信息 */}
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
                  <span className="ml-auto">
                    {formatDate(topic.published_at)}
                  </span>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
            className="px-3 py-1.5 rounded-md text-sm border border-line bg-paper text-ink-sub hover:bg-mist disabled:opacity-40 disabled:cursor-not-allowed"
          >
            上一页
          </button>
          <span className="text-sm text-ink-sub px-2">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || loading}
            className="px-3 py-1.5 rounded-md text-sm border border-line bg-paper text-ink-sub hover:bg-mist disabled:opacity-40 disabled:cursor-not-allowed"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
};

export default TopicListPage;
