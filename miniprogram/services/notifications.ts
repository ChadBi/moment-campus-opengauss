import { http } from './request'
import type { Notification, NotificationListResponse } from '../types'
import { normalizeNotification } from './normalize'
import { buildQuery } from '../utils/query'

export async function listNotifications(params?: {
  page?: number
  page_size?: number
  type?: string
}): Promise<NotificationListResponse> {
  const query = buildQuery(params)
  const raw = await http.get<any>(`/notifications${query ? `?${query}` : ''}`)
  const items = Array.isArray(raw?.items) ? raw.items : []
  return {
    items: items.map(normalizeNotification),
    total: Number(raw?.total || 0),
    page: Number(raw?.page || params?.page || 1),
    page_size: Number(raw?.page_size || params?.page_size || 20),
    has_more: raw?.has_more === true,
  }
}

export async function getUnreadCount(): Promise<{ unread_count: number; has_unread: boolean }> {
  return http.get('/notifications/unread-count')
}

export async function markAsRead(id: number): Promise<void> {
  return http.put(`/notifications/${id}/read`)
}

export async function markAllAsRead(): Promise<void> {
  return http.put('/notifications/read-all')
}
