import { api } from './api';

/**
 * ANA-02: 数据分析 API 客户端
 *
 * 端点对应后端 app/api/analytics.py 与 app/api/platform.py：
 *   GET /admin/analytics          校级分析指标（admin 及以上）
 *   GET /admin/analytics/zero-results  零结果主题洞察（隐私阈值保护）
 *   GET /platform/analytics       平台分析指标（super_admin 专用，跨校聚合）
 *
 * 设计要点：
 * - 平台只看学校级聚合，不暴露跨校用户轨迹
 * - 零结果主题样本量 < PRIVACY_THRESHOLD 时标记 hidden_for_privacy=true
 * - 每个指标附带元数据：time_window / sample_size / last_updated_at / empty_state
 */

// ============ 元数据 ============

/** 指标元数据：保证「可复算 + 显示窗口/样本量/最后更新/空数据状态」 */
export interface MetricMeta {
  /** 时间窗口起点（ISO 字符串）；可能为 null（如内容有效率无窗口概念） */
  time_window_start: string | null;
  /** 时间窗口终点（ISO 字符串） */
  time_window_end: string;
  /** 样本量 */
  sample_size: number;
  /** 最后更新时间（ISO 字符串） */
  last_updated_at: string;
  /** 是否为空数据状态 */
  empty_state: boolean;
}

// ============ 漏斗 ============

/** 漏斗阶段项 */
export interface FunnelStage {
  key: string;
  label: string;
  count: number;
}

/** 漏斗指标 */
export interface FunnelMetric {
  /** 5 阶段：school_viewed → search_started → post_submitted → pending_review → published */
  stages: FunnelStage[];
  /** 各阶段转化率（前一阶段 → 当前阶段） */
  conversion_rates: {
    school_viewed_to_search: number;
    search_to_post_submitted: number;
    post_submitted_to_pending: number;
    pending_to_published: number;
    /** 整体转化率：school_viewed → published */
    overall: number;
  };
  meta: MetricMeta;
}

// ============ 7 日回访 ============

export interface Retention7dMetric {
  baseline_users: number;
  revisit_users: number;
  retention_rate: number;
  window_days: number;
  meta: MetricMeta;
}

// ============ 搜索指标 ============

export interface SearchSuccessRateMetric {
  succeeded_searches: number;
  zero_searches: number;
  total_searches: number;
  success_rate: number;
  meta: MetricMeta;
}

export interface SearchZeroRateMetric {
  zero_searches: number;
  total_searches: number;
  zero_rate: number;
  meta: MetricMeta;
}

// ============ 分享订阅转化 ============

export interface ShareSubscriptionConversionMetric {
  share_clicked: number;
  subscribed: number;
  conversion_rate: number;
  meta: MetricMeta;
}

// ============ 内容有效率 ============

export interface ContentValidRateMetric {
  total_posts: number;
  valid_posts: number;
  valid_rate: number;
  meta: MetricMeta;
}

// ============ 审核治理 SLA ============

export interface GovernanceSlaMetric {
  /** 平均审核时长（秒） */
  avg_review_seconds: number;
  /** 平均举报处理时长（秒） */
  avg_report_handle_seconds: number;
  /** 平均问题报告处理时长（秒） */
  avg_change_report_handle_seconds: number;
  reviewed_count: number;
  reports_handled_count: number;
  change_reports_handled_count: number;
  meta: MetricMeta;
}

// ============ AI 用量 ============

export interface AiUsageMetric {
  total_calls: number;
  success_calls: number;
  fallback_calls: number;
  success_rate: number;
  fallback_rate: number;
  avg_latency_ms: number;
  avg_candidate_count: number;
  avg_result_count: number;
  meta: MetricMeta;
}

// ============ 校级分析响应 ============

export interface SchoolAnalyticsResponse {
  school_id: number;
  school_code: string | null;
  school_name: string | null;
  funnel: FunnelMetric;
  retention_7d: Retention7dMetric;
  search_success_rate: SearchSuccessRateMetric;
  search_zero_rate: SearchZeroRateMetric;
  share_subscription_conversion: ShareSubscriptionConversionMetric;
  content_valid_rate: ContentValidRateMetric;
  governance_sla: GovernanceSlaMetric;
  ai_usage: AiUsageMetric;
  generated_at: string;
}

// ============ 零结果洞察 ============

/** 零结果主题项（经隐私阈值保护） */
export interface ZeroResultTopic {
  keyword_length: number | null;
  category_code: string | null;
  occurrences: number;
  /** 样本量 < PRIVACY_THRESHOLD 时为 true，仍计入总数但不返回具体聚合字段 */
  hidden_for_privacy: boolean;
}

export interface ZeroResultsInsightResponse {
  school_id: number;
  school_code: string | null;
  total_zero_searches: number;
  privacy_threshold: number;
  topics: ZeroResultTopic[];
  last_updated_at: string | null;
}

// ============ 平台分析响应 ============

/** 各校聚合指标（不暴露跨校用户维度） */
export interface SchoolMetricItem {
  school_id: number;
  school_code: string | null;
  school_name: string | null;
  is_active: boolean;
  funnel_summary: {
    school_viewed: number;
    search_started: number;
    post_submitted: number;
    published: number;
  };
  search_success_rate: number;
  search_zero_rate: number;
  ai_calls: number;
  ai_fallback_rate: number;
}

/** 平台级漏斗聚合 */
export interface PlatformFunnelMetric {
  stages: FunnelStage[];
  overall_conversion: number;
  meta: MetricMeta;
}

/** 平台级搜索指标 */
export interface PlatformSearchMetric {
  succeeded_searches: number;
  zero_searches: number;
  total_searches: number;
  success_rate: number;
  zero_rate: number;
  meta: MetricMeta;
}

/** 平台级 AI 用量 */
export interface PlatformAiUsageMetric {
  total_calls: number;
  success_calls: number;
  fallback_calls: number;
  success_rate: number;
  fallback_rate: number;
  avg_latency_ms: number;
  meta: MetricMeta;
}

/** 平台级治理 SLA */
export interface PlatformGovernanceMetric {
  avg_review_seconds: number;
  avg_report_handle_seconds: number;
  reviewed_count: number;
  reports_handled_count: number;
  meta: MetricMeta;
}

export interface PlatformAnalyticsResponse {
  school_total: number;
  school_active: number;
  school_metrics: SchoolMetricItem[];
  platform_funnel: PlatformFunnelMetric;
  platform_search: PlatformSearchMetric;
  platform_ai_usage: PlatformAiUsageMetric;
  platform_governance: PlatformGovernanceMetric;
  generated_at: string;
}

// ============ 请求参数 ============

export interface AnalyticsQueryParams {
  /** 复算时间窗口（天），默认 30，范围 1-180 */
  window_days?: number;
}

// ============ API ============

export const analyticsApi = {
  /**
   * ANA-02.2: 获取校级分析指标（admin 及以上）
   *
   * 平台只看学校级聚合；本接口返回当前 admin 所属学校的聚合数据，
   * 不暴露跨校用户轨迹。super_admin 可通过 X-School-Code 切换查看任意学校。
   */
  getSchoolAnalytics: async (
    params?: AnalyticsQueryParams
  ): Promise<SchoolAnalyticsResponse> => {
    const response = await api.get<SchoolAnalyticsResponse>('/admin/analytics', {
      params,
    });
    return response.data;
  },

  /**
   * ANA-02.1: 零结果主题洞察（隐私阈值保护）
   *
   * - 从 search_zero 事件聚合 keyword_length + category_code
   * - 单个主题样本量 < PRIVACY_THRESHOLD（5）时标记 hidden_for_privacy=true
   * - 仍计入总数但不返回具体聚合字段（隐私硬约束）
   */
  getZeroResultsInsight: async (
    params?: AnalyticsQueryParams
  ): Promise<ZeroResultsInsightResponse> => {
    const response = await api.get<ZeroResultsInsightResponse>(
      '/admin/analytics/zero-results',
      { params }
    );
    return response.data;
  },

  /**
   * ANA-02.1: 获取平台分析指标（super_admin 专用，跨校聚合）
   *
   * - 平台只看学校级聚合：每所学校一行聚合指标，不暴露跨校用户轨迹
   * - 各校聚合后再次汇总成平台级指标（funnel / search / ai / governance）
   * - 平台层不返回零结果主题明细（隐私阈值由各校 admin 自行查看本校数据）
   */
  getPlatformAnalytics: async (
    params?: AnalyticsQueryParams
  ): Promise<PlatformAnalyticsResponse> => {
    const response = await api.get<PlatformAnalyticsResponse>(
      '/platform/analytics',
      { params }
    );
    return response.data;
  },
};
