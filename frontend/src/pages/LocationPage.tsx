import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  MapPin,
  Star,
  StarHalf,
  ChevronRight,
  LogIn,
  MessageSquare,
  Check,
  BadgeCheck,
  Search,
  X,
  Edit3,
} from 'lucide-react';
import {
  locationsApi,
  type LocationItem,
  type LocationReviewItem,
  type LocationDetail,
} from '../services/locations';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { EmptyState, ErrorState, LoadingState } from '../components/state';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';
import { useCampusStore } from '../store/useCampusStore';
import { VerifyGate } from '../components/VerifyGate';
import { logger } from '../utils/logger';
import { formatRelativeTime } from '../utils/date';

// A-05: 校园地点页（当前学校全部地点 + 设施评分评价）
// 页面形态：按名称排列的学校地点卡片列表；点击卡片打开详情 Modal（评分汇总 + 评价 + 提交/撤回）

function ScoreStars({ score, size = 14 }: { score: number; size?: number }) {
  const full = Math.floor(score);
  const half = score - full >= 0.25 && score - full < 0.75;
  const remainder = score - full - (half ? 0.5 : 0);
  return (
    <span className="inline-flex items-center gap-0.5 text-lamp" aria-label={`评分 ${score} 分`}>
      {Array.from({ length: full }).map((_, i) => (
        <Star key={`f${i}`} size={size} className="fill-current" />
      ))}
      {half && <StarHalf key="h" size={size} className="fill-current" />}
      {Array.from({ length: Math.max(0, 5 - full - (half ? 1 : 0)) }).map((_, i) => (
        <Star key={`e${i}`} size={size} className="text-line" />
      ))}
      {remainder > 0 && <Star key="r" size={size} className="fill-current opacity-60" />}
    </span>
  );
}

const LocationPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const { showToast } = useUIStore();
  const { currentSchoolName } = useCampusStore();

  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 详情 Modal 状态
  const [activeId, setActiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<(LocationDetail & { reviews: LocationReviewItem[] }) | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [myReview, setMyReview] = useState<LocationReviewItem | null>(null);
  // 评价表单
  const [score, setScore] = useState(5);
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [factKey, setFactKey] = useState('normal_hours');
  const [factLabel, setFactLabel] = useState('营业时间');
  const [factValue, setFactValue] = useState('');
  const [factReason, setFactReason] = useState('');
  const [submittingProposal, setSubmittingProposal] = useState(false);
  // 常态不展开编辑表单：已有 myReview 时，点击「更新评价」才进入编辑态
  const [editingReview, setEditingReview] = useState(false);

  // 地点列表搜索栏：按名称/描述/建筑/楼层过滤
  const [searchKeyword, setSearchKeyword] = useState('');
  const filteredLocations = useMemo(() => {
    const q = searchKeyword.trim().toLowerCase();
    if (!q) return locations;
    return locations.filter(
      (loc) =>
        loc.name.toLowerCase().includes(q) ||
        (loc.description?.toLowerCase().includes(q) ?? false) ||
        (loc.building?.toLowerCase().includes(q) ?? false) ||
        (loc.floor?.toLowerCase().includes(q) ?? false)
    );
  }, [locations, searchKeyword]);

  const loadLocations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await locationsApi.getLocations();
      setLocations(data);
    } catch (err: unknown) {
      logger.error('加载地点失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail || '加载地点失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const openDetail = useCallback(async (locationId: number) => {
    setActiveId(locationId);
    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    setMyReview(null);
    setScore(5);
    setContent('');
    try {
      const [d, reviews] = await Promise.all([
        locationsApi.getDetail(locationId),
        locationsApi.getReviews(locationId),
      ]);
      setDetail({ ...d, reviews: reviews.items });
      setMyReview(d.my_review ?? null);
      if (d.my_review) {
        setScore(d.my_review.score);
        setContent(d.my_review.content ?? '');
      }
    } catch (err: unknown) {
      logger.error('加载地点详情失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      setDetailError(e?.response?.data?.detail || '加载地点详情失败');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // 挂载后加载全部地点 + 处理深链 ?location={id}（地图地点面板「查看完整详情」跳转）
  useEffect(() => {
    void Promise.resolve().then(() => {
      void loadLocations();
      const locParam = searchParams.get('location');
      if (locParam) {
        const id = Number(locParam);
        if (Number.isInteger(id) && id > 0) {
          void openDetail(id);
        }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const closeDetail = useCallback(() => {
    setActiveId(null);
    setDetail(null);
    setMyReview(null);
    setFactValue('');
    setFactReason('');
  }, []);

  const handleSubmitFactProposal = useCallback(async () => {
    if (!activeId || !factValue.trim()) return;
    setSubmittingProposal(true);
    try {
      await locationsApi.submitFactProposal(activeId, {
        upserts: [{
          fact_key: factKey,
          label: factLabel.trim() || undefined,
          value: factValue.trim(),
        }],
        reason: factReason.trim() || undefined,
      });
      setFactValue('');
      setFactReason('');
      showToast('资料提议已提交，等待管理员审核', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '提交资料提议失败', 'error');
    } finally {
      setSubmittingProposal(false);
    }
  }, [activeId, factKey, factLabel, factReason, factValue, showToast]);

  const handleSubmitReview = useCallback(async () => {
    if (!activeId) return;
    setSubmitting(true);
    try {
      const review = await locationsApi.submitReview(activeId, {
        score,
        content: content.trim() || undefined,
      });
      const [d, reviews] = await Promise.all([
        locationsApi.getDetail(activeId),
        locationsApi.getReviews(activeId),
      ]);
      setDetail({ ...d, reviews: reviews.items });
      setMyReview(review);
      setEditingReview(false);
      showToast('评价已提交', 'success');
    } catch (err: unknown) {
      logger.error('提交评价失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '提交评价失败', 'error');
    } finally {
      setSubmitting(false);
    }
  }, [activeId, score, content, showToast]);

  const handleWithdrawReview = useCallback(async () => {
    if (!activeId) return;
    setSubmitting(true);
    try {
      await locationsApi.withdrawReview(activeId);
      const [d, reviews] = await Promise.all([
        locationsApi.getDetail(activeId),
        locationsApi.getReviews(activeId),
      ]);
      setDetail({ ...d, reviews: reviews.items });
      setMyReview(null);
      setScore(5);
      setContent('');
      setEditingReview(false);
      showToast('评价已撤回', 'success');
    } catch (err: unknown) {
      logger.error('撤回评价失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '撤回评价失败', 'error');
    } finally {
      setSubmitting(false);
    }
  }, [activeId, showToast]);

  return (
    <div className="max-w-3xl mx-auto py-4 px-1">
      {/* 页头 */}
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">
            校园地点
          </h1>
          <p className="text-ink-muted text-sm mt-1">
            {currentSchoolName || '学校'}全部地点 · 打印店 · 食堂 · 图书馆，看评分做选择
          </p>
        </div>
      </header>

      {/* 搜索框：放在地点列表的容器（bg-paper 卡片）内，统一搜索名称/描述/楼栋/楼层 */}
      <div className="bg-paper rounded-[16px] border border-line/60 p-4 shadow-sm mb-4">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
            aria-hidden="true"
          />
          <input
            type="search"
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            placeholder={`搜索${currentSchoolName || '学校'}地点（按名称/描述/楼栋/楼层）`}
            className="w-full h-11 pl-10 pr-10 rounded-[12px] bg-mist/40 border border-line/60 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake/40"
            aria-label="地点搜索"
          />
          {searchKeyword && (
            <button
              type="button"
              onClick={() => setSearchKeyword('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-paper flex items-center justify-center text-ink-sub hover:text-ink hover:bg-line transition-colors"
              aria-label="清除搜索"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="bg-paper rounded-[16px] border border-line/60">
          <LoadingState title="正在加载地点" />
        </div>
      ) : error ? (
        <div className="bg-paper rounded-[16px] border border-line/60">
          <ErrorState description={error} onRetry={() => void loadLocations()} />
        </div>
      ) : filteredLocations.length === 0 ? (
        <div className="bg-paper rounded-[16px] border border-line/60 shadow-sm">
          <EmptyState
            title={searchKeyword ? '没有匹配的地点' : '暂无地点'}
            description={searchKeyword ? '试试换个关键词吧' : '去探索更多校园角落吧。'}
            icon={<MapPin size={24} />}
          />
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {filteredLocations.map((loc) => (
            <button
              key={loc.id}
              onClick={() => void openDetail(loc.id)}
              className="text-left bg-paper rounded-[14px] border border-line/60 p-4 hover:border-lake/40 hover:shadow-md transition-all group"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-9 h-9 rounded-[10px] bg-mist grid place-items-center flex-shrink-0">
                    <MapPin size={16} className="text-lamp" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <h3 className="font-semibold text-ink text-sm truncate">{loc.name}</h3>
                      {loc.is_verified && (
                        <BadgeCheck size={14} className="text-lake flex-shrink-0" aria-label="官方核验" />
                      )}
                    </div>
                    <div className="text-xs text-ink-muted mt-0.5 truncate">
                      {loc.building || loc.floor || ''}
                    </div>
                  </div>
                </div>
                <ChevronRight size={16} className="text-ink-muted mt-1 flex-shrink-0 group-hover:text-lake transition-colors" />
              </div>

              {loc.description && (
                <p className="text-sm text-ink-sub mt-2.5 line-clamp-1">{loc.description}</p>
              )}

              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <ScoreStars score={loc.avg_score} />
                  <span className="text-xs font-semibold text-ink">{loc.avg_score.toFixed(1)}</span>
                  <span className="text-[11px] text-ink-muted">{loc.rating_count} 人评</span>
                </div>
                <span className="text-[11px] text-ink-muted inline-flex items-center gap-1">
                  <MessageSquare size={11} />
                  {loc.review_count} 条评价
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* 详情 Modal */}
      <Modal
        isOpen={activeId !== null}
        onClose={closeDetail}
        title={detail?.location.name || '地点详情'}
        size="md"
      >
        {detailLoading ? (
          <LoadingState title="正在加载详情" />
        ) : detailError ? (
          <ErrorState description={detailError} onRetry={activeId ? () => void openDetail(activeId) : undefined} />
        ) : detail ? (
          <div className="space-y-5">
            {/* 已审核稳定资料：不由 AI 改写 */}
            <section className="rounded-[12px] border border-line/60 p-4">
              <div className="flex items-center justify-between gap-2 mb-3">
                <h3 className="font-semibold text-ink text-sm">已审核资料</h3>
                <span className="text-[11px] text-ink-muted">管理员审核后生效</span>
              </div>
              {detail.facts.length === 0 ? (
                <p className="text-sm text-ink-muted">暂无稳定资料。</p>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  {detail.facts.map((fact) => (
                    <div key={fact.id} className="rounded-[10px] bg-mist/60 px-3 py-2">
                      <div className="text-xs text-ink-muted">{fact.label}</div>
                      <div className="text-sm text-ink mt-0.5 whitespace-pre-wrap">{fact.value}</div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* AI 此刻摘要：只展示管理员批准版本 */}
            <section className="rounded-[12px] border border-lake/20 bg-lake/5 p-4">
              <div className="flex items-center justify-between gap-2 mb-2">
                <h3 className="font-semibold text-ink text-sm">AI「此刻摘要」</h3>
                {detail.summary.confidence_level !== 'insufficient' && (
                  <span className="text-[11px] text-lake font-medium">
                    可信层级：{detail.summary.confidence_level}
                  </span>
                )}
              </div>
              {detail.summary.summary_text ? (
                <p className="text-sm text-ink-sub leading-relaxed">{detail.summary.summary_text}</p>
              ) : (
                <p className="text-sm text-ink-muted">暂无足够近期信息，暂不生成具体结论。</p>
              )}
              <div className="mt-2 text-[11px] text-ink-muted">
                {detail.summary.generated_at
                  ? `整理于 ${formatRelativeTime(detail.summary.generated_at)} · ${detail.summary.source_count} 条来源`
                  : '来源达到门槛并经管理员审核后才会展示'}
              </div>
              {detail.summary.claims.length > 0 && (
                <div className="mt-3 space-y-2">
                  {detail.summary.claims.map((claim) => (
                    <details key={claim.claim_id} className="rounded-[10px] bg-paper/80 px-3 py-2">
                      <summary className="cursor-pointer text-sm text-ink">{claim.text}</summary>
                      <div className="mt-2 text-[11px] text-ink-muted">
                        查看依据：{claim.source_refs.map((ref) => `${ref.source_type}:${ref.source_id}`).join('、')}
                      </div>
                    </details>
                  ))}
                </div>
              )}
              {detail.summary.conflicts.length > 0 && (
                <div className="mt-3 rounded-[10px] border border-lamp/30 bg-lamp/10 px-3 py-2 text-xs text-ink-sub">
                  <span className="font-medium">存在相互矛盾的信息：</span>
                  {detail.summary.conflicts.map((conflict) => conflict.text).join('；')}
                </div>
              )}
              {detail.summary.sources.length > 0 && (
                <div className="mt-3 border-t border-line/50 pt-2">
                  <div className="text-[11px] text-ink-muted mb-1">来源卡片</div>
                  <div className="space-y-1">
                    {detail.summary.sources.map((source) => (
                      <div key={`${source.source_type}:${source.source_id}`} className="text-xs text-ink-sub">
                        <span className="font-medium">{source.source_type}:{source.source_id}</span>
                        {source.snippet ? ` · ${source.snippet}` : ''}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>

            {/* 评分汇总 */}
            <div className="bg-mist/60 rounded-[12px] p-4">
              <div className="flex items-center gap-3">
                <ScoreStars score={detail.location.avg_score} size={18} />
                <span className="text-2xl font-display font-bold text-ink">
                  {detail.location.avg_score.toFixed(1)}
                </span>
                <span className="text-xs text-ink-muted">
                  {detail.location.rating_count} 人评分 · {detail.location.review_count} 条评价
                </span>
              </div>
              {detail.location.description && (
                <p className="text-sm text-ink-sub mt-2 leading-relaxed">{detail.location.description}</p>
              )}
              <div className="text-xs text-ink-muted mt-2 flex items-center gap-1">
                <MapPin size={12} className="flex-shrink-0" />
                {detail.location.building || detail.location.floor || '校园内'}
              </div>
            </div>

            {/* 我的评价：常态紧凑单层布局（标题+更新按钮同排，不做内层卡片嵌套）；避免常态裸露编辑表单误触 */}
            <div className="border border-line/60 rounded-[12px] p-3.5">
              {!myReview || editingReview ? (
                /* 未评价 / 编辑态：标题 + 编辑控件 */
                <>
                  <h3 className="font-semibold text-ink text-sm mb-3">
                    {myReview ? '我的评价' : '给这个地点打个分'}
                  </h3>
                  {!isAuthenticated ? (
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm text-ink-muted">登录后即可为校园设施评分评价</p>
                      <Button variant="primary" size="sm" icon={<LogIn size={14} />} onClick={() => navigate('/login')}>
                        去登录
                      </Button>
                    </div>
                  ) : (
                    /* D4: 编辑态 / 尚未评价：评分 + 文本 + 提交/撤回表单，VerifyGate 保护校园身份认证 */
                    <VerifyGate compact message="完成校园身份认证后即可评分评价">
                      <div className="space-y-3">
                      <div className="flex items-center gap-1" role="radiogroup" aria-label="评分">
                        {[1, 2, 3, 4, 5].map((value) => (
                          <button
                            key={value}
                            type="button"
                            onClick={() => setScore(value)}
                            aria-label={`${value} 星`}
                            aria-checked={score === value}
                            role="radio"
                            className="p-0.5"
                          >
                            <Star
                              size={24}
                              className={value <= score ? 'fill-current text-lamp' : 'text-line'}
                            />
                          </button>
                        ))}
                        <span className="ml-2 text-sm font-semibold text-ink">{score}.0 分</span>
                      </div>
                      <textarea
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        maxLength={500}
                        rows={3}
                        placeholder="分享你的体验，如排队情况、价格、营业时间等（最多 500 字）"
                        className="w-full rounded-[10px] border border-line bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-lake/30 resize-none"
                      />
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        {myReview && editingReview && (
                          <Button
                            variant="text"
                            size="sm"
                            onClick={() => setEditingReview(false)}
                          >
                            取消编辑
                          </Button>
                        )}
                        <div className="flex items-center justify-end gap-2 ml-auto">
                          {myReview && (
                            <Button variant="text" size="sm" loading={submitting} onClick={() => void handleWithdrawReview()}>
                              撤回评价
                            </Button>
                          )}
                          <Button variant="primary" size="sm" loading={submitting} onClick={() => void handleSubmitReview()} icon={<Check size={14} />}>
                            {myReview ? '更新评价' : '提交评价'}
                          </Button>
                        </div>
                      </div>
                      </div>
                    </VerifyGate>
                  )}
                </>
              ) : (
                /* 常态（已有评价 + 不在编辑）：单层紧凑布局，标题与「更新评价」同排；不嵌套内层卡片 */
                <>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <h3 className="font-semibold text-ink text-[13px] leading-none">
                      我的评价
                    </h3>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => {
                        setScore(myReview.score);
                        setContent(myReview.content ?? '');
                        setEditingReview(true);
                      }}
                      icon={<Edit3 size={14} />}
                    >
                      更新评价
                    </Button>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="font-medium text-ink text-[13px] truncate">我</span>
                      {myReview.author?.is_verified && (
                        <BadgeCheck size={13} className="text-lake flex-shrink-0" aria-label="已认证" />
                      )}
                      <span className="mx-1.5 h-3.5 w-px bg-line/60" aria-hidden="true" />
                      <ScoreStars score={myReview.score} size={13} />
                      <span className="text-xs text-ink-sub font-semibold">{myReview.score}.0</span>
                    </div>
                    <span className="text-[11px] text-ink-muted flex-shrink-0">
                      {formatRelativeTime(myReview.created_at)}
                    </span>
                  </div>
                  {myReview.content && (
                    <p className="text-[13px] text-ink-sub mt-2 leading-relaxed whitespace-pre-wrap">
                      {myReview.content}
                    </p>
                  )}
                </>
              )}
            </div>

            {/* 全部评价 */}
            <div>
              <h3 className="font-semibold text-ink text-sm mb-3">全部评价</h3>
              {detail.reviews.length === 0 ? (
                <p className="text-sm text-ink-muted">还没有评价，来当第一个吧。</p>
              ) : (
                <div className="divide-y divide-line/60">
                  {detail.reviews.map((review) => (
                    <div key={review.id} className="py-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="font-medium text-ink text-sm truncate">
                            {review.author?.nickname || '匿名用户'}
                          </span>
                          {review.author?.is_verified && (
                            <BadgeCheck size={13} className="text-lake flex-shrink-0" aria-label="已认证" />
                          )}
                        </div>
                        <span className="text-[11px] text-ink-muted flex-shrink-0">
                          {formatRelativeTime(review.created_at)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-1.5">
                        <ScoreStars score={review.score} size={12} />
                        <span className="text-xs text-ink-sub">{review.score}.0</span>
                      </div>
                      {review.content && (
                        <p className="text-sm text-ink-sub mt-1.5 leading-relaxed">{review.content}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 稳定资料提议 */}
            <section className="border border-line/60 rounded-[12px] p-4">
              <h3 className="font-semibold text-ink text-sm mb-1">补充地点资料</h3>
              <p className="text-xs text-ink-muted mb-3">仅认证用户可提交，管理员审核后才会公开。</p>
              {!isAuthenticated ? (
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm text-ink-muted">登录并完成校园认证后即可补充</span>
                  <Button variant="secondary" size="sm" onClick={() => navigate('/login')}>去登录</Button>
                </div>
              ) : (
                <VerifyGate compact message="完成校园身份认证后即可补充资料">
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        value={factKey}
                        onChange={(e) => setFactKey(e.target.value)}
                        className="rounded-[10px] border border-line bg-paper px-3 py-2 text-sm text-ink"
                      >
                        <option value="normal_hours">营业时间</option>
                        <option value="services">服务内容</option>
                        <option value="price_note">价格说明</option>
                        <option value="contact">联系方式</option>
                        <option value="access">进入方式</option>
                        <option value="booking">预约方式</option>
                        <option value="other">其他</option>
                      </select>
                      <input
                        value={factLabel}
                        onChange={(e) => setFactLabel(e.target.value)}
                        placeholder="资料标题"
                        className="rounded-[10px] border border-line bg-paper px-3 py-2 text-sm text-ink"
                      />
                    </div>
                    <textarea
                      value={factValue}
                      onChange={(e) => setFactValue(e.target.value)}
                      rows={2}
                      maxLength={2000}
                      placeholder="填写你确认过的地点资料"
                      className="w-full rounded-[10px] border border-line bg-paper px-3 py-2 text-sm text-ink resize-none"
                    />
                    <input
                      value={factReason}
                      onChange={(e) => setFactReason(e.target.value)}
                      maxLength={1000}
                      placeholder="补充说明（可选）"
                      className="w-full rounded-[10px] border border-line bg-paper px-3 py-2 text-sm text-ink"
                    />
                    <div className="flex justify-end">
                      <Button
                        variant="primary"
                        size="sm"
                        loading={submittingProposal}
                        disabled={!factValue.trim()}
                        onClick={() => void handleSubmitFactProposal()}
                      >
                        提交资料提议
                      </Button>
                    </div>
                  </div>
                </VerifyGate>
              )}
            </section>
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

export default LocationPage;
