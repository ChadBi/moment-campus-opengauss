import { http } from './request'
import type { SearchResult } from '../types'
import { normalizeSearchResult } from './normalize'
import { buildQuery } from '../utils/query'

export async function searchPosts(params: {
  keyword: string
  page?: number
  page_size?: number
  category_id?: number
}): Promise<SearchResult> {
  const query = buildQuery(params)
  return normalizeSearchResult(await http.get<any>(`/search${query ? `?${query}` : ''}`))
}

export async function aiSearch(params: {
  query: string
  page?: number
  page_size?: number
}): Promise<SearchResult> {
  return normalizeSearchResult(await http.post<any>('/search/ai', params, { timeout: 60000, loading: true }))
}

export async function getHotTags(): Promise<{ tags: string[] }> {
  return http.get('/search/hot-tags')
}
