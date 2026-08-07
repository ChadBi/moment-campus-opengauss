import React, { useCallback, useEffect, useState } from 'react';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import {
  analyticsApi,
  type SchoolAnalyticsResponse,
  type ZeroResultsInsightResponse,
  type MetricMeta,
} from '../../services/analytics';
import { useUIStore } from '../../store/useUIStore';
import {
  RefreshCw,
  Filter,
  Search,
  TrendingUp,
  TrendingDown,
  Share2,
  FileCheck,
  Cpu,
  Clock,
  AlertTriangle,
  Eye,
  EyeOff,
  Activity,
} from 'lucide-react';
import { formatShortDateTime } from '../../utils/date';

const formatRate = (rate: number): string => `${(rate * 100).toFixed(1)}%`;
const formatNumber = (n: number): string => n.toLocaleString('zh-CN');
const formatSeconds = (sec: number): string => {
  if (sec <= 0) return '-';
  if (sec < 60) return `${sec.toFixed(0)} 秒`;
  if (sec < 3600) return `${(sec / 60).toFixed(1)} 分`;
  return `${(sec / 3600).toFixed(1)} 时`;
};
const formatDateTime = (iso: string | null): string =>
  formatShortDateTime(iso);

/**
 * 元数据小卡：显示时间窗口/样本量/最后更新/空数据状态
 */
const MetaBadge: React.FC<{ meta: MetricMeta; label?: string }> = ({
  meta,
  label = '指标元数据',
}) => {
  if (meta.empty_state) {
    return (
      <div className="flex flex-wrap items-center gap-1.5 mt-2 text-[11px] text-ink-muted">
        <Badge variant="default">空数据</Badge>
        <span>样本量 0</span>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-2 text-[11px] text-ink-muted">
      <span title={label}>📊</span>
      <span>样本量 {formatNumber(meta.sample_size)}</span>
      {meta.time_window_start && (
        <span>
          · 窗口 {formatDateTime(meta.time_window_start)} ~ {formatDateTime(meta.time_window_end)}
        </span>
      )}
      <span>· 更新于 {formatDateTime(meta.last_updated_at)}</span>
    </div>
  );
};

/**
 * ANA-02.2 校级分析页：展示各项指标 + 零结果洞察 + 隐私阈值保护
 */
const AnalyticsPage: React.FC = () => {
  const showToast = useUIStore((s) => s.showToast);
  const [metrics, setMetrics] = useState<SchoolAnalyticsResponse | null>(null);
  const [insight, setInsight] = useState<ZeroResultsInsightResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [windowDays, setWindowDays] = useState<number>(30);

  const loadData = useCallback(async () => {
    try {
      const [m, i] = await Promise.all([
        analyticsApi.getSchoolAnalytics({ window_days: windowDays }),
        analyticsApi.getZeroResultsInsight({ window_days: windowDays }),
      ]);
      setMetrics(m);
      setInsight(i);
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载分析数据失败';
      showToast(message, 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showToast, windowDays]);

  useEffect(() => {
    void Promise.resolve().then(() => {
      setLoading(true);
      return loadData();
    });
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

  if (!metrics) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-sub">加载分析数据失败</p>
        <Button variant="secondary" size="sm" className="mt-3" onClick={handleRefresh}>
          重新加载
        </Button>
      </div>
    );
  }

  // 顶部汇总卡
  const summaryCards = [
    {
      title: '整体转化率',
      value: formatRate(metrics.funnel.conversion_rates.overall),
      sub: '学校查看 → 审核公开',
      icon: TrendingUp,
      color: 'text-lake',
      bgColor: 'bg-lake/10',
    },
    {
      title: '7 日回访率',
      value: formatRate(metrics.retention_7d.retention_rate),
      sub: `${metrics.retention_7d.revisit_users}/${metrics.retention_7d.baseline_users} 用户回访`,
      icon: Activity,
      color: 'text-grass',
      bgColor: 'bg-grass/15',
    },
    {
      title: '搜索成功率',
      value: formatRate(metrics.search_success_rate.success_rate),
      sub: `${metrics.search_success_rate.succeeded_searches}/${metrics.search_success_rate.total_searches} 次搜索`,
      icon: Search,
      color: 'text-info',
      bgColor: 'bg-info/10',
    },
    {
      title: '零结果率',
      value: formatRate(metrics.search_zero_rate.zero_rate),
      sub: `${metrics.search_zero_rate.zero_searches} 次零结果`,
      icon: TrendingDown,
      color: 'text-danger',
      bgColor: 'bg-danger/10',
    },
    {
      title: '内容有效率',
      value: formatRate(metrics.content_valid_rate.valid_rate),
      sub: `${metrics.content_valid_rate.valid_posts}/${metrics.content_valid_rate.total_posts} 已发布未过期`,
      icon: FileCheck,
      color: 'text-grass',
      bgColor: 'bg-grass/15',
    },
    {
      title: 'AI 降级率',
      value: formatRate(metrics.ai_usage.fallback_rate),
      sub: `${metrics.ai_usage.fallback_calls}/${metrics.ai_usage.total_calls} 次降级`,
      icon: Cpu,
      color: 'text-lamp',
      bgColor: 'bg-lamp/10',
    },
  ];

  // 漏斗各阶段最大值（用于柱状图比例）
  const maxFunnelCount = Math.max(
    ...metrics.funnel.stages.map((s) => s.count),
    1
  );

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">校级数据分析</h1>
          <p className="text-ink-sub text-sm mt-1">
            ANA-02.2 · {metrics.school_name || `学校 #${metrics.school_id}`}
            {metrics.school_code && (
              <span className="ml-1.5 text-ink-muted">({metrics.school_code})</span>
            )}
            <span className="ml-2 text-ink-muted">· 生成于 {formatDateTime(metrics.generated_at)}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <Filter size={14} className="text-ink-muted" />
            <select
              value={windowDays}
              onChange={(e) => setWindowDays(Number(e.target.value))}
              className="select-nice-sm w-auto"
              aria-label="时间窗口"
            >
              <option value={1}>近 1 天</option>
              <option value={7}>近 7 天</option>
              <option value={14}>近 14 天</option>
              <option value={30}>近 30 天</option>
              <option value={90}>近 90 天</option>
              <option value={180}>近 180 天</option>
            </select>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 text-sm text-ink-sub hover:text-lake transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            复算
          </button>
        </div>
      </div>

      {/* 汇总卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
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

      {/* 漏斗 */}
      <Card variant="outlined" padding="md">
        <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
          <TrendingUp size={18} className="text-lake" />
          用户行为漏斗
          <span className="text-xs text-ink-muted font-normal">
            学校查看 → 搜索 → 发布 → 审核 → 公开
          </span>
        </h2>
        <div className="space-y-3">
          {metrics.funnel.stages.map((stage, idx) => {
            const widthPercent = (stage.count / maxFunnelCount) * 100;
            const prevCount = idx > 0 ? metrics.funnel.stages[idx - 1].count : null;
            const stageRate =
              prevCount && prevCount > 0 ? (stage.count / prevCount) * 100 : null;
            return (
              <div key={stage.key} className="flex items-center gap-3 text-sm">
                <div className="w-24 shrink-0">
                  <p className="font-medium text-ink">{stage.label}</p>
                  <p className="text-[11px] text-ink-muted">阶段 {idx + 1}</p>
                </div>
                <div className="flex-1">
                  <div className="h-7 rounded-md bg-mist overflow-hidden relative">
                    <div
                      className="h-full bg-gradient-to-r from-lake/80 to-lake rounded-md transition-all"
                      style={{ width: `${Math.max(widthPercent, 2)}%` }}
                    />
                    <span className="absolute inset-0 flex items-center px-3 text-xs font-medium text-paper">
                      {formatNumber(stage.count)}
                    </span>
                  </div>
                </div>
                <div className="w-20 shrink-0 text-right">
                  {stageRate !== null && (
                    <Badge variant={stageRate >= 50 ? 'success' : stageRate >= 20 ? 'warning' : 'danger'}>
                      {stageRate.toFixed(1)}%
                    </Badge>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <MetaBadge meta={metrics.funnel.meta} label="漏斗元数据" />
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 搜索指标 */}
        <Card variant="outlined" padding="md">
          <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
            <Search size={18} className="text-info" />
            搜索成功率 vs 零结果率
          </h2>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="bg-grass/8 rounded-md p-3">
              <p className="text-xs text-ink-muted mb-1">搜索成功率</p>
              <p className="text-2xl font-bold text-grass">
                {formatRate(metrics.search_success_rate.success_rate)}
              </p>
              <p className="text-[11px] text-ink-muted mt-1">
                {formatNumber(metrics.search_success_rate.succeeded_searches)} 次有结果 / 共{' '}
                {formatNumber(metrics.search_success_rate.total_searches)} 次
              </p>
            </div>
            <div className="bg-danger/8 rounded-md p-3">
              <p className="text-xs text-ink-muted mb-1">零结果率</p>
              <p className="text-2xl font-bold text-danger">
                {formatRate(metrics.search_zero_rate.zero_rate)}
              </p>
              <p className="text-[11px] text-ink-muted mt-1">
                {formatNumber(metrics.search_zero_rate.zero_searches)} 次零结果 / 共{' '}
                {formatNumber(metrics.search_zero_rate.total_searches)} 次
              </p>
            </div>
          </div>
          {/* 双进度条对比 */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs">
              <span className="w-20 text-ink-muted">成功</span>
              <div className="flex-1 h-2 bg-mist rounded-full overflow-hidden">
                <div
                  className="h-full bg-grass rounded-full"
                  style={{
                    width: `${metrics.search_success_rate.total_searches > 0
                      ? (metrics.search_success_rate.succeeded_searches / metrics.search_success_rate.total_searches) * 100
                      : 0}%`,
                  }}
                />
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="w-20 text-ink-muted">零结果</span>
              <div className="flex-1 h-2 bg-mist rounded-full overflow-hidden">
                <div
                  className="h-full bg-danger rounded-full"
                  style={{
                    width: `${metrics.search_zero_rate.total_searches > 0
                      ? (metrics.search_zero_rate.zero_searches / metrics.search_zero_rate.total_searches) * 100
                      : 0}%`,
                  }}
                />
              </div>
            </div>
          </div>
          <MetaBadge meta={metrics.search_success_rate.meta} label="搜索指标元数据" />
        </Card>

        {/* 分享订阅转化 */}
        <Card variant="outlined" padding="md">
          <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
            <Share2 size={18} className="text-lamp" />
            分享订阅转化
          </h2>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-mist/60 rounded-md p-3 text-center">
              <p className="text-xs text-ink-muted mb-1">分享点击</p>
              <p className="text-xl font-bold text-ink">
                {formatNumber(metrics.share_subscription_conversion.share_clicked)}
              </p>
            </div>
            <div className="bg-mist/60 rounded-md p-3 text-center">
              <p className="text-xs text-ink-muted mb-1">新增订阅</p>
              <p className="text-xl font-bold text-ink">
                {formatNumber(metrics.share_subscription_conversion.subscribed)}
              </p>
            </div>
            <div className="bg-lamp/10 rounded-md p-3 text-center">
              <p className="text-xs text-ink-muted mb-1">转化率</p>
              <p className="text-xl font-bold text-lamp">
                {formatRate(metrics.share_subscription_conversion.conversion_rate)}
              </p>
            </div>
          </div>
          {/* 转化漏斗 */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs">
              <span className="w-20 text-ink-muted">分享</span>
              <div className="flex-1 h-2 bg-mist rounded-full overflow-hidden">
                <div className="h-full bg-info rounded-full" style={{ width: '100%' }} />
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="w-20 text-ink-muted">订阅</span>
              <div className="flex-1 h-2 bg-mist rounded-full overflow-hidden">
                <div
                  className="h-full bg-lamp rounded-full"
                  style={{
                    width: `${metrics.share_subscription_conversion.share_clicked > 0
                      ? (metrics.share_subscription_conversion.subscribed / metrics.share_subscription_conversion.share_clicked) * 100
                      : 0}%`,
                  }}
                />
              </div>
            </div>
          </div>
          <MetaBadge meta={metrics.share_subscription_conversion.meta} label="分享订阅转化元数据" />
        </Card>

        {/* 内容有效率 */}
        <Card variant="outlined" padding="md">
          <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
            <FileCheck size={18} className="text-grass" />
            内容有效率
          </h2>
          <div className="flex items-center justify-center mb-4">
            {/* 环形进度（简化版） */}
            <div className="relative w-32 h-32">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50" cy="50" r="42"
                  fill="none" stroke="currentColor" strokeWidth="8"
                  className="text-mist"
                />
                <circle
                  cx="50" cy="50" r="42"
                  fill="none" stroke="currentColor" strokeWidth="8"
                  className={metrics.content_valid_rate.valid_rate >= 0.7 ? 'text-grass' : 'text-sun'}
                  strokeDasharray={`${2 * Math.PI * 42 * metrics.content_valid_rate.valid_rate} ${2 * Math.PI * 42}`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold text-ink">
                  {formatRate(metrics.content_valid_rate.valid_rate)}
                </span>
                <span className="text-[11px] text-ink-muted">有效率</span>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="text-center">
              <p className="text-xs text-ink-muted">有效内容</p>
              <p className="text-lg font-semibold text-grass">
                {formatNumber(metrics.content_valid_rate.valid_posts)}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-ink-muted">总内容</p>
              <p className="text-lg font-semibold text-ink">
                {formatNumber(metrics.content_valid_rate.total_posts)}
              </p>
            </div>
          </div>
          <MetaBadge meta={metrics.content_valid_rate.meta} label="内容有效率元数据" />
        </Card>

        {/* AI 用量 */}
        <Card variant="outlined" padding="md">
          <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
            <Cpu size={18} className="text-info" />
            AI 检索用量
          </h2>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="bg-mist/60 rounded-md p-3">
              <p className="text-xs text-ink-muted mb-1">总调用</p>
              <p className="text-xl font-bold text-ink">
                {formatNumber(metrics.ai_usage.total_calls)}
              </p>
            </div>
            <div className="bg-grass/10 rounded-md p-3">
              <p className="text-xs text-ink-muted mb-1">成功率</p>
              <p className="text-xl font-bold text-grass">
                {formatRate(metrics.ai_usage.success_rate)}
              </p>
            </div>
            <div className="bg-danger/8 rounded-md p-3">
              <p className="text-xs text-ink-muted mb-1">降级次数</p>
              <p className="text-xl font-bold text-danger">
                {formatNumber(metrics.ai_usage.fallback_calls)}
              </p>
              <p className="text-[11px] text-ink-muted">
                降级率 {formatRate(metrics.ai_usage.fallback_rate)}
              </p>
            </div>
            <div className="bg-info/8 rounded-md p-3">
              <p className="text-xs text-ink-muted mb-1">平均延迟</p>
              <p className="text-xl font-bold text-info">
                {metrics.ai_usage.avg_latency_ms.toFixed(0)} ms
              </p>
              <p className="text-[11px] text-ink-muted">
                候选 {metrics.ai_usage.avg_candidate_count.toFixed(1)} · 结果 {metrics.ai_usage.avg_result_count.toFixed(1)}
              </p>
            </div>
          </div>
          <MetaBadge meta={metrics.ai_usage.meta} label="AI 用量元数据" />
        </Card>
      </div>

      {/* 治理 SLA */}
      <Card variant="outlined" padding="md">
        <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
          <Clock size={18} className="text-lamp" />
          审核治理 SLA
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          <div className="bg-mist/60 rounded-md p-3">
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs text-ink-muted">平均审核时长</p>
              <Badge variant="info">{metrics.governance_sla.reviewed_count} 次</Badge>
            </div>
            <p className="text-xl font-bold text-ink">
              {formatSeconds(metrics.governance_sla.avg_review_seconds)}
            </p>
            <p className="text-[11px] text-ink-muted mt-1">帖子提交 → 审核完成</p>
          </div>
          <div className="bg-mist/60 rounded-md p-3">
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs text-ink-muted">平均举报处理时长</p>
              <Badge variant="warning">{metrics.governance_sla.reports_handled_count} 次</Badge>
            </div>
            <p className="text-xl font-bold text-ink">
              {formatSeconds(metrics.governance_sla.avg_report_handle_seconds)}
            </p>
            <p className="text-[11px] text-ink-muted mt-1">举报创建 → 处理完成</p>
          </div>
        </div>
        <MetaBadge meta={metrics.governance_sla.meta} label="治理 SLA 元数据" />
      </Card>

      {/* 7 日回访 */}
      <Card variant="outlined" padding="md">
        <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
          <Activity size={18} className="text-grass" />
          7 日回访率
        </h2>
        <div className="flex items-center gap-6">
          <div className="text-center">
            <p className="text-xs text-ink-muted mb-1">基线用户</p>
            <p className="text-2xl font-bold text-ink">
              {formatNumber(metrics.retention_7d.baseline_users)}
            </p>
          </div>
          <div className="text-2xl text-ink-muted">→</div>
          <div className="text-center">
            <p className="text-xs text-ink-muted mb-1">回访用户</p>
            <p className="text-2xl font-bold text-grass">
              {formatNumber(metrics.retention_7d.revisit_users)}
            </p>
          </div>
          <div className="flex-1 pl-6 border-l border-line">
            <p className="text-xs text-ink-muted mb-1">回访率</p>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-3 bg-mist rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-grass/80 to-grass rounded-full"
                  style={{
                    width: `${Math.min(metrics.retention_7d.retention_rate * 100, 100)}%`,
                  }}
                />
              </div>
              <span className="text-xl font-bold text-grass">
                {formatRate(metrics.retention_7d.retention_rate)}
              </span>
            </div>
          </div>
        </div>
        <MetaBadge meta={metrics.retention_7d.meta} label="7 日回访元数据" />
      </Card>

      {/* 零结果主题洞察（隐私阈值保护） */}
      {insight && (
        <Card variant="outlined" padding="md">
          <h2 className="text-base font-semibold text-ink mb-1 flex items-center gap-2">
            <AlertTriangle size={18} className="text-danger" />
            零结果主题洞察
            <Badge variant="warning">
              隐私阈值 {insight.privacy_threshold}
            </Badge>
          </h2>
          <p className="text-xs text-ink-muted mb-4">
            样本量 &lt; {insight.privacy_threshold} 的主题自动隐藏具体聚合字段，仅计入总数
            （ANA-02.1 隐私硬约束）。共 {formatNumber(insight.total_zero_searches)} 次零结果搜索。
          </p>
          {insight.topics.length === 0 ? (
            <p className="text-sm text-ink-muted text-center py-6">
              暂无零结果主题（数据为空）
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-ink-muted text-xs">
                    <th className="text-left py-2 px-2">关键词长度</th>
                    <th className="text-left py-2 px-2">分类 code</th>
                    <th className="text-right py-2 px-2">出现次数</th>
                    <th className="text-center py-2 px-2">隐私状态</th>
                  </tr>
                </thead>
                <tbody>
                  {insight.topics.map((topic, idx) => (
                    <tr key={idx} className="border-b border-line/60 last:border-0">
                      <td className="py-2 px-2 text-ink">
                        {topic.hidden_for_privacy ? (
                          <span className="text-ink-muted">-</span>
                        ) : (
                          topic.keyword_length ?? '-'
                        )}
                      </td>
                      <td className="py-2 px-2 text-ink">
                        {topic.hidden_for_privacy ? (
                          <span className="text-ink-muted italic">已隐藏</span>
                        ) : (
                          <code className="text-xs bg-mist px-1.5 py-0.5 rounded">
                            {topic.category_code ?? '-'}
                          </code>
                        )}
                      </td>
                      <td className="py-2 px-2 text-right font-medium text-ink">
                        {formatNumber(topic.occurrences)}
                      </td>
                      <td className="py-2 px-2 text-center">
                        {topic.hidden_for_privacy ? (
                          <Badge variant="warning">
                            <EyeOff size={11} className="inline mr-1" />
                            隐私保护
                          </Badge>
                        ) : (
                          <Badge variant="success">
                            <Eye size={11} className="inline mr-1" />
                            可见
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {insight.last_updated_at && (
            <p className="mt-3 text-[11px] text-ink-muted">
              最后更新：{formatDateTime(insight.last_updated_at)}
            </p>
          )}
        </Card>
      )}
    </div>
  );
};

export default AnalyticsPage;
