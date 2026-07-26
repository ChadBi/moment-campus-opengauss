import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import {
  adminApi,
  type DashboardStats,
  type AdminLog,
  type TodoStats,
} from '../../services/admin';
import {
  FileText,
  Users,
  Flag,
  MessageCircle,
  TrendingUp,
  Calendar,
  ScrollText,
  CheckCircle2,
  FolderTree,
  MapPin,
  Clock,
  AlertTriangle,
  Lightbulb,
  Wrench,
  ArrowRight,
  Activity,
} from 'lucide-react';
import { logger } from '../../utils/logger';

/** 操作类型 → 中文标签 + 颜色 */
const ACTION_LABELS: Record<string, { label: string; variant: 'success' | 'danger' | 'info' | 'warning' | 'default' }> = {
  approve_post: { label: '通过审核', variant: 'success' },
  reject_post: { label: '拒绝审核', variant: 'danger' },
  enable_user: { label: '启用用户', variant: 'success' },
  disable_user: { label: '禁用用户', variant: 'danger' },
  handle_report: { label: '处理举报', variant: 'warning' },
  create_category: { label: '新建分类', variant: 'info' },
  update_category: { label: '更新分类', variant: 'info' },
  delete_category: { label: '禁用分类', variant: 'danger' },
  update_tag: { label: '更新标签', variant: 'info' },
  delete_tag: { label: '删除标签', variant: 'danger' },
  merge_tag: { label: '合并标签', variant: 'warning' },
  verify_location: { label: '核验地点', variant: 'success' },
  unverify_location: { label: '取消核验', variant: 'warning' },
  governance_resolve: { label: '治理-已解决', variant: 'success' },
  governance_dismiss: { label: '治理-驳回', variant: 'default' },
  governance_mark_expired: { label: '治理-确认过期', variant: 'warning' },
  governance_mark_conflict: { label: '治理-确认冲突', variant: 'danger' },
};

/** ADM-01.1: 待办类别 → 图标与颜色 */
const TODO_META: Record<string, { icon: React.ComponentType<{ size?: number; className?: string }>; color: string; bgColor: string }> = {
  pending_posts: { icon: FileText, color: 'text-sun', bgColor: 'bg-sun/15' },
  pending_reports: { icon: Flag, color: 'text-danger', bgColor: 'bg-danger/10' },
  unverified_locations: { icon: MapPin, color: 'text-lake', bgColor: 'bg-lake/10' },
  expiration_reports: { icon: Clock, color: 'text-lamp', bgColor: 'bg-lamp/10' },
  conflict_reports: { icon: AlertTriangle, color: 'text-danger', bgColor: 'bg-danger/10' },
  update_suggestions: { icon: Lightbulb, color: 'text-info', bgColor: 'bg-info/10' },
  failed_jobs: { icon: Wrench, color: 'text-ink-sub', bgColor: 'bg-mist' },
};

const AdminHomePage: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [todos, setTodos] = useState<TodoStats | null>(null);
  const [recentLogs, setRecentLogs] = useState<AdminLog[]>([]);
  const [loading, setLoading] = useState(true);

  // FND-01.4: 函数声明移到 useEffect 之前；setLoading 移出 effect 避免同步 setState
  const loadData = async () => {
    try {
      const [statsData, todosData, logsData] = await Promise.all([
        adminApi.getStats(),
        adminApi.getTodos(),
        adminApi.getLogs({ page: 1, page_size: 6 }),
      ]);
      setStats(statsData);
      setTodos(todosData);
      setRecentLogs(logsData.items);
    } catch (error) {
      logger.error('加载仪表盘数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadData();
  }, []);

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

  if (!stats) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-sub">加载统计数据失败</p>
        <button
          onClick={loadData}
          className="mt-3 text-sm text-lake hover:underline"
        >
          重新加载
        </button>
      </div>
    );
  }

  // 统计卡片：颜色回归设计系统
  const statCards = [
    { title: '信息总数', value: stats.total_posts, icon: FileText, color: 'text-lake', bgColor: 'bg-lake/10' },
    { title: '待审核信息', value: stats.pending_posts, icon: Calendar, color: 'text-sun', bgColor: 'bg-sun/15', highlight: stats.pending_posts > 0 },
    { title: '用户总数', value: stats.total_users, icon: Users, color: 'text-grass', bgColor: 'bg-grass/15' },
    { title: '活跃用户', value: stats.active_users, icon: TrendingUp, color: 'text-lake-dark', bgColor: 'bg-lake/10' },
    { title: '举报总数', value: stats.total_reports, icon: Flag, color: 'text-danger', bgColor: 'bg-danger/10' },
    { title: '待处理举报', value: stats.pending_reports, icon: Flag, color: 'text-lamp', bgColor: 'bg-lamp/10', highlight: stats.pending_reports > 0 },
    { title: '评论总数', value: stats.total_comments, icon: MessageCircle, color: 'text-info', bgColor: 'bg-info/10' },
  ];

  // 快速操作
  const quickActions = [
    { to: '/admin/review', icon: CheckCircle2, label: '内容审核', sub: `${stats.pending_posts} 条待审核`, color: 'text-sun' },
    { to: '/admin/reports', icon: Flag, label: '举报管理', sub: `${stats.pending_reports} 条待处理`, color: 'text-danger' },
    { to: '/admin/users', icon: Users, label: '用户管理', sub: `${stats.total_users} 个用户`, color: 'text-grass' },
    { to: '/admin/categories', icon: FolderTree, label: '分类管理', sub: '维护信息分类', color: 'text-lake' },
    { to: '/admin/logs', icon: ScrollText, label: '操作日志', sub: '查看操作记录', color: 'text-ink-sub' },
  ];

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold text-ink">仪表盘</h1>
        <p className="text-ink-sub text-sm mt-1">系统概览与快速操作</p>
      </div>

      {/* ADM-01.1: 待办事项（7 类，点击卡片进入对应筛选队列） */}
      {todos && (
        <Card variant="outlined" padding="md">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-ink flex items-center gap-2">
              <CheckCircle2 size={18} className="text-lamp" />
              待办事项
              {todos.total > 0 && (
                <Badge variant="warning">{todos.total} 项待处理</Badge>
              )}
            </h2>
            {todos.total === 0 && (
              <span className="text-xs text-ink-muted">全部处理完毕</span>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
            {todos.items.map((item) => {
              const meta = TODO_META[item.key] || TODO_META.pending_posts;
              const Icon = meta.icon;
              return (
                <button
                  key={item.key}
                  onClick={() => navigate(item.queue_url)}
                  className={`group text-left p-3 rounded-md border transition-all ${
                    item.count > 0
                      ? 'border-line bg-paper hover:border-lake hover:shadow-sm'
                      : 'border-line/50 bg-mist/40 opacity-70 hover:opacity-100'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className={`${meta.bgColor} p-2 rounded-md`}>
                      <Icon className={meta.color} size={16} />
                    </div>
                    <ArrowRight
                      size={14}
                      className="text-ink-disabled group-hover:text-lake transition-colors"
                    />
                  </div>
                  <p
                    className={`mt-2 text-xl font-bold ${
                      item.count > 0 ? 'text-ink' : 'text-ink-muted'
                    }`}
                  >
                    {item.count}
                  </p>
                  <p className="text-xs text-ink-muted mt-0.5 truncate">{item.label}</p>
                </button>
              );
            })}
          </div>
        </Card>
      )}

      {/* REL-02.3: AI 降级率监控（最近 24h 本校采样） */}
      {todos && (
        <Card variant="outlined" padding="md">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-ink flex items-center gap-2">
              <Activity size={18} className="text-lake" />
              AI 监控（最近 24h）
            </h2>
            {todos.ai_calls_24h === 0 ? (
              <span className="text-xs text-ink-muted">暂无调用</span>
            ) : todos.ai_fallback_rate >= 0.5 ? (
              <Badge variant="danger">降级率高</Badge>
            ) : todos.ai_fallback_rate >= 0.2 ? (
              <Badge variant="warning">降级率偏高</Badge>
            ) : (
              <Badge variant="success">正常</Badge>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 rounded-md border border-line bg-paper">
              <p className="text-xs text-ink-muted">调用次数</p>
              <p className="mt-1 text-2xl font-bold text-ink">
                {todos.ai_calls_24h}
              </p>
            </div>
            <div className="p-3 rounded-md border border-line bg-paper">
              <p className="text-xs text-ink-muted">降级次数</p>
              <p
                className={`mt-1 text-2xl font-bold ${
                  todos.ai_fallback_24h > 0 ? 'text-lamp' : 'text-ink'
                }`}
              >
                {todos.ai_fallback_24h}
              </p>
            </div>
            <div className="p-3 rounded-md border border-line bg-paper">
              <p className="text-xs text-ink-muted">降级率</p>
              <p
                className={`mt-1 text-2xl font-bold ${
                  todos.ai_fallback_rate >= 0.5
                    ? 'text-danger'
                    : todos.ai_fallback_rate >= 0.2
                    ? 'text-lamp'
                    : 'text-grass'
                }`}
              >
                {(todos.ai_fallback_rate * 100).toFixed(1)}%
              </p>
            </div>
          </div>
          {todos.ai_fallback_rate >= 0.5 && todos.ai_calls_24h >= 5 && (
            <p className="mt-3 text-xs text-danger flex items-center gap-1">
              <AlertTriangle size={12} />
              AI 降级率 ≥50%，建议检查 AI 配置（AI_PROVIDER / API Key）或网络连通性
            </p>
          )}
        </Card>
      )}

      {/* 统计卡片网格 */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
        {statCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <Card key={index} variant="outlined" padding="md">
              <div className="flex items-center gap-3">
                <div className={`${card.bgColor} p-2.5 rounded-md`}>
                  <Icon className={card.color} size={20} />
                </div>
                <div className="min-w-0">
                  <p className="text-ink-muted text-xs">{card.title}</p>
                  <p className={`text-xl font-bold ${card.highlight ? 'text-lamp' : 'text-ink'}`}>
                    {card.value}
                  </p>
                </div>
              </div>
            </Card>
          );
        })}

        {/* 待办提示卡 */}
        {(stats.pending_posts > 0 || stats.pending_reports > 0) && (
          <Card variant="filled" padding="md">
            <div className="flex items-center gap-3">
              <div className="bg-lamp/15 p-2.5 rounded-md">
                <Calendar className="text-lamp" size={20} />
              </div>
              <div className="min-w-0">
                <p className="text-ink-muted text-xs">待办合计</p>
                <p className="text-xl font-bold text-lamp">
                  {stats.pending_posts + stats.pending_reports}
                </p>
              </div>
            </div>
          </Card>
        )}
      </div>

      {/* 快速操作 + 近期操作日志 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 快速操作（占 2 列） */}
        <Card variant="outlined" padding="md" className="lg:col-span-2">
          <h2 className="text-base font-semibold text-ink mb-4 flex items-center gap-2">
            <TrendingUp size={18} className="text-lake" />
            快速操作
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <Link
                  key={action.to}
                  to={action.to}
                  className="flex items-center gap-3 p-3 bg-mist/50 rounded-md hover:bg-mist hover:shadow-sm transition-all"
                >
                  <Icon className={action.color} size={22} />
                  <div className="min-w-0">
                    <p className="font-medium text-ink text-sm">{action.label}</p>
                    <p className="text-xs text-ink-muted truncate">{action.sub}</p>
                  </div>
                </Link>
              );
            })}
          </div>
        </Card>

        {/* 近期操作日志（占 1 列） */}
        <Card variant="outlined" padding="md">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-ink flex items-center gap-2">
              <ScrollText size={18} className="text-lake" />
              近期操作
            </h2>
            <Link to="/admin/logs" className="text-xs text-lake hover:underline">
              查看全部
            </Link>
          </div>
          {recentLogs.length === 0 ? (
            <p className="text-sm text-ink-muted text-center py-6">暂无操作记录</p>
          ) : (
            <ul className="space-y-2.5">
              {recentLogs.map((log) => {
                const actionInfo = ACTION_LABELS[log.action] || { label: log.action, variant: 'default' as const };
                return (
                  <li key={log.id} className="flex items-start gap-2 text-sm">
                    <Badge variant={actionInfo.variant} className="mt-0.5 shrink-0">
                      {actionInfo.label}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      <p className="text-ink-sub text-xs truncate">
                        {log.detail || '无详情'}
                      </p>
                      <p className="text-ink-muted text-[11px] mt-0.5">
                        {log.admin_name || `管理员#${log.admin_id}`} ·{' '}
                        {new Date(log.created_at).toLocaleString('zh-CN', {
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
};

export default AdminHomePage;
