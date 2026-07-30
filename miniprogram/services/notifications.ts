import { http } from './request'
import type { Notification, NotificationListResponse } from '../types'

export async function listNotifications(params?: {
  page?: number
  page_size?: number
  type?: string
}): Promise<NotificationListResponse> {
  const query = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) query.append(k, String(v))
    })
  }
  return http.get<NotificationListResponse>(`/notifications?${query.toString()}`)
}

export async function getUnreadCount(): Promise<{ count: number }> {
  return http.get('/notifications/unread-count')
}

export async function markAsRead(id: number): Promise<void> {
  return http.put(`/notifications/${id}/read`)
}

export async function markAllAsRead(): Promise<void> {
  return http.post('/notifications/mark-all-read')
}

export async function deleteNotification(id: number): Promise<void> {
  return http.delete(`/notifications/${id}`)
}
