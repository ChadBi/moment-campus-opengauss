import { api } from './api';
import type {
  PostImageBrief,
} from '../types';

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

/** 批量操作单项失败明细（ADM-01.4） */
export interface BatchFailedItem {
  id: number;
  reason: string;
}

/** 批量操作结果 */
export interface BatchOperationResult {
  total: number;
  success: number;
  failed: number;
  failed_ids: number[];
  /** ADM-01.4: 每项失败明细（id + 原因） */
  failed_items: BatchFailedItem[];
  message: string;
}

// ============ ADM-01.1: 校级待办统计 ============

/** 单个待办类别：计数 + 前端跳转路径 */
export interface TodoItem {
  key: string;
  label: string;
  count: number;
  queue_url: string;
}

/** 校级后台首页待办统计（4 类 + REL-02.3 AI 降级率采样） */
export interface TodoStats {
  pending_posts: number;
  pending_reports: number;
  unverified_locations: number;
  failed_jobs: number;
  total: number;
  items: TodoItem[];
  /** REL-02.3: 最近 24h AI 调用次数（本校） */
  ai_calls_24h: number;
  /** REL-02.3: 最近 24h AI 降级次数（本校） */
  ai_fallback_24h: number;
  /** REL-02.3: 最近 24h AI 降级率（0~1） */
  ai_fallback_rate: number;
}

// ============ ADM-01.2: 审核详情（管理专用） ============

/** 作者历史统计 */
export interface AuthorHistoryStats {
  total_posts: number;
  published_posts: number;
  rejected_posts: number;
  report_received_count: number;
}

/** 审核详情（管理专用接口） */
export interface AdminPostDetail {
  id: number;
  title: string;
  content: string;
  status: string;
  is_anonymous: boolean;
  created_at: string;
  updated_at: string;
  expire_at: string | null;
  contact_info: string | null;
  lost_type: string | null;
  view_count: number;
  like_count: number;
  comment_count: number;
  valid_count: number;
  invalid_count: number;
  author_id: number;
  author_name: string | null;
  author_email: string | null;
  category_id: number;
  category_name: string | null;
  location_id: number | null;
  location_name: string | null;
  location_verified: boolean | null;
  images: PostImageBrief[];
  author_history: AuthorHistoryStats;
  pending_user_reports: number;
}

// ============ ADM-01.3: 原因模板 ============

/** 审核原因模板 */
export interface ReasonTemplate {
  code: string;
  label: string;
  text: string;
}

/** 通过/驳回原因模板 */
export interface ReasonTemplateResponse {
  approve: ReasonTemplate[];
  reject: ReasonTemplate[];
}

// ============ ADM-01.6: 地点核验 ============

/** 地点管理视图 */
export interface LocationAdmin {
  id: number;
  name: string;
  description: string | null;
  latitude: number;
  longitude: number;
  floor: string | null;
  building: string | null;
  post_count: number;
  is_verified: boolean;
  created_at: string;
}

// ============ ADM-02.1: 学校设置 ============

/**
 * 学校设置响应（后端真实存储，跨浏览器生效）
 *
 * 对应后端 SchoolSettingsResponse：
 *   GET /admin/settings / PUT /admin/settings
 * school_id 由 TenantContext 决定，不暴露给前端。
 */
export interface SchoolSettings {
  site_name: string | null;
  description: string | null;
  require_review: boolean;
  allow_anonymous: boolean;
  allow_comments: boolean;
  /** 每日发布上限（0 表示不限） */
  publish_frequency: number;
  /** 单帖图片上限 */
  image_limit: number;
  /** 默认有效期天数 */
  default_validity_days: number;
  /** 品牌色（如 #1890ff） */
  brand_color: string | null;
  logo_url: string | null;
  /** 最近一次更新时间（ISO 字符串） */
  updated_at: string;
}

/**
 * 更新学校设置请求（部分更新；全部字段可选）
 *
 * 对应后端 SchoolSettingsUpdate：未传字段保持原值；
 * school_id 不可改（由 TenantContext 决定）。
 */
export interface SchoolSettingsUpdateRequest {
  site_name?: string | null;
  description?: string | null;
  require_review?: boolean;
  allow_anonymous?: boolean;
  allow_comments?: boolean;
  /** 0~1000，0 表示不限 */
  publish_frequency?: number;
  /** 0~20 */
  image_limit?: number;
  /** 1~3650 */
  default_validity_days?: number;
  brand_color?: string | null;
  logo_url?: string | null;
}

// ============ GOV-02: 任务运行记录 ============

/** 任务运行记录 */
export interface JobRunRecord {
  id: number;
  job_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  processed_count: number;
  failed_count: number;
  error_message: string | null;
  triggered_by: string;
  triggered_user_id: number | null;
  dry_run: boolean;
  metadata: string | null;
  duration_seconds: number | null;
}

// ============ ADM-01.2: 平台首页跨校统计 ============

/** 单校 AI 调用统计 */
export interface SchoolAIStat {
  school_id: number;
  school_code: string | null;
  school_name: string | null;
  ai_calls: number;
  fallback_calls: number;
  fallback_rate: number;
}

/** 异常租户项 */
export interface AbnormalTenantItem {
  school_id: number;
  school_code: string | null;
  school_name: string | null;
  reasons: string[];
}

/** 学校开通记录 */
export interface ActivationRecordItem {
  school_id: number | null;
  school_code: string | null;
  school_name: string | null;
  operator_id: number | null;
  plan_code: string | null;
  created_at: string;
}

/** 平台首页跨校统计 */
export interface PlatformOverview {
  school_total: number;
  school_active: number;
  school_inactive: number;
  active_members: number;
  pending_posts: number;
  pending_reports: number;
  governance_total: number;
  ai_stats: SchoolAIStat[];
  ai_calls_total: number;
  ai_fallback_total: number;
  ai_fallback_rate: number;
  abnormal_tenants: AbnormalTenantItem[];
  activation_records: ActivationRecordItem[];
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

  // -------- ADM-01.1: 校级待办统计 --------
  getTodos: async (): Promise<TodoStats> => {
    const response = await api.get<TodoStats>('/admin/todos');
    return response.data;
  },

  // -------- ADM-01.2: 审核详情（管理专用接口） --------
  getAdminPostDetail: async (id: number): Promise<AdminPostDetail> => {
    const response = await api.get<AdminPostDetail>(`/admin/posts/${id}`);
    return response.data;
  },

  // -------- ADM-01.3: 审核原因模板 --------
  getReviewTemplates: async (): Promise<ReasonTemplateResponse> => {
    const response = await api.get<ReasonTemplateResponse>('/admin/review/templates');
    return response.data;
  },

  // -------- ADM-01.6: 地点核验 --------
  getAdminLocations: async (params?: {
    page?: number;
    page_size?: number;
    is_verified?: boolean;
    keyword?: string;
  }): Promise<PaginatedResponse<LocationAdmin>> => {
    const response = await api.get('/admin/locations', { params });
    return response.data;
  },

  verifyLocation: async (id: number, isVerified: boolean): Promise<LocationAdmin> => {
    const response = await api.put(`/admin/locations/${id}/verify`, null, {
      params: { is_verified: isVerified },
    });
    return response.data;
  },

  // -------- ADM-02.1: 学校设置（后端真实存储，跨浏览器生效） --------
  getSchoolSettings: async (): Promise<SchoolSettings> => {
    const response = await api.get<SchoolSettings>('/admin/settings');
    return response.data;
  },

  updateSchoolSettings: async (
    data: SchoolSettingsUpdateRequest,
  ): Promise<SchoolSettings> => {
    const response = await api.put<SchoolSettings>('/admin/settings', data);
    return response.data;
  },

  // -------- GOV-02: 任务运行记录 --------
  getJobRecords: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
  }): Promise<PaginatedResponse<JobRunRecord>> => {
    const response = await api.get('/admin/jobs/expire-posts/records', { params });
    return response.data;
  },

  triggerExpirePostsJob: async (dryRun: boolean): Promise<JobRunRecord> => {
    const response = await api.post('/admin/jobs/expire-posts', { dry_run: dryRun });
    return response.data;
  },

  // -------- TOPIC-01.2: 专题管理（CRUD/排序/上下线/编排） --------

  /** 专题管理响应（含全部状态） */
  // 类型定义见下方 export interface TopicAdmin / TopicAdminDetail

  getAdminTopics: async (params?: {
    page?: number;
    page_size?: number;
    status?: 'draft' | 'published' | 'archived';
    keyword?: string;
  }): Promise<PaginatedResponse<TopicAdmin>> => {
    const response = await api.get('/admin/topics', { params });
    return response.data;
  },

  getAdminTopic: async (id: number): Promise<TopicAdminDetail> => {
    const response = await api.get(`/admin/topics/${id}`);
    return response.data;
  },

  createTopic: async (data: TopicCreateRequest): Promise<TopicAdmin> => {
    const response = await api.post('/admin/topics', data);
    return response.data;
  },

  updateTopic: async (id: number, data: TopicUpdateRequest): Promise<TopicAdmin> => {
    const response = await api.put(`/admin/topics/${id}`, data);
    return response.data;
  },

  deleteTopic: async (id: number): Promise<{ message: string }> => {
    const response = await api.delete(`/admin/topics/${id}`);
    return response.data;
  },

  /** 批量排序专题 */
  sortTopics: async (items: Array<{ id: number; sort_order: number }>): Promise<{ message: string }> => {
    const response = await api.put('/admin/topics/sort', { items });
    return response.data;
  },

  /** 上线专题（draft/archived → published） */
  publishTopic: async (id: number): Promise<TopicAdmin> => {
    const response = await api.put(`/admin/topics/${id}/publish`);
    return response.data;
  },

  /** 下线专题（published → archived） */
  archiveTopic: async (id: number): Promise<TopicAdmin> => {
    const response = await api.put(`/admin/topics/${id}/archive`);
    return response.data;
  },

  /** 向专题添加帖子（仅同校已发布帖子可添加） */
  addPostsToTopic: async (
    topicId: number,
    posts: Array<{ post_id: number; sort_order: number }>
  ): Promise<TopicAdminDetail> => {
    const response = await api.post(`/admin/topics/${topicId}/posts`, { posts });
    return response.data;
  },

  /** 从专题移除帖子 */
  removePostFromTopic: async (topicId: number, postId: number): Promise<TopicAdminDetail> => {
    const response = await api.delete(`/admin/topics/${topicId}/posts/${postId}`);
    return response.data;
  },

  /** 调整专题内帖子的排序 */
  sortTopicPosts: async (
    topicId: number,
    posts: Array<{ post_id: number; sort_order: number }>
  ): Promise<TopicAdminDetail> => {
    const response = await api.put(`/admin/topics/${topicId}/posts/sort`, { posts });
    return response.data;
  },

  // ============ ORG-01.2: 官方发布主体管理（已下线） ============
  // 注：发布主体与模板相关接口已随 publisher_profiles / publisher_memberships /
  // post_templates 表删除而移除。如需恢复，请回溯到 a6b7c8d9e0f1 迁移之前的版本。
};

// ============ TOPIC-01.2: 专题类型定义 ============

/** 专题状态（3 态） */
export type TopicStatus = 'draft' | 'published' | 'archived';

/** 专题管理响应（后端 TopicAdminResponse） */
export interface TopicAdmin {
  id: number;
  title: string;
  description?: string | null;
  cover_url?: string | null;
  school_id: number;
  creator_id: number;
  creator_name?: string | null;
  post_count: number;
  view_count: number;
  status: TopicStatus;
  sort_order: number;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
}

/** 管理端专题内的帖子项（后端 TopicPostAdminItem） */
export interface TopicPostAdminItem {
  id: number;
  topic_collection_id: number;
  post_id: number;
  post_title?: string | null;
  post_status?: string | null;
  post_school_id?: number | null;
  sort_order: number;
  created_at: string;
}

/** 专题管理详情（后端 TopicAdminDetail，含关联帖子列表） */
export interface TopicAdminDetail extends TopicAdmin {
  posts: TopicPostAdminItem[];
}

/** 创建专题请求（后端 TopicCreate） */
export interface TopicCreateRequest {
  title: string;
  description?: string | null;
  cover_url?: string | null;
  sort_order?: number;
  status?: TopicStatus;
}

/** 更新专题请求（后端 TopicUpdate，部分更新） */
export interface TopicUpdateRequest {
  title?: string;
  description?: string | null;
  cover_url?: string | null;
  sort_order?: number;
}
