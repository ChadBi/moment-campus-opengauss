export interface User {
  id: number
  email: string
  nickname: string
  avatar_url?: string
  bio?: string
  school_id: number
  is_active: boolean
  created_at: string
  // B-01: 校园身份认证
  campus_verified?: boolean
  student_id?: string
  campus_email?: string
  campus_verified_at?: string
}

export interface School {
  id: number
  code: string
  name: string
  short_name: string
  logo_url?: string
  description?: string
  location?: string
  latitude?: number
  longitude?: number
  map_zoom?: number
  is_active: boolean
}

export interface SchoolMembership {
  id: number
  user_id: number
  school_id: number
  role: 'member' | 'admin' | 'super_admin'
  status: 'active' | 'pending' | 'expired'
  is_default: boolean
  joined_at: string
}

export interface Post {
  id: number
  title: string
  content: string
  images?: string[]
  location_name?: string
  latitude?: number
  longitude?: number
  category_id: number
  category_name?: string
  status: 'draft' | 'pending' | 'published' | 'expired' | 'conflict' | 'archived'
  author_id: number
  author_nickname?: string
  author_avatar?: string
  // B-01: 作者是否已通过校园身份认证
  is_verified?: boolean
  school_id: number
  school_name?: string
  views_count: number
  likes_count: number
  comments_count: number
  validations_count: number
  refutations_count: number
  expires_at?: string
  created_at: string
  updated_at: string
  governance_status?: string
}

export interface PostListResponse {
  items: Post[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

// B-01: 评论（作者是否已认证）
export interface Comment {
  id: number
  post_id: number
  parent_id?: number
  user_id: number
  content: string
  author_nickname?: string
  author_avatar?: string
  is_verified?: boolean
  created_at: string
}

export interface Category {
  id: number
  name: string
  icon?: string
  description?: string
  sort_order: number
  is_active: boolean
}

export interface MapMarker {
  id: number
  post_id: number
  latitude: number
  longitude: number
  title: string
  content_snippet?: string
  category_name?: string
  status: string
  school_id: number
  created_at: string
}

export interface SearchResult {
  posts: Post[]
  total: number
  ai_analysis?: AISearchAnalysis
}

export interface AISearchAnalysis {
  intent: string
  keywords: string[]
  match_reasons: string[]
  suggested_filters?: Record<string, string>
}

export interface Notification {
  id: number
  type: 'comment' | 'like' | 'validation' | 'report' | 'system'
  title: string
  content: string
  is_read: boolean
  related_post_id?: number
  related_user_id?: number
  created_at: string
}

export interface NotificationListResponse {
  items: Notification[]
  total: number
  unread_count: number
}

export interface Topic {
  id: number
  title: string
  description?: string
  cover_image?: string
  post_count: number
  is_featured: boolean
  sort_order: number
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user: User
}

export interface WechatExchangeBoundResponse {
  status: 'authenticated'
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  user_id: number
  user: User
}

export interface WechatExchangeUnboundResponse {
  status: 'binding_required'
  binding_ticket: string
  expires_in: number
}

export type WechatExchangeResponse = WechatExchangeBoundResponse | WechatExchangeUnboundResponse

export interface ApiResponse<T = unknown> {
  code?: number
  message?: string
  data?: T
  detail?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export type SessionType = 'web' | 'miniprogram' | 'wechat'

export interface AuthSessionInfo {
  id: number
  session_type: SessionType
  client_ip?: string
  user_agent?: string
  device_id?: string
  device_info?: string
  expires_at: string
  last_active_at?: string
  created_at: string
  is_current: boolean
}

export interface IdentityInfo {
  id: number
  identity_type: string
  identity_key: string
  openid?: string
  unionid?: string
  created_at: string
  last_used_at?: string
}

// ============== 校园地点 / 评分评价（对齐 Web services/locations.ts） ==============

export interface LocationAuthor {
  id: number
  nickname: string
  avatar_url?: string
  is_verified: boolean
}

export interface LocationItem {
  id: number
  school_id: number
  name: string
  description?: string
  latitude: number
  longitude: number
  floor?: string
  building?: string
  post_count: number
  is_verified: boolean
  avg_score: number
  rating_count: number
  review_count: number
  distance?: number
}

export interface LocationReview {
  id: number
  location_id: number
  user_id: number
  score: number
  content?: string
  created_at: string
  updated_at: string
  author: LocationAuthor | null
}

export interface LocationDetail {
  location: LocationItem
  my_review: LocationReview | null
}

export interface LocationNearbyResponse {
  items: LocationItem[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface LocationReviewsResponse {
  items: LocationReview[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}
