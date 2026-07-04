import React, { useState, useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useNavigate } from 'react-router-dom';
import { Navigation, Plus, Minus, Filter, X, MapPin, ArrowRight, Edit3, Send } from 'lucide-react';
import { mapApi, type MapMarker } from '../services/map';
import { postsApi } from '../services/posts';
import { Loading } from '../components/ui/Loading';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';

// 发帖表单的分类列表（与 PublishPage 一致）
const PUBLISH_CATEGORIES = [
  { id: 1, name: '校园美食', emoji: '🍜' },
  { id: 2, name: '校园动物', emoji: '🐈' },
  { id: 3, name: '打印服务', emoji: '🖨️' },
  { id: 4, name: '失物招领', emoji: '🔍' },
  { id: 5, name: '二手交易', emoji: '📦' },
  { id: 6, name: '学习交流', emoji: '📚' },
  { id: 7, name: '社团活动', emoji: '🎪' },
  { id: 8, name: '校园设施', emoji: '🏫' },
  { id: 9, name: '兼职实习', emoji: '💼' },
  { id: 10, name: '校园交通', emoji: '🚌' },
  { id: 11, name: '生活服务', emoji: '🧺' },
  { id: 12, name: '其他', emoji: '✨' },
];

// 侧滑面板模式：null=关闭 / view=查看 marker / create=发帖
type PanelMode = null | { type: 'view'; marker: MapMarker } | { type: 'create'; lngLat: { lng: number; lat: number } };

// 分类颜色映射
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

const DEFAULT_CENTER: [number, number] = [120.271166, 31.483706]; // 江南大学蠡湖校区 [lng, lat]
const DEFAULT_ZOOM = 16;

const MapPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const { showToast } = useUIStore();
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 用 ref 同步 isAuthenticated，避免地图 click 闭包陷阱
  const authRef = useRef(isAuthenticated);
  useEffect(() => {
    authRef.current = isAuthenticated;
  }, [isAuthenticated]);

  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [mapReady, setMapReady] = useState(false);
  // 侧滑面板模式
  const [panel, setPanel] = useState<PanelMode>(null);
  // 选中的帖子详情（view 模式下点击 marker 后异步加载）
  const [postDetail, setPostDetail] = useState<{ content: string } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  // 发帖表单状态（create 模式）
  const [publishForm, setPublishForm] = useState({
    title: '',
    content: '',
    category_id: 0,
    location_name: '',
    is_anonymous: false,
  });
  const [publishing, setPublishing] = useState(false);

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

      // 添加新标记
      data.forEach((marker) => {
        const color = CATEGORY_COLORS[marker.category_id] || '#95A5A6';

        // 外层 wrapper：不要设置任何 transform，maplibre-gl 会用 transform 定位 marker
        // 形状（旋转 -45deg 变成水滴形）放到内层 pin 元素上
        const el = document.createElement('div');
        el.className = 'custom-marker';
        el.style.cssText = `
          width: 28px;
          height: 28px;
          cursor: pointer;
        `;

        // 内层水滴形 pin：承担 rotate 变换，不影响外层定位
        const pin = document.createElement('div');
        pin.style.cssText = `
          width: 100%;
          height: 100%;
          border-radius: 50% 50% 50% 0;
          background: ${color};
          transform: rotate(-45deg);
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
          transition: transform 0.2s;
        `;

        const inner = document.createElement('div');
        inner.style.cssText = `
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: white;
          transform: rotate(45deg);
        `;
        pin.appendChild(inner);
        el.appendChild(pin);

        // 悬停效果：只缩放 pin，不动外层
        el.addEventListener('mouseenter', () => {
          pin.style.transform = 'rotate(-45deg) scale(1.2)';
        });
        el.addEventListener('mouseleave', () => {
          pin.style.transform = 'rotate(-45deg) scale(1)';
        });

        const markerInstance = new maplibregl.Marker({ element: el })
          .setLngLat([marker.longitude, marker.latitude])
          .addTo(map.current!);

        // 点击打开右侧侧滑面板（view 模式） + 异步加载帖子内容
        el.addEventListener('click', (e) => {
          e.stopPropagation(); // 阻止冒泡到地图 click（避免触发发帖）
          setPanel({ type: 'view', marker });
          setPostDetail(null);
          setDetailLoading(true);
          postsApi
            .getPost(marker.post_id)
            .then((detail) => setPostDetail({ content: (detail as { content?: string }).content ?? '' }))
            .catch(() => setPostDetail(null))
            .finally(() => setDetailLoading(false));
        });

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
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'osm-tiles',
            type: 'raster',
            source: 'osm',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

    mapInstance.on('load', () => {
      setMapReady(true);
      const bounds = mapInstance.getBounds();
      fetchMarkers(bounds, selectedCategory ?? undefined);
    });

    // 地图点击空白处：登录用户打开发帖面板，未登录提示
    mapInstance.on('click', (e) => {
      if (!authRef.current) {
        showToast('请先登录后再发布信息', 'info');
        return;
      }
      // 重置表单
      setPublishForm({
        title: '',
        content: '',
        category_id: 0,
        location_name: '',
        is_anonymous: false,
      });
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

  // 分类变化时重新获取标记
  useEffect(() => {
    if (!map.current || !mapReady) return;
    const bounds = map.current.getBounds();
    fetchMarkers(bounds, selectedCategory ?? undefined);
  }, [selectedCategory, mapReady, fetchMarkers]);

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
        // 定位失败，回到默认位置
        map.current!.flyTo({
          center: DEFAULT_CENTER,
          zoom: DEFAULT_ZOOM,
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
          {Object.entries(CATEGORY_NAMES).map(([id, name]) => {
            const numId = Number(id);
            const color = CATEGORY_COLORS[numId];
            const isActive = selectedCategory === numId;
            return (
              <button
                key={id}
                onClick={() => setSelectedCategory(isActive ? null : numId)}
                className={`flex-shrink-0 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
                  isActive ? 'text-white shadow-sm' : 'text-ink-sub hover:bg-line'
                }`}
                style={isActive ? { backgroundColor: color } : { backgroundColor: `${color}18` }}
              >
                {name}
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
              onClick={() => setPanel(null)}
            />
            <aside
              className="absolute top-0 right-0 bottom-0 z-30 w-full sm:w-[340px] md:w-[360px] bg-paper shadow-2xl border-l border-line flex flex-col map-slide-panel"
            >
              {/* 关闭按钮 */}
              <button
                onClick={() => setPanel(null)}
                className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-mist/80 backdrop-blur-sm flex items-center justify-center text-ink-sub hover:text-ink hover:bg-mist transition-colors"
                aria-label="关闭"
              >
                <X size={16} />
              </button>

              {panel.type === 'view' && (() => {
                const m = panel.marker;
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
                          {CATEGORY_NAMES[m.category_id] || '未知'}
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
                  <div className="h-[80px] bg-gradient-to-br from-lake/15 via-mist to-lamp/10 flex items-center px-5">
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

                  {/* 表单 */}
                  <form
                    className="flex-1 overflow-y-auto px-5 py-4 space-y-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (publishForm.title.length < 5 || publishForm.title.length > 100) {
                        showToast('标题长度需 5-100 字符', 'warning');
                        return;
                      }
                      if (publishForm.content.length < 10 || publishForm.content.length > 5000) {
                        showToast('内容长度需 10-5000 字符', 'warning');
                        return;
                      }
                      if (!publishForm.category_id) {
                        showToast('请选择分类', 'warning');
                        return;
                      }
                      if (!publishForm.location_name.trim()) {
                        showToast('请填写地点名称', 'warning');
                        return;
                      }
                      setPublishing(true);
                      postsApi
                        .createPost({
                          title: publishForm.title,
                          content: publishForm.content,
                          category_id: publishForm.category_id,
                          location_name: publishForm.location_name.trim(),
                          location_lat: panel.lngLat.lat,
                          location_lng: panel.lngLat.lng,
                          is_anonymous: publishForm.is_anonymous,
                          status: 'pending',
                        })
                        .then(() => {
                          showToast('已提交审核，等待管理员通过', 'success');
                          setPanel(null);
                          // 刷新地图标记
                          if (map.current) {
                            fetchMarkers(map.current.getBounds(), selectedCategory ?? undefined);
                          }
                        })
                        .catch((err: unknown) => {
                          const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '发布失败，请稍后重试';
                          showToast(msg, 'error');
                        })
                        .finally(() => setPublishing(false));
                    }}
                  >
                    {/* 标题 */}
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1.5">
                        标题 <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        value={publishForm.title}
                        onChange={(e) => setPublishForm({ ...publishForm, title: e.target.value })}
                        placeholder="例如：南门小树林有小猫"
                        maxLength={100}
                        className="w-full px-3.5 py-2.5 bg-white/78 border border-line rounded-md text-sm text-ink placeholder:text-ink-muted/70 focus:outline-none focus:bg-white focus:border-lake transition-all"
                      />
                    </div>

                    {/* 分类 */}
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1.5">
                        分类 <span className="text-danger">*</span>
                      </label>
                      <div className="grid grid-cols-3 gap-1.5">
                        {PUBLISH_CATEGORIES.map((cat) => {
                          const isActive = publishForm.category_id === cat.id;
                          return (
                            <button
                              key={cat.id}
                              type="button"
                              onClick={() => setPublishForm({ ...publishForm, category_id: cat.id })}
                              className={`flex items-center gap-1 px-2 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                                isActive
                                  ? 'bg-lake text-white shadow-lake'
                                  : 'bg-mist text-ink-sub hover:bg-line'
                              }`}
                            >
                              <span className="text-xs">{cat.emoji}</span>
                              <span className="truncate">{cat.name}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* 内容 */}
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1.5">
                        内容 <span className="text-danger">*</span>
                      </label>
                      <textarea
                        value={publishForm.content}
                        onChange={(e) => setPublishForm({ ...publishForm, content: e.target.value })}
                        placeholder="请描述具体位置和详情（10-5000字符），例如：从南门进去左手边第二片小树林，常出没三只橘猫"
                        rows={5}
                        maxLength={5000}
                        className="w-full px-3.5 py-2.5 bg-white/78 border border-line rounded-md text-sm text-ink placeholder:text-ink-muted/70 focus:outline-none focus:bg-white focus:border-lake transition-all resize-none"
                      />
                    </div>

                    {/* 地点名称 */}
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1.5">
                        地点名称 <span className="text-danger">*</span>
                      </label>
                      <input
                        type="text"
                        value={publishForm.location_name}
                        onChange={(e) => setPublishForm({ ...publishForm, location_name: e.target.value })}
                        placeholder="例如：南门小树林"
                        maxLength={100}
                        className="w-full px-3.5 py-2.5 bg-white/78 border border-line rounded-md text-sm text-ink placeholder:text-ink-muted/70 focus:outline-none focus:bg-white focus:border-lake transition-all"
                      />
                    </div>

                    {/* 坐标（只读显示） */}
                    <div className="font-data text-[11px] text-ink-muted bg-mist/60 rounded-md px-3 py-2 border border-line/60">
                      <div className="flex justify-between">
                        <span>LAT</span>
                        <span className="text-ink-sub">{panel.lngLat.lat.toFixed(6)}</span>
                      </div>
                      <div className="flex justify-between mt-0.5">
                        <span>LNG</span>
                        <span className="text-ink-sub">{panel.lngLat.lng.toFixed(6)}</span>
                      </div>
                    </div>

                    {/* 匿名 */}
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={publishForm.is_anonymous}
                        onChange={(e) => setPublishForm({ ...publishForm, is_anonymous: e.target.checked })}
                        className="w-4 h-4 text-lake border-line rounded focus:ring-lamp/40"
                      />
                      <span className="text-sm text-ink">匿名发布</span>
                    </label>

                    {/* 提交按钮 */}
                    <button
                      type="submit"
                      disabled={publishing}
                      className="w-full flex items-center justify-center gap-2 bg-lamp text-white font-semibold py-2.5 rounded-md shadow-md hover:bg-lamp/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {publishing ? (
                        <Loading size="sm" />
                      ) : (
                        <>
                          <Send size={15} />
                          提交审核
                        </>
                      )}
                    </button>

                    <p className="text-[11px] text-ink-muted leading-relaxed text-center">
                      信息提交后需管理员审核通过才会公开展示
                    </p>
                  </form>
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
