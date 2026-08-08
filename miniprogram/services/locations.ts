import { http } from './request'
import type {
  LocationItem,
  LocationDetail,
  LocationReview,
  LocationReviewsResponse,
  LocationSummary,
} from '../types'
import { normalizeLocation, normalizeLocationSummary } from './normalize'
import { buildQuery } from '../utils/query'

export async function getLocations(schoolCode?: string): Promise<LocationItem[]> {
  const raw = await http.get<any>('/locations', undefined, schoolCode ? { schoolCode } : undefined)
  const items = Array.isArray(raw) ? raw : (Array.isArray(raw?.items) ? raw.items : [])
  return items.map(normalizeLocation)
}

export interface CreateLocationResult {
  location: LocationItem
  message: string
  needs_review: boolean
}

export async function createLocation(data: {
  name: string
  latitude: number
  longitude: number
  description?: string
  building?: string
  floor?: string
}): Promise<CreateLocationResult> {
  const raw = await http.post<any>('/locations', data)
  return {
    location: normalizeLocation(raw.location || raw),
    message: raw.message || '提交成功',
    needs_review: raw.needs_review !== false,
  }
}

export async function getDetail(id: number, schoolCode?: string): Promise<LocationDetail> {
  const raw = await http.get<any>(`/locations/${id}`, undefined, schoolCode ? { schoolCode } : undefined)
  return {
    location: normalizeLocation(raw?.location || raw),
    my_review: raw?.my_review || null,
    facts: Array.isArray(raw?.facts) ? raw.facts : [],
    summary: normalizeLocationSummary(raw?.summary || {
      status: 'insufficient',
      summary_text: null,
      confidence_level: 'insufficient',
      claims: [],
      conflicts: [],
      source_count: 0,
      generated_at: null,
      stale_at: null,
      sources: [],
    }),
  }
}

export async function getReviews(
  id: number,
  params?: { page?: number; page_size?: number }
): Promise<LocationReviewsResponse> {
  const qs = buildQuery(params)
  const raw = await http.get<any>(`/locations/${id}/reviews${qs ? `?${qs}` : ''}`)
  return {
    items: Array.isArray(raw?.items) ? raw.items : [],
    total: Number(raw?.total || 0),
    page: Number(raw?.page || params?.page || 1),
    page_size: Number(raw?.page_size || params?.page_size || 20),
    has_more: raw?.has_more === true,
  }
}

export async function getSummary(id: number): Promise<LocationSummary> {
  const raw = await http.get<any>(`/locations/${id}/summary`)
  return normalizeLocationSummary(raw)
}

export async function submitReview(
  id: number,
  data: { score: number; content?: string }
): Promise<LocationReview> {
  return http.post<LocationReview>(`/locations/${id}/reviews`, data)
}

export async function withdrawReview(id: number): Promise<{ message: string }> {
  return http.delete<{ message: string }>(`/locations/${id}/reviews`)
}

export async function submitFactProposal(
  id: number,
  data: { upserts?: Array<{ fact_key: string; label?: string; value: string; sort_order?: number; source_note?: string }>; remove_keys?: string[]; reason?: string },
): Promise<{ id: number; status: string }> {
  return http.post<{ id: number; status: string }>(`/locations/${id}/fact-proposals`, data)
}
