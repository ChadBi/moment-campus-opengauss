export interface User {
  id: number
  email: string
  nickname: string
  avatar_url?: string
  bio?: string
  school_id: number
  is_active: boolean
  created_at: string
  campus_verified?: boolean
  campus_verified_at?: string
}

export interface School {
  id: number
  code: string
  name: string
  logo_url?: string
  description?: string
  province?: string
  city?: string
  center_lat: number
  center_lng: number
  map_zoom: number
  is_active: boolean
  domains?: string[]
}

export interface SchoolMembership {
  id: number
  user_id: number
  school_id: number
  school?: School
  role: 'member' | 'admin' | 'super_admin'
  status: 'active' | 'pending' | 'expired'
  is_default?: boolean
  joined_at: string
}

export interface PostImage {
  image_url: string
  thumbnail_url?: string
}

export interface PostAuthor {
  id: number
  nickname: string
  avatar_url?: string
  is_verified?: boolean
}

export interface PostCategory {
  id: number
  name: string
  code?: string
  icon?: string
}

export interface PostLocation {
  id: number
  name: string
  latitude: number
  longitude: number
  building?: string
  floor?: string
  is_verified?: boolean
}

export interface PostGovernance {
  status?: string
  valid_count: number
  invalid_count: number
  my_validation?: 'confirmation' | 'refutation' | null
}

export interface Post {
  id: number
  title: string
  content: string
  cover_image?: string
  images: PostImage[]
  location_id?: number | null
  location_name?: string
  location_lat?: number
  location_lng?: number
  category_id: number
  status: 'draft' | 'pending' | 'published' | 'expired' | 'conflict' | 'archived'
  is_anonymous?: boolean
  contact_info?: string | null
  lost_type?: string | null
  school_id: number
  school_name?: string
  author: PostAuthor
  category?: PostCategory | null
  location?: PostLocation | null
  like_count: number
  comment_count: number
  view_count: number
  valid_count: number
  invalid_count: number
  expire_at?: string | null
  created_at: string
  updated_at: string
  is_liked?: boolean
  governance?: PostGovernance | null
  is_verified?: boolean
  recommend_reason?: string
  recommend_score?: number
}

export interface PostListResponse {
  items: Post[]
  total: number
  page: number
  page_size: number
  has_more: boolean
  total_pages?: number
  mode?: {
    personalized?: boolean
    reason_code?: string
  } | null
}

export interface CommentAuthor {
  id: number
  nickname: string
  avatar_url?: string
  is_verified?: boolean
}

export interface Comment {
  id: number
  post_id: number
  parent_id?: number | null
  reply_to_user_id?: number | null
  reply_to_user?: CommentAuthor | null
  user_id: number
  content: string
  author?: CommentAuthor | null
  replies?: Comment[]
  reply_count?: number
  created_at: string
  updated_at?: string
}

export interface Category {
  id: number
  name: string
  code?: string
  icon?: string
  description?: string
  sort_order: number
  is_active: boolean
}

/** 微信地图 marker 的渲染结构；地点数据本身使用 LocationItem。 */
export interface MapMarker {
  id: number
  latitude: number
  longitude: number
  title: string
  location_id: number
  is_verified?: boolean
  iconPath?: string
  selectedIconPath?: string
}

export interface SearchResult {
  items: Post[]
  total: number
  page: number
  page_size: number
  has_more: boolean
  match_reasons?: Record<string, string[]>
  scores?: Record<string, number>
  fallback?: boolean
  fallback_reason?: string
  intent?: string
}

export interface Notification {
  id: number
  type: 'comment' | 'like' | 'validation' | 'report' | 'system' | string
  title: string
  content: string
  target_type?: 'post' | 'comment' | 'location' | 'topic' | 'system' | string
  target_id?: number | null
  actor_name?: string
  actor_avatar?: string
  is_read: boolean
  created_at: string
}

export interface NotificationListResponse {
  items: Notification[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface Topic {
  id: number
  title: string
  description?: string
  cover_url?: string
  post_count: number
  view_count: number
  is_featured?: boolean
  sort_order?: number
}

export interface Subscription {
  id: number
  target_type: 'category' | 'location'
  target_id: number
  target_name?: string
  created_at: string
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
  total_pages?: number
}

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
}

export interface LocationFact {
  id: number
  location_id: number
  fact_key: string
  label: string
  value: string
  sort_order: number
  source_note?: string
  approved_at?: string
  updated_at: string
}

export interface LocationSummarySource {
  source_type: string
  source_id: number
  title?: string
  snippet?: string
  created_at?: string
  author_name?: string
  score?: number
  confirmation_count?: number
  refutation_count?: number
}

export interface LocationSummaryClaim {
  claim_id: string
  text: string
  confidence_level: string
  source_refs: Array<{ source_type: string; source_id: number }>
}

export interface LocationSummaryConflict {
  text: string
  source_refs: Array<{ source_type: string; source_id: number }>
}

export interface LocationSummary {
  id?: number | null
  version?: number | null
  status: 'pending_review' | 'approved' | 'rejected' | 'failed' | 'archived' | string
  summary_text?: string | null
  confidence_level: string
  claims: LocationSummaryClaim[]
  conflicts: LocationSummaryConflict[]
  source_count: number
  generated_at?: string | null
  stale_at?: string | null
  sources: LocationSummarySource[]
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
  facts: LocationFact[]
  summary: LocationSummary
}

export interface MapLocationPanel {
  location: LocationItem
  scoreText: string
  /**
   * 当前地点查询实际返回的已发布帖子总数。
   * 不直接使用 Location.post_count：该字段是地点缓存字段，可能尚未随帖子状态变化刷新。
   */
  relatedPostCount: number
  detail?: LocationDetail
  relatedPosts: Post[]
  loading: boolean
  postsLoading: boolean
  reviewsLoading?: boolean
  error?: string
  postsError?: string
}

export interface LocationReviewsResponse {
  items: LocationReview[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}
