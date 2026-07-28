import { api } from './api';
import type {
  ValidationType,
  ValidationAggregation,
  ValidationVote,
} from '../types';

// GOV-01: 协同治理服务（2 类投票：confirmation/refutation）
// 问题报告功能已移除，保留协同验证投票

export const governanceApi = {
  /**
   * 提交有效性投票
   * - 禁止作者给自己投票（后端返回 403）
   * - 每用户每帖一条，第二次提交替换原记录
   */
  votePost: async (
    postId: number,
    validationType: ValidationType,
    comment?: string
  ): Promise<ValidationVote> => {
    const response = await api.post(`/posts/${postId}/validations`, {
      validation_type: validationType,
      comment,
    });
    return response.data;
  },

  /** 聚合投票统计（confirmation_count/refutation_count + 最近记录） */
  getValidationAggregation: async (
    postId: number
  ): Promise<ValidationAggregation> => {
    const response = await api.get(`/posts/${postId}/validations`);
    return response.data;
  },
};
