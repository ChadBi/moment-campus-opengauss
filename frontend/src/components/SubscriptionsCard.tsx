import React, { useCallback, useEffect, useState } from 'react';
import { Bell, Trash2, Tag, MapPin, FolderOpen } from 'lucide-react';
import { subscriptionsApi } from '../services/subscriptions';
import { useAuthStore } from '../store/useAuthStore';
import { useCampusStore } from '../store/useCampusStore';
import { Button } from './ui/Button';
import { Loading } from './ui/Loading';
import { Toast } from './ui/Toast';
import type { Subscription, SubscriptionTargetType } from '../types';
import { logger } from '../utils/logger';

/**
 * SUB-01: 我的订阅卡片
 *
 * 在「我的」页面展示当前用户在当前学校的全部订阅（分类/地点/专题），
 * 支持按目标类型筛选，并可直接取消订阅。
 *
 * 租户隔离：列表随当前学校切换自动重载（依赖 currentSchoolId）。
 */
const TARGET_TYPE_LABEL: Record<SubscriptionTargetType, string> = {
  category: '分类',
  location: '地点',
  topic: '专题',
};

const TARGET_TYPE_ICON: Record<SubscriptionTargetType, React.ReactNode> = {
  category: <Tag size={14} />,
  location: <MapPin size={14} />,
  topic: <FolderOpen size={14} />,
};

const TARGET_TYPE_FILTERS: Array<{ key: SubscriptionTargetType | 'all'; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'category', label: '分类' },
  { key: 'location', label: '地点' },
  { key: 'topic', label: '专题' },
];

const PAGE_SIZE = 20;

export const SubscriptionsCard: React.FC = () => {
  const { isAuthenticated } = useAuthStore();
  const { currentSchoolId, currentSchoolName } = useCampusStore();
  const [filter, setFilter] = useState<SubscriptionTargetType | 'all'>('all');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Subscription[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  const loadSubscriptions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await subscriptionsApi.listMySubscriptions({
        page,
        page_size: PAGE_SIZE,
        target_type: filter === 'all' ? undefined : filter,
      });
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      logger.error('加载订阅列表失败:', error);
      setToast({ message: '加载订阅列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [page, filter]);

  useEffect(() => {
    if (!isAuthenticated) return;
    void Promise.resolve().then(loadSubscriptions);
  }, [isAuthenticated, currentSchoolId, loadSubscriptions]);

  const handleFilterChange = (next: SubscriptionTargetType | 'all') => {
    setFilter(next);
    setPage(1);
  };

  const handleUnsubscribe = async (sub: Subscription) => {
    if (removingId) return;
    if (!window.confirm(`确定取消订阅「${sub.target_name ?? TARGET_TYPE_LABEL[sub.target_type]}」吗？`)) {
      return;
    }
    setRemovingId(sub.id);
    try {
      await subscriptionsApi.deleteSubscription(sub.id);
      setToast({ message: '已取消订阅', type: 'success' });
      // 重新加载当前页（若当前页删完后为空且非第 1 页，自动回退）
      if (items.length === 1 && page > 1) {
        setPage(page - 1);
      } else {
        void loadSubscriptions();
      }
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({
        message: e?.response?.data?.detail || '取消订阅失败',
        type: 'error',
      });
    } finally {
      setRemovingId(null);
    }
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-semibold text-ink flex items-center gap-2">
          <Bell size={18} className="text-lake" />
          我的订阅
        </h2>
        <span className="text-xs text-ink-muted bg-mist px-2 py-0.5 rounded-[6px]">
          {total} 项
        </span>
      </div>

      <div className="flex gap-1 overflow-x-auto pb-2 mb-3 -mx-1 px-1 border-b border-line/60">
        {TARGET_TYPE_FILTERS.map((tab) => {
          const isActive = filter === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => handleFilterChange(tab.key)}
              className={`px-3 py-1.5 rounded-[8px] text-xs font-medium whitespace-nowrap transition-colors ${
                isActive ? 'bg-lake text-white' : 'text-ink-sub hover:bg-paper-hover'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="py-8">
          <Loading text="加载中..." />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-8">
          <div className="text-[36px] leading-none mb-2">🔔</div>
          <p className="text-ink-sub text-sm">暂无订阅</p>
          <p className="text-ink-muted text-xs mt-1">
            在分类/地点/专题详情页点击「订阅」，有新内容时会通知你
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-0">
            {items.map((sub, idx) => (
              <div
                key={sub.id}
                className={`py-2.5 -mx-2 px-2 rounded-[10px] hover:bg-paper-hover transition-colors flex items-center gap-2 ${
                  idx > 0 ? 'border-t border-ink-divider/60' : ''
                }`}
              >
                <div className="w-7 h-7 rounded-[8px] bg-mist grid place-items-center text-lake flex-shrink-0">
                  {TARGET_TYPE_ICON[sub.target_type]}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium text-ink text-sm line-clamp-1">
                    {sub.target_name ?? `#${sub.target_id}`}
                  </h3>
                  <span className="text-[11px] text-ink-muted">
                    {TARGET_TYPE_LABEL[sub.target_type]}
                  </span>
                </div>
                <Button
                  variant="text"
                  size="sm"
                  disabled={removingId === sub.id}
                  onClick={() => handleUnsubscribe(sub)}
                  icon={<Trash2 size={12} />}
                >
                  取消
                </Button>
              </div>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                上一页
              </Button>
              <span className="text-xs text-ink-muted">
                {page} / {totalPages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages || loading}
                onClick={() => setPage((p) => p + 1)}
              >
                下一页
              </Button>
            </div>
          )}
        </>
      )}
      {currentSchoolName && (
        <p className="mt-3 text-[11px] text-ink-muted">
          订阅按当前学校「{currentSchoolName}」过滤，切换学校后将重新加载
        </p>
      )}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};
