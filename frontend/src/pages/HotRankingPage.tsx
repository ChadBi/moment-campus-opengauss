import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  ChevronRight,
  Eye,
  Heart,
  MessageCircle,
  Trophy,
  Medal,
  TrendingUp,
  Sparkles,
} from 'lucide-react';
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
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
}

interface RankingStat {
  totalViews: number;
  totalLikes: number;
  totalComments: number;
}

function summarize(posts: Post[]): RankingStat {
  return posts.reduce(
    (acc, p) => ({
      totalViews: acc.totalViews + (p.view_count || 0),
      totalLikes: acc.totalLikes + (p.like_count || 0),
      totalComments: acc.totalComments + (p.comment_count || 0),
    }),
    { totalViews: 0, totalLikes: 0, totalComments: 0 },
  );
}

function formatShort(value: number): string {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return String(value);
}

const easePremium = '[cubic-bezier(0.16,1,0.3,1)]';

const HotRankingPage: React.FC = () => {
  const navigate = useNavigate();
  const schoolKey = useSchoolQueryKey();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [...schoolKey, 'posts', 'hot-ranking', '7d', 'full'],
    queryFn: () =>
      postsApi.getPosts({
        page: 1,
        page_size: 10,
        status: 'published',
        sort: 'views',
        date_from: getHotSince(),
      }),
    staleTime: 60 * 1000,
  });
  const posts = (data?.items ?? []) as Post[];
  const stat = summarize(posts);

  return (
    <div
      className={`min-h-screen bg-[#FDF6F0] -mx-4 -my-4 sm:-mx-6 sm:-my-6 text-ink`}
    >
      {/* ========== HERO ========== */}
      <section
        className={`relative overflow-hidden bg-gradient-to-br from-[#FF8C5A] via-[#FF7149] to-[#EA5A2D] px-5 pt-5 pb-10 text-white shadow-[0_18px_40px_-18px_rgba(234,90,45,0.55)]`}
      >
        {/* Soft light overlays instead of hollow circles */}
        <div
          className={`pointer-events-none absolute -right-14 -top-20 h-72 w-72 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.22),transparent_60%)]`}
        />
        <div
          className={`pointer-events-none absolute -left-20 -bottom-24 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(255,223,160,0.28),transparent_58%)]`}
        />
        <div
          className={`pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_15%_0%,rgba(255,255,255,0.18),transparent_55%)]`}
        />

        {/* Nav bar */}
        <div className={`relative flex h-10 items-center justify-between`}>
          <button
            type="button"
            onClick={() => navigate(-1)}
            aria-label="返回"
            className={`flex h-9 w-9 items-center justify-center rounded-full bg-white/15 backdrop-blur-sm transition hover:bg-white/25 active:scale-95 duration-200 ${easePremium}`}
          >
            <ArrowLeft size={18} strokeWidth={2.2} />
          </button>
          <span
            className={`font-display font-semibold text-[14px] tracking-[0.22em] text-white/95`}
          >
            校园热榜
          </span>
          <div className={`w-9`} />
        </div>

        {/* Headline */}
        <div className={`relative mt-10 flex items-end justify-between gap-3`}>
          <div>
            <div
              className={`mb-2 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 backdrop-blur-sm text-[11px] font-medium tracking-wide text-white/90`}
            >
              <Sparkles size={12} className={`text-[#FFE6A3]`} />
              近 7 天 · 浏览量 TOP 10
            </div>
            <h1
              className={`font-display text-[44px] leading-[0.98] font-black tracking-tight`}
            >
              十大榜单
            </h1>
          </div>
          <div
            className={`hidden sm:flex h-14 w-14 shrink-0 items-center justify-center rounded-3xl bg-white/15 backdrop-blur-sm ring-1 ring-white/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.35)]`}
          >
            <TrendingUp size={26} className={`text-[#FFF2D0]`} strokeWidth={2.1} />
          </div>
        </div>

        <p className={`relative mt-3 text-[13px] leading-relaxed text-white/90`}>
          最受同学们关注的校园动态，按近 7 天浏览量实时排序
        </p>

        {/* Heat bar */}
        <div
          className={`relative mt-6 grid grid-cols-3 gap-2 rounded-[18px] bg-white/12 p-1.5 backdrop-blur-md ring-1 ring-white/15 shadow-[inset_0_1px_0_rgba(255,255,255,0.25)]`}
        >
          {[
            {
              label: '累计浏览',
              value: formatShort(stat.totalViews),
              icon: Eye,
            },
            {
              label: '累计点赞',
              value: formatShort(stat.totalLikes),
              icon: Heart,
            },
            {
              label: '累计评论',
              value: formatShort(stat.totalComments),
              icon: MessageCircle,
            },
          ].map((it) => (
            <div
              key={it.label}
              className={`flex flex-col items-center justify-center gap-0.5 rounded-2xl px-2 py-2.5`}
            >
              <div className={`flex items-center gap-1 text-white/80`}>
                <it.icon size={11} />
                <span className={`text-[10.5px] tracking-wide`}>{it.label}</span>
              </div>
              <span
                className={`font-display font-bold text-[19px] leading-none text-white`}
              >
                {it.value}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ========== LIST ========== */}
      <main className={`mx-auto max-w-3xl px-4 py-6`}>
        {isLoading && (
          <div className={`rounded-3xl bg-white/85 shadow-[0_8px_24px_rgba(234,90,45,0.08)]`}>
            <LoadingState title="正在翻阅校园热度" compact />
          </div>
        )}
        {isError && (
          <div className={`rounded-3xl bg-white/85 shadow-[0_8px_24px_rgba(234,90,45,0.08)]`}>
            <ErrorState
              title="校园热榜加载失败"
              onRetry={() => void refetch()}
              compact
            />
          </div>
        )}
        {!isLoading && !isError && posts.length === 0 && (
          <div className={`rounded-3xl bg-white/85 shadow-[0_8px_24px_rgba(234,90,45,0.08)]`}>
            <EmptyState title="近 7 天还没有形成热榜" />
          </div>
        )}

        {!isLoading && !isError && posts.length > 0 && (
          <>
            {/* Section label */}
            <div
              className={`mb-5 flex items-center gap-2 px-1 text-sm text-[#b05a3c]`}
            >
              <span
                className={`relative h-2 w-2 rounded-full bg-[#EA5A2D] before:absolute before:inset-0 before:-z-0 before:rounded-full before:bg-[#EA5A2D] before:animate-ping before:opacity-40`}
              />
              <span className={`font-medium`}>按浏览量排序</span>
              <span className={`ml-auto font-mono text-[12px] text-[#c48771]`}>
                共 {posts.length} 条
              </span>
            </div>

            {/* —— #1 CHAMPION CARD —— */}
            {posts[0] && (
              <article
                onClick={() => navigate(`/posts/${posts[0].id}`)}
                className={`group relative mb-5 cursor-pointer overflow-hidden rounded-[28px] bg-white ring-1 ring-black/[0.04]
                            shadow-[0_18px_50px_-20px_rgba(234,90,45,0.35),0_2px_6px_rgba(60,30,15,0.05)]
                            transition-all duration-500 ${easePremium}
                            hover:-translate-y-1 hover:shadow-[0_26px_60px_-22px_rgba(234,90,45,0.45)]`}
                style={{ animationDelay: '0ms' }}
              >
                {/* Gold halo top-left corner */}
                <div
                  className={`pointer-events-none absolute -left-10 -top-10 h-40 w-40 rounded-full bg-[radial-gradient(circle,rgba(255,191,64,0.35),transparent_62%)]`}
                />
                {/* Post thumbnail or fallback heat tile */}
                {posts[0].images?.[0]?.thumbnail_url ? (
                  <div className={`relative h-40 overflow-hidden rounded-t-[28px]`}>
                    <img
                      src={posts[0].images[0].thumbnail_url}
                      alt=""
                      className={`h-full w-full object-cover transition duration-700 ${easePremium} group-hover:scale-[1.04]`}
                      loading="lazy"
                    />
                    <div
                      className={`absolute inset-0 bg-gradient-to-t from-black/40 via-black/10 to-transparent`}
                    />
                  </div>
                ) : (
                  <div
                    className={`relative h-32 overflow-hidden rounded-t-[28px] bg-gradient-to-br from-[#FFE9B8] via-[#FFCD6D] to-[#FF9A3E]`}
                  >
                    <div
                      className={`absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(255,255,255,0.45),transparent_55%)]`}
                    />
                    <Trophy
                      size={72}
                      className={`absolute right-6 top-5 text-white/35`}
                      strokeWidth={1.2}
                    />
                  </div>
                )}

                <div className={`relative p-5 pb-4`}>
                  {/* Row: big rank badge on left + author info */}
                  <div className={`flex items-start gap-4`}>
                    {/* Champion rank */}
                    <div className={`relative -mt-10 shrink-0`}>
                      <div
                        className={`relative flex h-16 w-16 items-center justify-center rounded-2xl
                                    bg-gradient-to-br from-[#FFD76D] via-[#FFC245] to-[#FFA81E] text-[#704410]
                                    shadow-[0_10px_22px_-6px_rgba(255,168,30,0.55),inset_0_1px_0_rgba(255,255,255,0.55),inset_0_-2px_0_rgba(153,90,0,0.18)]
                                    ring-4 ring-white`}
                      >
                        <div className={`flex flex-col items-center leading-none`}>
                          <Trophy size={18} strokeWidth={2.3} className={`mb-0.5`} />
                          <span
                            className={`font-display font-black text-[20px] tracking-tight`}
                          >
                            01
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Author + category tag */}
                    <div className={`min-w-0 flex-1 pt-0.5`}>
                      <div className={`flex items-center gap-2`}>
                        <Avatar
                          src={posts[0].author?.avatar_url}
                          fallback={posts[0].author?.nickname?.[0] || '?'}
                          size="sm"
                        />
                        <div className={`min-w-0 flex-1`}>
                          <div className={`flex items-center gap-1.5`}>
                            <span
                              className={`truncate text-[14px] font-semibold text-ink`}
                            >
                              {posts[0].author?.nickname || '校园用户'}
                            </span>
                            {posts[0].author?.is_verified && <VerifiedBadge />}
                          </div>
                          <span
                            className={`mt-0.5 block text-[11px] font-mono text-ink-muted`}
                          >
                            {formatRelativeTime(posts[0].created_at)}
                          </span>
                        </div>
                      </div>
                      {posts[0].category?.name && (
                        <span
                          className={`mt-2.5 inline-flex items-center rounded-full bg-[#FFF1E6] px-2.5 py-0.5 text-[11px] font-medium text-[#C14A1F] ring-1 ring-inset ring-[#FFD6BD]`}
                        >
                          #{posts[0].category.name}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Title + content */}
                  <h2
                    className={`mt-4 line-clamp-2 text-[19px] font-bold leading-[1.35] text-ink`}
                  >
                    {posts[0].title}
                  </h2>
                  <p
                    className={`mt-1.5 line-clamp-2 text-[13.5px] leading-[1.65] text-ink-sub`}
                  >
                    {posts[0].content}
                  </p>

                  {/* Bottom metadata */}
                  <div
                    className={`mt-4 flex items-center justify-between border-t border-[#F1D8C8] pt-3 text-[11.5px]`}
                  >
                    <span
                      className={`max-w-[200px] truncate text-ink-muted`}
                      title={posts[0].location?.name || '校园动态'}
                    >
                      📍 {posts[0].location?.name || '校园动态'}
                    </span>
                    <div className={`flex items-center gap-3 font-mono text-[#C14A1F]`}>
                      <span
                        className={`flex items-center gap-1`}
                        title={`浏览 ${posts[0].view_count || 0}`}
                      >
                        <Eye size={13} strokeWidth={2} />
                        {posts[0].view_count || 0}
                      </span>
                      <span
                        className={`flex items-center gap-1`}
                        title={`点赞 ${posts[0].like_count || 0}`}
                      >
                        <Heart size={13} strokeWidth={2} />
                        {posts[0].like_count || 0}
                      </span>
                      <span
                        className={`flex items-center gap-1`}
                        title={`评论 ${posts[0].comment_count || 0}`}
                      >
                        <MessageCircle size={13} strokeWidth={2} />
                        {posts[0].comment_count || 0}
                      </span>
                      <ChevronRight
                        size={15}
                        strokeWidth={2.3}
                        className={`transition-transform duration-300 ${easePremium} group-hover:translate-x-0.5 text-[#EA5A2D]`}
                      />
                    </div>
                  </div>
                </div>
              </article>
            )}

            {/* —— #2 / #3 并列卡片 —— */}
            {posts.length > 1 && (
              <div
                className={`mb-5 grid gap-4 md:grid-cols-2`}
                style={{ animationDelay: '80ms' }}
              >
                {posts.slice(1, 3).map((post, i) => {
                  const rank = i + 2; // 2 or 3
                  const isSilver = rank === 2;
                  const medalGradient = isSilver
                    ? 'from-[#E8EEF5] via-[#D5DFEA] to-[#BCC9D7]'
                    : 'from-[#FFC6A8] via-[#F29567] to-[#E07A49]';
                  const medalText = isSilver
                    ? 'text-[#4B5B6B]'
                    : 'text-[#69321A]';
                  const medalShadow = isSilver
                    ? '0_10px_22px_-8px_rgba(120,140,160,0.40),inset_0_1px_0_rgba(255,255,255,0.7),inset_0_-2px_0_rgba(80,100,120,0.12)'
                    : '0_10px_22px_-8px_rgba(224,122,73,0.50),inset_0_1px_0_rgba(255,255,255,0.55),inset_0_-2px_0_rgba(120,45,10,0.14)';
                  const halo = isSilver
                    ? 'rgba(160,180,200,0.28)'
                    : 'rgba(240,140,90,0.32)';

                  return (
                    <article
                      key={post.id}
                      onClick={() => navigate(`/posts/${post.id}`)}
                      className={`group relative cursor-pointer overflow-hidden rounded-[22px] bg-white ring-1 ring-black/[0.04]
                                  shadow-[0_12px_30px_-14px_rgba(234,90,45,0.28),0_2px_6px_rgba(60,30,15,0.05)]
                                  transition-all duration-500 ${easePremium}
                                  hover:-translate-y-1 hover:shadow-[0_20px_40px_-16px_rgba(234,90,45,0.38)]`}
                    >
                      <div
                        className={`pointer-events-none absolute -left-6 -top-6 h-28 w-28 rounded-full`}
                        style={{
                          background: `radial-gradient(circle,${halo},transparent 62%)`,
                        }}
                      />
                      <div className={`p-4 pb-3.5`}>
                        {/* Medal + author row */}
                        <div className={`flex items-start gap-3`}>
                          <div
                            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${medalGradient} ${medalText} ring-4 ring-white`}
                            style={{ boxShadow: medalShadow }}
                          >
                            <div
                              className={`flex flex-col items-center leading-none`}
                            >
                              <Medal
                                size={14}
                                strokeWidth={2.3}
                                className={`mb-0.5`}
                              />
                              <span
                                className={`font-display font-black text-[13.5px] tracking-tight`}
                              >
                                0{rank}
                              </span>
                            </div>
                          </div>
                          <div className={`min-w-0 flex-1`}>
                            <div className={`flex items-center gap-1.5`}>
                              <Avatar
                                src={post.author?.avatar_url}
                                fallback={post.author?.nickname?.[0] || '?'}
                                size="sm"
                              />
                              <span
                                className={`truncate text-[13.5px] font-semibold text-ink`}
                              >
                                {post.author?.nickname || '校园用户'}
                              </span>
                              {post.author?.is_verified && <VerifiedBadge />}
                              <span
                                className={`ml-auto shrink-0 text-[10.5px] font-mono text-ink-muted`}
                              >
                                {formatRelativeTime(post.created_at)}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Category + title */}
                        {post.category?.name && (
                          <span
                            className={`mt-3 inline-flex items-center rounded-full bg-[#FFF6EF] px-2 py-0.5 text-[10.5px] font-medium text-[#C14A1F] ring-1 ring-inset ring-[#FFE2CC]`}
                          >
                            #{post.category.name}
                          </span>
                        )}
                        <h3
                          className={`mt-2 line-clamp-2 text-[16.5px] font-bold leading-[1.4] text-ink`}
                        >
                          {post.title}
                        </h3>
                        <p
                          className={`mt-1 line-clamp-2 text-[12.5px] leading-[1.6] text-ink-sub`}
                        >
                          {post.content}
                        </p>

                        {/* Bottom */}
                        <div
                          className={`mt-3.5 flex items-center justify-between border-t border-[#F1D8C8]/70 pt-2.5 text-[11px]`}
                        >
                          <span className={`truncate text-ink-muted max-w-[140px]`}>
                            {post.location?.name || '校园动态'}
                          </span>
                          <div
                            className={`flex items-center gap-2.5 font-mono text-[#C14A1F]`}
                          >
                            <span className={`flex items-center gap-1`}>
                              <Eye size={12} strokeWidth={2} />
                              {post.view_count || 0}
                            </span>
                            <span className={`flex items-center gap-1`}>
                              <Heart size={12} strokeWidth={2} />
                              {post.like_count || 0}
                            </span>
                            <span className={`flex items-center gap-1`}>
                              <MessageCircle size={12} strokeWidth={2} />
                              {post.comment_count || 0}
                            </span>
                            <ChevronRight
                              size={14}
                              strokeWidth={2.3}
                              className={`text-[#EA5A2D] transition-transform duration-300 ${easePremium} group-hover:translate-x-0.5`}
                            />
                          </div>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}

            {/* —— #4 - #10 紧凑列表 —— */}
            {posts.length > 3 && (
              <div
                className={`overflow-hidden rounded-3xl bg-white ring-1 ring-black/[0.04] shadow-[0_10px_28px_-14px_rgba(234,90,45,0.22)]`}
              >
                <div className={`flex items-center justify-between px-5 py-3 border-b border-[#F1D8C8]/80`}>
                  <span
                    className={`text-[12px] font-medium text-[#b05a3c] tracking-wide`}
                  >
                    第 4 - {posts.length} 名
                  </span>
                  <span className={`text-[10.5px] font-mono text-ink-muted`}>
                    紧凑视图 · 点击查看详情
                  </span>
                </div>
                <ul>
                  {posts.slice(3).map((post, i) => {
                    const rank = i + 4;
                    return (
                      <li
                        key={post.id}
                        onClick={() => navigate(`/posts/${post.id}`)}
                        className={`group relative cursor-pointer flex items-center gap-3 px-4 py-3.5
                                    border-b last:border-b-0 border-[#F5E2D4]/60
                                    transition-all duration-300 ${easePremium}
                                    hover:bg-gradient-to-r hover:from-[#FFF1E6] hover:to-transparent
                                    hover:pl-[calc(1rem-3px)]
                                    before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-[3px] before:rounded-r-full before:bg-[#EA5A2D]
                                    before:scale-y-0 before:origin-center before:transition before:duration-300 ${easePremium}
                                    hover:before:scale-y-100`}
                        style={{ animationDelay: `${(i + 3) * 50}ms` }}
                      >
                        {/* Rank badge */}
                        <div
                          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#FFE7D8] text-[#C14A1F] font-display font-black text-[13px] ring-1 ring-inset ring-[#FFD1B5] transition-all duration-300 ${easePremium} group-hover:bg-[#EA5A2D] group-hover:text-white group-hover:ring-[#EA5A2D]`}
                        >
                          {String(rank).padStart(2, '0')}
                        </div>

                        {/* Title + author */}
                        <div className={`min-w-0 flex-1`}>
                          <div className={`flex items-center gap-2`}>
                            <h4
                              className={`truncate text-[14.5px] font-semibold leading-snug text-ink transition-colors duration-200 group-hover:text-[#C14A1F]`}
                            >
                              {post.title}
                            </h4>
                            {post.category?.name && (
                              <span
                                className={`shrink-0 rounded-full bg-[#FFF6EF] px-1.5 py-[1px] text-[10px] font-medium text-[#C14A1F] ring-1 ring-inset ring-[#FFE2CC]`}
                              >
                                #{post.category.name}
                              </span>
                            )}
                          </div>
                          <div
                            className={`mt-1 flex items-center gap-2 text-[11px] text-ink-muted`}
                          >
                            <span
                              className={`truncate max-w-[110px]`}
                              title={post.author?.nickname}
                            >
                              {post.author?.nickname || '校园用户'}
                            </span>
                            <span className={`text-[#E8C9B5]`}>·</span>
                            <span className={`font-mono`}>
                              {formatRelativeTime(post.created_at)}
                            </span>
                            {post.location?.name && (
                              <>
                                <span className={`text-[#E8C9B5]`}>·</span>
                                <span className={`truncate max-w-[100px]`}>
                                  {post.location.name}
                                </span>
                              </>
                            )}
                          </div>
                        </div>

                        {/* Stats + chevron */}
                        <div
                          className={`ml-2 shrink-0 flex items-center gap-2.5 font-mono text-[11.5px] text-[#C14A1F]`}
                        >
                          <Eye size={12} strokeWidth={2} />
                          <span>{formatShort(post.view_count || 0)}</span>
                          <ChevronRight
                            size={14}
                            strokeWidth={2.3}
                            className={`text-[#EA5A2D]/70 transition-all duration-300 ${easePremium} group-hover:text-[#EA5A2D] group-hover:translate-x-0.5`}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {/* Footer note */}
            <p
              className={`mt-6 text-center text-[11px] font-mono text-[#c48771]/80`}
            >
              * 榜单每分钟刷新一次 · 仅统计近 7 天已发布的公开动态
            </p>
          </>
        )}
      </main>
    </div>
  );
};

export default HotRankingPage;
