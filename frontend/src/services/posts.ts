import { api } from './api';
import type {
  Post,
  PaginatedResponse,
  PostStatus,
  PostTransitionResponse,
  AIPublishSuggestRequest,
  AIPublishSuggestionResponse,
} from '../types';

// FND-01.3: Post 类型从 types/index.ts 统一导入，消除手写重复

interface CreatePostRequest {
  title: string;
  content: string;
  category_id: number;
  location_id?: number;
  // 地图点选发帖：直接传地点名称+坐标，后端自动创建 Location
  location_name?: string;
  location_lat?: number;
  location_lng?: number;
  is_anonymous?: boolean;
  /** 【新版推荐】一张图片的两个 URL（原图 + 缩略图），同时携带让详情页缩略带宽优化真正生效 */
  images?: Array<{ image_url: string; thumbnail_url?: string }>;
  /** 【旧版兼容】仅原图 URL 数组；建议迁移到新版 images，后端已同时兼容两种写法 */
  image_urls?: string[];
  /** PUB-01.2: 信息截止时间（ISO 字符串），未传则后端按分类默认有效期计算 */
  expire_at?: string;
  /** PUB-01.2: 联系方式（失物类信息使用） */
  contact_info?: string;
  /** PUB-01.2: 失物类型（lost/found） */
  lost_type?: string;
  // T-B-06: 支持创建时指定初始状态
  status?: 'draft' | 'pending';
  // ORG-01: publisher_id 字段已随发布主体功能移除
}

/**
 * DSC-01.1: 帖子列表筛选参数（与后端 app/api/posts.py 对齐）
 */
export type PostListStatusFilter = 'published' | 'expired' | 'valid';
export type PostListSort = 'latest' | 'hottest' | 'active';

interface PostFilters {
  page?: number;
  page_size?: number;
  category_id?: number;
  /** DSC-01.1: 地点 ID 筛选 */
  location_id?: number;
  /** DSC-01.1: 有效状态筛选（published / expired / valid），默认 valid（published + expired） */
  status?: PostListStatusFilter;
  /** DSC-01.1: 起始时间（ISO 字符串，created_at >= date_from） */
  date_from?: string;
  /** DSC-01.1: 截止时间（ISO 字符串，created_at <= date_to） */
  date_to?: string;
  /** DSC-01.1: 排序方式（latest / hottest / active） */
  sort?: PostListSort;
}

export const postsApi = {
  /**
   * DSC-01.1: 获取信息列表，支持多维度筛选 + 排序 + 分页
   * 返回 PaginatedResponse<Post>（含 total/total_pages/has_more）。
   */
  getPosts: async (filters?: PostFilters): Promise<PaginatedResponse<Post>> => {
    // 过滤 undefined / null / 空字符串，避免 axios 误传
    const cleaned = filters
      ? Object.fromEntries(
          Object.entries(filters).filter(
            ([, v]) => v !== undefined && v !== null && v !== ''
          )
        )
      : undefined;
    const response = await api.get('/posts', { params: cleaned });
    return response.data;
  },

  getPost: async (id: number, incrementView = true): Promise<Post> => {
    const response = await api.get(`/posts/${id}`, {
      params: incrementView ? {} : { increment_view: false },
    });
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

  /**
   * PUB-02: 获取我的发布，支持按状态筛选（草稿/待审核/已发布等），
   * 用于"我的发布"按状态分组分页展示；不传 status 返回全部状态。
   */
  getMyPosts: async (
    page = 1,
    pageSize = 20,
    status?: PostStatus
  ): Promise<PaginatedResponse<Post>> => {
    const response = await api.get('/users/me/posts', {
      params: { page, page_size: pageSize, ...(status ? { status } : {}) },
    });
    return response.data;
  },

  /**
   * PUB-02: 状态流转（普通用户仅支持自己的 draft → pending 提交审核 /
   * draft → archived 放弃草稿；其余流转由管理员操作）。
   */
  transitionPost: async (
    id: number,
    targetStatus: PostStatus
  ): Promise<PostTransitionResponse> => {
    const response = await api.post(`/posts/${id}/transition`, {
      target_status: targetStatus,
    });
    return response.data;
  },

  /**
   * AI-03: 调用 AI 辅助发布建议接口（POST /posts/ai-suggest）。
   *
   * 安全保证：
   * - 不修改原文：仅返回结构化建议，由用户在前端逐项确认采纳
   * - 失败不阻塞：fallback=true 时仍返回敏感检测/缺失提示结果，前端可继续手动发布
   * - 三校隔离：建议的分类/标签只来自当前学校白名单
   */
  aiSuggest: async (
    payload: AIPublishSuggestRequest
  ): Promise<AIPublishSuggestionResponse> => {
    const response = await api.post('/posts/ai-suggest', payload);
    return response.data;
  },
};
