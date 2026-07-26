import { api } from './api';
import type {
  ValidationType,
  ValidationStats,
  PostTransitionResponse,
  LikeResponse,
  ReportType,
} from '../types';

// FND-01.3: 类型从 types/index.ts 统一导出，消除手写重复
export type { ValidationType, ValidationStats, PostTransitionResponse };

export const interactionsApi = {
  // FND-01.1: 点赞响应统一为 is_liked
  likePost: async (postId: number): Promise<LikeResponse> => {
    const response = await api.post(`/posts/${postId}/like`);
    return response.data;
  },

  // FND-01.1: 协同验证（5 类类型，当前 UI 仅展示 confirmation/refutation）
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

  // FND-01.1: 举报类型统一为 5 类枚举
  reportPost: async (
    postId: number,
    reportType: ReportType,
    description: string
  ): Promise<void> => {
    await api.post(`/posts/${postId}/report`, {
      report_type: reportType,
      description,
    });
  },
};
