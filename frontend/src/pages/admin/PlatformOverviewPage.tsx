import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { platformApi } from '../../services/platform';
import { analyticsApi } from '../../services/analytics';
import type { PlatformAnalyticsResponse } from '../../services/analytics';
import type { PlatformOverview } from '../../services/admin';
import { useUIStore } from '../../store/useUIStore';
import {
  School as SchoolIcon,
  Users,
  ShieldCheck,
  Cpu,
  AlertTriangle,
  ClipboardList,
  RefreshCw,
  TrendingUp,
  Search,
  Clock,
  Filter,
} from 'lucide-react';
import { formatShortDateTime } from '../../utils/date';

const formatRate = (rate: number) => `${(rate * 100).toFixed(1)}%`;
const formatNumber = (n: number) => n.toLocaleString('zh-CN');
const formatSeconds = (sec: number): string => {
  if (sec <= 0) return '-';
  if (sec < 60) return `${sec.toFixed(0)} 秒`;
  if (sec < 3600) return `${(sec / 60).toFixed(1)} 分`;
  return `${(sec / 3600).toFixed(1)} 时`;
};
const formatDateTime = (iso: string | null): string =>
  formatShortDateTime(iso);

/** ADM-01.2: 平台首页跨校统计（仅 super_admin，入口在菜单中按角色隐藏） */
const PlatformOverviewPage: React.FC = () => {
  const showToast = useUIStore((s) => s.showToast);
  const [data, setData] = useState<PlatformOverview | null>(null);
  const [analytics, setAnalytics] = useState<PlatformAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyticsWindowDays, setAnalyticsWindowDays] = useState<number>(30);
  const [analyticsRefreshing, setAnalyticsRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [result, analyticsResult] = await Promise.all([
        platformApi.getOverview(),
        analyticsApi.getPlatformAnalytics({ window_days: analyticsWindowDays }),
      ]);
      setData(result);
      setAnalytics(analyticsResult);
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载平台统计失败';
      showToast(message, 'error');
    } finally {
      setLoading(false);
      setAnalyticsRefreshing(false);
    }
  }, [showToast, analyticsWindowDays]);

  const handleRefreshAnalytics = () => {
    setAnalyticsRefreshing(true);
    void loadData();
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadData();
  }, [loadData]);

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

  if (!data) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-sub">加载平台统计失败</p>
        <button onClick={() => void loadData()} className="mt-3 text-sm text-lake hover:underline">
          重新加载
        </button>
      </div>
    );
  }

  const summaryCards = [
    {
      title: '学校总数',
      value: data.school_total,
      sub: `正常 ${data.school_active} / 暂停 ${data.school_inactive}`,
      icon: SchoolIcon,
      color: 'text-lake',
      bgColor: 'bg-lake/10',
    },
    {
      title: '活跃成员',
      value: data.active_members,
      sub: '全平台 active 成员',
      icon: Users,
      color: 'text-grass',
      bgColor: 'bg-grass/15',
    },
    {
      title: '内容治理量',
      value: data.governance_total,
      sub: `待审 ${data.pending_posts} · 举报 ${data.pending_reports}`,
      icon: ShieldCheck,
      color: 'text-lamp',
      bgColor: 'bg-lamp/10',
    },
    {
      title: 'AI 调用降级率',
      value: formatRate(data.ai_fallback_rate),
      sub: `${data.ai_fallback_total}/${data.ai_calls_total} 次降级`,
      icon: Cpu,
      color: 'text-info',
      bgColor: 'bg-info/10',
    },
    {
      title: '异常租户',
      value: data.abnormal_tenants.length,
      sub: '暂停 / 高降级 / 订阅异常',
      icon: AlertTriangle,
      color: 'text-danger',
      bgColor: 'bg-danger/10',
    },
  ];

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">平台首页</h1>
          <p className="text-ink-sub text-sm mt-1">跨校统计概览（仅超级管理员可见）</p>
        </div>
        <button
          onClick={() => void loadData()}
          className="flex items-center gap-1.5 text-sm text-ink-sub hover:text-lake transition-colors"
        >
          <RefreshCw size={14} />
          刷新
        </button>
      </div>

      {/* 汇总卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
        {summaryCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.title} variant="outlined" padding="md">
              <div className="flex items-center gap-3">
                <div className={`${card.bgColor} p-2.5 rounded-md shrink-0`}>
                  <Icon className={card.color} size={20} />
                </div>
                <div className="min-w-0">
                  <p className="text-ink-muted text-xs">{card.title}</p>
                  <p className="text-xl font-bold text-ink">{card.value}</p>
                  <p className="text-[11px] text-ink-muted truncate">{card.sub}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 各校 AI 调用降级率 */}
        <Card variant="outlined" padding="md">
          <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
            <Cpu size={18} className="text-info" />
            各校 AI 调用降级率
          </h2>
          {data.ai_stats.length === 0 ? (
            <p className="text-sm text-ink-muted text-center py-6">暂无 AI 调用记录</p>
          ) : (
            <ul className="space-y-2.5">
              {data.ai_stats.map((stat) => (
                <li key={stat.school_id} className="flex items-center gap-3 text-sm">
                  <div className="w-32 shrink-0 truncate">
                    <p className="font-medium text-ink truncate">{stat.school_name || `#${stat.school_id}`}</p>
                    <p className="text-[11px] text-ink-muted">{stat.school_code}</p>
                  </div>
                  <div className="flex-1">
                    <div className="h-2 rounded-full bg-mist overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          stat.fallback_rate >= 0.5 ? 'bg-danger' : stat.fallback_rate >= 0.2 ? 'bg-sun' : 'bg-grass'
                        }`}
                        style={{ width: `${Math.min(100, stat.fallback_rate * 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="w-28 shrink-0 text-right">
                    <span className={`font-semibold ${stat.fallback_rate >= 0.5 ? 'text-danger' : 'text-ink'}`}>
                      {formatRate(stat.fallback_rate)}
                    </span>
                    <span className="text-[11px] text-ink-muted ml-1">
                      ({stat.fallback_calls}/{stat.ai_calls})
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* 异常租户 */}
        <Card variant="outlined" padding="md">
          <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
            <AlertTriangle size={18} className="text-danger" />
            异常租户
            {data.abnormal_tenants.length > 0 && (
              <Badge variant="danger">{data.abnormal_tenants.length}</Badge>
            )}
          </h2>
          {data.abnormal_tenants.length === 0 ? (
            <p className="text-sm text-ink-muted text-center py-6">所有租户运行正常</p>
          ) : (
            <ul className="space-y-3">
              {data.abnormal_tenants.map((tenant) => (
                <li key={tenant.school_id} className="text-sm border-b border-ink-divider last:border-0 pb-3 last:pb-0">
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-ink">
                      {tenant.school_name || `#${tenant.school_id}`}
                      <span className="text-[11px] text-ink-muted ml-1.5">{tenant.school_code}</span>
                    </p>
                    <Link
                      to="/admin/platform/schools"
                      className="text-xs text-lake hover:underline shrink-0"
                    >
                      前往处理
                    </Link>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {tenant.reasons.map((reason, idx) => (
                      <Badge key={idx} variant="warning">{reason}</Badge>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* 最近开通记录 */}
      <Card variant="outlined" padding="md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-ink flex items-center gap-2">
            <ClipboardList size={18} className="text-lake" />
            最近开通记录
          </h2>
          <Link to="/admin/platform/schools" className="text-xs text-lake hover:underline">
            学校管理
          </Link>
        </div>
        {data.activation_records.length === 0 ? (
          <p className="text-sm text-ink-muted text-center py-6">暂无开通记录</p>
        ) : (
          <ul className="space-y-2.5">
            {data.activation_records.map((record, idx) => (
              <li key={idx} className="flex items-center justify-between text-sm">
                <div className="min-w-0">
                  <span className="font-medium text-ink">
                    {record.school_name || `学校 #${record.school_id ?? '-'}`}
                  </span>
                  <span className="text-[11px] text-ink-muted ml-1.5">{record.school_code}</span>
                  {record.plan_code && (
                    <Badge variant="info" className="ml-2">{record.plan_code}</Badge>
                  )}
                </div>
                <span className="text-xs text-ink-muted shrink-0">
                  操作者 #{record.operator_id ?? '-'} ·{' '}
                  {new Date(record.created_at).toLocaleString('zh-CN', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ANA-02.1 平台级分析指标（跨校聚合，不暴露跨校用户轨迹） */}
      {analytics && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <div>
              <h2 className="text-xl font-bold text-ink flex items-center gap-2">
                <TrendingUp size={20} className="text-lake" />
                平台分析指标
                <Badge variant="info">ANA-02.1</Badge>
              </h2>
              <p className="text-ink-sub text-xs mt-1">
                平台只看学校级聚合，不提供跨校用户轨迹 · 生成于 {formatDateTime(analytics.generated_at)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <Filter size={14} className="text-ink-muted" />
                <select
                  value={analyticsWindowDays}
                  onChange={(e) => setAnalyticsWindowDays(Number(e.target.value))}
                  className="select-nice-sm w-auto"
                  aria-label="分析时间窗口"
                >
                  <option value={7}>近 7 天</option>
                  <option value={14}>近 14 天</option>
                  <option value={30}>近 30 天</option>
                  <option value={90}>近 90 天</option>
                  <option value={180}>近 180 天</option>
                </select>
              </div>
              <button
                onClick={handleRefreshAnalytics}
                disabled={analyticsRefreshing}
                className="flex items-center gap-1.5 text-sm text-ink-sub hover:text-lake transition-colors disabled:opacity-50"
              >
                <RefreshCw size={14} className={analyticsRefreshing ? 'animate-spin' : ''} />
                复算
              </button>
            </div>
          </div>

          {/* 平台级 4 大指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card variant="outlined" padding="md">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={16} className="text-lake" />
                <span className="text-xs text-ink-muted">整体转化率</span>
              </div>
              <p className="text-2xl font-bold text-lake">
                {formatRate(analytics.platform_funnel.overall_conversion)}
              </p>
              <p className="text-[11px] text-ink-muted mt-1">
                查看 {formatNumber(analytics.platform_funnel.stages[0]?.count ?? 0)} → 公开{' '}
                {formatNumber(analytics.platform_funnel.stages[analytics.platform_funnel.stages.length - 1]?.count ?? 0)}
              </p>
              {analytics.platform_funnel.meta.empty_state && (
                <Badge variant="default" className="mt-1">空数据</Badge>
              )}
            </Card>
            <Card variant="outlined" padding="md">
              <div className="flex items-center gap-2 mb-2">
                <Search size={16} className="text-info" />
                <span className="text-xs text-ink-muted">搜索成功率</span>
              </div>
              <p className="text-2xl font-bold text-info">
                {formatRate(analytics.platform_search.success_rate)}
              </p>
              <p className="text-[11px] text-ink-muted mt-1">
                {formatNumber(analytics.platform_search.succeeded_searches)}/{formatNumber(analytics.platform_search.total_searches)} 次搜索
              </p>
              {analytics.platform_search.meta.empty_state && (
                <Badge variant="default" className="mt-1">空数据</Badge>
              )}
            </Card>
            <Card variant="outlined" padding="md">
              <div className="flex items-center gap-2 mb-2">
                <Search size={16} className="text-danger" />
                <span className="text-xs text-ink-muted">零结果率</span>
              </div>
              <p className="text-2xl font-bold text-danger">
                {formatRate(analytics.platform_search.zero_rate)}
              </p>
              <p className="text-[11px] text-ink-muted mt-1">
                {formatNumber(analytics.platform_search.zero_searches)} 次零结果
              </p>
              {analytics.platform_search.meta.empty_state && (
                <Badge variant="default" className="mt-1">空数据</Badge>
              )}
            </Card>
            <Card variant="outlined" padding="md">
              <div className="flex items-center gap-2 mb-2">
                <Cpu size={16} className="text-lamp" />
                <span className="text-xs text-ink-muted">AI 降级率</span>
              </div>
              <p className="text-2xl font-bold text-lamp">
                {formatRate(analytics.platform_ai_usage.fallback_rate)}
              </p>
              <p className="text-[11px] text-ink-muted mt-1">
                {formatNumber(analytics.platform_ai_usage.fallback_calls)}/{formatNumber(analytics.platform_ai_usage.total_calls)} 次降级 · 平均 {analytics.platform_ai_usage.avg_latency_ms.toFixed(0)}ms
              </p>
              {analytics.platform_ai_usage.meta.empty_state && (
                <Badge variant="default" className="mt-1">空数据</Badge>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* 平台级漏斗 */}
            <Card variant="outlined" padding="md">
              <h3 className="text-base font-semibold text-ink mb-3 flex items-center gap-2">
                <TrendingUp size={16} className="text-lake" />
                平台漏斗
              </h3>
              <div className="space-y-2">
                {(() => {
                  const maxCount = Math.max(
                    ...analytics.platform_funnel.stages.map((s) => s.count),
                    1
                  );
                  return analytics.platform_funnel.stages.map((stage, idx) => {
                    const widthPercent = (stage.count / maxCount) * 100;
                    return (
                      <div key={stage.key} className="flex items-center gap-2 text-sm">
                        <div className="w-20 shrink-0 text-ink-muted text-xs">
                          {stage.label}
                        </div>
                        <div className="flex-1 h-6 rounded-md bg-mist overflow-hidden relative">
                          <div
                            className="h-full bg-gradient-to-r from-lake/80 to-lake rounded-md"
                            style={{ width: `${Math.max(widthPercent, 2)}%` }}
                          />
                          <span className="absolute inset-0 flex items-center px-2 text-[11px] font-medium text-paper">
                            {formatNumber(stage.count)}
                          </span>
                        </div>
                        <div className="w-12 shrink-0 text-right text-[11px] text-ink-muted">
                          {idx === 0 ? '100%' : `${((stage.count / (analytics.platform_funnel.stages[0].count || 1)) * 100).toFixed(1)}%`}
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
              <div className="mt-3 text-[11px] text-ink-muted">
                样本量 {formatNumber(analytics.platform_funnel.meta.sample_size)} · 更新于 {formatDateTime(analytics.platform_funnel.meta.last_updated_at)}
              </div>
            </Card>

            {/* 平台级治理 SLA */}
            <Card variant="outlined" padding="md">
              <h3 className="text-base font-semibold text-ink mb-3 flex items-center gap-2">
                <Clock size={16} className="text-lamp" />
                平台治理 SLA
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-mist/60 rounded-md p-3">
                  <p className="text-xs text-ink-muted mb-1">平均审核时长</p>
                  <p className="text-xl font-bold text-ink">
                    {formatSeconds(analytics.platform_governance.avg_review_seconds)}
                  </p>
                  <p className="text-[11px] text-ink-muted mt-1">
                    共 {formatNumber(analytics.platform_governance.reviewed_count)} 次审核
                  </p>
                </div>
                <div className="bg-mist/60 rounded-md p-3">
                  <p className="text-xs text-ink-muted mb-1">平均举报处理时长</p>
                  <p className="text-xl font-bold text-ink">
                    {formatSeconds(analytics.platform_governance.avg_report_handle_seconds)}
                  </p>
                  <p className="text-[11px] text-ink-muted mt-1">
                    共 {formatNumber(analytics.platform_governance.reports_handled_count)} 次举报
                  </p>
                </div>
              </div>
              {analytics.platform_governance.meta.empty_state && (
                <Badge variant="default" className="mt-3">暂无治理数据</Badge>
              )}
              <div className="mt-3 text-[11px] text-ink-muted">
                样本量 {formatNumber(analytics.platform_governance.meta.sample_size)} · 更新于 {formatDateTime(analytics.platform_governance.meta.last_updated_at)}
              </div>
            </Card>
          </div>

          {/* 各校聚合（仅显示统计数字，不暴露跨校用户轨迹） */}
          <Card variant="outlined" padding="md">
            <h3 className="text-base font-semibold text-ink mb-3 flex items-center gap-2">
              <SchoolIcon size={16} className="text-lake" />
              各校聚合指标
              <Badge variant="info">{analytics.school_metrics.length} 所学校</Badge>
            </h3>
            {analytics.school_metrics.length === 0 ? (
              <p className="text-sm text-ink-muted text-center py-6">暂无学校数据</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-ink-muted text-xs">
                      <th className="text-left py-2 px-2">学校</th>
                      <th className="text-right py-2 px-2">查看</th>
                      <th className="text-right py-2 px-2">搜索</th>
                      <th className="text-right py-2 px-2">提交</th>
                      <th className="text-right py-2 px-2">公开</th>
                      <th className="text-right py-2 px-2">搜索成功率</th>
                      <th className="text-right py-2 px-2">零结果率</th>
                      <th className="text-right py-2 px-2">AI 调用</th>
                      <th className="text-right py-2 px-2">AI 降级率</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.school_metrics.map((sm) => (
                      <tr key={sm.school_id} className="border-b border-line/60 last:border-0">
                        <td className="py-2 px-2">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-ink">
                              {sm.school_name || `#${sm.school_id}`}
                            </span>
                            {!sm.is_active && <Badge variant="danger">暂停</Badge>}
                          </div>
                          <p className="text-[11px] text-ink-muted">{sm.school_code}</p>
                        </td>
                        <td className="py-2 px-2 text-right text-ink">
                          {formatNumber(sm.funnel_summary.school_viewed)}
                        </td>
                        <td className="py-2 px-2 text-right text-ink">
                          {formatNumber(sm.funnel_summary.search_started)}
                        </td>
                        <td className="py-2 px-2 text-right text-ink">
                          {formatNumber(sm.funnel_summary.post_submitted)}
                        </td>
                        <td className="py-2 px-2 text-right text-ink">
                          {formatNumber(sm.funnel_summary.published)}
                        </td>
                        <td className="py-2 px-2 text-right">
                          <span className={sm.search_success_rate >= 0.5 ? 'text-grass' : 'text-sun'}>
                            {formatRate(sm.search_success_rate)}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-right">
                          <span className={sm.search_zero_rate >= 0.3 ? 'text-danger' : 'text-ink'}>
                            {formatRate(sm.search_zero_rate)}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-right text-ink">
                          {formatNumber(sm.ai_calls)}
                        </td>
                        <td className="py-2 px-2 text-right">
                          <span className={sm.ai_fallback_rate >= 0.5 ? 'text-danger' : sm.ai_fallback_rate >= 0.2 ? 'text-sun' : 'text-ink'}>
                            {formatRate(sm.ai_fallback_rate)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="mt-3 text-[11px] text-ink-muted">
              平台层只看学校级聚合，不提供跨校用户轨迹（ANA-02.1 隐私硬约束）
            </p>
          </Card>
        </>
      )}
    </div>
  );
};

export default PlatformOverviewPage;
