import { http } from './request'

export interface Feedback {
  id: number
  user_id: number
  school_id: number
  feedback_type: string
  content: string
  contact: string | null
  status: string
  remark: string | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}

export interface FeedbackListResponse {
  items: Feedback[]
  page: number
  page_size: number
  total: number
  total_pages: number
  has_more: boolean
}

export async function submitFeedback(data: {
  feedback_type: string
  content: string
  contact?: string
}): Promise<Feedback> {
  return http.post<Feedback>('/feedback', data)
}

export async function getMyFeedbacks(page: number, pageSize = 10): Promise<FeedbackListResponse> {
  return http.get<FeedbackListResponse>('/feedback', { page, page_size: pageSize })
}

/** 管理端更新反馈状态（通常由管理端调用，小程序侧备用） */
export async function updateFeedback(
  id: number,
  data: { status?: string; remark?: string }
): Promise<Feedback> {
  return http.patch<Feedback>(`/feedback/${id}`, data)
}