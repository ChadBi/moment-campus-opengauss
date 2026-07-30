import { http } from './request'

export async function likePost(postId: number): Promise<{ liked: boolean; likes_count: number }> {
  return http.post(`/posts/${postId}/like`)
}

export async function getPostInteractions(postId: number): Promise<{
  is_liked: boolean
  likes_count: number
  comments_count: number
}> {
  return http.get(`/posts/${postId}/interactions`)
}

export async function createComment(postId: number, content: string, parentId?: number): Promise<any> {
  return http.post(`/posts/${postId}/comments`, { content, parent_id: parentId })
}

export async function listComments(postId: number, page?: number): Promise<any> {
  return http.get(`/posts/${postId}/comments?page=${page || 1}`)
}

export async function deleteComment(commentId: number): Promise<void> {
  return http.delete(`/comments/${commentId}`)
}

export async function validatePost(postId: number, validationType: 'confirmation' | 'refutation'): Promise<any> {
  return http.post(`/posts/${postId}/validations`, { validation_type: validationType })
}

export async function getValidationStats(postId: number): Promise<any> {
  return http.get(`/posts/${postId}/validation-stats`)
}

export async function reportPost(postId: number, reason: string, type: string): Promise<any> {
  return http.post(`/posts/${postId}/report`, { reason, report_type: type })
}
