import React from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { postsApi } from '../services/posts';
import { recommendationsApi } from '../services/recommendations';
import type { Post, RecommendationItem } from '../types';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '../components/state';
import { VerifiedBadge } from '../components/VerifiedBadge';
import { Heart, MessageCircle, Eye, MapPin, Clock, Sparkles, FilePlus2 } from 'lucide-react';
import { useSchoolQueryKey } from '../hooks/useSchoolQueryKey';
import { formatRelativeTime as formatDate } from '../utils/date';
import { getCategoryVisual } from '../utils/categoryVisual';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const schoolKey = useSchoolQueryKey();

  // REC-01.1: 首页"为你推荐"区块（仅首页第一屏，取前 5 条）
  // 与 posts feed 分开查询，避免分页耦合
  const {
    data: recData,
    isLoading: recLoading,
    isError: recError,
    refetch: refetchRecommendations,
  } = useQuery({
    queryKey: [...schoolKey, 'recommendations', 'home'],
    queryFn: () => recommendationsApi.getRecommendations(1, 5),
    staleTime: 60 * 1000, // 1 分钟内不重复请求
  });

  const {
    data,
    isLoading,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: [...schoolKey, 'posts', 'feed'],
    queryFn: ({ pageParam = 1 }) => postsApi.getPosts({ page: pageParam, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
  });

  const posts = (data?.pages.flatMap(p => p.items) ?? []) as Post[];
  const recItems: RecommendationItem[] = recData?.items ?? [];
  const recMode = recData?.mode;
  const handleLoadMore = () => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  };

  const handlePostClick = (postId: number) => {
    navigate(`/posts/${postId}`);
  };

  // REC-01.2: 推荐模式文案（前端友好提示）
  const getModeHint = () => {
    if (!recMode) return null;
    if (recMode.personalized) {
      return '基于你的浏览/搜索/订阅偏好';
    }
    switch (recMode.reason_code) {
      case 'cold_start_guest':
        return '登录后开启个性化推荐';
      case 'cold_start_disabled':
        return '已关闭个性化，展示本校热门/最新';
      case 'cold_start_no_history':
        return '多浏览帖子，开启个性化推荐';
      default:
        return null;
    }
  };

  const modeHint = getModeHint();

  return (
    <div className="max-w-2xl mx-auto py-4">
      <header className="mb-6 px-1">
        <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">
          此刻校园
        </h1>
        <p className="text-ink-muted text-sm mt-1">把会消失的校园经验留下来</p>
      </header>

      {/* REC-01.1: 为你推荐区块 */}
      {recLoading ? (
        <div className="mb-6 bg-paper border border-line/60 rounded-[16px]">
          <LoadingState title="正在为你推荐" compact />
        </div>
      ) : recError ? (
        <div className="mb-6 bg-paper border border-line/60 rounded-[16px]">
          <ErrorState
            title="推荐暂时走丢了"
            description="普通信息流仍可继续浏览。"
            onRetry={() => void refetchRecommendations()}
            compact
          />
        </div>
      ) : recItems.length > 0 ? (
        <section className="mb-6 bg-paper border border-lake/30 rounded-[18px] shadow-sm overflow-hidden">
          <div className="px-5 pt-4 pb-3 bg-gradient-to-br from-lake/[0.06] to-mist/40 border-b border-line/60">
            <div className="flex items-center gap-2 mb-1">
              <Sparkles size={18} className="text-lake" />
              <h2 className="font-display font-bold text-[17px] text-lake">为你推荐</h2>
              {recMode?.personalized && (
                <span className="ml-auto text-[10px] text-lake bg-lake/10 px-2 py-0.5 rounded-[6px]">
                  个性化
                </span>
              )}
            </div>
            {modeHint && (
              <p className="text-[11px] text-ink-muted">{modeHint}</p>
            )}
          </div>
          <div className="divide-y divide-ink-divider/60">
            {recItems.map((item) => (
              <article
                key={item.id}
                className="px-5 py-3 hover:bg-paper-hover transition-colors cursor-pointer"
                onClick={() => handlePostClick(item.id)}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <Avatar
                    src={item.author?.avatar_url}
                    fallback={item.author?.nickname?.[0] || '?'}
                    size="sm"
                    className="flex-shrink-0"
                  />
                  <span className="font-medium text-ink text-sm flex items-center gap-1">
                    {item.author?.nickname || '匿名用户'}
                    {item.author?.is_verified && <VerifiedBadge />}
                  </span>
                  <Badge
                    style={{
                      backgroundColor: getCategoryVisual(item.category?.code).background,
                      color: getCategoryVisual(item.category?.code).text,
                    }}
                  >
                    {item.category?.name || '未分类'}
                  </Badge>
                  {/* REC-01.1: 推荐原因 */}
                  <span className="ml-auto text-[10px] text-lake bg-lake/10 px-1.5 py-0.5 rounded-[6px] flex items-center gap-0.5 flex-shrink-0">
                    <Sparkles size={9} />
                    {item.reason}
                  </span>
                </div>
                <h3 className="font-semibold text-[14px] text-ink mb-1 line-clamp-1 leading-[1.5]">
                  {item.title}
                </h3>
                <p className="text-ink-sub text-[13px] line-clamp-1 leading-[1.6]">
                  {item.content}
                </p>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[11px] text-ink-muted flex items-center gap-1">
                    <MapPin size={10} />
                    {item.location?.name || '未知地点'}
                  </span>
                  <div className="flex items-center gap-3 text-[11px] text-ink-muted">
                    <span className="flex items-center gap-0.5">
                      <Eye size={11} />
                      <span className="font-data font-bold text-ink-sub">{item.view_count || 0}</span>
                    </span>
                    <span className="flex items-center gap-0.5">
                      <Heart size={11} />
                      <span className="font-data font-bold text-ink-sub">{item.like_count || 0}</span>
                    </span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {/* 普通信息流（最新/最热/...） */}
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
                <span className="font-medium text-ink text-sm flex items-center gap-1">
                  {post.author?.nickname || '匿名用户'}
                  {post.author?.is_verified && <VerifiedBadge />}
                </span>
                <Badge
                  style={{ backgroundColor: getCategoryVisual(post.category?.code).background, color: getCategoryVisual(post.category?.code).text }}
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

      {isLoading && posts.length === 0 && (
        <div className="bg-paper border border-line/60 rounded-[16px]">
          <LoadingState
            title="正在加载校园此刻"
            description="正在翻阅这所学校刚刚发生的事。"
          />
        </div>
      )}

      {isError && posts.length === 0 && (
        <div className="bg-paper border border-line/60 rounded-[16px]">
          <ErrorState
            title="校园信息暂时无法加载"
            onRetry={() => void refetch()}
          />
        </div>
      )}

      {!isLoading && !isError && posts.length === 0 && recItems.length === 0 && (
        <div className="bg-paper border border-line/60 rounded-[16px]">
          <EmptyState
            title="这里还没有校园经验"
            description="发布第一条，把会消失的校园经验留下来。"
            icon={<FilePlus2 size={24} />}
            actionLabel="发布第一条"
            onAction={() => navigate('/publish')}
          />
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
