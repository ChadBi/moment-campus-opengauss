import { http } from './request'
import { normalizeComment } from './normalize'
import type { Comment } from '../types'

export async function likePost(postId: number): Promise<{ is_liked: boolean; like_count: number }> {
  const raw = await http.post<any>(`/posts/${postId}/like`)
  return {
    is_liked: raw?.is_liked === true,
    like_count: Number(raw?.like_count || 0),
  }
}

export async function createComment(postId: number, content: string, parentId?: number, replyToUserId?: number): Promise<Comment> {
  return normalizeComment(await http.post<any>(`/posts/${postId}/comments`, {
    content,
    parent_id: parentId,
    reply_to_user_id: replyToUserId,
  }))
}

export async function listComments(postId: number, page?: number): Promise<{ items: Comment[]; total: number; page: number; page_size: number; has_more: boolean }> {
  const raw = await http.get<any>(`/posts/${postId}/comments?page=${page || 1}&page_size=20`)
  return {
    items: (raw?.items || []).map(normalizeComment),
    total: Number(raw?.total || 0),
    page: Number(raw?.page || page || 1),
    page_size: Number(raw?.page_size || 20),
    has_more: raw?.has_more === true,
  }
}

export async function deleteComment(commentId: number): Promise<void> {
  return http.delete(`/comments/${commentId}`)
}

export async function validatePost(postId: number, validationType: 'confirmation' | 'refutation'): Promise<any> {
  return http.post(`/posts/${postId}/validate`, { validation_type: validationType })
}

export async function getValidationStats(postId: number): Promise<any> {
  return http.get(`/posts/${postId}/validation-stats`)
}

export async function reportPost(postId: number, reason: string, type: string): Promise<any> {
  return http.post(`/posts/${postId}/report`, { report_type: type, description: reason })
}
