import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MapPin,
  Navigation,
  Star,
  StarHalf,
  ChevronRight,
  LogIn,
  MessageSquare,
  Check,
  BadgeCheck,
} from 'lucide-react';
import { locationsApi, type LocationItem, type LocationReviewItem } from '../services/locations';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { EmptyState, ErrorState, LoadingState } from '../components/state';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';
import { useCampusStore } from '../store/useCampusStore';
import { logger } from '../utils/logger';
import { formatRelativeTime } from '../utils/date';
import { wgs84ToGcj02 } from '../utils/coordinates';

// A-05: 校园地点页（附近 + 设施评分评价）
// 页面形态：顶部定位状态 + 附近地点卡片列表；点击卡片打开详情 Modal（评分汇总 + 评价 + 提交/撤回）

const FALLBACK_CENTER: [number, number] = [120.27116, 31.483652];

interface NearbyState {
  lat: number;
  lng: number;
  source: 'gps' | 'school' | 'fallback';
  label: string;
}

function formatDistance(m?: number | null): string {
  if (m == null) return '未知距离';
  if (m < 1000) return `${Math.round(m)} 米`;
  return `${(m / 1000).toFixed(1)} 公里`;
}

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
  const { isAuthenticated } = useAuthStore();
  const { showToast } = useUIStore();
  const { currentSchoolCenter, currentSchoolName } = useCampusStore();

  const [nearby, setNearby] = useState<LocationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [center, setCenter] = useState<NearbyState | null>(null);
  const [radius, setRadius] = useState(5000);

  // 详情 Modal 状态
  const [activeId, setActiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<{ location: LocationItem; reviews: LocationReviewItem[] } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [myReview, setMyReview] = useState<LocationReviewItem | null>(null);
  // 评价表单
  const [score, setScore] = useState(5);
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const activeCenter: [number, number] = useMemo(
    () =>
      currentSchoolCenter
        ? [currentSchoolCenter.lng, currentSchoolCenter.lat]
        : FALLBACK_CENTER,
    [currentSchoolCenter]
  );

  const loadNearby = useCallback(
    async (lat: number, lng: number, source: NearbyState['source'], label: string) => {
      setLoading(true);
      setError(null);
      setCenter({ lat, lng, source, label });
      try {
        const data = await locationsApi.getNearby(lat, lng, radius);
        setNearby(data.items);
      } catch (err: unknown) {
        logger.error('加载附近地点失败:', err);
        const e = err as { response?: { data?: { detail?: string } } };
        setError(e?.response?.data?.detail || '加载附近地点失败');
      } finally {
        setLoading(false);
      }
    },
    [radius]
  );

  const handleGeolocate = useCallback(() => {
    if (!navigator.geolocation) {
      void loadNearby(activeCenter[1], activeCenter[0], 'school', currentSchoolName || '校园中心');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const gcj02 = wgs84ToGcj02(position.coords.latitude, position.coords.longitude);
        setLocating(false);
        void loadNearby(gcj02.latitude, gcj02.longitude, 'gps', '我的位置');
      },
      () => {
        setLocating(false);
        void loadNearby(activeCenter[1], activeCenter[0], 'school', currentSchoolName || '校园中心');
      }
    );
  }, [activeCenter, currentSchoolName, loadNearby]);

  useEffect(() => {
    // 用 microtask 延迟同步 setState，避免 react-hooks/set-state-in-effect 规则告警
    void Promise.resolve().then(() => handleGeolocate());
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      setDetail({ location: d.location, reviews: reviews.items });
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

  const closeDetail = useCallback(() => {
    setActiveId(null);
    setDetail(null);
    setMyReview(null);
  }, []);

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
      setDetail({ location: d.location, reviews: reviews.items });
      setMyReview(review);
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
      setDetail({ location: d.location, reviews: reviews.items });
      setMyReview(null);
      setScore(5);
      setContent('');
      showToast('评价已撤回', 'success');
    } catch (err: unknown) {
      logger.error('撤回评价失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '撤回评价失败', 'error');
    } finally {
      setSubmitting(false);
    }
  }, [activeId, showToast]);

  const handleRadiusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = Number(e.target.value);
    setRadius(value);
    if (center) {
      void loadNearby(center.lat, center.lng, center.source, center.label);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-4 px-1">
      {/* 页头 */}
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">
            校园地点
          </h1>
          <p className="text-ink-muted text-sm mt-1">
            附近设施 · 打印店 · 食堂 · 图书馆，看评分做选择
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={radius}
            onChange={handleRadiusChange}
            className="h-9 rounded-[10px] border border-line bg-paper px-3 text-xs text-ink-sub focus:outline-none focus:ring-2 focus:ring-lake/30"
            aria-label="搜索半径"
          >
            <option value={1000}>1 公里内</option>
            <option value={3000}>3 公里内</option>
            <option value={5000}>5 公里内</option>
            <option value={10000}>10 公里内</option>
          </select>
          <Button
            variant="secondary"
            size="sm"
            loading={locating}
            onClick={handleGeolocate}
            icon={!locating ? <Navigation size={14} /> : undefined}
          >
            {center?.source === 'gps' ? '重新定位' : '定位'}
          </Button>
        </div>
      </header>

      {/* 定位状态条 */}
      {center && (
        <div className="mb-4 flex items-center gap-2 text-xs text-ink-sub bg-mist rounded-[10px] px-3 py-2">
          <MapPin size={14} className="text-lake flex-shrink-0" />
          <span className="truncate">
            {center.source === 'gps'
              ? `当前定位：${center.label}`
              : `展示 ${center.label} 附近（未授权定位）`}
          </span>
        </div>
      )}

      {loading ? (
        <div className="bg-paper rounded-[16px] border border-line/60">
          <LoadingState title="正在加载附近地点" />
        </div>
      ) : error ? (
        <div className="bg-paper rounded-[16px] border border-line/60">
          <ErrorState description={error} onRetry={() => center && void loadNearby(center.lat, center.lng, center.source, center.label)} />
        </div>
      ) : nearby.length === 0 ? (
        <div className="bg-paper rounded-[16px] border border-line/60 shadow-sm">
          <EmptyState
            title="附近暂无地点"
            description="换个范围或稍后再来看看校园设施。"
            icon={<MapPin size={24} />}
          />
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {nearby.map((loc) => (
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
                    <div className="text-xs text-ink-muted mt-0.5 flex items-center gap-1">
                      <Navigation size={11} className="flex-shrink-0" />
                      {formatDistance(loc.distance)}
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
                {detail.location.distance != null && `（距你 ${formatDistance(detail.location.distance)}）`}
              </div>
            </div>

            {/* 我的评价 */}
            <div className="border border-line/60 rounded-[12px] p-4">
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
                  <div className="flex items-center justify-end gap-2">
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
          </div>
        ) : null}
      </Modal>
    </div>
  );
};

export default LocationPage;