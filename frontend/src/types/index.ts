// 用户类型
export interface User {
  id: number;
  email: string;
  nickname: string;
  avatar_url?: string;
  school_id: number;
  role: string;
  bio?: string;
  is_active: boolean;
  created_at: string;
}

// 帖子类型
export interface Post {
  id: number;
  title: string;
  content: string;
  category_id: number;
  location_id?: number;
  user_id: number;
  is_anonymous: boolean;
  status: string;
  view_count: number;
  like_count: number;
  comment_count: number;
  favorite_count: number;
  valid_count: number;
  invalid_count: number;
  created_at: string;
  updated_at: string;
  author?: {
    id: number;
    nickname: string;
    avatar_url?: string;
  };
  category?: {
    id: number;
    name: string;
  };
  location?: {
    id: number;
    name: string;
    latitude?: number;
    longitude?: number;
  };
  tags?: Array<{
    id: number;
    name: string;
  }>;
}

// 评论类型
export interface Comment {
  id: number;
  post_id: number;
  user_id: number;
  parent_id?: number;
  content: string;
  like_count: number;
  status: string;
  created_at: string;
  author?: {
    id: number;
    nickname: string;
    avatar_url?: string;
  };
  replies?: Comment[];
}

// 通知类型
export interface Notification {
  id: number;
  user_id: number;
  type: string;
  title: string;
  content: string;
  target_type?: string;
  target_id?: number;
  actor_id?: number;
  is_read: boolean;
  read_at?: string;
  created_at: string;
  actor?: {
    id: number;
    nickname: string;
    avatar_url?: string;
  };
}

// 分类类型
export interface Category {
  id: number;
  name: string;
  code: string;
  icon?: string;
  description?: string;
}

// 地点类型
export interface Location {
  id: number;
  school_id: number;
  name: string;
  description?: string;
  latitude: number;
  longitude: number;
  floor?: string;
  building?: string;
}

// 分页响应类型
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// API 响应类型
export interface ApiResponse<T> {
  data: T;
  message?: string;
}
