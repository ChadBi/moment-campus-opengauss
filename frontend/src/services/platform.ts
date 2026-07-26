import { api } from './api';
import type {
  PlatformPlan,
  PlatformSubscription,
  PlatformSchool,
  PlatformSchoolDetail,
  PlatformAuditLog,
  SchoolAlertsResponse,
  PlatformAlertsResponse,
  ImportResponse,
  ActivationFunnelResponse,
} from '../types';
import type { PlatformOverview } from './admin';

// 透传类型，供页面层统一从 services/platform 导入
export type { SchoolAlertsResponse, PlatformAlertsResponse };

/**
 * COM-02：平台管理 API 客户端
 *
 * 端点对应后端 app/api/platform.py（全部 super_admin）：
 *   GET    /platform/plans                            套餐及权益字典
 *   GET    /platform/subscriptions                    订阅列表
 *   POST   /platform/schools/{id}/subscription        分配/续期套餐
 *   PUT    /platform/subscriptions/{id}               续期/暂停/恢复订阅
 *   GET    /platform/schools                          平台学校列表
 *   GET    /platform/schools/{id}                     学校详情（含开通清单）
 *   POST   /platform/schools                          创建学校
 *   PUT    /platform/schools/{id}/status              启用/暂停学校
 *   GET    /platform/audit                            平台审计日志
 *   GET    /platform/schools/{id}/subscription-history 套餐历史变更
 *   GET    /platform/schools/{id}/alerts              学校额度告警
 *   GET    /platform/alerts                           全平台告警汇总
 *   GET    /platform/import-template                  下载 CSV 模板
 *   POST   /platform/schools/{id}/import              批量导入（dry_run 预览）
 *   GET    /platform/activation-funnel                激活漏斗
 */

// ============ 请求参数类型 ============

export interface PlanListResult {
  items: PlatformPlan[];
}

export interface SubscriptionQueryParams {
  page?: number;
  page_size?: number;
  school_id?: number;
  status?: string;
}

export interface SubscriptionListResponse {
  items: PlatformSubscription[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_more: boolean;
}

export interface SubscriptionAssignRequest {
  plan_code: string;
  expires_at?: string | null;
  note?: string;
}

export interface SubscriptionUpdateRequest {
  status?: string;
  expires_at?: string | null;
  note?: string;
}

export interface SchoolListQueryParams {
  page?: number;
  page_size?: number;
  is_active?: boolean;
  keyword?: string;
}

export interface SchoolListResponse {
  items: PlatformSchool[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_more: boolean;
}

export interface SchoolCreateRequest {
  code: string;
  name: string;
  center_lat?: number | null;
  center_lng?: number | null;
  map_zoom?: number | null;
  logo_url?: string | null;
  brand_color?: string | null;
  description?: string | null;
  admin_email?: string | null;
  plan_code?: string | null;
  province?: string | null;
  city?: string | null;
  address?: string | null;
}

export interface SchoolStatusUpdateRequest {
  is_active: boolean;
  reason?: string;
}

export interface AuditQueryParams {
  page?: number;
  page_size?: number;
  action?: string;
  target_school_id?: number;
  operator_id?: number;
}

export interface AuditListResponse {
  items: PlatformAuditLog[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_more: boolean;
}

export interface SubscriptionHistoryResponse {
  items: PlatformSubscription[];
  total: number;
}

export interface ImportRowsRequest {
  rows: Array<Record<string, unknown>>;
}

export interface ActivationFunnelQueryParams {
  keyword?: string;
  is_active?: boolean;
}

// ============ API ============

export const platformApi = {
  // -------- 套餐与权益 --------
  listPlans: async (): Promise<PlatformPlan[]> => {
    const response = await api.get<PlatformPlan[]>('/platform/plans');
    return response.data;
  },

  // -------- 订阅 --------
  listSubscriptions: async (
    params?: SubscriptionQueryParams
  ): Promise<SubscriptionListResponse> => {
    const response = await api.get('/platform/subscriptions', { params });
    return response.data;
  },

  assignSubscription: async (
    schoolId: number,
    data: SubscriptionAssignRequest
  ): Promise<PlatformSubscription> => {
    const response = await api.post(
      `/platform/schools/${schoolId}/subscription`,
      data
    );
    return response.data;
  },

  updateSubscription: async (
    subscriptionId: number,
    data: SubscriptionUpdateRequest
  ): Promise<PlatformSubscription> => {
    const response = await api.put(
      `/platform/subscriptions/${subscriptionId}`,
      data
    );
    return response.data;
  },

  // -------- 学校 --------
  listSchools: async (
    params?: SchoolListQueryParams
  ): Promise<SchoolListResponse> => {
    const response = await api.get('/platform/schools', { params });
    return response.data;
  },

  getSchoolDetail: async (
    schoolId: number
  ): Promise<PlatformSchoolDetail> => {
    const response = await api.get(`/platform/schools/${schoolId}`);
    return response.data;
  },

  createSchool: async (
    data: SchoolCreateRequest
  ): Promise<Record<string, unknown>> => {
    const response = await api.post('/platform/schools', data);
    return response.data;
  },

  updateSchoolStatus: async (
    schoolId: number,
    data: SchoolStatusUpdateRequest
  ): Promise<PlatformSchool> => {
    const response = await api.put(
      `/platform/schools/${schoolId}/status`,
      data
    );
    return response.data;
  },

  // -------- 套餐历史 --------
  getSubscriptionHistory: async (
    schoolId: number
  ): Promise<SubscriptionHistoryResponse> => {
    const response = await api.get(
      `/platform/schools/${schoolId}/subscription-history`
    );
    return response.data;
  },

  // -------- 告警 --------
  getSchoolAlerts: async (schoolId: number): Promise<SchoolAlertsResponse> => {
    const response = await api.get(`/platform/schools/${schoolId}/alerts`);
    return response.data;
  },

  listAllAlerts: async (): Promise<PlatformAlertsResponse> => {
    const response = await api.get('/platform/alerts');
    return response.data;
  },

  // -------- 审计 --------
  listAuditLogs: async (
    params?: AuditQueryParams
  ): Promise<AuditListResponse> => {
    const response = await api.get('/platform/audit', { params });
    return response.data;
  },

  // -------- 批量导入 --------
  downloadImportTemplate: async (): Promise<Blob> => {
    const response = await api.get('/platform/import-template', {
      responseType: 'blob',
    });
    return response.data as Blob;
  },

  importSchoolData: async (
    schoolId: number,
    data: ImportRowsRequest,
    dryRun = false
  ): Promise<ImportResponse> => {
    const response = await api.post(
      `/platform/schools/${schoolId}/import`,
      data,
      { params: dryRun ? { dry_run: 'true' } : undefined }
    );
    return response.data;
  },

  // -------- 激活漏斗 --------
  getActivationFunnel: async (
    params?: ActivationFunnelQueryParams
  ): Promise<ActivationFunnelResponse> => {
    const response = await api.get('/platform/activation-funnel', { params });
    return response.data;
  },

  // -------- ADM-01.2: 平台首页跨校统计 --------
  getOverview: async (): Promise<PlatformOverview> => {
    const response = await api.get<PlatformOverview>('/platform/overview');
    return response.data;
  },
};

// ============ 校级用量（admin/super_admin） ============

export interface SchoolUsageResponse {
  school_id: number;
  school_code: string;
  plan_code?: string | null;
  plan_name?: string | null;
  subscription_status?: string | null;
  subscription_expires_at?: string | null;
  days_to_expire?: number | null;
  entitlements: Array<{
    key: string;
    limit_value: number | null;
    current_value: number | null;
    remaining: number | null;
    is_hard: boolean;
    code: string;
    message: string;
    allowed: boolean;
  }>;
  alerts: Array<{
    key: string;
    code: string;
    message: string;
    severity: 'warning' | 'critical';
    days_to_expire?: number;
  }>;
  alerts_count: number;
  stats: {
    members_count: number;
    posts_count: number;
    ai_calls_today: number;
    storage_used_mb: number;
    last_updated_at: string | null;
    stat_basis: string;
  };
  contact_platform_hint: string;
}

export const usageApi = {
  /** COM-02.3：校级用量页（admin/super_admin） */
  getSchoolUsage: async (): Promise<SchoolUsageResponse> => {
    const response = await api.get<SchoolUsageResponse>('/admin/usage');
    return response.data;
  },
};
