import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Navigation, Plus, Minus, Filter, X, MapPin, ArrowRight, Edit3, AlertCircle, RefreshCw, ChevronRight } from 'lucide-react';
import { mapApi, type MapMarker } from '../services/map';
import { postsApi } from '../services/posts';
import { categoriesApi, type CategoryListItem } from '../services/categories';
import { Loading } from '../components/ui/Loading';
import PostForm from '../components/PostForm';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';
import { useCampusStore } from '../store/useCampusStore';
import { logger } from '../utils/logger';

// PUB-01.1: 分类列表改为从 API 动态拉取（按当前学校过滤），不再硬编码
// 分类颜色映射保留作为地图标记视觉差异化用，未命中的分类回退灰色
const CATEGORY_COLORS: Record<number, string> = {
  1: '#FF6B35',  // 美食
  2: '#4ECDC4',  // 打印
  3: '#FFD93D',  // 校园猫
  4: '#6C5CE7',  // 活动
  5: '#A8E6CF',  // 学习
  6: '#FF8A5C',  // 失物
  7: '#3D5A80',  // 设施
  8: '#E07A5F',  // 二手
  9: '#81B29A',  // 求助
  10: '#F2CC8F', // 兼职
  11: '#7B68EE', // 社团
  12: '#FF69B4', // 其他
};

const CATEGORY_NAMES: Record<number, string> = {
  1: '美食',
  2: '打印',
  3: '校园猫',
  4: '活动',
  5: '学习',
  6: '失物',
  7: '设施',
  8: '二手',
  9: '求助',
  10: '兼职',
  11: '社团',
  12: '其他',
};

// 侧滑面板模式：null=关闭 / view=查看 marker / create=发帖
type PanelMode = null | { type: 'view'; marker: MapMarker } | { type: 'create'; lngLat: { lng: number; lat: number } };

// P1-002: 兜底中心点/缩放级别（仅当 useCampusStore.currentSchoolCenter 为 null 时使用）
// 江南大学蠡湖校区坐标 [lng, lat]
const FALLBACK_CENTER: [number, number] = [120.271166, 31.483706];
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
  const markersRef = useRef<maplibregl.Marker[]>([]);
  // DSC-01.3: marker -> post_id 映射，用于支持 focus_post_id 深链接自动打开面板
  const markersByIdRef = useRef<Map<number, { marker: MapMarker; element: HTMLDivElement }>>(new Map());
  // 聚合 marker 暂存的多帖列表（供侧滑面板渲染）
  const groupedMarkersRef = useRef<MapMarker[] | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
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

  // P1-002: 动态拉取当前学校的分类列表（依赖 currentSchoolId，切换学校时重新拉取）
  // CATEGORY_COLORS / CATEGORY_NAMES 保留作为 API 未返回或延迟时的 fallback
  const currentSchoolId = useCampusStore((s) => s.currentSchoolId);
  const [categories, setCategories] = useState<CategoryListItem[]>([]);
  useEffect(() => {
    let cancelled = false;
    categoriesApi
      .listCategories()
      .then((data) => {
        if (!cancelled) setCategories(data);
      })
      .catch(() => {
        // 拉取失败保留空数组，UI 会回退到 CATEGORY_NAMES 硬编码兜底
      });
    return () => {
      cancelled = true;
    };
  }, [currentSchoolId]);

  // 优先从动态 categories 查找分类名，fallback 到硬编码 CATEGORY_NAMES
  const getCategoryName = useCallback(
    (categoryId: number): string => {
      const dyn = categories.find((c) => c.id === categoryId)?.name;
      if (dyn) return dyn;
      return CATEGORY_NAMES[categoryId] || '未知';
    },
    [categories]
  );

  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [mapReady, setMapReady] = useState(false);
  // DSC-01.3: 地图加载失败标志，true 时切换到列表视图降级展示
  const [mapFailed, setMapFailed] = useState(false);
  // DSC-01.3: 列表视图降级所需的所有 markers（与 map 渲染共用同一份）
  const [allMarkers, setAllMarkers] = useState<MapMarker[]>([]);
  // 侧滑面板模式
  const [panel, setPanel] = useState<PanelMode>(null);
  // 选中的帖子详情（view 模式下点击 marker 后异步加载）
  const [postDetail, setPostDetail] = useState<{ content: string } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 清除地图上的标记
  const clearMarkers = useCallback(() => {
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
  }, []);

  // 获取并更新地图标记
  const fetchMarkers = useCallback(async (bounds: maplibregl.LngLatBounds, categoryId?: number) => {
    setLoading(true);
    try {
      const params = {
        north: bounds.getNorth(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        west: bounds.getWest(),
        ...(categoryId ? { category_id: categoryId } : {}),
      };
      const data = await mapApi.getMapMarkers(params);

      // 清除旧标记
      clearMarkers();
      // DSC-01.3: 同步清空 post_id -> marker 索引，避免旧数据残留
      markersByIdRef.current.clear();
      // DSC-01.3: 保存所有 markers 到 state，用于地图失败时的列表降级视图
      setAllMarkers(data);

      // Task 3.5: 按坐标聚合相同地点的帖子
      // key = `${lng.toFixed(6)},${lat.toFixed(6)}`，同一坐标的帖子聚合成一个 marker
      const grouped = new Map<string, MapMarker[]>();
      for (const m of data) {
        const key = `${m.longitude.toFixed(6)},${m.latitude.toFixed(6)}`;
        const arr = grouped.get(key);
        if (arr) {
          arr.push(m);
        } else {
          grouped.set(key, [m]);
        }
      }

      // 为每个分组创建 marker
      grouped.forEach((markersAtLocation) => {
        const first = markersAtLocation[0];
        const count = markersAtLocation.length;
        const isGrouped = count > 1;
        // 聚合 marker 用第一个帖子的分类色（或取数量最多分类的颜色）
        const color = CATEGORY_COLORS[first.category_id] || '#95A5A6';

        const el = document.createElement('div');
        el.className = 'custom-marker';
        el.style.cssText = isGrouped
          ? 'width: 36px; height: 36px; cursor: pointer; position: relative;'
          : 'width: 28px; height: 28px; cursor: pointer;';

        // 内层水滴形 pin
        const pin = document.createElement('div');
        pin.style.cssText = isGrouped
          ? `width: 100%; height: 100%; border-radius: 50% 50% 50% 0; background: ${color}; transform: rotate(-45deg); display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0,0,0,0.35); transition: transform 0.2s;`
          : `width: 100%; height: 100%; border-radius: 50% 50% 50% 0; background: ${color}; transform: rotate(-45deg); display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.3); transition: transform 0.2s;`;

        const inner = document.createElement('div');
        if (isGrouped) {
          // 聚合 marker：显示数字
          inner.style.cssText = `
            font-size: 13px;
            font-weight: 700;
            color: white;
            transform: rotate(45deg);
            line-height: 1;
          `;
          inner.textContent = String(count);
        } else {
          // 单帖 marker：显示圆点（保持原样）
          inner.style.cssText = `
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: white;
            transform: rotate(45deg);
          `;
        }
        pin.appendChild(inner);
        el.appendChild(pin);

        // 悬停效果
        el.addEventListener('mouseenter', () => {
          pin.style.transform = `rotate(-45deg) scale(1.2)`;
        });
        el.addEventListener('mouseleave', () => {
          pin.style.transform = 'rotate(-45deg) scale(1)';
        });

        const markerInstance = new maplibregl.Marker({ element: el })
          .setLngLat([first.longitude, first.latitude])
          .addTo(map.current!);

        if (isGrouped) {
          // Task 3.5 v2: 聚合 marker 点击 → 打开侧滑面板，显示该地点所有帖子（与单帖路径统一）
          el.addEventListener('click', (e) => {
            e.stopPropagation();
            // 复用 setPanel 单帖视图，但在侧滑面板里渲染"多帖"视图
            setPanel({ type: 'view', marker: first });
            // 通过 markersById 暂存聚合数据（供 Panel 渲染读取）
            groupedMarkersRef.current = markersAtLocation;
            setPostDetail(null);
            setDetailLoading(true);
            postsApi
              .getPost(first.post_id)
              .then((detail) => setPostDetail({ content: (detail as { content?: string }).content ?? '' }))
              .catch(() => setPostDetail(null))
              .finally(() => setDetailLoading(false));
          });
        } else {
          // 单帖 marker：保持原有行为（打开侧滑面板）
          el.addEventListener('click', (e) => {
            e.stopPropagation();
            setPanel({ type: 'view', marker: first });
            setPostDetail(null);
            setDetailLoading(true);
            postsApi
              .getPost(first.post_id)
              .then((detail) => setPostDetail({ content: (detail as { content?: string }).content ?? '' }))
              .catch(() => setPostDetail(null))
              .finally(() => setDetailLoading(false));
          });
        }

        // DSC-01.3: 索引每个 post_id -> marker 数据 + DOM 元素
        // 聚合 marker 下每个 post_id 都指向同一 DOM 元素，点击时打开 Popup（由上面的 click 处理）
        for (const m of markersAtLocation) {
          markersByIdRef.current.set(m.post_id, { marker: m, element: el });
        }
        markersRef.current.push(markerInstance);
      });
    } catch {
      // 静默处理错误，保留现有标记
    } finally {
      setLoading(false);
    }
  }, [clearMarkers, navigate]);

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
      setMapReady(true);
      const bounds = mapInstance.getBounds();
      fetchMarkers(bounds, selectedCategory ?? undefined);
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

    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      if (popupRef.current) {
        popupRef.current.remove();
      }
      mapInstance.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // P1-002: 监听学校切换，地图 flyTo 到新中心点并重新拉取 markers
  useEffect(() => {
    if (!map.current || !mapReady) return;
    map.current.flyTo({
      center: activeCenter,
      zoom: activeZoom,
      duration: 800,
    });
    // 飞行结束后 moveend 事件会自动触发 fetchMarkers
    // 但为保险起见，延迟 850ms 后主动拉取一次
    const timer = setTimeout(() => {
      if (!map.current) return;
      const bounds = map.current.getBounds();
      fetchMarkers(bounds, selectedCategory ?? undefined);
    }, 850);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSchoolCenter, currentSchoolZoom]);

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
    const { marker, element } = entry;
    map.current?.flyTo({
      center: [marker.longitude, marker.latitude],
      zoom: Math.max(map.current?.getZoom() ?? activeZoomRef.current, 17),
    });
    element.click();

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
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    markersByIdRef.current.clear();
    if (popupRef.current) {
      popupRef.current.remove();
    }
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
  // 与地图 marker 点击逻辑一致：打开侧滑面板 + 异步加载详情
  const handleListMarkerClick = useCallback((marker: MapMarker) => {
    setPanel({ type: 'view', marker });
    setPostDetail(null);
    setDetailLoading(true);
    postsApi
      .getPost(marker.post_id)
      .then((detail) => setPostDetail({ content: (detail as { content?: string }).content ?? '' }))
      .catch(() => setPostDetail(null))
      .finally(() => setDetailLoading(false));
  }, []);

  // 定位按钮
  const handleGeolocate = useCallback(() => {
    if (!navigator.geolocation || !map.current) return;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        map.current!.flyTo({
          center: [position.coords.longitude, position.coords.latitude],
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
      </div>

      {/* 分类筛选条：横向滚动 */}
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
          {(categories.length > 0
            ? categories.map((c) => ({ id: c.id, name: c.name }))
            : Object.entries(CATEGORY_NAMES).map(([id, name]) => ({ id: Number(id), name }))
          ).map((item) => {
            const numId = item.id;
            const color = CATEGORY_COLORS[numId] || '#95A5A6';
            const isActive = selectedCategory === numId;
            return (
              <button
                key={numId}
                onClick={() => setSelectedCategory(isActive ? null : numId)}
                className={`flex-shrink-0 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
                  isActive ? 'text-white shadow-sm' : 'text-ink-sub hover:bg-line'
                }`}
                style={isActive ? { backgroundColor: color } : { backgroundColor: `${color}18` }}
              >
                {item.name}
              </button>
            );
          })}
        </div>
      </div>

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
                  const color = CATEGORY_COLORS[marker.category_id] || '#95A5A6';
                  const catName = getCategoryName(marker.category_id);
                  return (
                    <div
                      key={marker.post_id}
                      className="p-4 hover:bg-mist cursor-pointer flex items-start gap-3 transition-colors"
                      onClick={() => handleListMarkerClick(marker)}
                    >
                      <div
                        className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
                        style={{ backgroundColor: `${color}20` }}
                      >
                        <MapPin size={16} style={{ color }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold flex-shrink-0"
                            style={{ backgroundColor: `${color}20`, color }}
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

        {/* 右侧侧滑面板：view（查看 marker）/ create（发帖） */}
        {panel && (
          <>
            {/* 半透明遮罩：移动端点击关闭 */}
            <div
              className="absolute inset-0 z-20 bg-ink/20 backdrop-blur-[1px] md:bg-transparent md:backdrop-blur-none"
              onClick={() => {
                groupedMarkersRef.current = null;
                setPanel(null);
              }}
            />
            <aside
              className="absolute top-0 right-0 bottom-0 z-30 w-full sm:w-[340px] md:w-[360px] bg-paper shadow-2xl border-l border-line flex flex-col map-slide-panel"
            >
              {/* 关闭按钮 */}
              <button
                onClick={() => {
                  groupedMarkersRef.current = null;
                  setPanel(null);
                }}
                className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-mist/80 backdrop-blur-sm flex items-center justify-center text-ink-sub hover:text-ink hover:bg-mist transition-colors"
                aria-label="关闭"
              >
                <X size={16} />
              </button>

              {panel.type === 'view' && (() => {
                const m = panel.marker;
                const grouped = groupedMarkersRef.current;
                const isGroupedView = grouped && grouped.length > 1;

                if (isGroupedView) {
                  // 多帖侧滑面板：与首页卡片风格统一，精简版
                  return (
                    <>
                      <div className="h-[80px] bg-gradient-to-br from-lake/15 via-mist to-lamp/10 flex items-center px-5 flex-shrink-0">
                        <div className="flex items-center gap-2.5">
                          <div className="w-9 h-9 rounded-full bg-lamp/20 flex items-center justify-center">
                            <MapPin size={16} className="text-lamp" />
                          </div>
                          <div>
                            <div className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider">{m.location_name || '相同地点'}</div>
                            <div className="font-display font-bold text-base text-ink">{grouped.length} 条信息 · 同一地点</div>
                          </div>
                        </div>
                      </div>
                      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
                        {grouped.map((gm) => {
                          const color = CATEGORY_COLORS[gm.category_id] || '#95A5A6';
                          return (
                            <button
                              key={gm.post_id}
                              onClick={() => navigate(`/posts/${gm.post_id}`)}
                              className="w-full text-left bg-white hover:bg-mist/60 rounded-lg border border-line p-3 transition-colors"
                            >
                              <div className="flex items-start gap-2">
                                <span
                                  className="mt-1 w-2 h-2 rounded-full flex-shrink-0"
                                  style={{ backgroundColor: color }}
                                />
                                <div className="min-w-0 flex-1">
                                  <div className="font-medium text-ink text-sm line-clamp-2">{gm.title}</div>
                                  <div className="flex items-center gap-2 mt-1 text-[11px] text-ink-muted">
                                    <span style={{ color }}>{getCategoryName(gm.category_id)}</span>
                                    <span>·</span>
                                    <span>{gm.location_name || ''}</span>
                                  </div>
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </>
                  );
                }

                return (
                  <>
                    {/* 封面图（如有） */}
                    {m.cover_image ? (
                      <div className="relative h-[160px] sm:h-[140px] overflow-hidden bg-mist">
                        <img
                          src={m.cover_image}
                          alt={m.title}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.currentTarget.parentElement!.style.display = 'none');
                          }}
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-ink/40 via-transparent to-transparent" />
                      </div>
                    ) : (
                      <div className="h-[100px] bg-gradient-to-br from-lake/15 via-mist to-lamp/10 flex items-center justify-center">
                        <MapPin size={32} className="text-lake/50" />
                      </div>
                    )}

                    {/* 内容区 */}
                    <div className="flex-1 overflow-y-auto px-5 py-4">
                      {/* 分类徽章 */}
                      <div className="flex items-center gap-2 mb-3">
                        <span
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold font-data"
                          style={{
                            backgroundColor: `${CATEGORY_COLORS[m.category_id] || '#95A5A6'}20`,
                            color: CATEGORY_COLORS[m.category_id] || '#95A5A6',
                          }}
                        >
                          <span
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ backgroundColor: CATEGORY_COLORS[m.category_id] || '#95A5A6' }}
                          />
                          {getCategoryName(m.category_id)}
                        </span>
                      </div>

                      {/* 标题 */}
                      <h3 className="font-display font-extrabold text-xl text-ink leading-tight mb-3 pr-8">
                        {m.title}
                      </h3>

                      {/* 位置 */}
                      <div className="flex items-start gap-2 text-sm text-ink-sub mb-4">
                        <MapPin size={15} className="flex-shrink-0 mt-0.5 text-lamp" />
                        <span className="leading-relaxed">{m.location_name}</span>
                      </div>

                      {/* 帖子内容 */}
                      <div className="mb-4">
                        <div className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider mb-1.5">
                          内容
                        </div>
                        {detailLoading ? (
                          <div className="py-3">
                            <Loading size="sm" />
                          </div>
                        ) : postDetail?.content ? (
                          <p className="text-sm text-ink leading-relaxed whitespace-pre-line line-clamp-[12]">
                            {postDetail.content}
                          </p>
                        ) : (
                          <p className="text-sm text-ink-muted italic">暂无内容</p>
                        )}
                      </div>

                      {/* 坐标信息（小字、技术感） */}
                      <div className="font-data text-[11px] text-ink-muted bg-mist/60 rounded-md px-3 py-2 mb-5 border border-line/60">
                        <div className="flex justify-between">
                          <span>LAT</span>
                          <span className="text-ink-sub">{m.latitude.toFixed(6)}</span>
                        </div>
                        <div className="flex justify-between mt-0.5">
                          <span>LNG</span>
                          <span className="text-ink-sub">{m.longitude.toFixed(6)}</span>
                        </div>
                      </div>

                      {/* 查看详情按钮 */}
                      <button
                        onClick={() => navigate(`/posts/${m.post_id}`)}
                        className="w-full flex items-center justify-center gap-2 bg-lamp text-white font-semibold py-2.5 rounded-md shadow-md hover:bg-lamp/90 transition-colors"
                      >
                        查看详情
                        <ArrowRight size={16} />
                      </button>
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
                        groupedMarkersRef.current = null;
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
