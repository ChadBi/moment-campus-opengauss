import { api } from './api';

interface Post {
  id: number;
  title: string;
  content: string;
  category_id: number;
  location_id: number;
  user_id: number;
  post_type_id: number;
  is_anonymous: boolean;
  status: string;
  view_count: number;
  like_count: number;
  comment_count: number;
  valid_count: number;
  invalid_count: number;
  created_at: string;
  updated_at: string;
  user?: {
    id: number;
    nickname: string;
    avatar_url?: string;
  };
  category?: {
    id: number;
    name: string;
    icon: string;
  };
  location?: {
    id: number;
    name: string;
  };
  tags?: Array<{
    id: number;
    name: string;
  }>;
  images?: Array<{
    id: number;
    image_url: string;
    thumbnail_url?: string;
  }>;
}

interface PostListResponse {
  items: Post[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface CreatePostRequest {
  title: string;
  content: string;
  category_id: number;
  location_id?: number;
  // 地图点选发帖：直接传地点名称+坐标，后端自动创建 Location
  location_name?: string;
  location_lat?: number;
  location_lng?: number;
  post_type_id?: number;
  is_anonymous?: boolean;
  tags?: string[];
  expire_at?: string;
  // T-B-06: 支持创建时指定初始状态
  status?: 'draft' | 'pending';
}

interface PostFilters {
  page?: number;
  page_size?: number;
  category_id?: number;
  post_type_id?: number;
  status?: string;
  sort?: 'latest' | 'hottest' | 'nearest';
}

export const postsApi = {
  getPosts: async (filters?: PostFilters): Promise<PostListResponse> => {
    const response = await api.get('/posts', { params: filters });
    return response.data;
  },

  getPost: async (id: number): Promise<Post> => {
    const response = await api.get(`/posts/${id}`);
    return response.data;
  },

  createPost: async (data: CreatePostRequest): Promise<Post> => {
    const response = await api.post('/posts', data);
    return response.data;
  },

  updatePost: async (id: number, data: Partial<CreatePostRequest>): Promise<Post> => {
    const response = await api.put(`/posts/${id}`, data);
    return response.data;
  },

  deletePost: async (id: number): Promise<void> => {
    await api.delete(`/posts/${id}`);
  },

  getMyPosts: async (page = 1, pageSize = 20): Promise<PostListResponse> => {
    const response = await api.get('/users/me/posts', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },
};
