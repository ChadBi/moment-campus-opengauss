import { api } from './api';

interface Notification {
  id: number;
  type: string;
  title: string;
  content: string;
  target_type?: string;
  target_id?: number;
  actor_id?: number;
  is_read: boolean;
  created_at: string;
  actor?: {
    id: number;
    nickname: string;
    avatar_url?: string;
  };
}

interface NotificationListResponse {
  items: Notification[];
  total: number;
  page: number;
  page_size: number;
}

interface UnreadCountResponse {
  unread_count: number;
  has_unread: boolean;
}

// UX-01.5: 通知偏好（6 类开关）
export interface NotificationPreference {
  instant_enabled: boolean;
  subscription_enabled: boolean;
  interaction_enabled: boolean;
  audit_enabled: boolean;
  governance_enabled: boolean;
  system_enabled: boolean;
}

export type NotificationPreferenceUpdate = Partial<NotificationPreference>;

export const notificationsApi = {
  getNotifications: async (
    page = 1,
    pageSize = 20,
    type?: string
  ): Promise<NotificationListResponse> => {
    const response = await api.get('/notifications', {
      params: { page, page_size: pageSize, ...(type ? { type } : {}) },
    });
    return response.data;
  },

  markAsRead: async (notificationId: number): Promise<void> => {
    await api.put(`/notifications/${notificationId}/read`);
  },

  markAllAsRead: async (): Promise<void> => {
    await api.put('/notifications/read-all');
  },

  /**
   * PRF-01.2: 未读通知数量（页头角标实时显示）
   * 通知按 user_id 隔离，不区分学校，跨校通知聚合到该用户的通知中心。
   */
  getUnreadCount: async (): Promise<UnreadCountResponse> => {
    const response = await api.get('/notifications/unread-count');
    return response.data;
  },

  /**
   * UX-01.5: 获取当前用户通知偏好
   * 首次访问后端自动 upsert 默认偏好（全部开启）。
   * 通知偏好按 user_id 隔离，不区分学校。
   */
  getPreferences: async (): Promise<NotificationPreference> => {
    const response = await api.get('/notifications/preferences');
    return response.data;
  },

  /**
   * UX-01.5: 更新当前用户通知偏好
   * 仅传需要更新的字段；安全账号通知（system/audit）不可全关，
   * 若 system/audit/instant 全关，后端返回 400 拒绝。
   */
  updatePreferences: async (
    payload: NotificationPreferenceUpdate
  ): Promise<NotificationPreference> => {
    const response = await api.put('/notifications/preferences', payload);
    return response.data;
  },
};
