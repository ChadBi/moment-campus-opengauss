import { http } from './request'
import type {
  LocationItem,
  LocationDetail,
  LocationReview,
  LocationReviewsResponse,
} from '../types'
import { normalizeLocation } from './normalize'

export async function getLocations(): Promise<LocationItem[]> {
  const raw = await http.get<any>('/locations')
  const items = Array.isArray(raw) ? raw : (Array.isArray(raw?.items) ? raw.items : [])
  return items.map(normalizeLocation)
}

export async function getDetail(id: number): Promise<LocationDetail> {
  const raw = await http.get<any>(`/locations/${id}`)
  return {
    location: normalizeLocation(raw?.location || raw),
    my_review: raw?.my_review || null,
    facts: Array.isArray(raw?.facts) ? raw.facts : [],
    summary: raw?.summary || {
      status: 'pending_review',
      summary_text: null,
      confidence_level: 'insufficient',
      claims: [],
      conflicts: [],
      source_count: 0,
      generated_at: null,
      stale_at: null,
      sources: [],
    },
  }
}

export async function getReviews(
  id: number,
  params?: { page?: number; page_size?: number }
): Promise<LocationReviewsResponse> {
  const query = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) query.append(k, String(v))
    })
  }
  const qs = query.toString()
  const raw = await http.get<any>(`/locations/${id}/reviews${qs ? `?${qs}` : ''}`)
  return {
    items: Array.isArray(raw?.items) ? raw.items : [],
    total: Number(raw?.total || 0),
    page: Number(raw?.page || params?.page || 1),
    page_size: Number(raw?.page_size || params?.page_size || 20),
    has_more: raw?.has_more === true,
  }
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
