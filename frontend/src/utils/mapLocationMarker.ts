import type { Feature, FeatureCollection, Point } from 'geojson';
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl';
import type { LocationItem } from '../services/locations';

// A-06: 地图地点标记图层（独立于帖子标记图层）
// 每个标记为水滴 pin，内部绘制该地点的评分（avg_score），未评分显示「新」。

export const MAP_LOCATION_SOURCE_ID = 'campus-location-markers';
export const MAP_LOCATION_LAYER_ID = 'campus-location-marker-symbols';

export const MAP_LOCATION_PATH =
  'M 50 100 C 46 91 10 64 10 37 C 10 16.6 27.9 0 50 0 C 72.1 0 90 16.6 90 37 C 90 64 54 91 50 100 Z';

interface LocationMarkerProperties {
  locationId: number;
  imageId: string;
  name: string;
  avgScore: number;
  ratingCount: number;
}

const markerImageId = (score: number, verified: boolean) => {
  const key = score > 0 ? `loc-${score.toFixed(1).replace('.', '')}` : 'loc-new';
  return `campus-loc-pin-${key}-${verified ? 'v' : 'n'}`;
};

const createLocationMarkerImage = (score: number, verified: boolean): ImageData => {
  const pixelRatio = 2;
  const size = 40;
  const canvas = document.createElement('canvas');
  canvas.width = size * pixelRatio;
  canvas.height = size * pixelRatio;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('2D canvas is unavailable for location map marker sprite');

  context.scale((size * pixelRatio) / 100, (size * pixelRatio) / 100);

  // 水滴底色：已核验用 lake（蓝），未核验用 lamp（琥珀）
  const baseColor = verified ? '#2f7f8f' : '#e8a741';
  context.fillStyle = baseColor;
  context.fill(new Path2D(MAP_LOCATION_PATH));

  // 中央圆形评分徽标
  context.beginPath();
  context.arc(50, 35, verified ? 22 : 20, 0, Math.PI * 2);
  context.fillStyle = verified ? '#ffffff' : 'rgba(255,255,255,0.92)';
  context.fill();

  context.fillStyle = baseColor;
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  if (score > 0) {
    context.font = '700 30px system-ui, sans-serif';
    context.fillText(score.toFixed(1), 50, 36);
  } else {
    context.font = '700 26px system-ui, sans-serif';
    context.fillText('新', 50, 36);
  }

  return context.getImageData(0, 0, canvas.width, canvas.height);
};

export const installMapLocationLayer = (map: MapLibreMap) => {
  if (!map.getSource(MAP_LOCATION_SOURCE_ID)) {
    map.addSource(MAP_LOCATION_SOURCE_ID, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    });
  }
  if (!map.getLayer(MAP_LOCATION_LAYER_ID)) {
    map.addLayer({
      id: MAP_LOCATION_LAYER_ID,
      type: 'symbol',
      source: MAP_LOCATION_SOURCE_ID,
      layout: {
        'icon-image': ['get', 'imageId'],
        'icon-anchor': 'bottom',
        'icon-allow-overlap': true,
        'icon-ignore-placement': true,
        'icon-padding': 0,
        'icon-size': 1,
      },
    });
  }
};

export const setMapLocationLayerData = (map: MapLibreMap, locations: LocationItem[]) => {
  const features: Array<Feature<Point, LocationMarkerProperties>> = locations.map((loc) => {
    const imageId = markerImageId(loc.avg_score, loc.is_verified);
    if (!map.hasImage(imageId)) {
      map.addImage(imageId, createLocationMarkerImage(loc.avg_score, loc.is_verified), {
        pixelRatio: 2,
      });
    }
    return {
      type: 'Feature',
      id: String(loc.id),
      geometry: {
        type: 'Point',
        coordinates: [loc.longitude, loc.latitude],
      },
      properties: {
        locationId: loc.id,
        imageId,
        name: loc.name,
        avgScore: loc.avg_score,
        ratingCount: loc.rating_count,
      },
    };
  });

  const collection: FeatureCollection<Point, LocationMarkerProperties> = {
    type: 'FeatureCollection',
    features,
  };
  const source = map.getSource(MAP_LOCATION_SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(collection);
};

export const clearMapLocationLayer = (map: MapLibreMap | null) => {
  if (!map) return;
  const source = map.getSource(MAP_LOCATION_SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData({ type: 'FeatureCollection', features: [] });
};
