import { api } from './api';

export interface MapMarker {
  post_id: number;
  title: string;
  latitude: number;
  longitude: number;
  location_name: string;
  category_id: number;
  cover_image?: string;
}

interface MapMarkersParams {
  north: number;
  south: number;
  east: number;
  west: number;
  category_id?: number;
}

export const mapApi = {
  getMapMarkers: async (params: MapMarkersParams): Promise<MapMarker[]> => {
    const response = await api.get('/map/markers', { params });
    return response.data;
  },
};
