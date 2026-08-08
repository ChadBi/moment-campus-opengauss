import { http } from './request'
import type { Post, PostListResponse, Topic, Category } from '../types'
import { normalizeCategory, normalizePost, normalizePostList, normalizeTopic } from './normalize'
import { buildQuery } from '../utils/query'

export async function listPosts(params?: {
  page?: number
  page_size?: number
  category_id?: number
  location_id?: number
  status?: string
  sort?: 'latest' | 'hottest' | 'active' | 'views'
  date_from?: string
  date_to?: string
  keyword?: string
}): Promise<PostListResponse> {
  const query = buildQuery(params)
  return normalizePostList(await http.get<any>(`/posts${query ? `?${query}` : ''}`))
}

/**
 * 校园热榜：近 7 天按浏览量排序的已发布帖子。
 * 时间窗口和排序都在后端完成，避免客户端只取一页后再排序造成榜单失真。
 */
export async function listHotPosts(days = 7, pageSize = 10): Promise<PostListResponse> {
  const date = new Date(Date.now() - days * 24 * 60 * 60 * 1000)
  const pad = (value: number) => String(value).padStart(2, '0')
  // Post.created_at 是后端无时区时间戳；传本地墙上时间，避免 asyncpg
  // 将带 Z 的 aware datetime 与 timestamp without time zone 比较时报 500。
  const dateFrom = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  return listPosts({
    page: 1,
    page_size: pageSize,
    status: 'published',
    sort: 'views',
    date_from: dateFrom,
  })
}

export async function getPost(id: number): Promise<Post> {
  return normalizePost(await http.get<any>(`/posts/${id}`))
}

export interface CreatePostRequest {
  title: string
  content: string
  category_id: number
  location_id?: number
  location_name?: string
  location_lat?: number
  location_lng?: number
  is_anonymous?: boolean
  contact_info?: string
  lost_type?: 'lost' | 'found' | string
  images?: Array<{ image_url: string; thumbnail_url?: string }>
  expire_at?: string
  status?: 'draft' | 'pending'
}

export async function createPost(data: CreatePostRequest): Promise<Post> {
  return normalizePost(await http.post<any>('/posts', data))
}

export async function updatePost(id: number, data: Partial<CreatePostRequest>): Promise<Post> {
  return normalizePost(await http.put<any>(`/posts/${id}`, data))
}

export type PostTransitionStatus = 'draft' | 'pending' | 'published' | 'expired' | 'conflict' | 'archived'

export async function transitionPost(id: number, targetStatus: PostTransitionStatus, reason?: string): Promise<Post> {
  await http.post(`/posts/${id}/transition`, {
    target_status: targetStatus,
    ...(reason ? { reason } : {}),
  })
  return getPost(id)
}

export interface AIPublishSuggestion {
  fallback?: boolean
  fallback_reason?: string
  suggestions?: {
    title?: string
    optimized_title?: string
    optimized_content?: string
    summary?: string
    category_id?: number
    tags?: string[]
    default_validity_days?: number
  }
  missing_info?: string[]
  sensitive_warnings?: string[]
}

export interface AIPublishSuggestRequest {
  title: string
  content: string
  category_id?: number
  location_id?: number
  contact_info?: string
  lost_type?: 'lost' | 'found' | string
  expire_at?: string
}

export async function suggestPost(request: AIPublishSuggestRequest): Promise<AIPublishSuggestion> {
  return http.post<AIPublishSuggestion>('/posts/ai-suggest', request)
}

export async function deletePost(id: number): Promise<void> {
  return http.delete(`/posts/${id}`)
}

export async function listMyPosts(status?: string): Promise<PostListResponse> {
  const query = status ? `?status=${status}` : ''
  return normalizePostList(await http.get<any>(`/users/me/posts${query}`))
}

export async function listTopics(): Promise<Topic[]> {
  const raw = await http.get<any>('/topics')
  const items = Array.isArray(raw) ? raw : (raw?.items || [])
  return items.map(normalizeTopic)
}

export async function getTopic(id: number): Promise<Topic & { posts: Post[] }> {
  const raw = await http.get<any>(`/topics/${id}`)
  return { ...normalizeTopic(raw), posts: (raw?.posts || []).map(normalizePost) }
}

export async function listCategories(): Promise<Category[]> {
  const raw = await http.get<any>('/categories')
  const items = Array.isArray(raw) ? raw : (raw?.items || [])
  return items.map(normalizeCategory)
}
