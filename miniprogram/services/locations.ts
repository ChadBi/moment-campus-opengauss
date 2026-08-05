import { http } from './request'
import type {
  LocationItem,
  LocationDetail,
  LocationReview,
  LocationNearbyResponse,
  LocationReviewsResponse,
} from '../types'

export async function getNearby(params: {
  lat: number
  lng: number
  radius?: number
  page?: number
  page_size?: number
}): Promise<LocationNearbyResponse> {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined) query.append(k, String(v))
  })
  return http.get<LocationNearbyResponse>(`/locations/nearby?${query.toString()}`)
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