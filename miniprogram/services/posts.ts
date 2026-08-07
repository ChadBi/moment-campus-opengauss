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
  sort?: 'latest' | 'hottest' | 'active'
  keyword?: string
}): Promise<PostListResponse> {
  const query = buildQuery(params)
  return normalizePostList(await http.get<any>(`/posts${query ? `?${query}` : ''}`))
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
    summary?: string
    category_id?: number
    tags?: string[]
    default_validity_days?: number
  }
  missing_info?: string[]
  sensitive_warnings?: string[]
}

export async function suggestPost(title: string, content: string): Promise<AIPublishSuggestion> {
  return http.post<AIPublishSuggestion>('/posts/ai-suggest', { title, content })
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
