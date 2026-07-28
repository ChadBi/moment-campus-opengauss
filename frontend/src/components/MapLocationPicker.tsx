import React, { useEffect, useRef, useState, useMemo } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapPin, Check } from 'lucide-react';
import { useCampusStore } from '../store/useCampusStore';
import { logger } from '../utils/logger';

/**
 * Task 3.1 / 6.1: 基于 maplibre-gl 的地图选点组件
 *
 * 用法：
 *   - 表单选点模式（默认）：点击地图设置 marker，调用 onPick 回调
 *   - 只读模式（readOnly=true）：仅展示坐标点，不可点击
 *
 * 中心点优先级：initialLat/Lng → 当前学校中心点 → 兜底江南大学坐标
 */

// 兜底中心点：江南大学蠡湖校区
const FALLBACK_CENTER: [number, number] = [120.271166, 31.483706];
const FALLBACK_ZOOM = 16;

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
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

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
