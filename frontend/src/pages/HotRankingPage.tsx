import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ChevronRight, Eye, Heart, MessageCircle } from 'lucide-react';
import { postsApi } from '../services/posts';
import type { Post } from '../types';
import { Avatar } from '../components/ui/Avatar';
import { VerifiedBadge } from '../components/VerifiedBadge';
import { EmptyState, ErrorState, LoadingState } from '../components/state';
import { useSchoolQueryKey } from '../hooks/useSchoolQueryKey';
import { formatRelativeTime } from '../utils/date';

function getHotSince(): string {
  const date = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

const HotRankingPage: React.FC = () => {
  const navigate = useNavigate();
  const schoolKey = useSchoolQueryKey();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [...schoolKey, 'posts', 'hot-ranking', '7d', 'full'],
    queryFn: () => postsApi.getPosts({
      page: 1,
      page_size: 10,
      status: 'published',
      sort: 'views',
      date_from: getHotSince(),
    }),
    staleTime: 60 * 1000,
  });
  const posts = (data?.items ?? []) as Post[];

  return (
    <div className="min-h-screen bg-[#fff4ee] -mx-4 -my-4 sm:-mx-6 sm:-my-6">
      <section className="relative overflow-hidden bg-gradient-to-br from-[#f58c6b] via-[#f47a5b] to-[#ed6f51] px-5 pt-5 pb-8 text-white">
        <div className="absolute -right-20 -top-28 w-72 h-72 rounded-full border border-white/20" />
        <div className="absolute -left-28 -bottom-48 w-64 h-64 rounded-full border border-white/20" />
        <div className="relative flex items-center justify-between h-9">
          <button type="button" className="w-9 h-9 rounded-full bg-white/15 flex items-center justify-center hover:bg-white/25" onClick={() => navigate(-1)} aria-label="返回">
            <ArrowLeft size={18} />
          </button>
          <span className="font-display font-bold tracking-[0.18em]">校园热榜</span>
          <span className="w-9" />
        </div>
        <div className="relative mt-14 flex items-end gap-3">
          <h1 className="font-display text-5xl font-black tracking-[0.18em] drop-shadow-[3px_3px_0_rgba(145,62,38,.22)]">大榜单</h1>
          <span className="mb-2 rotate-[-3deg] rounded bg-[#713723]/90 px-2 py-1 text-[11px] tracking-[0.18em] text-[#ffe7a2]">校园热榜</span>
        </div>
        <p className="relative mt-2 text-sm text-white/90 tracking-wide">近 7 天浏览量最高的 10 条校园动态</p>
        <div className="relative mt-5 flex items-center gap-3 text-[11px] text-white/75"><span className="h-px flex-1 bg-white/35" /><span>实时更新</span><span className="h-px flex-1 bg-white/35" /></div>
      </section>

      <main className="mx-auto max-w-2xl px-4 py-5">
        {isLoading && <div className="rounded-2xl bg-white/75"><LoadingState title="正在翻阅校园热度" compact /></div>}
        {isError && <div className="rounded-2xl bg-white/75"><ErrorState title="校园热榜加载失败" onRetry={() => void refetch()} compact /></div>}
        {!isLoading && !isError && posts.length === 0 && <div className="rounded-2xl bg-white/75"><EmptyState title="近 7 天还没有形成热榜" /></div>}

        {!isLoading && !isError && posts.length > 0 && (
          <>
            <div className="mb-4 flex items-center gap-2 px-1 text-sm text-[#a36b5b]"><span className="h-2 w-2 rounded-full bg-[#e67340] shadow-[0_0_0_5px_rgba(230,115,64,.12)]" /><span>按浏览量排序</span><span className="ml-auto font-data text-[#c18c7c]">共 {posts.length} 条</span></div>
            {posts.map((post, index) => (
              <article key={post.id} className="mb-3.5 rounded-[18px] border border-[#cf947e]/25 bg-white/95 p-4 shadow-[0_7px_22px_rgba(161,81,52,.08)] transition hover:-translate-y-0.5 hover:shadow-[0_12px_28px_rgba(161,81,52,.13)] cursor-pointer" onClick={() => navigate(`/posts/${post.id}`)}>
                <div className="flex items-center gap-2.5">
                  <span className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-[11px] text-xs font-bold font-data ${index === 0 ? 'bg-[#ffd34e] text-[#8f581e] shadow-[0_3px_0_#e5a928]' : index === 1 ? 'bg-[#d9e2e8] text-[#5c7180] shadow-[0_3px_0_#b7c6cf]' : index === 2 ? 'bg-[#e8c19a] text-[#84522e] shadow-[0_3px_0_#cc9d70]' : 'bg-[#e9edef] text-[#7a8b8f]'}`}>{String(index + 1).padStart(2, '0')}</span>
                  <Avatar src={post.author?.avatar_url} fallback={post.author?.nickname?.[0] || '?'} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5"><span className="truncate text-sm font-semibold text-ink">{post.author?.nickname || '校园用户'}</span>{post.author?.is_verified && <VerifiedBadge />}</div>
                    <span className="block mt-0.5 text-[11px] text-ink-muted font-data">{formatRelativeTime(post.created_at)}</span>
                  </div>
                  {post.category?.name && <span className="max-w-[120px] truncate rounded-full bg-[#fff0e7] px-2 py-0.5 text-[10px] text-[#b65335]">#{post.category.name}</span>}
                </div>
                <h2 className="mt-4 line-clamp-2 text-[16px] font-bold leading-[1.5] text-ink">{post.title}</h2>
                <p className="mt-1 line-clamp-2 text-sm leading-[1.65] text-ink-sub">{post.content}</p>
                <div className="mt-3 flex items-center justify-between border-t border-[#cf947e]/15 pt-2.5 text-[11px] text-ink-muted font-data">
                  <span className="truncate max-w-[180px]">{post.location?.name || '校园动态'}</span>
                  <span className="flex items-center gap-3"><span className="flex items-center gap-1 text-[#b65335]" title="浏览量"><Eye size={12} />{post.view_count || 0}</span><span className="flex items-center gap-1"><Heart size={12} />{post.like_count || 0}</span><span className="flex items-center gap-1"><MessageCircle size={12} />{post.comment_count || 0}</span><ChevronRight size={13} /></span>
                </div>
              </article>
            ))}
          </>
        )}
      </main>
    </div>
  );
};

export default HotRankingPage;
