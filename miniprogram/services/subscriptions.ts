import { http } from './request'
import { normalizeSubscription } from './normalize'
import type { Subscription } from '../types'

export async function listSubscriptions(params?: { target_type?: string }): Promise<Subscription[]> {
  const query = new URLSearchParams()
  if (params?.target_type) query.set('target_type', params.target_type)
  const raw = await http.get<any>(`/subscriptions${query.toString() ? `?${query}` : ''}`)
  const items = Array.isArray(raw) ? raw : (raw?.items || [])
  return items.map(normalizeSubscription)
}

export async function createSubscription(target_type: 'category' | 'location' | 'topic', target_id: number): Promise<Subscription> {
  const raw = await http.post<any>('/subscriptions', { target_type, target_id })
  return normalizeSubscription(raw?.subscription || raw)
}

export async function removeSubscription(id: number): Promise<void> {
  await http.delete(`/subscriptions/${id}`)
}

export async function checkSubscription(target_type: 'category' | 'location' | 'topic', target_id: number): Promise<{ subscribed: boolean; subscription_id?: number }> {
  return http.get(`/subscriptions/check?target_type=${target_type}&target_id=${target_id}`)
}
