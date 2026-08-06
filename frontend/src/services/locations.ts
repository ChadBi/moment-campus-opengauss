import { api } from './api';

// A-05: 地点评分/评价/地点知识层（backend/app/api/locations.py 契约对齐）

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
}

export interface LocationFactItem {
  id: number;
  location_id: number;
  fact_key: string;
  label: string;
  value: string;
  sort_order: number;
  source_note?: string | null;
  approved_at?: string | null;
  updated_at: string;
}

export interface LocationSummarySource {
  source_type: 'post' | 'review' | 'fact';
  source_id: number;
  title?: string | null;
  snippet?: string | null;
  created_at?: string | null;
  author_name?: string | null;
  score?: number | null;
  confirmation_count?: number;
  refutation_count?: number;
}

export interface LocationSummaryClaim {
  claim_id: string;
  text: string;
  confidence_level: string;
  source_refs: Array<{ source_type: string; source_id: number }>;
}

export interface LocationSummary {
  id?: number | null;
  version?: number | null;
  status: string;
  summary_text?: string | null;
  confidence_level: string;
  claims: LocationSummaryClaim[];
  conflicts: Array<{ text: string; source_refs: Array<{ source_type: string; source_id: number }> }>;
  source_count: number;
  generated_at?: string | null;
  stale_at?: string | null;
  sources: LocationSummarySource[];
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
  facts: LocationFactItem[];
  summary: LocationSummary;
}

export interface PaginatedReviews {
  items: LocationReviewItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReviewPayload {
  score: number;
  content?: string;
}

export interface LocationFactProposalPayload {
  upserts?: Array<{
    fact_key: string;
    label?: string;
    value: string;
    sort_order?: number;
    source_note?: string;
  }>;
  remove_keys?: string[];
  reason?: string;
}

export const locationsApi = {
  /** 当前学校全部地点（含评分汇总），供地图/地点页使用 */
  getLocations: async (): Promise<LocationItem[]> => {
    const response = await api.get('/locations');
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

  /** 提交地点稳定资料提议（仅校园认证用户） */
  submitFactProposal: async (
    locationId: number,
    payload: LocationFactProposalPayload,
  ): Promise<{ id: number; status: string }> => {
    const response = await api.post(`/locations/${locationId}/fact-proposals`, payload);
    return response.data;
  },

  /** 查看地点 AI 摘要与可追溯来源 */
  getSummary: async (locationId: number): Promise<LocationSummary> => {
    const response = await api.get(`/locations/${locationId}/summary`);
    return response.data;
  },

  /** 撤回本人评价 */
  withdrawReview: async (locationId: number): Promise<{ message: string }> => {
    const response = await api.delete(`/locations/${locationId}/reviews`);
    return response.data;
  },
};
