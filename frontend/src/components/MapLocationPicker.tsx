import React, { useEffect, useRef, useState, useMemo } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapPin, Check } from 'lucide-react';
import { useCampusStore } from '../store/useCampusStore';
import { logger } from '../utils/logger';

// 兜底中心点：江南大学蠡湖校区
const FALLBACK_CENTER: [number, number] = [120.271166, 31.483706];
const FALLBACK_ZOOM = 16;

/**
 * P1-003: 滚轮缩放节流
 * 当用户快速滚动滚轮时，浏览器会在短时间内触发大量 wheel 事件，
 * maplibre 的默认处理可能产生卡顿和"抽搐"感。
 * 通过节流 wheel 事件至 ~30ms 一次，保证缩放平滑。
 */
const throttleWheel = (callback: (deltaY: number) => void, wait = 30) => {
  let lastTime = 0;
  let queuedDelta = 0;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const flush = () => {
    timeoutId = null;
    if (queuedDelta !== 0) {
      callback(queuedDelta);
      queuedDelta = 0;
    }
  };

  return (deltaY: number) => {
    const now = Date.now();
    const elapsed = now - lastTime;
    queuedDelta += deltaY;
    if (elapsed >= wait) {
      lastTime = now;
      callback(queuedDelta);
      queuedDelta = 0;
    } else if (timeoutId === null) {
      timeoutId = setTimeout(flush, wait - elapsed);
    }
  };
};

export interface MapLocationPickerProps {
  /** 初始纬度 */
  initialLat?: number;
  /** 初始经度 */
  initialLng?: number;
  /** 初始地点名称（仅展示用） */
  initialName?: string;
  /** 只读模式：仅展示，不可点击选点 */
  readOnly?: boolean;
  /** 选点回调（readOnly=true 时不触发） */
  onPick?: (lat: number, lng: number) => void;
  /** 容器高度（默认 320px） */
  height?: number | string;
}

const MapLocationPicker: React.FC<MapLocationPickerProps> = ({
  initialLat,
  initialLng,
  initialName,
  readOnly = false,
  onPick,
  height = 320,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const { currentSchoolCenter, currentSchoolZoom } = useCampusStore();
  const [picked, setPicked] = useState<{ lat: number; lng: number } | null>(
    initialLat != null && initialLng != null
      ? { lat: initialLat, lng: initialLng }
      : null
  );

  // 计算初始中心点（initialLat/Lng 优先，其次当前学校，最后兜底）
  const activeCenter: [number, number] = useMemo(() => {
    if (initialLat != null && initialLng != null) {
      return [initialLng, initialLat];
    }
    if (currentSchoolCenter) {
      return [currentSchoolCenter.lng, currentSchoolCenter.lat];
    }
    return FALLBACK_CENTER;
  }, [initialLat, initialLng, currentSchoolCenter]);

  const activeZoom = currentSchoolZoom ?? FALLBACK_ZOOM;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
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
      center: activeCenter,
      zoom: activeZoom,
      interactive: !readOnly,
      // P1-003: 地图交互稳定性
      dragRotate: false,
      doubleClickZoom: false,
      pitch: 0,
      bearing: 0,
      maxPitch: 0,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

    // P1-003: 节流 wheel 事件，避免快速滚动时缩放抽搐
    const wheelHandler = throttleWheel((deltaY) => {
      if (!mapRef.current) return;
      const currentZoom = mapRef.current.getZoom();
      // 单次节流周期内最多 ±0.3 zoom，防止单次滚动 zoom 过激
      const step = Math.max(0.05, Math.min(0.3, Math.abs(deltaY) * 0.002));
      const nextZoom = deltaY > 0 ? currentZoom - step : currentZoom + step;
      mapRef.current.zoomTo(nextZoom, { duration: 50 });
    }, 40);
    const wheelListener = (e: WheelEvent) => {
      e.preventDefault();
      wheelHandler(e.deltaY);
    };
    map.getContainer().addEventListener('wheel', wheelListener, { passive: false });

    // 初始 marker（若有 initialLat/Lng）
    if (initialLat != null && initialLng != null) {
      const m = new maplibregl.Marker({ draggable: false })
        .setLngLat([initialLng, initialLat])
        .addTo(map);
      markerRef.current = m;
    }

    map.on('error', (e) => {
      const err = (e as unknown as { error?: Error })?.error;
      logger.error('MapLocationPicker 地图加载失败:', err || e);
    });

    if (!readOnly) {
      map.on('click', (e) => {
        const { lng, lat } = e.lngLat;
        // 清除旧 marker
        if (markerRef.current) {
          markerRef.current.remove();
        }
        // 添加新 marker
        const m = new maplibregl.Marker({ draggable: false })
          .setLngLat([lng, lat])
          .addTo(map);
        markerRef.current = m;
        setPicked({ lat, lng });
        onPick?.(lat, lng);
      });
    }

    mapRef.current = map;

    return () => {
      map.getContainer().removeEventListener('wheel', wheelListener);
      if (markerRef.current) {
        markerRef.current.remove();
        markerRef.current = null;
      }
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 切换学校时平移到新中心（仅未选点时）
  useEffect(() => {
    if (!mapRef.current || picked) return;
    mapRef.current.flyTo({
      center: activeCenter,
      zoom: activeZoom,
      duration: 600,
    });
  }, [activeCenter, activeZoom, picked]);

  return (
    <div className="w-full">
      <div
        ref={containerRef}
        style={{ height: typeof height === 'number' ? `${height}px` : height }}
        className="w-full rounded-[10px] overflow-hidden border border-line"
      />
      {/* 选中坐标展示 */}
      <div className="mt-2 flex items-center gap-2 text-xs text-ink-sub bg-mist/60 rounded-md px-3 py-2 border border-line/60">
        <MapPin size={12} className="text-lamp flex-shrink-0" />
        {picked ? (
          <>
            {readOnly ? (
              <Check size={12} className="text-grass flex-shrink-0" />
            ) : null}
            <span>
              {initialName ? `${initialName} · ` : ''}
              纬度 {picked.lat.toFixed(6)}，经度 {picked.lng.toFixed(6)}
            </span>
          </>
        ) : (
          <span>
            {readOnly ? '未提供坐标' : '点击地图选择位置'}
          </span>
        )}
      </div>
    </div>
  );
};

export default MapLocationPicker;
