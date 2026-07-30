import { http } from './request'
import type { School, SchoolMembership, User } from '../types'

export async function listSchools(): Promise<{
  schools: School[]
}> {
  return http.get('/schools')
}

export async function getCurrentSchool(): Promise<{ school: School }> {
  return http.get('/me/school')
}

export async function switchSchool(schoolId: number): Promise<{ school: School }> {
  return http.post('/me/school/switch', { school_id: schoolId })
}

export async function listMemberships(): Promise<{
  memberships: SchoolMembership[]
}> {
  return http.get('/me/schools')
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
  return http.get(`/recommendations?${query.toString()}`)
}
