import { api } from './api';
import type {
  PaginatedResponse,
  Subscription,
  SubscriptionCreateRequest,
  SubscriptionCheckResponse,
  SubscriptionTargetsResponse,
  SubscriptionTargetType,
} from '../types';

/**
 * SUB-01: 用户级内容订阅 API（分类/地点/专题）
 *
 * 后端端点（app/api/subscriptions.py）：
 *   GET    /subscriptions                 当前用户在当前学校的订阅列表
 *   POST   /subscriptions                 创建订阅（订阅某分类/地点/专题）
 *   DELETE /subscriptions/{subscription_id}  取消订阅
 *   GET    /subscriptions/check            检查是否已订阅某目标（按钮状态用）
 *   GET    /subscriptions/targets          按目标聚合：返回当前用户已订阅的
 *                                          category/location/topic ID 列表（批量渲染用）
 *
 * 租户隔离：通过 Axios 拦截器注入 X-School-Code 头实现跨校隔离。
 * 订阅与通知严格按学校隔离，跨校订阅不可见，跨校通知不触发。
 */
export const subscriptionsApi = {
  /** 获取当前用户在当前学校的订阅列表（支持按 target_type 筛选 + 分页） */
  listMySubscriptions: async (params?: {
    target_type?: SubscriptionTargetType;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Subscription>> => {
    const response = await api.get('/subscriptions', { params });
    return response.data;
  },

  /** 一次性返回当前用户已订阅的全部目标 ID（按 target_type 分组，前端批量渲染按钮状态用） */
  listMySubscriptionTargets: async (): Promise<SubscriptionTargetsResponse> => {
    const response = await api.get('/subscriptions/targets');
    return response.data;
  },

  /** 检查是否已订阅某目标（单点按钮状态用，跨校查询恒返回 subscribed=false） */
  checkSubscription: async (
    target_type: SubscriptionTargetType,
    target_id: number
  ): Promise<SubscriptionCheckResponse> => {
    const response = await api.get('/subscriptions/check', {
      params: { target_type, target_id },
    });
    return response.data;
  },

  /** 订阅某分类/地点/专题（同用户同校同目标只能订阅一次，重复订阅返回 409） */
  createSubscription: async (
    payload: SubscriptionCreateRequest
  ): Promise<Subscription> => {
    const response = await api.post('/subscriptions', payload);
    return response.data;
  },

  /** 取消订阅（按订阅记录 ID，仅可删除本人订阅） */
  deleteSubscription: async (subscriptionId: number): Promise<void> => {
    await api.delete(`/subscriptions/${subscriptionId}`);
  },
};
