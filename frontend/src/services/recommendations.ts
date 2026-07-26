import { api } from './api';
import type {
  RecommendationResponse,
  RecommendationPreference,
} from '../types';

/**
 * REC-01: 推荐服务
 *
 * - GET /recommendations              首页"为你推荐"
 * - GET /users/me/recommendation-preferences   获取个性化开关
 * - PUT /users/me/recommendation-preferences   更新个性化开关（关闭时清除浏览历史）
 * - DELETE /users/me/recommendation-history    清除推荐画像历史（浏览+搜索）
 */
export const recommendationsApi = {
  /**
   * REC-01.1: 获取"为你推荐"列表
   *
   * - 登录用户开启个性化且历史足够：基于浏览/搜索/订阅/新鲜度/验证结果打分
   * - 游客 / 关闭个性化 / 历史不足：冷启动（本校热门 + 最新 + 管理员推荐）
   * - 每条结果附带推荐原因
   */
  getRecommendations: async (
    page = 1,
    pageSize = 10
  ): Promise<RecommendationResponse> => {
    const response = await api.get('/recommendations', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  /**
   * REC-01.2: 获取推荐隐私偏好
   *
   * 首次访问自动 upsert 默认行（personalization_enabled=true）。
   */
  getMyPreferences: async (): Promise<RecommendationPreference> => {
    const response = await api.get('/users/me/recommendation-preferences');
    return response.data;
  },

  /**
   * REC-01.2: 更新推荐隐私偏好
   *
   * - 关闭个性化：同步清除当前用户在所有学校的浏览历史
   * - 开启个性化：不影响历史数据，重新开始积累画像
   */
  updateMyPreferences: async (
    personalizationEnabled: boolean
  ): Promise<RecommendationPreference> => {
    const response = await api.put('/users/me/recommendation-preferences', {
      personalization_enabled: personalizationEnabled,
    });
    return response.data;
  },

  /**
   * REC-01.2: 清除推荐画像历史（浏览 + 搜索）
   *
   * - 浏览历史按当前学校过滤清除
   * - 搜索历史不区分学校，全部清除
   * - 清除后画像重建从零开始，下次推荐走冷启动
   */
  clearMyHistory: async (): Promise<{
    message: string;
    data?: { browse_deleted: number; search_deleted: number; school_id: number };
  }> => {
    const response = await api.delete('/users/me/recommendation-history');
    return response.data;
  },
};
