import { api } from './api';

// T-B-02: 2 类协同验证类型 + 旧 2 类别名
export type ValidationType =
  | 'confirmation'
  | 'refutation'
  // 旧 2 类别名（向后兼容）
  | 'valid'
  | 'invalid';

// T-B-04: 协同验证统计响应
export interface ValidationStats {
  post_id: number;
  // 旧 2 类兼容字段
  valid_count: number;
  invalid_count: number;
  // 2 类细分计数
  confirmation_count: number;
  refutation_count: number;
  total_count: number;
  validity_status: 'valid' | 'invalid' | 'uncertain';
  // 当前用户对此帖的验证类型（用于前端高亮按钮；null 表示未验证）
  user_validation_type: 'confirmation' | 'refutation' | null;
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

  // T-B-02: 2 类协同验证（证实/证伪 互斥可切换）
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
};
