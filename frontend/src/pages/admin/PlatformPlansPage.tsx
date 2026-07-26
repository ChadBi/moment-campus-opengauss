import React, { useEffect, useState, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import {
  platformApi,
  type SubscriptionListResponse,
  type SubscriptionAssignRequest,
  type SubscriptionUpdateRequest,
} from '../../services/platform';
import { useUIStore } from '../../store/useUIStore';
import { useAuthStore } from '../../store/useAuthStore';
import type { PlatformPlan, PlatformSubscription } from '../../types';
import {
  RefreshCw,
  Package,
  CreditCard,
  Calendar,
  Plus,
  Pencil,
  Ban,
  Play,
} from 'lucide-react';

/** 权益 key 中文标签 */
const ENTITLEMENT_LABELS: Record<string, string> = {
  members_max: '成员上限',
  posts_max: '信息上限',
  storage_mb: '存储 (MB)',
  ai_calls_daily: 'AI 调用/日',
};

/** 订阅状态 → Badge variant */
const statusVariant = (
  status: string
): 'success' | 'warning' | 'danger' | 'default' => {
  if (status === 'active') return 'success';
  if (status === 'suspended') return 'warning';
  if (status === 'expired' || status === 'cancelled') return 'danger';
  return 'default';
};

/** 订阅状态中文 */
const statusLabel = (status: string): string => {
  const map: Record<string, string> = {
    active: '已激活',
    suspended: '已暂停',
    expired: '已过期',
    cancelled: '已取消',
  };
  return map[status] || status;
};

const PlatformPlansPage: React.FC = () => {
  const { user } = useAuthStore();
  const isSuperAdmin = user?.role === 'super_admin';
  const showToast = useUIStore((s) => s.showToast);

  const [plans, setPlans] = useState<PlatformPlan[]>([]);
  const [subscriptions, setSubscriptions] =
    useState<SubscriptionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('');

  // 分配/编辑订阅弹窗
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [editingSub, setEditingSub] = useState<PlatformSubscription | null>(
    null
  );
  const [assignSchoolId, setAssignSchoolId] = useState<number | null>(null);
  const [formData, setFormData] = useState<{
    plan_code: string;
    expires_at: string;
    note: string;
    status: string;
  }>({ plan_code: '', expires_at: '', note: '', status: 'active' });
  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [plansData, subsData] = await Promise.all([
        platformApi.listPlans(),
        platformApi.listSubscriptions({
          page,
          page_size: 10,
          status: statusFilter || undefined,
        }),
      ]);
      setPlans(plansData);
      setSubscriptions(subsData);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '加载套餐数据失败';
      showToast(message, 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, statusFilter, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    void loadData();
  };

  /** 打开编辑订阅弹窗 */
  const openEditModal = (sub: PlatformSubscription) => {
    setEditingSub(sub);
    setAssignSchoolId(sub.school_id);
    setFormData({
      plan_code: sub.plan_code || '',
      expires_at: sub.expires_at
        ? new Date(sub.expires_at).toISOString().slice(0, 16)
        : '',
      note: sub.note || '',
      status: sub.status,
    });
    setAssignModalOpen(true);
  };

  /** 提交分配/编辑 */
  const handleSubmit = async () => {
    if (!assignSchoolId) return;
    if (!formData.plan_code) {
      showToast('请选择套餐', 'error');
      return;
    }
    setSubmitting(true);
    try {
      if (editingSub) {
        // 编辑现有订阅
        const updateData: SubscriptionUpdateRequest = {
          status: formData.status,
          expires_at: formData.expires_at
            ? new Date(formData.expires_at).toISOString()
            : null,
          note: formData.note || undefined,
        };
        await platformApi.updateSubscription(editingSub.id, updateData);
        showToast('订阅更新成功', 'success');
      } else {
        // 分配新订阅
        const assignData: SubscriptionAssignRequest = {
          plan_code: formData.plan_code,
          expires_at: formData.expires_at
            ? new Date(formData.expires_at).toISOString()
            : null,
          note: formData.note || undefined,
        };
        await platformApi.assignSubscription(assignSchoolId, assignData);
        showToast('套餐分配成功', 'success');
      }
      setAssignModalOpen(false);
      void loadData();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '操作失败';
      showToast(message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isSuperAdmin) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-sub">仅超级管理员可访问平台套餐管理</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="py-16 flex items-center justify-center">
        <div className="flex items-center gap-3 text-ink-muted">
          <div className="w-5 h-5 border-2 border-lake/30 border-t-lake rounded-full animate-spin" />
          <span>加载中...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">套餐管理</h1>
          <p className="text-ink-sub text-sm mt-1">
            管理产品套餐、权益项与学校订阅
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={<RefreshCw size={14} />}
          loading={refreshing}
          onClick={handleRefresh}
        >
          刷新
        </Button>
      </div>

      {/* 套餐字典 */}
      <div>
        <h2 className="text-base font-semibold text-ink mb-3 flex items-center gap-2">
          <Package size={18} className="text-lake" />
          套餐字典（{plans.length}）
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {plans.map((plan) => (
            <Card key={plan.id} variant="outlined" padding="md">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-ink">
                      {plan.name}
                    </span>
                    <Badge variant="info">{plan.code}</Badge>
                  </div>
                  {plan.description && (
                    <p className="text-xs text-ink-muted mt-1">
                      {plan.description}
                    </p>
                  )}
                </div>
                <Badge
                  variant={plan.status === 'active' ? 'success' : 'default'}
                >
                  {plan.status === 'active' ? '启用' : '停用'}
                </Badge>
              </div>
              <div className="space-y-1.5">
                {plan.entitlements.length === 0 ? (
                  <p className="text-xs text-ink-muted">无权益项</p>
                ) : (
                  plan.entitlements.map((ent) => (
                    <div
                      key={ent.id}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="text-ink-sub">
                        {ENTITLEMENT_LABELS[ent.key] || ent.key}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-ink font-medium">
                          {ent.limit_value === null || ent.limit_value === 0
                            ? '不限'
                            : String(ent.limit_value)}
                        </span>
                        <Badge variant={ent.is_hard ? 'danger' : 'default'}>
                          {ent.is_hard ? '硬' : '软'}
                        </Badge>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* 订阅列表 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-ink flex items-center gap-2">
            <CreditCard size={18} className="text-lake" />
            学校订阅
            {subscriptions && (
              <span className="text-ink-muted text-sm">
                （共 {subscriptions.total} 条）
              </span>
            )}
          </h2>
          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="h-9 px-3 bg-paper border border-line rounded-[10px] text-sm text-ink focus:outline-none focus:border-lake"
            >
              <option value="">全部状态</option>
              <option value="active">已激活</option>
              <option value="suspended">已暂停</option>
              <option value="expired">已过期</option>
            </select>
          </div>
        </div>

        {subscriptions && subscriptions.items.length > 0 ? (
          <Card variant="outlined" padding="none">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-ink-muted border-b border-line">
                    <th className="py-3 px-4 font-medium">学校 ID</th>
                    <th className="py-3 px-4 font-medium">套餐</th>
                    <th className="py-3 px-4 font-medium">状态</th>
                    <th className="py-3 px-4 font-medium">开始时间</th>
                    <th className="py-3 px-4 font-medium">到期时间</th>
                    <th className="py-3 px-4 font-medium">备注</th>
                    <th className="py-3 px-4 font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {subscriptions.items.map((sub) => (
                    <tr
                      key={sub.id}
                      className="border-b border-line/50 last:border-b-0 hover:bg-paper-hover/50"
                    >
                      <td className="py-3 px-4 text-ink">#{sub.school_id}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5">
                          <span className="text-ink font-medium">
                            {sub.plan_name || sub.plan_code || '-'}
                          </span>
                          {sub.plan_code && (
                            <Badge variant="info">{sub.plan_code}</Badge>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={statusVariant(sub.status)}>
                          {statusLabel(sub.status)}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-ink-sub text-xs">
                        {new Date(sub.started_at).toLocaleDateString('zh-CN')}
                      </td>
                      <td className="py-3 px-4 text-ink-sub text-xs">
                        {sub.expires_at
                          ? new Date(sub.expires_at).toLocaleDateString('zh-CN')
                          : '不限'}
                      </td>
                      <td className="py-3 px-4 text-ink-muted text-xs max-w-[200px] truncate">
                        {sub.note || '-'}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1">
                          <Button
                            variant="text"
                            size="sm"
                            icon={<Pencil size={14} />}
                            onClick={() => openEditModal(sub)}
                          >
                            编辑
                          </Button>
                          {sub.status === 'active' && (
                            <Button
                              variant="text"
                              size="sm"
                              className="text-lamp"
                              icon={<Ban size={14} />}
                              onClick={() => openEditModal(sub)}
                            >
                              暂停
                            </Button>
                          )}
                          {sub.status === 'suspended' && (
                            <Button
                              variant="text"
                              size="sm"
                              className="text-grass"
                              icon={<Play size={14} />}
                              onClick={() => openEditModal(sub)}
                            >
                              恢复
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 分页 */}
            {subscriptions.total_pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-line">
                <span className="text-xs text-ink-muted">
                  第 {subscriptions.page} / {subscriptions.total_pages} 页
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(page - 1)}
                  >
                    上一页
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page >= subscriptions.total_pages}
                    onClick={() => setPage(page + 1)}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            )}
          </Card>
        ) : (
          <Card variant="filled" padding="md">
            <p className="text-center text-ink-muted text-sm">
              暂无订阅记录
            </p>
          </Card>
        )}
      </div>

      {/* 分配/编辑订阅弹窗 */}
      <Modal
        isOpen={assignModalOpen}
        onClose={() => setAssignModalOpen(false)}
        title={editingSub ? '编辑订阅' : '分配套餐'}
        size="md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">
              套餐
              <span className="text-danger ml-1">*</span>
            </label>
            <select
              value={formData.plan_code}
              onChange={(e) =>
                setFormData({ ...formData, plan_code: e.target.value })
              }
              disabled={!!editingSub}
              className="w-full h-10 px-3.5 bg-paper border border-line rounded-[10px] text-sm text-ink focus:outline-none focus:border-lake disabled:opacity-60"
            >
              {plans.map((p) => (
                <option key={p.id} value={p.code}>
                  {p.name}（{p.code}）
                </option>
              ))}
            </select>
          </div>

          {editingSub && (
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                状态
              </label>
              <select
                value={formData.status}
                onChange={(e) =>
                  setFormData({ ...formData, status: e.target.value })
                }
                className="w-full h-10 px-3.5 bg-paper border border-line rounded-[10px] text-sm text-ink focus:outline-none focus:border-lake"
              >
                <option value="active">已激活</option>
                <option value="suspended">已暂停</option>
                <option value="expired">已过期</option>
              </select>
            </div>
          )}

          <Input
            label="到期时间"
            type="datetime-local"
            value={formData.expires_at}
            onChange={(e) =>
              setFormData({ ...formData, expires_at: e.target.value })
            }
            icon={<Calendar size={16} />}
          />

          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">
              备注
            </label>
            <textarea
              value={formData.note}
              onChange={(e) =>
                setFormData({ ...formData, note: e.target.value })
              }
              rows={3}
              placeholder="分配原因 / 续期说明 / 暂停原因"
              className="w-full px-3.5 py-2 bg-paper border border-line rounded-[10px] text-sm text-ink placeholder:text-ink-muted/60 focus:outline-none focus:border-lake resize-none"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAssignModalOpen(false)}
            >
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={submitting}
              icon={editingSub ? undefined : <Plus size={14} />}
              onClick={handleSubmit}
            >
              {editingSub ? '保存' : '分配'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default PlatformPlansPage;
