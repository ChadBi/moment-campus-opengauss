import { http } from './request'
import type { School, SchoolMembership, User } from '../types'
import { normalizeMembership, normalizeSchool, normalizePostList } from './normalize'

export async function listSchools(): Promise<School[]> {
  const raw = await http.get<any>('/schools')
  const items = Array.isArray(raw) ? raw : (Array.isArray(raw?.items) ? raw.items : [])
  return items.map((item: any) => normalizeSchool(item))
}

export async function getCurrentSchool(schoolCode?: string): Promise<School> {
  const raw = await http.get<any>('/schools/current', undefined, schoolCode ? { schoolCode } : undefined)
  return normalizeSchool(raw?.school || raw)
}

export async function joinSchool(code: string): Promise<any> {
  return http.post(`/schools/${encodeURIComponent(code)}/join`, undefined, { schoolCode: code })
}

export async function listMemberships(): Promise<SchoolMembership[]> {
  const raw = await http.get<any>('/me/memberships')
  const items = Array.isArray(raw) ? raw : (Array.isArray(raw?.items) ? raw.items : [])
  return items.map((item: any) => normalizeMembership(item))
}

export async function getUserProfile(): Promise<User> {
  return http.get('/users/me')
}

export async function updateUserProfile(data: Partial<User>): Promise<User> {
  return http.put('/users/me', data)
}

export async function getRecommendations(params?: {
  page?: number
  page_size?: number
}): Promise<any> {
  const query = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) query.append(k, String(v))
    })
  }
  return normalizePostList(await http.get<any>(`/recommendations?${query.toString()}`))
}
