import { api } from './api';
import type {
  PublisherBrief,
  PublisherDetail,
  PublisherAggregation,
  PublisherCreateRequest,
  PublisherUpdateRequest,
  PostTemplate,
  PostTemplateCreateRequest,
  PostTemplateScene,
  PaginatedResponse,
  PublisherVerifiedStatus,
  PublisherType,
} from '../types';

// ============ ORG-01: 官方发布主体用户端服务 ============

/** 列表筛选参数 */
export interface PublisherListParams {
  page?: number;
  page_size?: number;
  type?: PublisherType;
  verified_status?: PublisherVerifiedStatus;
  keyword?: string;
}

/** 模板列表筛选参数 */
export interface TemplateListParams {
  scene?: PostTemplateScene;
}

export const publishersApi = {
  // -------- 公开端点 --------

  /** 发布主体列表（本校，认证主体优先） */
  list: async (params?: PublisherListParams): Promise<PaginatedResponse<PublisherBrief>> => {
    const response = await api.get<PaginatedResponse<PublisherBrief>>('/publishers', { params });
    return response.data;
  },

  /** 发布主体详情（主页：基本信息+成员+最近内容，浏览时 view_count +1） */
  getDetail: async (id: number): Promise<PublisherDetail> => {
    const response = await api.get<PublisherDetail>(`/publishers/${id}`);
    return response.data;
  },

  /** 组织后台聚合效果（浏览/订阅/分享/反馈/零结果） */
  getAggregation: async (id: number): Promise<PublisherAggregation> => {
    const response = await api.get<PublisherAggregation>(`/publishers/${id}/aggregation`);
    return response.data;
  },

  /** 主体专属模板列表（公开主页展示） */
  getPublisherTemplates: async (id: number): Promise<PostTemplate[]> => {
    const response = await api.get<PostTemplate[]>(`/publishers/${id}/templates`);
    return response.data;
  },

  /** 学校级公共模板列表（用于 PostForm 选择） */
  getPublicTemplates: async (params?: TemplateListParams): Promise<PostTemplate[]> => {
    const response = await api.get<PostTemplate[]>('/templates', { params });
    return response.data;
  },

  // -------- 登录用户端点 --------

  /** 申请创建发布主体（强制 verified_status=pending，创建者自动成为 owner） */
  create: async (data: PublisherCreateRequest): Promise<PublisherDetail> => {
    const response = await api.post<PublisherDetail>('/publishers', data);
    return response.data;
  },

  /** 更新发布主体信息（仅 owner/admin 成员，verified_status 不可改） */
  update: async (id: number, data: PublisherUpdateRequest): Promise<PublisherDetail> => {
    const response = await api.put<PublisherDetail>(`/publishers/${id}`, data);
    return response.data;
  },

  /** 当前用户加入的发布主体列表 */
  listMine: async (): Promise<PublisherBrief[]> => {
    const response = await api.get<PublisherBrief[]>('/me/publishers');
    return response.data;
  },

  /** 有效性反馈/零结果关联需求聚合 */
  submitFeedback: async (
    id: number,
    feedbackType: 'valid' | 'invalid' | 'zero_result',
  ): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>(`/publishers/${id}/feedback`, {
      feedback_type: feedbackType,
    });
    return response.data;
  },

  /** 分享计数上报 */
  share: async (id: number): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>(`/publishers/${id}/share`, {});
    return response.data;
  },

  /** 创建主体专属模板（仅 owner/admin 成员） */
  createPublisherTemplate: async (
    publisherId: number,
    data: PostTemplateCreateRequest,
  ): Promise<PostTemplate> => {
    const response = await api.post<PostTemplate>(
      `/publishers/${publisherId}/templates`,
      data,
    );
    return response.data;
  },

  /** 更新模板（公共模板需 admin，主体专属模板需 owner/admin） */
  updateTemplate: async (
    templateId: number,
    data: Partial<PostTemplateCreateRequest> & { is_active?: boolean },
  ): Promise<PostTemplate> => {
    const response = await api.put<PostTemplate>(`/templates/${templateId}`, data);
    return response.data;
  },
};
