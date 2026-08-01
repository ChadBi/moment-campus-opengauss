import type { Feature, FeatureCollection, Point } from 'geojson';
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl';
import type { MapMarker } from '../services/map';
import { getCategoryVisual } from './categoryVisual';

export const MAP_MARKER_SOURCE_ID = 'campus-post-markers';
export const MAP_MARKER_LAYER_ID = 'campus-post-marker-symbols';

export const MAP_MARKER_PATH =
  'M 50 100 C 46 91 10 64 10 37 C 10 16.6 27.9 0 50 0 C 72.1 0 90 16.6 90 37 C 90 64 54 91 50 100 Z';

interface MarkerProperties {
  groupKey: string;
  imageId: string;
  count: number;
  firstPostId: number;
  locationName: string;
}

export interface MapMarkerGroup {
  key: string;
  markers: MapMarker[];
  longitude: number;
  latitude: number;
}

export interface MapMarkerLayerData {
  groups: Map<string, MapMarkerGroup>;
  posts: Map<number, { marker: MapMarker; groupKey: string }>;
}

const EMPTY_COLLECTION: FeatureCollection<Point, MarkerProperties> = {
  type: 'FeatureCollection',
  features: [],
};

const markerImageId = (color: string, count: number, size: number) =>
  `campus-pin-${color.replace('#', '').toLowerCase()}-${count}-${size}`;

/**
 * Rasterize the deterministic SVG path into a MapLibre sprite. The sprite and
 * AMap tiles are then painted by the same WebGL canvas, avoiding a second DOM
 * compositor transform during animated/fractional zooms.
 */
const createMarkerImage = (color: string, count: number, size: number): ImageData => {
  const pixelRatio = 2;
  const canvas = document.createElement('canvas');
  canvas.width = size * pixelRatio;
  canvas.height = size * pixelRatio;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('2D canvas is unavailable for map marker sprite');

  context.scale((size * pixelRatio) / 100, (size * pixelRatio) / 100);
  context.fillStyle = color;
  context.fill(new Path2D(MAP_MARKER_PATH));

  context.fillStyle = '#ffffff';
  if (count > 1) {
    context.font = `700 ${count >= 100 ? 27 : count >= 10 ? 31 : 36}px system-ui, sans-serif`;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(String(count), 50, 36);
  } else {
    context.beginPath();
    context.arc(50, 35, 18, 0, Math.PI * 2);
    context.fill();
  }

  // getImageData is deliberately called after applying the drawing transform:
  // it reads the complete physical-pixel backing store, while addImage's
  // pixelRatio maps it back to the requested 28/36 CSS-pixel geometry.
  return context.getImageData(0, 0, canvas.width, canvas.height);
};

export const installMapMarkerLayer = (map: MapLibreMap) => {
  if (!map.getSource(MAP_MARKER_SOURCE_ID)) {
    map.addSource(MAP_MARKER_SOURCE_ID, {
      type: 'geojson',
      data: EMPTY_COLLECTION,
    });
  }
  if (!map.getLayer(MAP_MARKER_LAYER_ID)) {
    map.addLayer({
      id: MAP_MARKER_LAYER_ID,
      type: 'symbol',
      source: MAP_MARKER_SOURCE_ID,
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

export const setMapMarkerLayerData = (
  map: MapLibreMap,
  markers: MapMarker[],
): MapMarkerLayerData => {
  const groups = new Map<string, MapMarkerGroup>();
  const posts = new Map<number, { marker: MapMarker; groupKey: string }>();

  for (const marker of markers) {
    const key = `${marker.longitude.toFixed(6)},${marker.latitude.toFixed(6)}`;
    const existing = groups.get(key);
    if (existing) {
      existing.markers.push(marker);
    } else {
      groups.set(key, {
        key,
        markers: [marker],
        longitude: marker.longitude,
        latitude: marker.latitude,
      });
    }
  }

  const features: Array<Feature<Point, MarkerProperties>> = [];
  for (const group of groups.values()) {
    const first = group.markers[0];
    const count = group.markers.length;
    const size = count > 1 ? 36 : 28;
    const color = getCategoryVisual(first.category_code).marker;
    const imageId = markerImageId(color, count, size);
    if (!map.hasImage(imageId)) {
      map.addImage(imageId, createMarkerImage(color, count, size), { pixelRatio: 2 });
    }

    features.push({
      type: 'Feature',
      id: group.key,
      geometry: {
        type: 'Point',
        coordinates: [group.longitude, group.latitude],
      },
      properties: {
        groupKey: group.key,
        imageId,
        count,
        firstPostId: first.post_id,
        locationName: first.location_name || '',
      },
    });
    for (const marker of group.markers) {
      posts.set(marker.post_id, { marker, groupKey: group.key });
    }
  }

  const collection: FeatureCollection<Point, MarkerProperties> = {
    type: 'FeatureCollection',
    features,
  };
  const source = map.getSource(MAP_MARKER_SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(collection);
  return { groups, posts };
};

export const clearMapMarkerLayer = (map: MapLibreMap | null) => {
  if (!map) return;
  const source = map.getSource(MAP_MARKER_SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(EMPTY_COLLECTION);
};

export const setHoveredMapMarker = (map: MapLibreMap, groupKey: string | null) => {
  map.setLayoutProperty(
    MAP_MARKER_LAYER_ID,
    'icon-size',
    groupKey
      ? ['case', ['==', ['get', 'groupKey'], groupKey], 1.2, 1]
      : 1,
  );
};
