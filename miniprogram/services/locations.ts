import { http } from './request'
import type {
  LocationItem,
  LocationDetail,
  LocationReview,
  LocationReviewsResponse,
} from '../types'

export async function getLocations(): Promise<LocationItem[]> {
  return http.get<LocationItem[]>('/locations')
}

export async function getDetail(id: number): Promise<LocationDetail> {
  return http.get<LocationDetail>(`/locations/${id}`)
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
  return http.get<LocationReviewsResponse>(`/locations/${id}/reviews${qs ? `?${qs}` : ''}`)
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
