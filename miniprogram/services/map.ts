import { http } from './request'
import type { MapMarker } from '../types'

export async function getMapMarkers(params?: {
  school_id?: number
  category_id?: number
  status?: string
}): Promise<{ markers: MapMarker[] }> {
  const query = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) query.append(k, String(v))
    })
  }
  return http.get<{ markers: MapMarker[] }>(`/map/markers?${query.toString()}`)
}

export async function getMapCenter(schoolCode: string): Promise<{
  latitude: number
  longitude: number
  zoom: number
  name: string
}> {
  return http.get(`/map/center/${schoolCode}`)
}
