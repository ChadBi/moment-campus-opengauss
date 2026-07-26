import React, { useEffect, useState } from 'react';
import { Bell, BellRing, Check } from 'lucide-react';
import { Button } from './ui/Button';
import { Toast } from './ui/Toast';
import { subscriptionsApi } from '../services/subscriptions';
import { useAuthStore } from '../store/useAuthStore';
import type { SubscriptionTargetType } from '../types';
import { logger } from '../utils/logger';

interface SubscribeButtonProps {
  target_type: SubscriptionTargetType;
  target_id: number;
  /** 可选：外部预订阅状态（如父组件已批量查询），未传则组件自查询 */
  initialSubscribed?: boolean;
  /** 可选：订阅记录 ID（与 initialSubscribed 配合使用，用于直接删除） */
  initialSubscriptionId?: number | null;
  /** 按钮尺寸（默认 sm） */
  size?: 'sm' | 'md' | 'lg';
  /** 按钮变体样式（未订阅时使用） */
  variant?: 'primary' | 'secondary' | 'text';
  /** 状态变更回调（外部刷新缓存用） */
  onChange?: (subscribed: boolean, subscriptionId: number | null) => void;
}

/**
 * SUB-01: 通用订阅按钮组件
 *
 * 用于在分类/地点/专题详情页展示订阅状态并支持一键订阅/取消订阅。
 *
 * 行为：
 * - 未登录：渲染为跳转登录样式（点击触发 toast 提示）
 * - 已登录未订阅：渲染"订阅"按钮，点击调用 POST /subscriptions
 * - 已登录已订阅：渲染"已订阅"按钮（次要样式），点击调用 DELETE /subscriptions/{id}
 *
 * 状态来源优先级：initialSubscribed（外部预查） > 自查询 GET /subscriptions/check
 * 切换后本地状态立即更新（乐观更新），同时通过 onChange 通知父组件。
 */
export const SubscribeButton: React.FC<SubscribeButtonProps> = ({
  target_type,
  target_id,
  initialSubscribed,
  initialSubscriptionId,
  size = 'sm',
  variant = 'primary',
  onChange,
}) => {
  const { isAuthenticated } = useAuthStore();
  const [subscribed, setSubscribed] = useState<boolean>(initialSubscribed ?? false);
  const [subscriptionId, setSubscriptionId] = useState<number | null>(
    initialSubscriptionId ?? null
  );
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  // 外部预订阅状态变化时同步（如父组件批量查询后传入）
  useEffect(() => {
    if (initialSubscribed !== undefined) {
      setSubscribed(initialSubscribed);
      setSubscriptionId(initialSubscriptionId ?? null);
    }
  }, [initialSubscribed, initialSubscriptionId]);

  // 外部未传初始状态时，登录后自查询一次
  useEffect(() => {
    if (initialSubscribed === undefined && isAuthenticated) {
      void subscriptionsApi
        .checkSubscription(target_type, target_id)
        .then((resp) => {
          setSubscribed(resp.subscribed);
          setSubscriptionId(resp.subscription_id ?? null);
        })
        .catch((err) => {
          // 静默失败：单点状态查询失败不阻塞页面渲染
          logger.warn('订阅状态查询失败:', err);
        });
    }
  }, [initialSubscribed, isAuthenticated, target_type, target_id]);

  const handleToggle = async () => {
    if (!isAuthenticated) {
      setToast({ message: '请先登录后再订阅', type: 'warning' });
      return;
    }
    if (loading) return;
    setLoading(true);
    try {
      if (subscribed && subscriptionId) {
        await subscriptionsApi.deleteSubscription(subscriptionId);
        setSubscribed(false);
        setSubscriptionId(null);
        setToast({ message: '已取消订阅', type: 'success' });
        onChange?.(false, null);
      } else {
        const sub = await subscriptionsApi.createSubscription({ target_type, target_id });
        setSubscribed(true);
        setSubscriptionId(sub.id);
        setToast({ message: '订阅成功，有新内容时会通知你', type: 'success' });
        onChange?.(true, sub.id);
      }
    } catch (error) {
      const e = error as { response?: { status?: number; data?: { detail?: string } } };
      // 409 冲突：已被订阅（可能并发提交），重新查询状态修正
      if (e?.response?.status === 409) {
        setSubscribed(true);
        setToast({ message: '该目标已订阅', type: 'info' });
      } else {
        setToast({
          message: e?.response?.data?.detail || '操作失败，请重试',
          type: 'error',
        });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        variant={subscribed ? 'secondary' : variant}
        size={size}
        loading={loading}
        onClick={handleToggle}
        icon={subscribed ? <Check size={14} /> : <Bell size={14} />}
      >
        {subscribed ? '已订阅' : '订阅'}
      </Button>
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </>
  );
};

/** 订阅状态徽标（用于列表/卡片角落，无交互） */
export const SubscribeBadge: React.FC<{ subscribed: boolean }> = ({ subscribed }) => {
  if (!subscribed) return null;
  return (
    <span className="inline-flex items-center gap-0.5 text-[10px] text-lake bg-lake/10 px-1.5 py-0.5 rounded-[4px]">
      <BellRing size={10} /> 已订阅
    </span>
  );
};
