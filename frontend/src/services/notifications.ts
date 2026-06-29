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

export const notificationsApi = {
  getNotifications: async (page = 1, pageSize = 20): Promise<NotificationListResponse> => {
    const response = await api.get('/notifications', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  markAsRead: async (notificationId: number): Promise<void> => {
    await api.put(`/notifications/${notificationId}/read`);
  },

  markAllAsRead: async (): Promise<void> => {
    await api.put('/notifications/read-all');
  },
};
