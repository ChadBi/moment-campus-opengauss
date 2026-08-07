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
import { Heart, MessageCircle, Eye, MapPin, Clock, Sparkles, FilePlus2, Flame, ChevronRight } from 'lucide-react';
import { useSchoolQueryKey } from '../hooks/useSchoolQueryKey';
import { formatRelativeTime as formatDate } from '../utils/date';
import { getCategoryVisual } from '../utils/categoryVisual';

function getHotSince(): string {
  const date = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

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
    data: hotData,
    isLoading: hotLoading,
    isError: hotError,
    refetch: refetchHot,
  } = useQuery({
    queryKey: [...schoolKey, 'posts', 'hot-ranking', '7d'],
    queryFn: () => postsApi.getPosts({
      page: 1,
      page_size: 10,
      status: 'published',
      sort: 'views',
      date_from: getHotSince(),
    }),
    staleTime: 60 * 1000,
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
  // 推荐接口仍取 5 条供服务端排序，但首页只展示一条精选，避免首屏被长列表占满。
  const recItems: RecommendationItem[] = (recData?.items ?? []).slice(0, 1);
  const hotItems = hotData?.items ?? [];
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

  const hotSection = (
    /* 近 7 天浏览量热榜：横向预览，点击标题进入完整榜单 */
    (hotLoading || hotError || hotItems.length > 0) && (
      <section className="mb-6 rounded-[18px] border border-[#cf947e]/30 bg-gradient-to-br from-[#fff1e8] to-paper shadow-sm overflow-hidden">
        <button
          type="button"
          className="w-full px-5 pt-4 pb-3 flex items-center justify-between text-left hover:bg-white/30 transition-colors"
          onClick={() => navigate('/hot-ranking')}
        >
          <span className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-[11px] bg-[#e67340] text-white flex items-center justify-center shadow-sm">
              <Flame size={17} />
            </span>
            <span>
              <span className="block font-display font-bold text-[17px] text-[#9e422b]">校园热榜</span>
              <span className="block mt-0.5 text-[11px] text-[#a36b5b]">近 7 天浏览量 Top10</span>
            </span>
          </span>
          <span className="flex items-center gap-0.5 text-xs text-[#b65335]">查看榜单 <ChevronRight size={14} /></span>
        </button>

        {hotLoading ? (
          <div className="px-5 pb-4 space-y-2"><div className="h-4 rounded-full bg-[#e67340]/15 animate-pulse" /><div className="h-4 w-2/3 rounded-full bg-[#e67340]/10 animate-pulse" /></div>
        ) : hotError ? (
          <button type="button" className="px-5 pb-4 text-sm text-[#b65335]" onClick={() => void refetchHot()}>热榜暂时走丢了，点击重试</button>
        ) : (
          <div className="flex gap-3 overflow-x-auto px-5 pb-4 snap-x">
            {hotItems.map((item, index) => (
              <article
                key={item.id}
                className="relative min-w-[250px] snap-start rounded-[15px] border border-[#cf947e]/20 bg-white/90 p-3.5 cursor-pointer hover:-translate-y-0.5 transition-transform"
                onClick={() => handlePostClick(item.id)}
              >
                <div className="flex items-start gap-2.5">
                  <span className={`w-7 h-7 rounded-[10px] flex items-center justify-center flex-shrink-0 text-xs font-bold font-data ${index < 3 ? 'bg-[#ffd34e] text-[#8f581e]' : 'bg-[#edf1f2] text-ink-muted'}`}>{index + 1}</span>
                  <div className="min-w-0">
                    <h3 className="h-[42px] text-sm font-semibold text-ink line-clamp-2 leading-[1.45]">{item.title}</h3>
                    <div className="flex items-center gap-2 mt-2 text-[11px] text-ink-muted font-data"><span className="text-[#b65335]">{item.view_count || 0} 浏览</span><span>{item.comment_count || 0} 评论</span></div>
                  </div>
                </div>
                {item.category?.name && <span className="inline-block mt-2 rounded-full bg-[#fff0e7] px-2 py-0.5 text-[10px] text-[#b65335]">{item.category.name}</span>}
              </article>
            ))}
          </div>
        )}
      </section>
    )
  );

  return (
    <div className="max-w-2xl mx-auto py-4">
      <header className="mb-6 px-1">
        <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">
          此刻校园
        </h1>
        <p className="text-ink-muted text-sm mt-1">把会消失的校园经验留下来</p>
      </header>

      {hotSection}

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
                    {item.is_anonymous && (
                      <span className="bg-neutral-100 text-neutral-500 text-[10px] px-2 py-0.5 rounded-full border border-neutral-200">
                        匿名
                      </span>
                    )}
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
                  {post.is_anonymous && (
                    <span className="bg-neutral-100 text-neutral-500 text-[10px] px-2 py-0.5 rounded-full border border-neutral-200">
                      匿名
                    </span>
                  )}
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
