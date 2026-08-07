import { http } from './request'
import type { SearchResult } from '../types'
import { normalizeSearchResult } from './normalize'

export async function searchPosts(params: {
  keyword: string
  page?: number
  page_size?: number
  category_id?: number
}): Promise<SearchResult> {
  const query = new URLSearchParams()
  query.append('keyword', params.keyword)
  if (params.page) query.append('page', String(params.page))
  if (params.page_size) query.append('page_size', String(params.page_size))
  if (params.category_id) query.append('category_id', String(params.category_id))
  return normalizeSearchResult(await http.get<any>(`/search?${query.toString()}`))
}

export async function aiSearch(params: {
  query: string
  page?: number
  page_size?: number
}): Promise<SearchResult> {
  return normalizeSearchResult(await http.post<any>('/search/ai', params))
}

export async function getHotTags(): Promise<{ tags: string[] }> {
  return http.get('/search/hot-tags')
}
