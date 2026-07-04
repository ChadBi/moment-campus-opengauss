import { api } from './api';

// ============ 类型定义 ============

/** 仪表盘统计数据 */
export interface DashboardStats {
  total_posts: number;
  pending_posts: number;
  total_users: number;
  active_users: number;
  total_reports: number;
  pending_reports: number;
  total_comments: number;
}

/** 操作日志 */
export interface AdminLog {
  id: number;
  admin_id: number;
  admin_name: string | null;
  action: string;
  target_type: string;
  target_id: number;
  detail: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

/** 分类（管理视图，含禁用项与统计） */
export interface CategoryAdmin {
  id: number;
  name: string;
  code: string;
  icon: string;
  description: string | null;
  default_validity_days: number;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  post_count: number;
}

/** 标签（管理视图，含已删项） */
export interface TagAdmin {
  id: number;
  name: string;
  slug: string;
  usage_count: number;
  is_official: boolean;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

/** 批量操作结果 */
export interface BatchOperationResult {
  total: number;
  success: number;
  failed: number;
  failed_ids: number[];
  message: string;
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

/** 待审核帖子简要 */
export interface PostBrief {
  id: number;
  title: string;
  content: string;
  status: string;
  created_at: string;
  author_id: number;
  author_name: string | null;
  category_id: number;
  category_name: string | null;
}

/** 用户简要 */
export interface UserBrief {
  id: number;
  email: string;
  nickname: string;
  role: string;
  is_active: boolean;
  created_at: string;
  school_id: number;
}

/** 举报简要 */
export interface ReportBrief {
  id: number;
  post_id: number | null;
  post_title: string | null;
  reporter_id: number;
  reporter_name: string | null;
  report_type: string;
  description: string | null;
  status: string;
  created_at: string;
}

// ============ 请求参数类型 ============

export interface LogQueryParams {
  page?: number;
  page_size?: number;
  admin_id?: number;
  action?: string;
  target_type?: string;
  date_from?: string;
  date_to?: string;
}

export interface CategoryQueryParams {
  page?: number;
  page_size?: number;
  is_active?: boolean;
}

export interface TagQueryParams {
  page?: number;
  page_size?: number;
  name?: string;
  is_official?: boolean;
  is_deleted?: boolean;
}

export interface UserQueryParams {
  page?: number;
  page_size?: number;
  is_active?: boolean;
}

export interface ReportQueryParams {
  page?: number;
  page_size?: number;
  status?: string;
}

export interface PendingPostQueryParams {
  page?: number;
  page_size?: number;
}

// ============ 请求体类型 ============

export interface CategoryCreateRequest {
  name: string;
  code: string;
  icon: string;
  description?: string;
  default_validity_days?: number;
  sort_order?: number;
  is_active?: boolean;
}

export interface CategoryUpdateRequest {
  name?: string;
  icon?: string;
  description?: string;
  default_validity_days?: number;
  sort_order?: number;
  is_active?: boolean;
}

export interface TagUpdateRequest {
  name?: string;
  is_official?: boolean;
}

export interface TagMergeRequest {
  source_tag_ids: number[];
  target_tag_id: number;
}

export interface BatchApproveRequest {
  post_ids: number[];
  reason?: string;
}

export interface BatchRejectRequest {
  post_ids: number[];
  reason: string;
}

export interface BatchToggleActiveRequest {
  user_ids: number[];
  is_active: boolean;
  reason?: string;
}

export interface ApproveRequest {
  reason?: string;
}

export interface RejectRequest {
  reason: string;
}

export interface ToggleActiveRequest {
  is_active: boolean;
  reason?: string;
}

export interface HandleReportRequest {
  action: 'dismiss' | 'warn' | 'delete_post' | 'ban_user';
  reason: string;
}

// ============ API ============

export const adminApi = {
  // -------- 仪表盘 --------
  getStats: async (): Promise<DashboardStats> => {
    const response = await api.get<DashboardStats>('/admin/stats');
    return response.data;
  },

  // -------- 操作日志 --------
  getLogs: async (params?: LogQueryParams): Promise<PaginatedResponse<AdminLog>> => {
    const response = await api.get('/admin/logs', { params });
    return response.data;
  },

  // -------- 分类管理 --------
  getCategories: async (params?: CategoryQueryParams): Promise<PaginatedResponse<CategoryAdmin>> => {
    const response = await api.get('/admin/categories', { params });
    return response.data;
  },

  createCategory: async (data: CategoryCreateRequest): Promise<CategoryAdmin> => {
    const response = await api.post('/admin/categories', data);
    return response.data;
  },

  updateCategory: async (id: number, data: CategoryUpdateRequest): Promise<CategoryAdmin> => {
    const response = await api.put(`/admin/categories/${id}`, data);
    return response.data;
  },

  deleteCategory: async (id: number): Promise<{ message: string }> => {
    const response = await api.delete(`/admin/categories/${id}`);
    return response.data;
  },

  // -------- 标签管理 --------
  getTags: async (params?: TagQueryParams): Promise<PaginatedResponse<TagAdmin>> => {
    const response = await api.get('/admin/tags', { params });
    return response.data;
  },

  updateTag: async (id: number, data: TagUpdateRequest): Promise<TagAdmin> => {
    const response = await api.put(`/admin/tags/${id}`, data);
    return response.data;
  },

  deleteTag: async (id: number): Promise<{ message: string }> => {
    const response = await api.delete(`/admin/tags/${id}`);
    return response.data;
  },

  mergeTags: async (data: TagMergeRequest): Promise<BatchOperationResult> => {
    const response = await api.post('/admin/tags/merge', data);
    return response.data;
  },

  // -------- 帖子审核 --------
  getPendingPosts: async (params?: PendingPostQueryParams): Promise<PaginatedResponse<PostBrief>> => {
    const response = await api.get('/admin/posts/pending', { params });
    return response.data;
  },

  approvePost: async (id: number, data?: ApproveRequest): Promise<{ message: string }> => {
    const response = await api.put(`/admin/posts/${id}/approve`, data || {});
    return response.data;
  },

  rejectPost: async (id: number, data: RejectRequest): Promise<{ message: string }> => {
    const response = await api.put(`/admin/posts/${id}/reject`, data);
    return response.data;
  },

  // -------- 用户管理 --------
  getUsers: async (params?: UserQueryParams): Promise<PaginatedResponse<UserBrief>> => {
    const response = await api.get('/admin/users', { params });
    return response.data;
  },

  toggleUserActive: async (id: number, data: ToggleActiveRequest): Promise<{ message: string }> => {
    const response = await api.put(`/admin/users/${id}/toggle-active`, data);
    return response.data;
  },

  // -------- 举报管理 --------
  getReports: async (params?: ReportQueryParams): Promise<PaginatedResponse<ReportBrief>> => {
    const response = await api.get('/admin/reports', { params });
    return response.data;
  },

  handleReport: async (id: number, data: HandleReportRequest): Promise<{ message: string }> => {
    const response = await api.put(`/admin/reports/${id}/handle`, data);
    return response.data;
  },

  // -------- 批量操作 --------
  batchApprovePosts: async (data: BatchApproveRequest): Promise<BatchOperationResult> => {
    const response = await api.post('/admin/posts/batch-approve', data);
    return response.data;
  },

  batchRejectPosts: async (data: BatchRejectRequest): Promise<BatchOperationResult> => {
    const response = await api.post('/admin/posts/batch-reject', data);
    return response.data;
  },

  batchToggleUsersActive: async (data: BatchToggleActiveRequest): Promise<BatchOperationResult> => {
    const response = await api.post('/admin/users/batch-toggle-active', data);
    return response.data;
  },
};
