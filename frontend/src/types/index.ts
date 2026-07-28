// ==========================================
// FND-01.3: 前端 TS 类型（与后端 OpenAPI schema 对齐）
// ==========================================

// ===== 枚举类型 =====

/** 帖子状态（6 态状态机） */
export type PostStatus =
  | 'draft'
  | 'pending'
  | 'published'
  | 'expired'
  | 'conflict'
  | 'archived';

/** 举报类型（5 类） */
export type ReportType =
  | 'spam'
  | 'abuse'
  | 'harassment'
  | 'false_info'
  | 'other';

/** 协同验证类型（5 类） */
export type ValidationType =
  | 'confirmation'
  | 'refutation'
  | 'update'
  | 'expiration_report'
  | 'conflict_report';

/** 问题报告类型（GOV-01，3 类） */
export type ChangeReportType = 'update' | 'expiration_report' | 'conflict_report';

/** 问题报告处理状态（GOV-01） */
export type ChangeReportStatus = 'open' | 'in_review' | 'resolved' | 'dismissed';

// ===== 关联数据（Brief 模型） =====

/** 作者/用户简要信息（后端 UserBrief） */
export interface Author {
  id: number;
  nickname: string;
  avatar_url?: string;
}

/** 分类简要信息（后端 CategoryBrief） */
export interface CategoryBrief {
  id: number;
  name: string;
  code: string;
  icon: string;
}

/** 地点简要信息（后端 LocationBrief） */
export interface LocationBrief {
  id: number;
  name: string;
  latitude?: number;
  longitude?: number;
  building?: string;
  floor?: string;
}

/** 帖子图片简要（后端 PostImageBrief） */
export interface PostImageBrief {
  id: number;
  image_url: string;
  thumbnail_url?: string;
  sort_order: number;
}

// ===== 用户类型 =====

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

// ===== 帖子类型 =====

/** 帖子详情（后端 PostResponse） */
export interface Post {
  id: number;
  user_id: number;
  school_id: number;
  category_id: number;
  location_id?: number;
  // ORG-01: 关联官方发布主体 ID（None 表示普通用户发布）
  publisher_id?: number;
  title: string;
  content: string;
  is_anonymous: boolean;
  status: PostStatus;
  view_count: number;
  like_count: number;
  comment_count: number;
  valid_count: number;
  invalid_count: number;
  expire_at?: string;
  lost_type?: string;
  contact_info?: string;
  is_recommend: boolean;
  created_at: string;
  updated_at: string;
  // 关联数据
  author?: Author;
  category?: CategoryBrief;
  location?: LocationBrief;
  images?: PostImageBrief[];
  // 前端需要的额外字段（由后端 PostResponse 注入）
  is_liked?: boolean;
  // GOV-01.4: 协同治理聚合（仅详情端点返回）
  governance?: GovernanceSummary;
}

/** 帖子列表项（后端 PostListResponse） */
export interface PostListItem {
  id: number;
  user_id: number;
  title: string;
  content: string;
  is_anonymous: boolean;
  status: PostStatus;
  category?: CategoryBrief;
  location?: LocationBrief;
  author?: Author;
  cover_image?: string;
  like_count: number;
  comment_count: number;
  view_count: number;
  valid_count: number;
  invalid_count: number;
  is_recommend: boolean;
  created_at: string;
  expire_at?: string;
}

// ===== 评论类型 =====

export interface Comment {
  id: number;
  post_id: number;
  user_id: number;
  parent_id?: number;
  reply_to_user_id?: number;
  content: string;
  like_count: number;
  status: string;
  created_at: string;
  updated_at?: string;
  // 关联数据
  author?: Author;
  reply_to_user?: Author;
  // 子评论列表（用于嵌套展示）
  replies?: Comment[];
  // 回复数量（用于分页加载）
  reply_count?: number;
}

// ===== 通知类型 =====

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
  actor?: Author;
}

// ===== 分类类型 =====

export interface Category {
  id: number;
  name: string;
  code: string;
  icon?: string;
  description?: string;
  default_validity_days?: number;
  sort_order?: number;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

// ===== 地点类型 =====

export interface Location {
  id: number;
  school_id: number;
  name: string;
  description?: string;
  latitude: number;
  longitude: number;
  floor?: string;
  building?: string;
  /** PUB-01.2: 是否已核验（用户自建地点为 false，进核验队列） */
  is_verified?: boolean;
}

// ===== 互动类型 =====

/** 点赞响应（后端 LikeResponse） */
export interface LikeResponse {
  post_id: number;
  like_count: number;
  is_liked: boolean;
}

/** 协同验证记录（后端 ValidationResponse） */
export interface ValidationRecord {
  id: number;
  post_id: number;
  user_id: number;
  validation_type: ValidationType;
  comment?: string;
  created_at: string;
  user?: Author;
}

/** 协同验证统计（后端 ValidationStatsResponse） */
export interface ValidationStats {
  post_id: number;
  valid_count: number;
  invalid_count: number;
  confirmation_count: number;
  refutation_count: number;
  total_count: number;
  validity_status: 'valid' | 'invalid' | 'uncertain';
  user_validation_type: ValidationType | null;
  records?: ValidationRecord[];
}

// ===== GOV-01 协同治理类型 =====

/** 投票记录响应（后端 ValidationVoteResponse） */
export interface ValidationVote {
  id: number;
  post_id: number;
  user_id: number;
  validation_type: ValidationType;
  comment?: string;
  created_at: string;
  user?: Author;
}

/** 聚合投票统计（后端 ValidationAggregation，GET /posts/{id}/validations） */
export interface ValidationAggregation {
  post_id: number;
  confirmation_count: number;
  refutation_count: number;
  total_count: number;
  validity_status: 'valid' | 'invalid' | 'uncertain';
  user_validation_type: ValidationType | null;
  recent_records: ValidationVote[];
}

/** 问题报告（后端 ChangeReportResponse） */
export interface ChangeReport {
  id: number;
  post_id: number;
  reporter_id: number;
  report_type: ChangeReportType;
  description?: string;
  evidence_url?: string;
  status: ChangeReportStatus;
  handler_id?: number;
  handler_note?: string;
  handled_at?: string;
  created_at: string;
  updated_at: string;
  reporter?: Author;
  handler?: Author;
}

/** 问题报告列表（后端 ChangeReportListResponse） */
export interface ChangeReportList {
  post_id: number;
  items: ChangeReport[];
  total: number;
  open_count: number;
}

/** 帖子详情治理聚合（后端 GovernanceSummary，嵌入 PostResponse.governance） */
export interface GovernanceSummary {
  confirmation_count: number;
  refutation_count: number;
  total_validation_count: number;
  validity_status: 'valid' | 'invalid' | 'uncertain';
  /** DSC-02.1: 当前登录用户对此帖的投票类型；游客恒为 null（前端据此隐藏投票按钮） */
  user_validation_type: ValidationType | null;
  change_reports_total: number;
  change_reports_open: number;
  recent_change_reports: ChangeReport[];
}

/** 状态流转响应（后端 PostTransitionResponse） */
export interface PostTransitionResponse {
  post_id: number;
  previous_status: PostStatus;
  current_status: PostStatus;
  transitioned_at: string;
  transitioned_by: number;
}

// ===== 举报类型 =====

/** 举报创建请求 */
export interface ReportCreate {
  report_type: ReportType;
  description?: string;
}

/** 举报记录 */
export interface Report {
  id: number;
  post_id?: number;
  comment_id?: number;
  reporter_id: number;
  report_type: ReportType;
  description?: string;
  status: string;
  handler_id?: number;
  handle_result?: string;
  handled_at?: string;
  created_at: string;
  updated_at: string;
}

// ===== 分页响应类型 =====

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_more: boolean;
}

// ===== API 响应类型 =====

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

// ===== 学校类型（TEN-03） =====

/** 学校简要（公开目录用） */
export interface School {
  id: number;
  code: string;
  name: string;
  logo_url?: string | null;
  province?: string | null;
  city?: string | null;
  center_lat?: number | null;
  center_lng?: number | null;
  map_zoom?: number | null;
  is_active?: boolean;
}

/** 学校成员关系 */
export interface SchoolMembership {
  id: number;
  school_id: number;
  role: string;
  status: string;
  is_default: boolean;
  joined_at: string;
  school: {
    id: number;
    code: string;
    name: string;
    logo_url?: string | null;
  };
}

// ===== 商业类型（COM-01 / COM-02） =====

/** 套餐权益项（后端 PlanEntitlementBrief） */
export interface PlanEntitlement {
  id: number;
  plan_id: number;
  key: string;
  limit_value: number | null;
  is_hard: boolean;
  description?: string | null;
}

/** 套餐详情（后端 PlanDetail） */
export interface PlatformPlan {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  status: string;
  sort_order: number;
  entitlements: PlanEntitlement[];
}

/** 订阅摘要（后端 SubscriptionBrief） */
export interface PlatformSubscription {
  id: number;
  school_id: number;
  plan_id: number;
  plan_code?: string | null;
  plan_name?: string | null;
  status: string;
  started_at: string;
  expires_at?: string | null;
  assigned_by?: number | null;
  assigned_at: string;
  note?: string | null;
  created_at: string;
  updated_at: string;
}

/** 平台学校简要（后端 SchoolBrief） */
export interface PlatformSchool {
  id: number;
  code: string;
  name: string;
  logo_url?: string | null;
  center_lat?: number | null;
  center_lng?: number | null;
  map_zoom?: number | null;
  province?: string | null;
  city?: string | null;
  address?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  member_count: number;
  post_count: number;
  category_count: number;
  subscription_status?: string | null;
  subscription_plan_code?: string | null;
  subscription_expires_at?: string | null;
}

/** 开通清单项 */
export interface ProvisioningChecklist {
  brand_set: boolean;
  admin_accepted: boolean;
  locations_imported: boolean;
  first_content: boolean;
  first_members: boolean;
  all_done: boolean;
}

/** 平台学校详情（后端 SchoolDetail） */
export interface PlatformSchoolDetail extends PlatformSchool {
  description?: string | null;
  brand_color?: string | null;
  checklist: ProvisioningChecklist;
}

/** 平台审计日志（后端 PlatformAuditBrief） */
export interface PlatformAuditLog {
  id: number;
  operator_id?: number | null;
  target_school_id?: number | null;
  action: string;
  old_value?: string | null;
  new_value?: string | null;
  reason?: string | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
}

/** 权益告警项 */
export interface EntitlementAlert {
  key: string;
  code: string;
  message: string;
  limit_value?: number | null;
  current_value?: number | null;
  is_hard?: boolean;
  severity: 'warning' | 'critical';
  expires_at?: string;
  days_to_expire?: number;
}

/** 学校告警响应（GET /platform/schools/{id}/alerts） */
export interface SchoolAlertsResponse {
  school_id: number;
  school_code: string;
  school_name: string;
  is_active: boolean;
  plan_code?: string | null;
  subscription_status?: string | null;
  subscription_expires_at?: string | null;
  days_to_expire?: number | null;
  entitlements: Array<{
    key: string;
    limit_value: number | null;
    is_hard: boolean;
    current_value: number | null;
    code: string;
    message: string;
    allowed: boolean;
  }>;
  alerts: EntitlementAlert[];
  alerts_count: number;
}

/** 全平台告警响应（GET /platform/alerts） */
export interface PlatformAlertsResponse {
  items: SchoolAlertsResponse[];
  total: number;
  alert_schools_count: number;
}

/** 批量导入预览行（地点） */
export interface ImportPreviewLocation {
  row_index: number;
  name: string;
  description?: string | null;
  latitude: number;
  longitude: number;
  floor?: string | null;
  building?: string | null;
}

/** 批量导入预览行（帖子） */
export interface ImportPreviewPost {
  row_index: number;
  title: string;
  content: string;
  category_code: string;
  category_id: number;
  location_name?: string;
  expire_at?: string | null;
  is_anonymous: boolean;
  contact_info?: string | null;
}

/** 批量导入预览错误 */
export interface ImportRowError {
  row_index: number;
  field: string;
  message: string;
}

/** 批量导入预览结果 */
export interface ImportPreviewResult {
  school_id: number;
  total_rows: number;
  locations_count: number;
  posts_count: number;
  valid: boolean;
  errors: ImportRowError[];
  locations: ImportPreviewLocation[];
  posts: ImportPreviewPost[];
}

/** 批量导入提交结果 */
export interface ImportCommitResult {
  batch_id: string;
  school_id: number;
  locations_created: number;
  posts_created: number;
  total_created: number;
  errors: ImportRowError[];
}

/** 批量导入响应（preview / commit 两种 mode） */
export interface ImportResponse {
  mode: 'preview' | 'commit';
  result: ImportPreviewResult | ImportCommitResult;
}

/** 激活漏斗单条（每校一行） */
export interface ActivationFunnelItem {
  school_id: number;
  school_code: string;
  school_name: string;
  is_active: boolean;
  plan_code?: string | null;
  subscription_status?: string | null;
  checklist: ProvisioningChecklist;
  activated: boolean;
  activated_stage: number;
}

/** 激活漏斗响应 */
export interface ActivationFunnelResponse {
  items: ActivationFunnelItem[];
  total: number;
  activated_count: number;
  avg_activated_stage: number;
}

/** 校级用量响应（GET /admin/usage） */
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
  alerts: EntitlementAlert[];
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

// ===== AI-02 AI 搜索类型 =====

/** AI 排序方式（在普通搜索排序基础上扩展 relevance） */
export type AISearchSort =
  | 'latest'
  | 'hottest'
  | 'nearest'
  | 'active'
  | 'relevance';

/** AI 解析的地图范围（可选筛选条件） */
export interface AISearchMapBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

/** 用户编辑后的筛选覆盖项（POST /search/ai overrides 字段） */
export interface AISearchOverrides {
  keyword?: string;
  category_id?: number;
  location_id?: number;
  sort?: AISearchSort;
  date_from?: string;
  date_to?: string;
}

/** AI 解析出的结构化筛选条件 */
export interface AISearchIntentFilters {
  keyword?: string | null;
  category_id?: number | null;
  category_name?: string | null;
  location_id?: number | null;
  sort: string;
  date_from?: string | null;
  date_to?: string | null;
  map_bounds?: AISearchMapBounds | null;
}

/** AI 解析出的完整意图 */
export interface AISearchIntent {
  intent: string;
  filters: AISearchIntentFilters;
  reasons: string[];
}

/** AI 搜索请求体（POST /search/ai） */
export interface AISearchRequest {
  query: string;
  overrides?: AISearchOverrides;
  page?: number;
  page_size?: number;
}

/** AI 搜索响应（POST /search/ai 返回结构） */
export interface AISearchResponse {
  items: PostListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_more: boolean;
  intent?: AISearchIntent | null;
  match_reasons: Record<number, string[]>;
  scores: Record<number, number>;
  fallback: boolean;
  fallback_reason?: string | null;
  ai_log_id?: number | null;
}

// ===== AI-03 AI 辅助发布建议类型 =====

/** AI 发布建议请求体（POST /posts/ai-suggest） */
export interface AIPublishSuggestRequest {
  title: string;
  content: string;
  category_id?: number | null;
  location_id?: number | null;
  /** Task 1.3 后向后兼容字段：标签模型已删除，AI 建议仍接收但不再实际处理 */
  tags?: string[] | null;
  contact_info?: string | null;
  lost_type?: string | null;
  expire_at?: string | null;
}

/** AI 返回的结构化建议（每项均可空，表示无建议） */
export interface AIPublishSuggestions {
  title?: string | null;
  summary?: string | null;
  /** 建议分类名（白名单校验前的原始值） */
  category?: string | null;
  /** 建议分类ID（白名单校验后的最终值；非法置空） */
  category_id?: number | null;
  /** 建议标签列表（白名单校验后的最终值） */
  tags: string[];
  /** 建议默认有效期天数（来自当前学校分类配置） */
  default_validity_days?: number | null;
}

/** AI 发布建议响应（POST /posts/ai-suggest 返回结构） */
export interface AIPublishSuggestionResponse {
  suggestions?: AIPublishSuggestions | null;
  /** 遗漏信息提示（前端逐项展示） */
  missing_info: string[];
  /** 敏感信息提醒（前端高亮展示） */
  sensitive_warnings: string[];
  /** 敏感信息命中明细 type→[matched...]，便于前端定位高亮 */
  sensitive_findings: Record<string, string[]>;
  /** 是否已降级（AI 失败 / 输入过短等） */
  fallback: boolean;
  fallback_reason?: string | null;
  ai_log_id?: number | null;
}

// ===== ORG-01 官方发布主体类型 =====

/** 主体类型：部门/社团/服务组织 */
export type PublisherType = 'department' | 'club' | 'service_org';

/** 认证状态：pending/verified/revoked/rejected（仅 admin 可流转） */
export type PublisherVerifiedStatus = 'pending' | 'verified' | 'revoked' | 'rejected';

/** 成员角色：owner/admin/member */
export type PublisherMemberRole = 'owner' | 'admin' | 'member';

/** 模板场景：营业时间/讲座/失物/通知/其他 */
export type PostTemplateScene =
  | 'business_hours'
  | 'lecture'
  | 'lost'
  | 'notification'
  | 'other';

/** 发布主体简要（列表用） */
export interface PublisherBrief {
  id: number;
  name: string;
  type: PublisherType;
  logo_url?: string | null;
  verified_status: PublisherVerifiedStatus;
  intro?: string | null;
  subscribe_count: number;
  view_count: number;
}

/** 发布主体成员关系简要 */
export interface PublisherMembershipBrief {
  id: number;
  user_id: number;
  role: PublisherMemberRole;
  joined_at: string;
  user_nickname?: string | null;
  user_email?: string | null;
}

/** 发布主体最近内容简要 */
export interface PublisherPostBrief {
  id: number;
  title: string;
  status: PostStatus;
  category_id?: number | null;
  category_name?: string | null;
  created_at: string;
  view_count: number;
  like_count: number;
}

/** 发布主体详情（公开主页） */
export interface PublisherProfile {
  id: number;
  school_id: number;
  name: string;
  type: PublisherType;
  intro?: string | null;
  logo_url?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  service_hours?: string | null;
  contact?: string | null;
  verified_status: PublisherVerifiedStatus;
  verified_at?: string | null;
  view_count: number;
  subscribe_count: number;
  share_count: number;
  valid_feedback_count: number;
  invalid_feedback_count: number;
  zero_result_count: number;
  created_at: string;
  updated_at: string;
  /** 当前用户是否为该主体成员 */
  is_member: boolean;
  /** 当前用户在该主体的角色（非成员为 null） */
  my_role?: PublisherMemberRole | null;
}

/** 发布主体详情响应（含成员与最近内容） */
export interface PublisherDetail extends PublisherProfile {
  memberships: PublisherMembershipBrief[];
  recent_posts: PublisherPostBrief[];
}

/** 发布主体聚合效果（ORG-01.4） */
export interface PublisherAggregation {
  publisher_id: number;
  publisher_name: string;
  view_count: number;
  subscribe_count: number;
  share_count: number;
  valid_feedback_count: number;
  invalid_feedback_count: number;
  zero_result_count: number;
  total_posts: number;
  published_posts: number;
  pending_posts: number;
  /** 有效性反馈率（valid / (valid + invalid)），分母为 0 时为 null */
  valid_rate?: number | null;
}

/** 管理端发布主体详情（含审核字段） */
export interface PublisherAdmin {
  id: number;
  school_id: number;
  name: string;
  type: PublisherType;
  intro?: string | null;
  logo_url?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  service_hours?: string | null;
  contact?: string | null;
  verified_status: PublisherVerifiedStatus;
  verified_at?: string | null;
  verified_by?: number | null;
  verified_by_name?: string | null;
  verify_note?: string | null;
  view_count: number;
  subscribe_count: number;
  share_count: number;
  valid_feedback_count: number;
  invalid_feedback_count: number;
  zero_result_count: number;
  created_at: string;
  updated_at: string;
  member_count: number;
}

/** 发布模板响应 */
export interface PostTemplate {
  id: number;
  school_id: number;
  publisher_id?: number | null;
  publisher_name?: string | null;
  name: string;
  title_template: string;
  content_template: string;
  category_id?: number | null;
  scene: PostTemplateScene;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** 创建发布主体请求 */
export interface PublisherCreateRequest {
  name: string;
  type: PublisherType;
  intro?: string;
  logo_url?: string;
  location_id?: number;
  service_hours?: string;
  contact?: string;
}

/** 更新发布主体请求 */
export interface PublisherUpdateRequest {
  name?: string;
  intro?: string;
  logo_url?: string;
  location_id?: number;
  service_hours?: string;
  contact?: string;
}

/** 审核动作：approve/reject/revoke/restore */
export type PublisherVerifyAction = 'approve' | 'reject' | 'revoke' | 'restore';

/** 创建/更新模板请求 */
export interface PostTemplateCreateRequest {
  publisher_id?: number | null;
  name: string;
  title_template: string;
  content_template: string;
  category_id?: number | null;
  scene: PostTemplateScene;
  sort_order?: number;
}

// ===== REC-01 推荐类型 =====

/** 推荐项 = PostListItem + 推荐原因 + 综合分 */
export interface RecommendationItem extends PostListItem {
  reason: string;
  score: number;
}

/** 推荐模式说明 */
export interface RecommendationMode {
  personalized: boolean;
  reason_code:
    | 'personalized'
    | 'cold_start_no_history'
    | 'cold_start_disabled'
    | 'cold_start_guest';
}

/** 推荐列表响应（含模式说明） */
export interface RecommendationResponse {
  items: RecommendationItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_more: boolean;
  mode: RecommendationMode;
}

/** 推荐隐私偏好 */
export interface RecommendationPreference {
  personalization_enabled: boolean;
  updated_at: string;
}

// ===== SUB-01 订阅类型 =====

/** 订阅目标类型：分类/地点/专题 */
export type SubscriptionTargetType = 'category' | 'location' | 'topic';

/** 订阅记录（后端 SubscriptionResponse） */
export interface Subscription {
  id: number;
  user_id: number;
  school_id: number;
  target_type: SubscriptionTargetType;
  target_id: number;
  target_name?: string | null;
  created_at: string;
}

/** 创建订阅请求 */
export interface SubscriptionCreateRequest {
  target_type: SubscriptionTargetType;
  target_id: number;
}

/** 订阅状态检查响应（前端按钮状态用） */
export interface SubscriptionCheckResponse {
  subscribed: boolean;
  subscription_id?: number | null;
}

/** 当前用户已订阅的目标 ID 列表（按类型分组） */
export interface SubscriptionTargetsResponse {
  category: number[];
  location: number[];
  topic: number[];
}

/** 订阅通知类型常量（与后端 SubscriptionNotificationType 对齐） */
export type SubscriptionNotificationType =
  | 'subscription_new'
  | 'subscription_update'
  | 'subscription_expired'
  | 'subscription_conflict';
