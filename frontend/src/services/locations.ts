import { api } from './api';

// A-05: 地点评分/评价/附近（backend/app/api/locations.py 契约对齐）

// 地点列表/详情响应
export interface LocationItem {
  id: number;
  school_id: number;
  name: string;
  description?: string | null;
  latitude: number;
  longitude: number;
  floor?: string | null;
  building?: string | null;
  post_count: number;
  is_verified: boolean;
  // REV-01: 评分汇总
  avg_score: number;
  rating_count: number;
  review_count: number;
  // 附近（可选，米）
  distance?: number | null;
}

export interface ReviewAuthor {
  id: number;
  nickname: string;
  avatar_url?: string | null;
  is_verified?: boolean;
}

export interface LocationReviewItem {
  id: number;
  location_id: number;
  user_id: number;
  score: number;
  content?: string | null;
  created_at: string;
  updated_at: string;
  author?: ReviewAuthor | null;
}

export interface LocationDetail {
  location: LocationItem;
  my_review?: LocationReviewItem | null;
}

export interface PaginatedReviews {
  items: LocationReviewItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface NearbyLocationsResponse {
  items: LocationItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReviewPayload {
  score: number;
  content?: string;
}

export const locationsApi = {
  /** 附近地点：以 lat/lng 为中心、radius 半径内按距离升序返回（含评分、距离） */
  getNearby: async (
    lat: number,
    lng: number,
    radius = 5000,
    page = 1,
    pageSize = 20
  ): Promise<NearbyLocationsResponse> => {
    const response = await api.get('/locations/nearby', {
      params: { lat, lng, radius, page, page_size: pageSize },
    });
    return response.data;
  },

  /** 地点详情（含评分汇总 + 我的评价） */
  getDetail: async (locationId: number): Promise<LocationDetail> => {
    const response = await api.get(`/locations/${locationId}`);
    return response.data;
  },

  /** 地点评价列表 */
  getReviews: async (
    locationId: number,
    page = 1,
    pageSize = 20
  ): Promise<PaginatedReviews> => {
    const response = await api.get(`/locations/${locationId}/reviews`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  /** 提交/更新本人评价（每地点每用户一条，重复提交=更新） */
  submitReview: async (
    locationId: number,
    payload: ReviewPayload
  ): Promise<LocationReviewItem> => {
    const response = await api.post(`/locations/${locationId}/reviews`, payload);
    return response.data;
  },

  /** 撤回本人评价 */
  withdrawReview: async (locationId: number): Promise<{ message: string }> => {
    const response = await api.delete(`/locations/${locationId}/reviews`);
    return response.data;
  },
};