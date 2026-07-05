import React from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { postsApi } from '../services/posts';
import type { Post } from '../types';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Loading } from '../components/ui/Loading';
import { Button } from '../components/ui/Button';
import { Heart, MessageCircle, Eye, MapPin, Clock } from 'lucide-react';
import { colors as categoryColors } from '../styles/tokens';

const CATEGORY_COLOR_MAP: Record<string, keyof typeof categoryColors.category> = {
  '美食': 'food', '食物': 'food', '餐饮': 'food',
  '活动': 'event', '事件': 'event',
  '服务': 'service',
  '学习': 'study', '学术': 'study',
  '失物招领': 'lostFound', '失物': 'lostFound',
  '社团': 'club',
};
const getCategoryColor = (name?: string) => {
  const key = name ? CATEGORY_COLOR_MAP[name] : undefined;
  return categoryColors.category[key ?? 'default'];
};

const HomePage: React.FC = () => {
  const navigate = useNavigate();

  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['posts', 'feed'],
    queryFn: ({ pageParam = 1 }) => postsApi.getPosts({ page: pageParam, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
  });

  const posts = (data?.pages.flatMap(p => p.items) ?? []) as Post[];
  const loading = isLoading || isFetchingNextPage;

  const handleLoadMore = () => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  };

  const handlePostClick = (postId: number) => {
    navigate(`/posts/${postId}`);
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

  return (
    <div className="max-w-2xl mx-auto py-4">
      <header className="mb-6 px-1">
        <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">
          此刻校园
        </h1>
        <p className="text-ink-muted text-sm mt-1">把会消失的校园经验留下来</p>
      </header>

      <div className="space-y-0">
        {posts.map((post, index) => (
          <article
            key={post.id}
            className="bg-paper border border-line/60 rounded-[16px] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] cursor-pointer mb-3 stagger-card overflow-hidden"
            style={{ animationDelay: `${index * 40}ms` }}
            onClick={() => handlePostClick(post.id)}
          >
            <div className="px-5 pt-4 pb-3">
              <div className="flex items-center gap-2 mb-2">
                <Avatar
                  src={post.author?.avatar_url}
                  fallback={post.author?.nickname?.[0] || '?'}
                  size="sm"
                  className="flex-shrink-0"
                />
                <span className="font-medium text-ink text-sm">
                  {post.author?.nickname || '匿名用户'}
                </span>
                <Badge
                  style={{ backgroundColor: getCategoryColor(post.category?.name).light, color: getCategoryColor(post.category?.name).main }}
                >
                  {post.category?.name || '未分类'}
                </Badge>
                <span className="text-xs text-ink-muted ml-auto flex items-center gap-1">
                  <Clock size={11} />
                  {formatDate(post.created_at)}
                </span>
              </div>

              <h3 className="font-semibold text-[15px] text-ink mb-1.5 line-clamp-2 leading-[1.5]">
                {post.title}
              </h3>
              <p className="text-ink-sub text-[14px] line-clamp-2 leading-[1.7]">
                {post.content}
              </p>
            </div>

            <div className="px-5 py-2.5 border-t border-ink-divider/60 flex items-center justify-between">
              <span className="text-xs text-ink-muted flex items-center gap-1">
                <MapPin size={11} />
                {post.location?.name || '未知地点'}
              </span>
              <div className="flex items-center gap-4 text-xs text-ink-muted">
                <span className="flex items-center gap-1">
                  <Eye size={12} />
                  <span className="font-data font-bold text-ink-sub">{post.view_count || 0}</span>
                </span>
                <span className="flex items-center gap-1">
                  <Heart size={12} />
                  <span className="font-data font-bold text-ink-sub">{post.like_count || 0}</span>
                </span>
                <span className="flex items-center gap-1">
                  <MessageCircle size={12} />
                  <span className="font-data font-bold text-ink-sub">{post.comment_count || 0}</span>
                </span>
              </div>
            </div>
          </article>
        ))}
      </div>

      {loading && posts.length === 0 && (
        <div className="py-16">
          <Loading text="加载中..." />
        </div>
      )}

      {isError && (
        <div className="text-center py-16 text-danger">加载失败，请稍后重试</div>
      )}

      {!loading && posts.length === 0 && (
        <div className="text-center py-16">
          <div className="text-5xl mb-4">⌖</div>
          <p className="font-medium text-ink mb-1.5">这里还没有校园经验</p>
          <p className="text-sm text-ink-muted">发布第一条，把会消失的校园经验留下来。</p>
        </div>
      )}

      {hasNextPage && posts.length > 0 && (
        <div className="mt-6 text-center">
          <Button
            variant="secondary"
            onClick={handleLoadMore}
            loading={isFetchingNextPage}
            disabled={!hasNextPage}
          >
            加载更多
          </Button>
        </div>
      )}
    </div>
  );
};

export default HomePage;
