export { api } from './api';
export { authApi } from './auth';
export { postsApi } from './posts';
export { commentsApi } from './comments';
export { interactionsApi } from './interactions';
export { searchApi } from './search';
export { notificationsApi } from './notifications';
export { uploadApi } from './upload';
export { usersApi } from './users';
export { mapApi } from './map';
export type { MapMarker } from './map';
export { adminApi } from './admin';
export type {
  DashboardStats,
  AdminLog,
  CategoryAdmin,
  BatchOperationResult,
  PaginatedResponse,
  PostBrief,
  UserBrief,
  ReportBrief,
} from './admin';
export { schoolsApi } from './schools';
export type {
  CurrentSchool,
  JoinSchoolResponse,
  SetDefaultSchoolResponse,
} from './schools';
// COM-02：平台管理 + 校级用量 API
export { platformApi } from './platform';
export type {
  SubscriptionAssignRequest,
  SubscriptionUpdateRequest,
  SubscriptionListResponse,
  SchoolListResponse,
  SchoolCreateRequest,
  SchoolStatusUpdateRequest,
  AuditListResponse,
  SubscriptionHistoryResponse,
  ImportRowsRequest,
  ActivationFunnelQueryParams,
  SchoolUsageResponse,
} from './platform';
export { usageApi } from './platform';
// ANA-02: 数据分析 API（校级 + 平台级）
export { analyticsApi } from './analytics';
export type {
  SchoolAnalyticsResponse,
  ZeroResultsInsightResponse,
  PlatformAnalyticsResponse,
  MetricMeta,
  FunnelMetric,
  Retention7dMetric,
  SearchSuccessRateMetric,
  SearchZeroRateMetric,
  ShareSubscriptionConversionMetric,
  ContentValidRateMetric,
  GovernanceSlaMetric,
  AiUsageMetric,
  ZeroResultTopic,
  SchoolMetricItem,
  PlatformFunnelMetric,
  PlatformSearchMetric,
  PlatformAiUsageMetric,
  PlatformGovernanceMetric,
  AnalyticsQueryParams,
} from './analytics';
export { categoriesApi } from './categories';
export type {
  CategoryListItem,
  LocationListItem,
  CreateLocationRequest,
} from './categories';
// TOPIC-01.1: 用户端专题
export { topicsApi } from './topics';
export type {
  TopicListItem,
  TopicPostItem,
  TopicDetail,
} from './topics';
// TOPIC-01.2: 专题管理（admin 端类型从 ./admin 复用）
export type {
  TopicAdmin,
  TopicAdminDetail,
  TopicPostAdminItem,
  TopicCreateRequest,
  TopicUpdateRequest,
  TopicStatus as AdminTopicStatus,
} from './admin';
// SUB-01: 用户级内容订阅（分类/地点/专题）
export { subscriptionsApi } from './subscriptions';
