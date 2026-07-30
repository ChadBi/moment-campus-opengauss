import { http } from './request'
import type { Post, PostListResponse, Topic, Category } from '../types'

export async function listPosts(params?: {
  page?: number
  page_size?: number
  category_id?: number
  status?: string
  keyword?: string
}): Promise<PostListResponse> {
  const query = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) query.append(k, String(v))
    })
  }
  return http.get<PostListResponse>(`/posts?${query.toString()}`)
}

export async function getPost(id: number): Promise<Post> {
  return http.get<Post>(`/posts/${id}`)
}

export async function createPost(data: {
  title: string
  content: string
  category_id: number
  location_name?: string
  latitude?: number
  longitude?: number
  images?: string[]
  expires_at?: string
}): Promise<Post> {
  return http.post<Post>('/posts', data)
}

export async function updatePost(id: number, data: Partial<Post>): Promise<Post> {
  return http.put<Post>(`/posts/${id}`, data)
}

export async function deletePost(id: number): Promise<void> {
  return http.delete(`/posts/${id}`)
}

export async function listMyPosts(status?: string): Promise<PostListResponse> {
  const query = status ? `?status=${status}` : ''
  return http.get<PostListResponse>(`/users/me/posts${query}`)
}

export async function listTopics(): Promise<{ topics: Topic[] }> {
  return http.get('/topics')
}

export async function getTopic(id: number): Promise<Topic & { posts: Post[] }> {
  return http.get(`/topics/${id}`)
}

export async function listCategories(): Promise<{ categories: Category[] }> {
  return http.get('/categories')
}
