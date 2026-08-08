import { http } from './request'

export interface NotificationPreferences {
  instant_enabled: boolean
  interaction_enabled: boolean
  audit_enabled: boolean
  governance_enabled: boolean
  system_enabled: boolean
}

export async function getPreferences(): Promise<NotificationPreferences> {
  return http.get<NotificationPreferences>('/notifications/preferences')
}

export async function updatePreferences(
  data: NotificationPreferences
): Promise<NotificationPreferences> {
  return http.put<NotificationPreferences>('/notifications/preferences', data)
}
