import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useNavigate } from 'react-router-dom';
import { Plus, Minus, X, MapPin, AlertCircle, RefreshCw, ChevronRight, Edit3, Star, MessageSquare, Check, LogIn, BadgeCheck, StarHalf } from 'lucide-react';
import { locationsApi, type LocationItem, type LocationReviewItem } from '../services/locations';
import { postsApi } from '../services/posts';
import type { Post } from '../types';
import { Loading } from '../components/ui/Loading';
import { Button } from '../components/ui/Button';
import PostForm from '../components/PostForm';
import { VerifyGate } from '../components/VerifyGate';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';
import { useCampusStore } from '../store/useCampusStore';
import { logger } from '../utils/logger';
import { formatRelativeTime } from '../utils/date';
import {
  clearMapLocationLayer,
  installMapLocationLayer,
  setMapLocationLayerData,
  MAP_LOCATION_LAYER_ID,
} from '../utils/mapLocationMarker';

// 侧滑面板：null=关闭 / create=发帖
type CreatePanel = { type: 'create'; lngLat: { lng: number; lat: number } } | null;

// P1-002: 兜底中心点/缩放级别（仅当 useCampusStore.currentSchoolCenter 为 null 时使用）
// 江南大学蠡湖校区坐标 [lng, lat]
const FALLBACK_CENTER: [number, number] = [120.271160, 31.483652];
const FALLBACK_ZOOM = 16;

const MapPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const { showToast } = useUIStore();
  // P1-002: 从全局 store 读取当前学校中心点/缩放，支持多租户切换
  const { currentSchoolCenter, currentSchoolZoom } = useCampusStore();
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  // 地点标记由同一 WebGL canvas 渲染；这里保存 location_id -> LocationItem 映射供点击查找
  const locationsRef = useRef<Map<number, LocationItem>>(new Map());
  const locationRequestRef = useRef(0);
  // 用 ref 同步 isAuthenticated，避免地图 click 闭包陷阱
  const authRef = useRef(isAuthenticated);
  useEffect(() => {
    authRef.current = isAuthenticated;
  }, [isAuthenticated]);

  // P1-002: 计算当前应使用的中心点/缩放（优先 store，兜底 FALLBACK）
  const activeCenter: [number, number] = useMemo(
    () =>
      currentSchoolCenter
        ? [currentSchoolCenter.lng, currentSchoolCenter.lat]
        : FALLBACK_CENTER,
    [currentSchoolCenter]
  );
  const activeZoom = currentSchoolZoom ?? FALLBACK_ZOOM;
  const activeCenterRef = useRef(activeCenter);
  const activeZoomRef = useRef(activeZoom);
  useEffect(() => {
    activeCenterRef.current = activeCenter;
    activeZoomRef.current = activeZoom;
  }, [activeCenter, activeZoom]);

  const currentSchoolId = useCampusStore((s) => s.currentSchoolId);

  const [mapReady, setMapReady] = useState(false);
  // DSC-01.3: 地图加载失败标志，true 时切换到列表视图降级展示
  const [mapFailed, setMapFailed] = useState(false);
  // 地图加载失败降级所需的全部地点（与地图渲染共用同一份数据）
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(false);
  const [locationsError, setLocationsError] = useState(false);
  // 发帖侧滑面板
  const [createPanel, setCreatePanel] = useState<CreatePanel>(null);
  // D-04: 地点面板
  const [locationPanel, setLocationPanel] = useState<LocationItem | null>(null);

  // 地点面板：评价列表展开状态
  const [locationReviewsOpen, setLocationReviewsOpen] = useState(false);
  const [locationReviews, setLocationReviews] = useState<LocationReviewItem[]>([]);
  const [locationReviewsLoading, setLocationReviewsLoading] = useState(false);
  // 地点面板：我的评价与评分表单
  const [locationMyReview, setLocationMyReview] = useState<LocationReviewItem | null>(null);
  const [locationScore, setLocationScore] = useState(5);
  const [locationReviewContent, setLocationReviewContent] = useState('');
  const [locationReviewSubmitting, setLocationReviewSubmitting] = useState(false);
  // 常态不展开编辑表单：已有评价时，点「更新评价」才进入编辑态
  const [locationEditingReview, setLocationEditingReview] = useState(false);

  // D-04: 地点面板相关帖子（GET /posts?location_id=）
  const [locationPosts, setLocationPosts] = useState<Post[]>([]);
  const [locationPostsLoading, setLocationPostsLoading] = useState(false);
  const [locationPostsError, setLocationPostsError] = useState(false);

  // 评分星星展示组件（复现 LocationPage 的 ScoreStars）
  function ScoreStars({ score, size = 14 }: { score: number; size?: number }) {
    const full = Math.floor(score);
    const half = score - full >= 0.25 && score - full < 0.75;
    return (
      <span className="inline-flex items-center gap-0.5 text-lamp" aria-label={`评分 ${score} 分`}>
        {Array.from({ length: full }).map((_, i) => (
          <Star key={`f${i}`} size={size} className="fill-current" />
        ))}
        {half && <StarHalf key="h" size={size} className="fill-current" />}
        {Array.from({ length: Math.max(0, 5 - full - (half ? 1 : 0)) }).map((_, i) => (
          <Star key={`e${i}`} size={size} className="text-line" />
        ))}
      </span>
    );
  }

  // 提交/更新评价
  const handleLocationSubmitReview = useCallback(async () => {
    if (!locationPanel) return;
    setLocationReviewSubmitting(true);
    try {
      const review = await locationsApi.submitReview(locationPanel.id, {
        score: locationScore,
        content: locationReviewContent.trim() || undefined,
      });
      setLocationMyReview(review);
      // 重新拉取评价列表与最新地点信息（评分汇总会变化）
      const reviewsRes = await locationsApi.getReviews(locationPanel.id, 1, 20);
      setLocationReviews(reviewsRes.items);
      const detail = await locationsApi.getDetail(locationPanel.id);
      // 同步回 locationPanel 的汇总字段，使 UI 立即刷新
      setLocationPanel({
        ...locationPanel,
        avg_score: detail.location.avg_score,
        rating_count: detail.location.rating_count,
        review_count: detail.location.review_count,
      });
      setLocationEditingReview(false);
      showToast('评价已提交', 'success');
    } catch (err: unknown) {
      logger.error('提交评价失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '提交评价失败', 'error');
    } finally {
      setLocationReviewSubmitting(false);
    }
  }, [locationPanel, locationScore, locationReviewContent, showToast]);

  // 撤回评价
  const handleLocationWithdrawReview = useCallback(async () => {
    if (!locationPanel) return;
    setLocationReviewSubmitting(true);
    try {
      await locationsApi.withdrawReview(locationPanel.id);
      setLocationMyReview(null);
      setLocationScore(5);
      setLocationReviewContent('');
      setLocationEditingReview(false);
      const reviewsRes = await locationsApi.getReviews(locationPanel.id, 1, 20);
      setLocationReviews(reviewsRes.items);
      const detail = await locationsApi.getDetail(locationPanel.id);
      setLocationPanel({
        ...locationPanel,
        avg_score: detail.location.avg_score,
        rating_count: detail.location.rating_count,
        review_count: detail.location.review_count,
      });
      showToast('评价已撤回', 'success');
    } catch (err: unknown) {
      logger.error('撤回评价失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '撤回评价失败', 'error');
    } finally {
      setLocationReviewSubmitting(false);
    }
  }, [locationPanel, showToast]);

  // D-04: 打开地点面板时并行拉取相关帖子 + 评价列表（默认关闭）+ 我的评价
  useEffect(() => {
    if (!locationPanel) {
      void Promise.resolve().then(() => {
        setLocationPosts([]);
        setLocationReviews([]);
        setLocationReviewsOpen(false);
        setLocationMyReview(null);
        setLocationScore(5);
        setLocationReviewContent('');
        setLocationEditingReview(false);
      });
      return;
    }
    let cancelled = false;
    void Promise.resolve()
      .then(async () => {
        setLocationPostsLoading(true);
        setLocationPostsError(false);
        setLocationReviewsLoading(true);
        const [postsRes, reviewsRes, detail] = await Promise.all([
          postsApi.getPosts({
            location_id: locationPanel.id,
            page: 1,
            page_size: 5,
            sort: 'latest',
          }),
          locationsApi.getReviews(locationPanel.id, 1, 20),
          locationsApi.getDetail(locationPanel.id),
        ]);
        if (!cancelled) {
          setLocationPosts(postsRes.items ?? []);
          setLocationReviews(reviewsRes.items);
          setLocationMyReview(detail.my_review ?? null);
          if (detail.my_review) {
            setLocationScore(detail.my_review.score);
            setLocationReviewContent(detail.my_review.content ?? '');
          }
        }
      })
      .catch(() => {
        if (!cancelled) setLocationPostsError(true);
      })
      .finally(() => {
        if (!cancelled) {
          setLocationPostsLoading(false);
          setLocationReviewsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [locationPanel]);

  // 加载当前学校全部地点并渲染到地图（统一数据源：locations 表）
  const loadLocations = useCallback(async () => {
    const requestId = ++locationRequestRef.current;
    setLocationsLoading(true);
    setLocationsError(false);
    try {
      const data = await locationsApi.getLocations();
      if (requestId !== locationRequestRef.current) return;
      setLocations(data);
      locationsRef.current = new Map(data.map((loc) => [loc.id, loc]));
      if (map.current) setMapLocationLayerData(map.current, data);
    } catch (err: unknown) {
      if (requestId === locationRequestRef.current) {
        logger.error('加载地点失败:', err);
        setLocationsError(true);
      }
    } finally {
      if (requestId === locationRequestRef.current) setLocationsLoading(false);
    }
  }, []);

  const handleRetryLocations = useCallback(() => {
    void loadLocations();
  }, [loadLocations]);

  // 初始化地图
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          // P2-008: 切换为国内可达瓦片源（高德栅格），避免 OSM 瓦片在国内加载缓慢/不可达
          amap: {
            type: 'raster',
            tiles: [
              'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
              'https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
              'https://webrd03.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
              'https://webrd04.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
            ],
            tileSize: 256,
            attribution: '&copy; 高德地图 (AMap)',
          },
        },
        layers: [
          {
            id: 'amap-tiles',
            type: 'raster',
            source: 'amap',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: activeCenterRef.current,
      zoom: activeZoomRef.current,
      // P1-003: 地图交互稳定性配置
      dragRotate: false,
      doubleClickZoom: false,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
    });

    mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

    mapInstance.on('load', () => {
      installMapLocationLayer(mapInstance);
      setMapReady(true);
      void loadLocations();
    });

    // 地点标记点击 → 打开地点信息面板（评分 + 描述 + 相关帖子）
    mapInstance.on('click', MAP_LOCATION_LAYER_ID, (event) => {
      const locationId = event.features?.[0]?.properties?.locationId;
      if (typeof locationId !== 'number') return;
      const loc = locationsRef.current.get(locationId);
      if (loc) setLocationPanel(loc);
    });
    mapInstance.on('mouseenter', MAP_LOCATION_LAYER_ID, () => {
      mapInstance.getCanvas().style.cursor = 'pointer';
    });
    mapInstance.on('mouseleave', MAP_LOCATION_LAYER_ID, () => {
      mapInstance.getCanvas().style.cursor = '';
    });

    // DSC-01.3: 监听地图加载错误，触发降级到列表视图
    mapInstance.on('error', (e) => {
      const err = (e as unknown as { error?: Error })?.error;
      logger.error('地图加载失败:', err || e);
      setMapFailed(true);
      showToast('地图加载失败，已切换到列表视图', 'error');
    });

    // 地图点击空白处：登录用户打开发帖面板，未登录提示
    mapInstance.on('click', (e) => {
      // 地点标记的点击由上面的图层事件处理，不能同时打开“发布”面板。
      if (mapInstance.queryRenderedFeatures(e.point, { layers: [MAP_LOCATION_LAYER_ID] }).length > 0) return;
      if (!authRef.current) {
        showToast('请先登录后再发布信息', 'info');
        return;
      }
      setCreatePanel({ type: 'create', lngLat: { lng: e.lngLat.lng, lat: e.lngLat.lat } });
    });

    map.current = mapInstance;
    if (import.meta.env.DEV) {
      (window as Window & { __momentCampusMap?: maplibregl.Map }).__momentCampusMap = mapInstance;
    }

    return () => {
      locationRequestRef.current += 1;
      locationsRef.current.clear();
      if (import.meta.env.DEV) {
        delete (window as Window & { __momentCampusMap?: maplibregl.Map }).__momentCampusMap;
      }
      mapInstance.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 学校切换：清空旧学校地点标记并重新定位
  useEffect(() => {
    if (!map.current || !mapReady) return;
    locationRequestRef.current += 1;
    clearMapLocationLayer(map.current);
    locationsRef.current.clear();
    setLocations([]);
    setLocationPanel(null);
    setLocationsError(false);
    map.current.flyTo({
      center: activeCenter,
      zoom: activeZoom,
      duration: 800,
    });
    // 切换后主动加载该校全部地点
    void loadLocations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSchoolId, currentSchoolCenter, currentSchoolZoom, mapReady]);

  // DSC-01.3: 地图加载失败后的"重试地图"按钮
  const handleRetryMap = useCallback(() => {
    locationRequestRef.current += 1;
    clearMapLocationLayer(map.current);
    locationsRef.current.clear();
    if (map.current) {
      map.current.remove();
      map.current = null;
    }
    setMapReady(false);
    setMapFailed(false);
    setCreatePanel(null);
    setTimeout(() => window.location.reload(), 100);
  }, []);

  // 缩放控制
  const handleZoomIn = useCallback(() => {
    map.current?.zoomIn();
  }, []);

  const handleZoomOut = useCallback(() => {
    map.current?.zoomOut();
  }, []);

  return (
    <div className="relative h-[calc(100vh-4rem)] -m-4 md:-m-6 flex flex-col bg-mist">
      {/* 顶部工具栏：标题（楷体）+ 实时状态标签 */}
      <div className="flex items-center justify-between gap-3 px-4 py-3 bg-paper/80 backdrop-blur-md border-b border-line/60 z-20">
        <div className="flex items-center gap-3 min-w-0">
          <h2 className="font-display font-extrabold text-lg md:text-xl text-lake whitespace-nowrap tracking-[0.04em]">
            校园生活地图
          </h2>
          <span className="inline-flex items-center gap-1.5 text-grass bg-grass/15 rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap">
            <span className="w-1.5 h-1.5 bg-grass rounded-full animate-pulse-soft" />
            实时更新
          </span>
        </div>
      </div>

      {/* 地图容器：大圆角(23px) + 纸张纹理叠加 */}
      <div className="relative flex-1 m-3 rounded-[23px] overflow-hidden border border-line shadow-md">
        <div ref={mapContainer} className="w-full h-full" />
        {/* 纸张噪点纹理 */}
        <div className="paper-noise" />

        {/* DSC-01.3: 地图加载失败时的列表降级视图 */}
        {mapFailed && (
          <div className="absolute inset-0 bg-paper z-10 overflow-y-auto">
            <div className="p-4 border-b border-line/60 flex items-center justify-between sticky top-0 bg-paper/95 backdrop-blur-sm z-10">
              <div className="flex items-center gap-2 min-w-0">
                <AlertCircle size={18} className="text-danger flex-shrink-0" />
                <div className="min-w-0">
                  <h3 className="font-display font-bold text-lg text-ink">地点列表</h3>
                  <p className="text-[11px] text-ink-muted">地图暂不可用，已切换为列表视图</p>
                </div>
              </div>
              <button
                onClick={handleRetryMap}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-lake text-white text-xs font-medium hover:bg-lake/90 transition-colors flex-shrink-0"
              >
                <RefreshCw size={14} />
                重试地图
              </button>
            </div>

            {locationsLoading ? (
              <div className="p-8 text-center text-ink-muted">
                <MapPin size={36} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm">正在加载地点...</p>
              </div>
            ) : locationsError ? (
              <div className="p-8 text-center text-ink-muted">
                <AlertCircle size={36} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm">地点加载失败</p>
                <button
                  onClick={handleRetryLocations}
                  className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-lake text-white text-xs font-medium hover:bg-lake/90 transition-colors"
                >
                  <RefreshCw size={14} />
                  重试
                </button>
              </div>
            ) : locations.length === 0 ? (
              <div className="p-8 text-center text-ink-muted">
                <MapPin size={36} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm">当前学校暂无地点</p>
              </div>
            ) : (
              <div className="divide-y divide-line/60">
                {locations.map((loc) => (
                  <div
                    key={loc.id}
                    className="p-4 hover:bg-mist cursor-pointer flex items-start gap-3 transition-colors"
                    onClick={() => setLocationPanel(loc)}
                  >
                    <div className="w-9 h-9 rounded-full bg-lamp/15 flex items-center justify-center flex-shrink-0">
                      <MapPin size={16} className="text-lamp" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-semibold text-ink line-clamp-1">{loc.name}</h4>
                        <span className="inline-flex items-center gap-1 text-xs text-lamp font-semibold">
                          <Star size={11} className="fill-current" />
                          {loc.avg_score.toFixed(1)}
                        </span>
                      </div>
                      <p className="text-sm text-ink-sub mt-0.5 line-clamp-1 flex items-center gap-1">
                        <MessageSquare size={11} className="flex-shrink-0 text-lamp" />
                        {loc.review_count} 条评价
                      </p>
                    </div>
                    <ChevronRight size={16} className="text-ink-muted mt-1 flex-shrink-0" />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 自定义缩放控制 */}
        <div className="absolute bottom-6 right-3 z-10 flex flex-col gap-1">
          <button
            onClick={handleZoomIn}
            className="w-9 h-9 bg-paper/90 backdrop-blur-sm rounded-t-md shadow-md border border-line flex items-center justify-center hover:bg-white active:bg-mist transition-colors"
            aria-label="放大"
          >
            <Plus size={16} className="text-ink" />
          </button>
          <button
            onClick={handleZoomOut}
            className="w-9 h-9 bg-paper/90 backdrop-blur-sm rounded-b-md shadow-md border border-line border-t-0 flex items-center justify-center hover:bg-white active:bg-mist transition-colors"
            aria-label="缩小"
          >
            <Minus size={16} className="text-ink" />
          </button>
        </div>

        {/* 加载指示器 */}
        {locationsLoading && (
          <div className="absolute top-3 right-3 z-10">
            <div className="bg-paper/90 backdrop-blur-sm rounded-full px-3 py-1.5 shadow-md border border-line flex items-center gap-2">
              <Loading size="sm" />
              <span className="text-xs text-ink-sub">加载中</span>
            </div>
          </div>
        )}

        {locationsError && !locationsLoading && !mapFailed && (
          <div className="absolute top-3 left-3 z-10 bg-paper border border-danger/30 rounded-md px-3 py-2 shadow-md flex items-center gap-2">
            <AlertCircle size={14} className="text-danger" />
            <span className="text-xs text-ink-sub">地点加载失败</span>
            <button type="button" onClick={handleRetryLocations} className="text-xs font-medium text-danger inline-flex items-center gap-1">
              <RefreshCw size={12} />
              重试
            </button>
          </div>
        )}

        {/* D-04: 地点侧滑面板 */}
        {locationPanel && (
          <aside className="absolute top-2 right-2 bottom-2 z-30 w-[320px] max-w-[85vw] bg-paper shadow-2xl border border-line rounded-[16px] flex flex-col overflow-hidden">
            <div className="px-5 py-4 bg-gradient-to-br from-lake/15 via-mist to-lamp/10 border-b border-line/60 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <MapPin size={16} className="text-lamp flex-shrink-0" />
                  <h3 className="font-display font-bold text-base text-ink truncate">{locationPanel.name}</h3>
                  {locationPanel.is_verified && (
                    <MapPin size={13} className="text-lake flex-shrink-0" aria-label="官方核验" />
                  )}
                </div>
                <div className="mt-1 flex items-center gap-1.5">
                  <Star size={14} className="text-lamp fill-current" />
                  <span className="text-lg font-display font-bold text-ink">{locationPanel.avg_score.toFixed(1)}</span>
                  <span className="text-[11px] text-ink-muted">{locationPanel.rating_count} 人评分</span>
                </div>
              </div>
              <button
                onClick={() => setLocationPanel(null)}
                className="w-8 h-8 rounded-full bg-mist/80 flex items-center justify-center text-ink-sub hover:text-ink transition-colors flex-shrink-0"
                aria-label="关闭"
              >
                <X size={15} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
              {locationPanel.description && (
                <p className="text-sm text-ink-sub leading-relaxed">{locationPanel.description}</p>
              )}
              <div className="flex items-center gap-2 text-xs text-ink-sub">
                <MapPin size={12} className="text-lake flex-shrink-0" />
                {locationPanel.building || locationPanel.floor || '校园内'}
              </div>

              {/* 评价区：点击展开/收起评价列表 */}
              <button
                type="button"
                onClick={() => setLocationReviewsOpen((v) => !v)}
                className="w-full flex items-center justify-between text-left text-xs text-ink-muted border-t border-line/60 pt-3 hover:text-ink transition-colors"
                aria-expanded={locationReviewsOpen}
                aria-label={`${locationReviewsOpen ? '收起' : '查看'} ${locationPanel.review_count} 条评价`}
              >
                <span className="flex items-center gap-2">
                  <MessageSquare size={12} />
                  <span>{locationPanel.review_count} 条评价</span>
                </span>
                <ChevronRight
                  size={14}
                  className={`text-ink-muted transition-transform ${locationReviewsOpen ? 'rotate-90' : ''}`}
                />
              </button>
              {locationReviewsOpen && (
                <div className="-mt-1 border-l-2 border-line/60 ml-2 pl-3 space-y-2">
                  {locationReviewsLoading ? (
                    <div className="flex items-center justify-center py-3">
                      <RefreshCw size={14} className="animate-spin text-ink-muted" />
                    </div>
                  ) : locationReviews.length === 0 ? (
                    <p className="text-xs text-ink-muted py-2">还没有评价，在下方提交第一条吧。</p>
                  ) : (
                    locationReviews.map((review) => (
                      <div key={review.id} className="py-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span className="font-medium text-ink text-xs truncate">
                              {review.author?.nickname || '匿名用户'}
                            </span>
                            {review.author?.is_verified && (
                              <BadgeCheck size={12} className="text-lake flex-shrink-0" aria-label="已认证" />
                            )}
                          </div>
                          <span className="text-[10px] text-ink-muted flex-shrink-0">
                            {formatRelativeTime(review.created_at)}
                          </span>
                        </div>
                        <div className="mt-0.5 flex items-center gap-1.5">
                          <ScoreStars score={review.score} size={11} />
                          <span className="text-[11px] text-ink-sub">{review.score}.0</span>
                        </div>
                        {review.content && (
                          <p className="text-[12px] text-ink-sub mt-1 leading-relaxed line-clamp-3">
                            {review.content}
                          </p>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 评分/评价表单：常态只读摘要 + 「更新评价」展开编辑；紧凑单层布局，不做卡片嵌套 */}
              <div className="border border-line/60 rounded-[10px] p-2.5">
                {!locationMyReview || locationEditingReview ? (
                  /* 未评价 / 编辑态：顶行标题 + 主按钮（提交/更新）同排，与常态「更新评价」布局一致 */
                  <>
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <h4 className="font-semibold text-ink text-[11px] leading-none">
                        {locationMyReview ? '我的评价' : '给这个地点打个分'}
                      </h4>
                      {isAuthenticated && (
                        <Button
                          variant="primary"
                          size="sm"
                          loading={locationReviewSubmitting}
                          onClick={() => void handleLocationSubmitReview()}
                          icon={<Check size={11} />}
                          className="h-8 px-3 text-[11px] gap-1 rounded-[8px]"
                        >
                          {locationMyReview ? '更新' : '提交'}
                        </Button>
                      )}
                    </div>
                    {!isAuthenticated ? (
                      <div className="flex items-center justify-between gap-2 mt-1">
                        <p className="text-[11px] text-ink-muted">登录后即可评分评价</p>
                        <Button
                          variant="primary"
                          size="sm"
                          icon={<LogIn size={12} />}
                          onClick={() => navigate('/login')}
                          className="h-8 px-3 text-[11px] gap-1 rounded-[8px]"
                        >
                          去登录
                        </Button>
                      </div>
                    ) : (
                      <VerifyGate compact message="完成校园身份认证后即可评分评价">
                        <div className="space-y-1.5 mt-0.5">
                          <div className="flex items-center gap-1" role="radiogroup" aria-label="评分">
                            {[1, 2, 3, 4, 5].map((value) => (
                              <button
                                key={value}
                                type="button"
                                onClick={() => setLocationScore(value)}
                                aria-label={`${value} 星`}
                                aria-checked={locationScore === value}
                                role="radio"
                                className="p-0.5"
                              >
                                <Star
                                  size={18}
                                  className={
                                    value <= locationScore
                                      ? 'fill-current text-lamp'
                                      : 'text-line'
                                  }
                                />
                              </button>
                            ))}
                            <span className="ml-2 text-xs font-semibold text-ink">
                              {locationScore}.0 分
                            </span>
                          </div>
                          <textarea
                            value={locationReviewContent}
                            onChange={(e) => setLocationReviewContent(e.target.value)}
                            maxLength={500}
                            rows={2}
                            placeholder="分享你的体验（最多 500 字，可选）"
                            className="w-full rounded-[8px] border border-line bg-paper px-2.5 py-1.5 text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-lake/30 resize-none"
                          />
                          {/* 次按钮：取消编辑 / 撤回，放在底部右对齐 */}
                          {(locationMyReview && locationEditingReview) || locationMyReview ? (
                            <div className="flex items-center justify-end gap-2 pt-0.5">
                              {locationMyReview && locationEditingReview && (
                                <Button
                                  variant="text"
                                  size="sm"
                                  onClick={() => setLocationEditingReview(false)}
                                >
                                  取消编辑
                                </Button>
                              )}
                              {locationMyReview && (
                                <Button
                                  variant="text"
                                  size="sm"
                                  loading={locationReviewSubmitting}
                                  onClick={() => void handleLocationWithdrawReview()}
                                >
                                  撤回
                                </Button>
                              )}
                            </div>
                          ) : null}
                        </div>
                      </VerifyGate>
                    )}
                  </>
                ) : (
                  /* 常态（已有评价 + 不在编辑）：紧凑单层布局，标题行与更新按钮同排；取消内层 bg-mist 嵌套卡片 */
                  <>
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <h4 className="font-semibold text-ink text-[11px] leading-none">
                        我的评价
                      </h4>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => {
                          setLocationScore(locationMyReview.score);
                          setLocationReviewContent(locationMyReview.content ?? '');
                          setLocationEditingReview(true);
                        }}
                        icon={<Edit3 size={11} />}
                        className="h-8 px-3 text-[11px] gap-1 rounded-[8px]"
                      >
                        更新评价
                      </Button>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="font-medium text-ink text-[12px] truncate">我</span>
                        {locationMyReview.author?.is_verified && (
                          <BadgeCheck size={12} className="text-lake flex-shrink-0" aria-label="已认证" />
                        )}
                        <span className="mx-1 h-3 w-px bg-line/60" aria-hidden="true" />
                        <ScoreStars score={locationMyReview.score} size={12} />
                        <span className="text-[11px] text-ink-sub font-semibold">
                          {locationMyReview.score}.0
                        </span>
                      </div>
                      <span className="text-[10px] text-ink-muted flex-shrink-0">
                        {formatRelativeTime(locationMyReview.created_at)}
                      </span>
                    </div>
                    {locationMyReview.content && (
                      <p className="text-[12px] text-ink-sub mt-1.5 leading-relaxed whitespace-pre-wrap line-clamp-4">
                        {locationMyReview.content}
                      </p>
                    )}
                  </>
                )}
              </div>

              {/* D-04: 相关帖子列表 */}
              <div className="border-t border-line/60 pt-3">
                <p className="text-xs font-medium text-ink mb-2">相关帖子</p>
                {locationPostsLoading ? (
                  <div className="flex items-center justify-center py-3">
                    <RefreshCw size={14} className="animate-spin text-ink-muted" />
                  </div>
                ) : locationPostsError ? (
                  <p className="text-xs text-danger/80 py-2">相关帖子加载失败</p>
                ) : locationPosts.length === 0 ? (
                  <p className="text-xs text-ink-muted py-2">暂无相关帖子，快来发布第一条吧</p>
                ) : (
                  <div className="space-y-1.5">
                    {locationPosts.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => navigate(`/posts/${p.id}`)}
                        className="w-full text-left p-2.5 rounded-[8px] border border-line/60 bg-paper hover:bg-paper-hover transition-colors flex items-center gap-2 group"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] text-ink truncate group-hover:text-lake transition-colors">
                            {p.title}
                          </p>
                          <p className="text-[11px] text-ink-muted mt-0.5 truncate">
                            {p.author?.nickname || '匿名用户'}
                            {p.author?.is_verified ? ' · 已认证' : ''}
                          </p>
                        </div>
                        <ChevronRight size={14} className="text-ink-muted flex-shrink-0 group-hover:text-lake" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="px-5 py-3 border-t border-line/60 flex gap-2">
              <Button variant="primary" size="sm" onClick={() => navigate(`/locations?location=${locationPanel.id}`)} icon={<MapPin size={14} />}>
                查看完整详情
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setLocationPanel(null)}>
                关闭
              </Button>
            </div>
          </aside>
        )}

        {/* 发帖侧滑面板 */}
        {createPanel && (
          <>
            {/* 半透明遮罩：移动端点击关闭 */}
            <div
              className="absolute inset-0 z-20 bg-ink/20 backdrop-blur-[1px] md:bg-transparent md:backdrop-blur-none"
              onClick={() => setCreatePanel(null)}
            />
            <aside className="absolute top-0 right-0 bottom-0 z-30 w-full sm:w-[340px] md:w-[360px] bg-paper shadow-2xl border-l border-line flex flex-col map-slide-panel">
              <button
                onClick={() => setCreatePanel(null)}
                className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-mist/80 backdrop-blur-sm flex items-center justify-center text-ink-sub hover:text-ink hover:bg-mist transition-colors"
                aria-label="关闭"
              >
                <X size={16} />
              </button>
              <div className="h-[80px] bg-gradient-to-br from-lake/15 via-mist to-lamp/10 flex items-center px-5 flex-shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-full bg-lamp/20 flex items-center justify-center">
                    <Edit3 size={16} className="text-lamp" />
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider">New Post</div>
                    <div className="font-display font-bold text-base text-ink">在此处发布信息</div>
                  </div>
                </div>
              </div>

              {/* PUB-01.1：表单复用 PostForm（variant='panel'） */}
              <div className="flex-1 overflow-y-auto px-5 py-4">
                <PostForm
                  key={`${createPanel.lngLat.lat.toFixed(6)},${createPanel.lngLat.lng.toFixed(6)}`}
                  variant="panel"
                  defaultLocationLat={createPanel.lngLat.lat}
                  defaultLocationLng={createPanel.lngLat.lng}
                  showCancelButton={false}
                  onSuccess={() => {
                    setCreatePanel(null);
                    // 发布成功后刷新地点（帖子数可能变化）
                    void loadLocations();
                    // PUB-01.3：发布成功后跳"我的发布"
                    setTimeout(() => navigate('/profile'), 800);
                  }}
                />
              </div>
            </aside>
          </>
        )}
      </div>
    </div>
  );
};

export default MapPage;