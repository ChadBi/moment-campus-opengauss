import { api } from './api';

// T-B-02: 5 类协同验证类型 + 旧 3 类别名
export type ValidationType =
  | 'confirmation'
  | 'refutation'
  | 'update'
  | 'expiration_report'
  | 'conflict_report'
  // 旧 3 类别名（向后兼容）
  | 'valid'
  | 'invalid'
  | 'uncertain';

// T-B-04: 协同验证统计响应
export interface ValidationStats {
  post_id: number;
  // 旧 3 类兼容字段
  valid_count: number;
  invalid_count: number;
  uncertain_count: number;
  // 5 类细分计数
  confirmation_count: number;
  refutation_count: number;
  update_count: number;
  expiration_report_count: number;
  conflict_report_count: number;
  total_count: number;
  validity_status: 'valid' | 'invalid' | 'uncertain';
}

// T-B-04: 状态流转响应
export interface PostTransitionResponse {
  post_id: number;
  previous_status: string;
  current_status: string;
  transitioned_at: string;
  transitioned_by: number;
}

export const interactionsApi = {
  likePost: async (postId: number): Promise<{ liked: boolean; like_count: number }> => {
    const response = await api.post(`/posts/${postId}/like`);
    return response.data;
  },

  favoritePost: async (postId: number): Promise<{ favorited: boolean; favorite_count: number }> => {
    const response = await api.post(`/posts/${postId}/favorite`);
    return response.data;
  },

  // T-B-02: 5 类协同验证（兼容旧 3 类别名）
  validatePost: async (
    postId: number,
    validationType: ValidationType,
    comment?: string
  ): Promise<{ id: number; validation_type: string; comment?: string }> => {
    const response = await api.post(`/posts/${postId}/validate`, {
      validation_type: validationType,
      comment,
    });
    return response.data;
  },

  // T-B-04: 获取协同验证统计
  getValidationStats: async (postId: number): Promise<ValidationStats> => {
    const response = await api.get(`/posts/${postId}/validation-stats`);
    return response.data;
  },

  // T-B-04: 状态流转
  transitionPost: async (
    postId: number,
    targetStatus: string,
    reason?: string
  ): Promise<PostTransitionResponse> => {
    const response = await api.post(`/posts/${postId}/transition`, {
      target_status: targetStatus,
      reason,
    });
    return response.data;
  },

  // T-B-04: 获取可流转状态列表
  getAllowedTransitions: async (
    postId: number
  ): Promise<{ post_id: number; current_status: string; allowed_transitions: string[] }> => {
    const response = await api.get(`/posts/${postId}/allowed-transitions`);
    return response.data;
  },

  reportPost: async (
    postId: number,
    reportType: string,
    description: string
  ): Promise<void> => {
    await api.post(`/posts/${postId}/report`, {
      report_type: reportType,
      description,
    });
  },

  getMyFavorites: async (page = 1, pageSize = 20): Promise<any> => {
    const response = await api.get('/users/me/favorites', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },
};
