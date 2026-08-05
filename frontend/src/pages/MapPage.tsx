import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Navigation, Plus, Minus, Filter, X, MapPin, ArrowRight, Edit3, AlertCircle, RefreshCw, ChevronRight, Star, MessageSquare } from 'lucide-react';
import { mapApi, type MapMarker } from '../services/map';
import { locationsApi, type LocationItem } from '../services/locations';
import { categoriesApi, type CategoryListItem } from '../services/categories';
import { Loading } from '../components/ui/Loading';
import { Button } from '../components/ui/Button';
import PostForm from '../components/PostForm';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';
import { useCampusStore } from '../store/useCampusStore';
import { logger } from '../utils/logger';
import {
  clearMapMarkerLayer,
  installMapMarkerLayer,
  MAP_MARKER_LAYER_ID,
  setHoveredMapMarker,
  setMapMarkerLayerData,
  type MapMarkerGroup,
} from '../utils/mapMarker';
import { wgs84ToGcj02 } from '../utils/coordinates';
import { getCategoryVisual } from '../utils/categoryVisual';
import {
  clearMapLocationLayer,
  installMapLocationLayer,
  setMapLocationLayerData,
  MAP_LOCATION_LAYER_ID,
} from '../utils/mapLocationMarker';

// 侧滑面板模式：null=关闭 / view=查看 marker / create=发帖
type PanelMode = null | { type: 'view'; marker: MapMarker } | { type: 'create'; lngLat: { lng: number; lat: number } };

// P1-002: 兜底中心点/缩放级别（仅当 useCampusStore.currentSchoolCenter 为 null 时使用）
// 江南大学蠡湖校区坐标 [lng, lat]
const FALLBACK_CENTER: [number, number] = [120.271160, 31.483652];
const FALLBACK_ZOOM = 16;

const MapPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const { showToast } = useUIStore();
  // P1-002: 从全局 store 读取当前学校中心点/缩放，支持多租户切换
  const { currentSchoolCenter, currentSchoolZoom } = useCampusStore();
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  // Map marker 与高德瓦片由同一个 WebGL canvas 渲染；这里仅保存交互索引。
  const markerGroupsRef = useRef<Map<string, MapMarkerGroup>>(new Map());
  // DSC-01.3: post_id -> source feature 映射，用于 focus_post_id 深链接。
  const markersByIdRef = useRef<Map<number, { marker: MapMarker; groupKey: string }>>(new Map());
  const markerRequestRef = useRef(0);
  // A-06: location_id -> LocationItem 映射，供附近模式地点标记点击事件查找
  const nearbyLocationsRef = useRef<Map<number, LocationItem>>(new Map());
  // 聚合 marker 暂存的多帖列表（供侧滑面板渲染）
  const [groupedMarkers, setGroupedMarkers] = useState<MapMarker[] | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 用 ref 同步 isAuthenticated，避免地图 click 闭包陷阱
  const authRef = useRef(isAuthenticated);
  useEffect(() => {
    authRef.current = isAuthenticated;
  }, [isAuthenticated]);

  // P1-002: 计算当前应使用的中心点/缩放（优先 store，兜底 FALLBACK）
  // 使用 useMemo 避免 conditional 引用变化导致 useEffect 依赖抖动
  const activeCenter: [number, number] = useMemo(
    () =>
      currentSchoolCenter
        ? [currentSchoolCenter.lng, currentSchoolCenter.lat]
        : FALLBACK_CENTER,
    [currentSchoolCenter]
  );
  const activeZoom = currentSchoolZoom ?? FALLBACK_ZOOM;
  // 用 ref 保存最新的 activeCenter/activeZoom，供初始化 useEffect 与切换 useEffect 共享
  const activeCenterRef = useRef(activeCenter);
  const activeZoomRef = useRef(activeZoom);
  useEffect(() => {
    activeCenterRef.current = activeCenter;
    activeZoomRef.current = activeZoom;
  }, [activeCenter, activeZoom]);

  const currentSchoolId = useCampusStore((s) => s.currentSchoolId);
  const [categoryState, setCategoryState] = useState<{
    schoolId: number | null;
    items: CategoryListItem[];
    loading: boolean;
    error: boolean;
  }>({ schoolId: null, items: [], loading: true, error: false });
  const [categoriesRetry, setCategoriesRetry] = useState(0);
  const categories = useMemo(
    () => categoryState.schoolId === currentSchoolId ? categoryState.items : [],
    [categoryState, currentSchoolId]
  );
  const categoriesLoading = categoryState.schoolId !== currentSchoolId || categoryState.loading;
  const categoriesError = categoryState.schoolId === currentSchoolId && categoryState.error;
  useEffect(() => {
    let cancelled = false;
    categoriesApi
      .listCategories()
      .then((data) => {
        if (!cancelled) {
          setCategoryState({ schoolId: currentSchoolId, items: data, loading: false, error: false });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCategoryState({ schoolId: currentSchoolId, items: [], loading: false, error: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentSchoolId, categoriesRetry]);

  const categoriesById = useMemo(
    () => new Map(categories.map((category) => [category.id, category])),
    [categories]
  );

  const [loading, setLoading] = useState(false);
  const [categorySelection, setCategorySelection] = useState<{ schoolId: number | null; id: number } | null>(null);
  const selectedCategory = categorySelection?.schoolId === currentSchoolId ? categorySelection.id : null;
  const setSelectedCategory = (id: number | null) => {
    setCategorySelection(id === null ? null : { schoolId: currentSchoolId, id });
  };
  const [mapReady, setMapReady] = useState(false);
  // DSC-01.3: 地图加载失败标志，true 时切换到列表视图降级展示
  const [mapFailed, setMapFailed] = useState(false);
  const [markersError, setMarkersError] = useState(false);
  // DSC-01.3: 列表视图降级所需的所有 markers（与 map 渲染共用同一份）
  const [allMarkers, setAllMarkers] = useState<MapMarker[]>([]);
  // 侧滑面板模式
  const [panel, setPanel] = useState<PanelMode>(null);

  // A-06: 地图「附近」模式（独立于帖子标记，展示附近地点 + 评分徽标）
  const [nearbyMode, setNearbyMode] = useState(false);
  const [nearbyLocations, setNearbyLocations] = useState<LocationItem[]>([]);
  const [nearbyError, setNearbyError] = useState(false);
  const [locatingNearby, setLocatingNearby] = useState(false);
  const [locationPanel, setLocationPanel] = useState<LocationItem | null>(null);

  // 获取并更新地图标记
  const fetchMarkers = useCallback(async (bounds: maplibregl.LngLatBounds, categoryId?: number) => {
    const requestId = ++markerRequestRef.current;
    setLoading(true);
    setMarkersError(false);
    try {
      const params = {
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest(),
        ...(categoryId ? { category_id: categoryId } : {}),
      };
      const data = await mapApi.getMapMarkers(params);
      // 学校切换或快速缩放时忽略较早请求，防止旧学校的点覆盖新地图。
      if (requestId !== markerRequestRef.current || !map.current) return;

      // DSC-01.3: 保存所有 markers 到 state，用于地图失败时的列表降级视图
      setAllMarkers(data);
      const layerData = setMapMarkerLayerData(map.current, data);
      markerGroupsRef.current = layerData.groups;
      markersByIdRef.current = layerData.posts;
    } catch {
      if (requestId === markerRequestRef.current) setMarkersError(true);
    } finally {
      if (requestId === markerRequestRef.current) setLoading(false);
    }
  }, []);

  const handleRetryMarkers = useCallback(() => {
    if (!map.current) return;
    void fetchMarkers(map.current.getBounds(), selectedCategory ?? undefined);
  }, [fetchMarkers, selectedCategory]);

  // A-06: 拉取附近地点并渲染到地图（GPS 优先，回退校园中心）
  const fetchNearby = useCallback(() => {
    if (!map.current) return;
    setNearbyError(false);
    setLocatingNearby(true);
    const loadNearby = (lat: number, lng: number) => {
      locationsApi
        .getNearby(lat, lng, 5000, 1, 100)
        .then((data) => {
          setNearbyLocations(data.items);
          nearbyLocationsRef.current = new Map(
            data.items.map((loc) => [loc.id, loc])
          );
          if (map.current) setMapLocationLayerData(map.current, data.items);
        })
        .catch((err: unknown) => {
          const e = err as { response?: { data?: { detail?: string } } };
          logger.error('加载附近地点失败:', e?.response?.data?.detail || err);
          setNearbyError(true);
        })
        .finally(() => setLocatingNearby(false));
    };
    const loadFromCenter = () => {
      loadNearby(activeCenterRef.current[1], activeCenterRef.current[0]);
    };
    if (!navigator.geolocation) {
      loadFromCenter();
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const gcj02 = wgs84ToGcj02(position.coords.latitude, position.coords.longitude);
        loadNearby(gcj02.latitude, gcj02.longitude);
      },
      () => loadFromCenter()
    );
  }, []);

  // A-06: 切换「附近」模式：开启时隐藏帖子标记、渲染附近地点；关闭时反之
  const handleToggleNearby = useCallback(() => {
    setPanel(null);
    setLocationPanel(null);
    const next = !nearbyMode;
    setNearbyMode(next);
    if (!map.current) return;
    if (next) {
      clearMapMarkerLayer(map.current);
      installMapLocationLayer(map.current);
      fetchNearby();
    } else {
      clearMapLocationLayer(map.current);
      setNearbyLocations([]);
      const bounds = map.current.getBounds();
      void fetchMarkers(bounds, selectedCategory ?? undefined);
    }
  }, [nearbyMode, fetchNearby, fetchMarkers, selectedCategory]);

  // 初始化地图
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          // P2-008: 切换为国内可达瓦片源（高德栅格），避免 OSM 瓦片在国内加载缓慢/不可达
          // 高德栅格瓦片无需 API Key 即可访问基础底图（适用于校园级演示场景）
          // 如需商业使用，请申请高德 Key 并切换为官方瓦片接口
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
      // - 禁用双指旋转/倾斜，避免 zoom 后竖直位置漂移
      // - 禁用双击缩放，与 marker 点击冲突
      dragRotate: false,
      doubleClickZoom: false,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
    });

    mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

    mapInstance.on('load', () => {
      installMapMarkerLayer(mapInstance);
      setMapReady(true);
      const bounds = mapInstance.getBounds();
      fetchMarkers(bounds, selectedCategory ?? undefined);
    });

    mapInstance.on('mouseenter', MAP_MARKER_LAYER_ID, (event) => {
      mapInstance.getCanvas().style.cursor = 'pointer';
      const groupKey = event.features?.[0]?.properties?.groupKey;
      if (typeof groupKey === 'string') setHoveredMapMarker(mapInstance, groupKey);
    });
    mapInstance.on('mouseleave', MAP_MARKER_LAYER_ID, () => {
      mapInstance.getCanvas().style.cursor = '';
      setHoveredMapMarker(mapInstance, null);
    });
    mapInstance.on('click', MAP_MARKER_LAYER_ID, (event) => {
      const groupKey = event.features?.[0]?.properties?.groupKey;
      if (typeof groupKey !== 'string') return;
      const group = markerGroupsRef.current.get(groupKey);
      if (!group) return;
      const first = group.markers[0];
      setPanel({ type: 'view', marker: first });
      setGroupedMarkers(group.markers.length > 1 ? group.markers : null);
    });

    // A-06: 附近模式地点标记点击 → 打开地点信息面板
    mapInstance.on('click', MAP_LOCATION_LAYER_ID, (event) => {
      const locationId = event.features?.[0]?.properties?.locationId;
      if (typeof locationId !== 'number') return;
      const loc = nearbyLocationsRef.current.get(locationId);
      if (loc) setLocationPanel(loc);
    });
    mapInstance.on('mouseenter', MAP_LOCATION_LAYER_ID, () => {
      mapInstance.getCanvas().style.cursor = 'pointer';
    });
    mapInstance.on('mouseleave', MAP_LOCATION_LAYER_ID, () => {
      mapInstance.getCanvas().style.cursor = '';
    });

    // DSC-01.3: 监听地图加载错误（瓦片源不可达 / style 解析失败等），
    // 触发降级到列表视图，避免用户看到空白地图
    mapInstance.on('error', (e) => {
      // 仅在地图源/style 错误时降级；普通 marker 加载错误不影响主视图
      const err = (e as unknown as { error?: Error })?.error;
      logger.error('地图加载失败:', err || e);
      setMapFailed(true);
      showToast('地图加载失败，已切换到列表视图', 'error');
    });

    // 地图点击空白处：登录用户打开发帖面板，未登录提示
    // PUB-01.1：表单逻辑已抽取到 PostForm，这里只负责打开 create 面板并传入选点坐标
    mapInstance.on('click', (e) => {
      // symbol layer 的点击由上面的图层事件处理，不能同时打开“发布”面板。
      if (mapInstance.queryRenderedFeatures(e.point, { layers: [MAP_MARKER_LAYER_ID] }).length > 0) return;
      if (!authRef.current) {
        showToast('请先登录后再发布信息', 'info');
        return;
      }
      setPanel({ type: 'create', lngLat: { lng: e.lngLat.lng, lat: e.lngLat.lat } });
    });

    // 地图移动时重新获取标记（防抖）
    mapInstance.on('moveend', () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
      debounceTimer.current = setTimeout(() => {
        const bounds = mapInstance.getBounds();
        fetchMarkers(bounds, selectedCategory ?? undefined);
      }, 300);
    });

    map.current = mapInstance;
    if (import.meta.env.DEV) {
      (window as Window & { __momentCampusMap?: maplibregl.Map }).__momentCampusMap = mapInstance;
    }

    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
      markerRequestRef.current += 1;
      markerGroupsRef.current.clear();
      markersByIdRef.current.clear();
      if (import.meta.env.DEV) {
        delete (window as Window & { __momentCampusMap?: maplibregl.Map }).__momentCampusMap;
      }
      mapInstance.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 学校切换：清空旧学校标记并重新定位
  useEffect(() => {
    if (!map.current || !mapReady) return;
    markerRequestRef.current += 1;
    clearMapMarkerLayer(map.current);
    markerGroupsRef.current.clear();
    markersByIdRef.current.clear();
    setAllMarkers([]);
    setGroupedMarkers(null);
    setPanel(null);
    setLocationPanel(null);
    setMarkersError(false);
    // A-06: 学校切换时同步清理附近地点标记
    clearMapLocationLayer(map.current);
    nearbyLocationsRef.current.clear();
    setNearbyLocations([]);
    setNearbyError(false);
    map.current.flyTo({
      center: activeCenter,
      zoom: activeZoom,
      duration: 800,
    });
    // 附近模式下，学校切换后重新拉取该校附近地点
    if (nearbyMode) {
      fetchNearby();
    } else {
      // 飞行结束后 moveend 事件会自动触发 fetchMarkers
      // 但为保险起见，延迟 850ms 后主动拉取一次
      const timer = setTimeout(() => {
        if (!map.current) return;
        const bounds = map.current.getBounds();
        fetchMarkers(bounds, selectedCategory ?? undefined);
      }, 850);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSchoolId, currentSchoolCenter, currentSchoolZoom, nearbyMode, fetchNearby]);

  // 分类变化时重新获取标记
  useEffect(() => {
    if (!map.current || !mapReady) return;
    const bounds = map.current.getBounds();
    fetchMarkers(bounds, selectedCategory ?? undefined);
  }, [selectedCategory, mapReady, fetchMarkers]);

  // DSC-01.3: 处理 ?focus_post_id=xxx 深链接
  // 场景：用户在 SearchPage 点击"在地图查看"按钮跳转过来，
  // 需要自动聚焦对应标记并打开详情面板。
  useEffect(() => {
    if (!mapReady || mapFailed) return;
    const focusPostIdStr = searchParams.get('focus_post_id');
    if (!focusPostIdStr) return;
    const focusPostId = Number(focusPostIdStr);
    if (Number.isNaN(focusPostId)) return;

    const entry = markersByIdRef.current.get(focusPostId);
    if (!entry) return;

    // 平移地图到该 marker 并触发点击打开面板
    const { marker, groupKey } = entry;
    map.current?.flyTo({
      center: [marker.longitude, marker.latitude],
      zoom: Math.max(map.current?.getZoom() ?? activeZoomRef.current, 17),
    });
    const group = markerGroupsRef.current.get(groupKey);
    setPanel({ type: 'view', marker });
    setGroupedMarkers(group && group.markers.length > 1 ? group.markers : null);

    // 触发后清掉 URL 参数，避免刷新或后退时重复打开
    const next = new URLSearchParams(searchParams);
    next.delete('focus_post_id');
    setSearchParams(next, { replace: true });
  }, [mapReady, mapFailed, searchParams, setSearchParams]);

  // DSC-01.3: 地图加载失败后的"重试地图"按钮
  // 销毁当前 map 实例并重置 mapFailed，触发地图 useEffect 重新初始化
  const handleRetryMap = useCallback(() => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
    markerRequestRef.current += 1;
    clearMapMarkerLayer(map.current);
    markerGroupsRef.current.clear();
    markersByIdRef.current.clear();
    if (map.current) {
      map.current.remove();
      map.current = null;
    }
    setMapReady(false);
    setMapFailed(false);
    setPanel(null);
    // 重新初始化由地图初始化 useEffect 触发（依赖项不变，需通过强制刷新触发）
    // 这里采用 location reload 的轻量等价：直接重置 mapContainer ref 触发重渲染
    // 注意：地图初始化 useEffect 依赖 []，组件本身不会重渲染触发它
    // 为保证可重试，使用 window.location.reload() 作为兜底（极少触发，仅在用户主动点击）
    setTimeout(() => window.location.reload(), 100);
  }, []);

  // DSC-01.3: 列表降级视图中的 marker 点击处理
  // 与地图 marker 点击逻辑一致：打开侧滑面板（统一预览卡片视图）
  const handleListMarkerClick = useCallback((marker: MapMarker) => {
    setPanel({ type: 'view', marker });
    setGroupedMarkers(null);
  }, []);

  // 定位按钮
  const handleGeolocate = useCallback(() => {
    if (!navigator.geolocation || !map.current) return;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const gcj02 = wgs84ToGcj02(position.coords.latitude, position.coords.longitude);
        map.current!.flyTo({
          center: [gcj02.longitude, gcj02.latitude],
          zoom: 16,
        });
      },
      () => {
        // 定位失败，回到当前学校中心点（P1-002: 多租户适配）
        map.current!.flyTo({
          center: activeCenterRef.current,
          zoom: activeZoomRef.current,
        });
      }
    );
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
        {/* A-06: 附近模式切换 */}
        <button
          type="button"
          onClick={handleToggleNearby}
          className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all whitespace-nowrap flex-shrink-0 ${
            nearbyMode
              ? 'bg-lake text-white shadow-lake'
              : 'bg-mist text-ink-sub hover:bg-line'
          }`}
          aria-pressed={nearbyMode}
        >
          {locatingNearby && nearbyMode ? (
            <Loading size="sm" />
          ) : (
            <Navigation size={13} />
          )}
          {nearbyMode ? '查看附近地点' : '附近'}
        </button>
      </div>

      {/* 分类筛选条：横向滚动（附近模式下隐藏） */}
      {!nearbyMode && (
        <div className="bg-paper/70 backdrop-blur-sm border-b border-line/60 z-20">
          <div className="flex items-center gap-2 px-4 py-2.5 overflow-x-auto scrollbar-hide">
            <Filter size={16} className="text-ink-muted flex-shrink-0" />
          <button
            onClick={() => setSelectedCategory(null)}
            className={`flex-shrink-0 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
              selectedCategory === null
                ? 'bg-lake text-white shadow-lake'
                : 'bg-mist text-ink-sub hover:bg-line'
            }`}
          >
            全部
          </button>
          {categories.map((item) => {
            const numId = item.id;
            const visual = getCategoryVisual(item.code);
            const isActive = selectedCategory === numId;
            return (
              <button
                key={numId}
                onClick={() => setSelectedCategory(isActive ? null : numId)}
                className={`flex-shrink-0 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
                  isActive ? 'text-white shadow-sm' : 'text-ink-sub hover:bg-line'
                }`}
                style={isActive ? { backgroundColor: visual.marker } : { backgroundColor: visual.background, color: visual.text }}
              >
                {item.name}
              </button>
            );
          })}
          {categoriesLoading && <span className="text-xs text-ink-muted">分类加载中...</span>}
          {categoriesError && (
            <button
              type="button"
              onClick={() => {
                setCategoryState({ schoolId: currentSchoolId, items: [], loading: true, error: false });
                setCategoriesRetry((value) => value + 1);
              }}
              className="flex-shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium bg-danger/10 text-danger hover:bg-danger/15"
            >
              <RefreshCw size={12} />
              重试分类
            </button>
          )}
        </div>
      </div>
      )}

      {/* 地图容器：大圆角(23px) + 纸张纹理叠加 */}
      <div className="relative flex-1 m-3 rounded-[23px] overflow-hidden border border-line shadow-md">
        <div ref={mapContainer} className="w-full h-full" />
        {/* 纸张噪点纹理 */}
        <div className="paper-noise" />

        {/* DSC-01.3: 地图加载失败时的列表降级视图（graceful degradation） */}
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

            {allMarkers.length === 0 ? (
              <div className="p-8 text-center text-ink-muted">
                <MapPin size={36} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm">当前范围内暂无地点信息</p>
              </div>
            ) : (
              <div className="divide-y divide-line/60">
                {allMarkers.map((marker) => {
                  const category = categoriesById.get(marker.category_id);
                  const visual = getCategoryVisual(marker.category_code ?? category?.code);
                  const catName = marker.category_name ?? category?.name ?? '未分类';
                  return (
                    <div
                      key={marker.post_id}
                      className="p-4 hover:bg-mist cursor-pointer flex items-start gap-3 transition-colors"
                      onClick={() => handleListMarkerClick(marker)}
                    >
                      <div
                        className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
                        style={{ backgroundColor: visual.background }}
                      >
                        <MapPin size={16} style={{ color: visual.marker }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold flex-shrink-0"
                            style={{ backgroundColor: visual.background, color: visual.text }}
                          >
                            {catName}
                          </span>
                        </div>
                        <h4 className="font-semibold text-ink line-clamp-1">{marker.title}</h4>
                        <p className="text-sm text-ink-sub mt-0.5 line-clamp-1 flex items-center gap-1">
                          <MapPin size={11} className="flex-shrink-0 text-lamp" />
                          {marker.location_name}
                        </p>
                      </div>
                      <ChevronRight size={16} className="text-ink-muted mt-1 flex-shrink-0" />
                    </div>
                  );
                })}
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

        {/* 定位按钮 */}
        <button
          onClick={handleGeolocate}
          className="absolute bottom-6 left-3 z-10 w-9 h-9 bg-paper/90 backdrop-blur-sm rounded-md shadow-md border border-line flex items-center justify-center hover:bg-white active:bg-mist transition-colors"
          aria-label="定位"
        >
          <Navigation size={16} className="text-lake" />
        </button>

        {/* 加载指示器 */}
        {loading && (
          <div className="absolute top-3 right-3 z-10">
            <div className="bg-paper/90 backdrop-blur-sm rounded-full px-3 py-1.5 shadow-md border border-line flex items-center gap-2">
              <Loading size="sm" />
              <span className="text-xs text-ink-sub">加载中</span>
            </div>
          </div>
        )}

        {markersError && !loading && !mapFailed && (
          <div className="absolute top-3 left-3 z-10 bg-paper border border-danger/30 rounded-md px-3 py-2 shadow-md flex items-center gap-2">
            <AlertCircle size={14} className="text-danger" />
            <span className="text-xs text-ink-sub">地图信息加载失败</span>
            <button type="button" onClick={handleRetryMarkers} className="text-xs font-medium text-danger inline-flex items-center gap-1">
              <RefreshCw size={12} />
              重试
            </button>
          </div>
        )}

        {/* A-06: 附近模式加载/错误/空状态提示 */}
        {nearbyMode && !locatingNearby && !nearbyError && nearbyLocations.length === 0 && !mapFailed && (
          <div className="absolute top-3 left-3 z-10 bg-paper border border-line/60 rounded-md px-3 py-2 shadow-md text-xs text-ink-muted">
            附近暂无地点，试试切换学校或稍后再看
          </div>
        )}
        {nearbyMode && nearbyError && !mapFailed && (
          <div className="absolute top-3 left-3 z-10 bg-paper border border-danger/30 rounded-md px-3 py-2 shadow-md flex items-center gap-2">
            <AlertCircle size={14} className="text-danger" />
            <span className="text-xs text-ink-sub">附近地点加载失败</span>
            <button type="button" onClick={fetchNearby} className="text-xs font-medium text-danger inline-flex items-center gap-1">
              <RefreshCw size={12} />
              重试
            </button>
          </div>
        )}

        {/* A-06: 附近模式地点侧滑面板 */}
        {nearbyMode && locationPanel && (
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
                <Navigation size={12} className="text-lake" />
                {locationPanel.distance != null
                  ? locationPanel.distance < 1000
                    ? `${Math.round(locationPanel.distance)} 米`
                    : `${(locationPanel.distance / 1000).toFixed(1)} 公里`
                  : '校园内'}
                {locationPanel.building ? ` · ${locationPanel.building}` : ''}
                {locationPanel.floor ? ` · ${locationPanel.floor} 层` : ''}
              </div>
              <div className="flex items-center gap-2 text-xs text-ink-muted border-t border-line/60 pt-3">
                <MessageSquare size={12} />
                <span>{locationPanel.review_count} 条评价</span>
              </div>
            </div>
            <div className="px-5 py-3 border-t border-line/60 flex gap-2">
              <Button variant="primary" size="sm" onClick={() => navigate('/locations')} icon={<MapPin size={14} />}>
                查看评价与评分
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setLocationPanel(null)}>
                关闭
              </Button>
            </div>
          </aside>
        )}

        {/* 右侧侧滑面板：view（查看 marker）/ create（发帖） */}
        {panel && (
          <>
            {/* 半透明遮罩：移动端点击关闭 */}
            <div
              className="absolute inset-0 z-20 bg-ink/20 backdrop-blur-[1px] md:bg-transparent md:backdrop-blur-none"
              onClick={() => {
                setGroupedMarkers(null);
                setPanel(null);
              }}
            />
            <aside
              className="absolute top-0 right-0 bottom-0 z-30 w-full sm:w-[340px] md:w-[360px] bg-paper shadow-2xl border-l border-line flex flex-col map-slide-panel"
            >
              {/* 关闭按钮 */}
              <button
                onClick={() => {
                  setGroupedMarkers(null);
                  setPanel(null);
                }}
                className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-mist/80 backdrop-blur-sm flex items-center justify-center text-ink-sub hover:text-ink hover:bg-mist transition-colors"
                aria-label="关闭"
              >
                <X size={16} />
              </button>

              {panel.type === 'view' && (() => {
                // ACC-01.4: 统一单帖与多帖渲染逻辑，都使用预览卡片列表
                const m = panel.marker;
                const grouped = groupedMarkers;
                const posts = grouped && grouped.length > 1 ? grouped : [m];
                const count = posts.length;
                const isGroupedView = count > 1;

                return (
                  <>
                    <div className="h-[80px] bg-gradient-to-br from-lake/15 via-mist to-lamp/10 flex items-center px-5 flex-shrink-0">
                      <div className="flex items-center gap-2.5">
                        <div className="w-9 h-9 rounded-full bg-lamp/20 flex items-center justify-center">
                          <MapPin size={16} className="text-lamp" />
                        </div>
                        <div>
                          <div className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider">{m.location_name || '相同地点'}</div>
                          <div className="font-display font-bold text-base text-ink">
                            {isGroupedView ? `${count} 条信息 · 同一地点` : '1 条信息'}
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
                      {posts.map((gm) => {
                        const category = categoriesById.get(gm.category_id);
                        const visual = getCategoryVisual(gm.category_code ?? category?.code);
                        return (
                          <button
                            key={gm.post_id}
                            onClick={() => navigate(`/posts/${gm.post_id}`)}
                            className="w-full text-left bg-white hover:bg-mist/60 rounded-lg border border-line p-3 transition-colors"
                          >
                            <div className="flex items-start gap-2">
                              <span
                                className="mt-1 w-2 h-2 rounded-full flex-shrink-0"
                                style={{ backgroundColor: visual.marker }}
                              />
                              <div className="min-w-0 flex-1">
                                <div className="font-medium text-ink text-sm line-clamp-2">{gm.title}</div>
                                <div className="flex items-center gap-2 mt-1 text-[11px] text-ink-muted">
                                  <span style={{ color: visual.text }}>{gm.category_name ?? category?.name ?? '未分类'}</span>
                                  <span>·</span>
                                  <span>{gm.location_name || ''}</span>
                                </div>
                              </div>
                              <ArrowRight size={14} className="text-ink-muted mt-1 flex-shrink-0" />
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </>
                );
              })()}

              {panel.type === 'create' && (
                <>
                  {/* 顶部装饰条 */}
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

                  {/* PUB-01.1：表单复用 PostForm（variant='panel'）
                       - 地图点选坐标通过 defaultLocationLat/Lng 传入（只读预填）
                       - 字段 / 校验 / 草稿恢复 / 图片 / 标签 / 地点选择 与 PublishPage 完全一致
                       - key 绑定选点坐标，确保每次打开面板都重新初始化表单
                       - onSuccess：关闭面板 + 刷新地图标记 + 跳"我的发布"（PUB-01.3） */}
                  <div className="flex-1 overflow-y-auto px-5 py-4">
                    <PostForm
                      key={`${panel.lngLat.lat.toFixed(6)},${panel.lngLat.lng.toFixed(6)}`}
                      variant="panel"
                      defaultLocationLat={panel.lngLat.lat}
                      defaultLocationLng={panel.lngLat.lng}
                      showCancelButton={false}
                      onSuccess={(status) => {
                        void status;
                        setGroupedMarkers(null);
                        setPanel(null);
                        // 刷新地图标记
                        if (map.current) {
                          fetchMarkers(map.current.getBounds(), selectedCategory ?? undefined);
                        }
                        // PUB-01.3：发布成功后跳"我的发布"，而非无条件留在地图页
                        setTimeout(() => navigate('/profile'), 800);
                      }}
                    />
                  </div>
                </>
              )}
            </aside>
          </>
        )}
      </div>
    </div>
  );
};

export default MapPage;
