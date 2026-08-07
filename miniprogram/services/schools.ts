import { http } from './request'
import type { School, SchoolMembership, User } from '../types'
import { normalizeMembership, normalizeSchool, normalizePostList } from './normalize'
import { buildQuery } from '../utils/query'

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
  const query = buildQuery(params)
  return normalizePostList(await http.get<any>(`/recommendations${query ? `?${query}` : ''}`))
}

export interface PublicSchoolSettings {
  allow_anonymous?: boolean
  allow_comments?: boolean
  publish_frequency?: number
  image_limit?: number
  default_validity_days?: number
  require_review?: boolean
}

export async function getSchoolSettings(): Promise<PublicSchoolSettings> {
  return http.get<PublicSchoolSettings>('/schools/current/settings')
}
