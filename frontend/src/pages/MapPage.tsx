import React, { useState, useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useNavigate } from 'react-router-dom';
import { Navigation, Plus, Minus, Filter } from 'lucide-react';
import { mapApi } from '../services/map';
import { Loading } from '../components/ui/Loading';

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
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const [mapReady, setMapReady] = useState(false);

  // 清除地图上的标记
  const clearMarkers = useCallback(() => {
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    if (popupRef.current) {
      popupRef.current.remove();
      popupRef.current = null;
    }
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
        const categoryName = CATEGORY_NAMES[marker.category_id] || '未知';

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

        // 点击弹窗
        el.addEventListener('click', () => {
          if (popupRef.current) {
            popupRef.current.remove();
          }

          const popupContent = document.createElement('div');
          popupContent.style.cssText = 'padding: 12px; min-width: 200px; font-family: var(--font-body);';
          popupContent.innerHTML = `
            <div style="font-weight: 700; font-size: 15px; margin-bottom: 6px; color: #152629; font-family: var(--font-display);">${marker.title}</div>
            <div style="font-size: 12px; color: #40575b; margin-bottom: 4px; display: flex; align-items: center;">
              <span style="display: inline-block; width: 8px; height: 8px; border-radius: 3px; background: ${color}; margin-right: 6px;"></span>
              ${categoryName}
            </div>
            <div style="font-size: 12px; color: #71858a; margin-bottom: 10px;">📍 ${marker.location_name}</div>
            <a href="/posts/${marker.post_id}" style="
              display: inline-block;
              padding: 6px 14px;
              background: #ff8a4c;
              color: white;
              border-radius: 10px;
              font-size: 12px;
              font-weight: 600;
              text-decoration: none;
              cursor: pointer;
              box-shadow: 0 6px 14px rgba(255,138,76,0.24);
            ">查看详情</a>
          `;

          // 处理查看详情点击
          const link = popupContent.querySelector('a');
          link?.addEventListener('click', (e) => {
            e.preventDefault();
            navigate(`/posts/${marker.post_id}`);
          });

          const popup = new maplibregl.Popup({
            offset: 20,
            closeButton: true,
            maxWidth: '260px',
          })
            .setDOMContent(popupContent)
            .setLngLat([marker.longitude, marker.latitude])
            .addTo(map.current!);

          popupRef.current = popup;
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
      </div>
    </div>
  );
};

export default MapPage;
