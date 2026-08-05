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

  /**
   * ACC-01.4: 标记完成首次使用引导
   * FirstUseGuide 完成/跳过时调用，后端将 onboarding_completed 设为 True
   */
  completeOnboarding: async (): Promise<void> => {
    await api.put('/users/me/onboarding');
  },

  uploadAvatar: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/users/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

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

  /**
   * B-01: 发起校园身份认证（提交学号 + 校园邮箱）
   * 本地开发环境响应中携带 code / verify_link（未配置邮件服务），便于演示闭环。
   */
  sendCampusVerify: async (data: {
    student_id: string;
    campus_email: string;
  }): Promise<{ message: string; code?: string; verify_link?: string }> => {
    const response = await api.post('/users/me/verify-campus/send', data);
    return response.data;
  },

  /**
   * B-01: 确认校园身份认证（学号 + 校园邮箱 + token 或 code 二选一）
   */
  confirmCampusVerify: async (data: {
    student_id: string;
    campus_email: string;
    token?: string;
    code?: string;
  }): Promise<{ message: string; campus_verified: boolean }> => {
    const response = await api.post('/users/me/verify-campus/confirm', data);
    return response.data;
  },
};
