import { api } from './api';
import type { PaginatedResponse } from '../types';

export interface UserStats {
  school_id: number;
  published_count: number;
  draft_count: number;
  pending_count: number;
  expired_count: number;
  conflict_count: number;
  archived_count: number;
  total_count: number;
  /** 贡献验证：已发布帖子收到的 confirmation 票数 */
  confirmation_count: number;
}

export interface ViewHistoryItem {
  id: number;
  post_id: number;
  title: string;
  status: string;
  cover_image?: string | null;
  category_name?: string | null;
  location_name?: string | null;
  viewed_at: string;
  created_at: string;
}

export const usersApi = {
  getCurrentUser: () => api.get('/users/me'),

  updateUser: (data: { nickname?: string; bio?: string; avatar_url?: string }) =>
    api.put('/users/me', data),

  uploadAvatar: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/users/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  getMyPosts: (page = 1, pageSize = 20) =>
    api.get('/users/me/posts', { params: { page, page_size: pageSize } }),

  /**
   * PRF-01.2: 我的真实统计（按当前学校过滤）
   * 替代前端用 6 次拉取计数拼凑的方式，一次性返回真实统计。
   */
  getMyStats: async (): Promise<UserStats> => {
    const response = await api.get('/users/me/stats');
    return response.data;
  },

  /**
   * PRF-01.3: 我的浏览历史（按当前学校过滤）
   */
  getMyViewHistory: async (
    page = 1,
    pageSize = 20
  ): Promise<PaginatedResponse<ViewHistoryItem>> => {
    const response = await api.get('/users/me/view-history', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  /**
   * PRF-01.3: 清除当前学校下的全部浏览历史
   */
  clearMyViewHistory: async (): Promise<{ message: string; deleted_count: number }> => {
    const response = await api.delete('/users/me/view-history');
    return response.data;
  },

  /**
   * PRF-01.3: 删除单条浏览历史
   */
  deleteViewHistoryItem: async (postId: number): Promise<void> => {
    await api.delete(`/users/me/view-history/${postId}`);
  },
};
