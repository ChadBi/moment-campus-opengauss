import React, { useEffect, useState, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { usageApi, type SchoolUsageResponse } from '../../services/platform';
import { useUIStore } from '../../store/useUIStore';
import {
  AlertTriangle,
  RefreshCw,
  Users,
  FileText,
  Cpu,
  HardDrive,
  Mail,
  Clock,
} from 'lucide-react';

/** 权益 key → 中文标签 */
const ENTITLEMENT_LABELS: Record<string, string> = {
  members_max: '成员上限',
  posts_max: '信息上限',
  storage_mb: '存储 (MB)',
  ai_calls_daily: 'AI 调用/日',
};

/** 权益 code → Badge variant */
const codeBadgeVariant = (
  code: string
): 'success' | 'warning' | 'danger' | 'default' => {
  if (code === 'ENT_OK' || code === 'ENT_ENTITLEMENT_MISSING') return 'success';
  if (code === 'ENT_WARNING_80' || code === 'ENT_WARNING_100') return 'warning';
  if (code === 'ENT_WARNING_SOFT_EXCEEDED') return 'warning';
  if (
    code === 'ENT_LIMIT_HARD_EXCEEDED' ||
    code === 'ENT_NO_SUBSCRIPTION' ||
    code === 'ENT_SUBSCRIPTION_EXPIRING'
  ) {
    return 'danger';
  }
  return 'default';
};

const UsagePage: React.FC = () => {
  const [usage, setUsage] = useState<SchoolUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const showToast = useUIStore((s) => s.showToast);

  const loadData = useCallback(async () => {
    try {
      const data = await usageApi.getSchoolUsage();
      setUsage(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '加载用量数据失败';
      console.error('加载用量数据失败:', err);
      showToast(message, 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    void loadData();
  };

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

  if (!usage) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-sub">加载用量数据失败</p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={handleRefresh}
        >
          重新加载
        </Button>
      </div>
    );
  }

  const stats = [
    {
      title: '成员数',
      value: usage.stats.members_count,
      icon: Users,
      color: 'text-grass',
      bgColor: 'bg-grass/15',
    },
    {
      title: '信息数',
      value: usage.stats.posts_count,
      icon: FileText,
      color: 'text-lake',
      bgColor: 'bg-lake/10',
    },
    {
      title: '今日 AI 调用',
      value: usage.stats.ai_calls_today,
      icon: Cpu,
      color: 'text-lamp',
      bgColor: 'bg-lamp/15',
    },
    {
      title: '存储 (MB)',
      value: usage.stats.storage_used_mb,
      icon: HardDrive,
      color: 'text-info',
      bgColor: 'bg-info/10',
    },
  ];

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">用量与套餐</h1>
          <p className="text-ink-sub text-sm mt-1">
            当前学校套餐与额度使用情况（统计口径：{usage.stats.stat_basis}）
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

      {/* 当前套餐卡片 */}
      <Card variant="outlined" padding="md">
        <div className="flex flex-wrap items-start gap-4">
          <div className="flex-1 min-w-[200px]">
            <p className="text-ink-muted text-xs mb-1">当前套餐</p>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-2xl font-bold text-ink">
                {usage.plan_name || usage.plan_code || '未开通'}
              </span>
              {usage.plan_code && (
                <Badge variant="info">{usage.plan_code}</Badge>
              )}
              {usage.subscription_status && (
                <Badge
                  variant={
                    usage.subscription_status === 'active'
                      ? 'success'
                      : 'danger'
                  }
                >
                  {usage.subscription_status === 'active'
                    ? '已激活'
                    : usage.subscription_status === 'suspended'
                    ? '已暂停'
                    : '已过期'}
                </Badge>
              )}
            </div>
            {usage.subscription_expires_at && (
              <p className="text-ink-sub text-xs mt-2 flex items-center gap-1">
                <Clock size={12} />
                到期时间：
                {new Date(usage.subscription_expires_at).toLocaleString(
                  'zh-CN'
                )}
                {usage.days_to_expire !== null &&
                  usage.days_to_expire !== undefined && (
                    <span className="ml-2">
                      （剩余 {usage.days_to_expire} 天）
                    </span>
                  )}
              </p>
            )}
          </div>
          <div className="text-right">
            <p className="text-ink-muted text-xs mb-1">最后更新</p>
            <p className="text-sm text-ink-sub">
              {usage.stats.last_updated_at
                ? new Date(usage.stats.last_updated_at).toLocaleString('zh-CN')
                : '暂无统计快照'}
            </p>
          </div>
        </div>
      </Card>

      {/* 告警区 */}
      {usage.alerts.length > 0 && (
        <Card variant="filled" padding="md">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={18} className="text-lamp" />
            <h2 className="text-base font-semibold text-ink">
              告警（{usage.alerts.length}）
            </h2>
          </div>
          <ul className="space-y-2">
            {usage.alerts.map((alert, idx) => (
              <li
                key={`${alert.key}-${idx}`}
                className="flex items-start gap-2 text-sm"
              >
                <Badge
                  variant={alert.severity === 'critical' ? 'danger' : 'warning'}
                  className="mt-0.5 shrink-0"
                >
                  {alert.severity === 'critical' ? '严重' : '提醒'}
                </Badge>
                <span className="text-ink-sub flex-1">{alert.message}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* 实时统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((card, idx) => {
          const Icon = card.icon;
          return (
            <Card key={idx} variant="outlined" padding="md">
              <div className="flex items-center gap-3">
                <div className={`${card.bgColor} p-2.5 rounded-md`}>
                  <Icon className={card.color} size={20} />
                </div>
                <div className="min-w-0">
                  <p className="text-ink-muted text-xs">{card.title}</p>
                  <p className="text-xl font-bold text-ink">{card.value}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* 各额度余量 */}
      <Card variant="outlined" padding="md">
        <h2 className="text-base font-semibold text-ink mb-4">额度余量</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-muted border-b border-line">
                <th className="py-2 pr-4 font-medium">权益项</th>
                <th className="py-2 pr-4 font-medium">限额</th>
                <th className="py-2 pr-4 font-medium">已用</th>
                <th className="py-2 pr-4 font-medium">剩余</th>
                <th className="py-2 pr-4 font-medium">类型</th>
                <th className="py-2 pr-4 font-medium">状态</th>
                <th className="py-2 font-medium">说明</th>
              </tr>
            </thead>
            <tbody>
              {usage.entitlements.map((ent) => {
                const label = ENTITLEMENT_LABELS[ent.key] || ent.key;
                const limitText =
                  ent.limit_value === null || ent.limit_value === 0
                    ? '不限'
                    : String(ent.limit_value);
                const remainingText =
                  ent.remaining === null ? '不限' : String(ent.remaining);
                const usagePercent =
                  ent.limit_value &&
                  ent.limit_value > 0 &&
                  ent.current_value !== null
                    ? Math.min(
                        100,
                        Math.round(
                          (Number(ent.current_value) / ent.limit_value) * 100
                        )
                      )
                    : 0;
                return (
                  <tr
                    key={ent.key}
                    className="border-b border-line/50 last:border-b-0"
                  >
                    <td className="py-2.5 pr-4 font-medium text-ink">
                      {label}
                    </td>
                    <td className="py-2.5 pr-4 text-ink-sub">{limitText}</td>
                    <td className="py-2.5 pr-4 text-ink-sub">
                      {ent.current_value ?? '-'}
                      {ent.limit_value && ent.limit_value > 0 && (
                        <span className="ml-1 text-xs text-ink-muted">
                          ({usagePercent}%)
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 pr-4 text-ink-sub">
                      {remainingText}
                    </td>
                    <td className="py-2.5 pr-4">
                      <Badge variant={ent.is_hard ? 'danger' : 'info'}>
                        {ent.is_hard ? '硬限制' : '软限制'}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-4">
                      <Badge variant={codeBadgeVariant(ent.code)}>
                        {ent.code === 'ENT_OK'
                          ? '正常'
                          : ent.code === 'ENT_WARNING_80'
                          ? '80% 告警'
                          : ent.code === 'ENT_WARNING_100'
                          ? '100% 告警'
                          : ent.code === 'ENT_WARNING_SOFT_EXCEEDED'
                          ? '软超'
                          : ent.code === 'ENT_LIMIT_HARD_EXCEEDED'
                          ? '硬超'
                          : ent.code === 'ENT_NO_SUBSCRIPTION'
                          ? '无套餐'
                          : ent.code}
                      </Badge>
                    </td>
                    <td className="py-2.5 text-ink-muted text-xs">
                      {ent.message}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* 联系平台入口 */}
      <Card variant="filled" padding="md">
        <div className="flex items-center gap-3">
          <Mail size={20} className="text-lake" />
          <div className="flex-1">
            <p className="text-sm font-medium text-ink">需要扩容或续期？</p>
            <p className="text-xs text-ink-muted mt-0.5">
              {usage.contact_platform_hint}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default UsagePage;
