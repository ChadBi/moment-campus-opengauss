import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi, type AdminLog, type LogQueryParams } from '../../services/admin';
import { ScrollText, Search, X, RotateCcw } from 'lucide-react';

const PAGE_SIZE = 20;

/** 操作类型 → 中文标签 + 颜色（与 AdminHomePage 一致） */
const ACTION_LABELS: Record<
  string,
  { label: string; variant: 'success' | 'danger' | 'info' | 'warning' | 'default' }
> = {
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
  batch_approve: { label: '批量通过', variant: 'success' },
  batch_reject: { label: '批量拒绝', variant: 'danger' },
  batch_toggle_active: { label: '批量启用/禁用', variant: 'warning' },
};

/** 目标类型 → 中文标签 */
const TARGET_TYPE_LABELS: Record<string, string> = {
  post: '信息',
  user: '用户',
  report: '举报',
  category: '分类',
  tag: '标签',
  comment: '评论',
};

const AdminLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<AdminLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  // 筛选状态
  const [filterAdminId, setFilterAdminId] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [filterTargetType, setFilterTargetType] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  // 已应用的筛选（触发查询用）
  const [applied, setApplied] = useState<LogQueryParams>({});

  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const loadLogs = useCallback(async (p: number, params: LogQueryParams) => {
    try {
      setLoading(true);
      const data = await adminApi.getLogs({ ...params, page: p, page_size: PAGE_SIZE });
      setLogs(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error('加载操作日志失败:', error);
      setToast({ message: '加载操作日志失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLogs(page, applied);
  }, [page, applied, loadLogs]);

  /** 应用筛选 */
  const handleApplyFilter = () => {
    const params: LogQueryParams = {};
    if (filterAdminId.trim()) {
      const n = parseInt(filterAdminId.trim());
      if (!isNaN(n)) params.admin_id = n;
    }
    if (filterAction) params.action = filterAction;
    if (filterTargetType) params.target_type = filterTargetType;
    if (filterDateFrom) params.date_from = filterDateFrom;
    if (filterDateTo) params.date_to = filterDateTo;
    setApplied(params);
    setPage(1);
  };

  /** 清空筛选 */
  const handleClearFilter = () => {
    setFilterAdminId('');
    setFilterAction('');
    setFilterTargetType('');
    setFilterDateFrom('');
    setFilterDateTo('');
    setApplied({});
    setPage(1);
  };

  /** 是否有筛选条件 */
  const hasFilter =
    !!filterAdminId ||
    !!filterAction ||
    !!filterTargetType ||
    !!filterDateFrom ||
    !!filterDateTo;

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 表格列配置
  const columns: Column<AdminLog>[] = [
    {
      key: 'admin_name',
      title: '管理员',
      width: 130,
      nowrap: true,
      render: (value, row) => (
        <div className="min-w-0">
          <p className="font-medium text-ink truncate">{value || '未知'}</p>
          <p className="text-xs text-ink-muted">#{row.admin_id}</p>
        </div>
      ),
    },
    {
      key: 'action',
      title: '操作',
      width: 130,
      nowrap: true,
      render: (value) => {
        const info = ACTION_LABELS[value] || { label: value, variant: 'default' as const };
        return <Badge variant={info.variant}>{info.label}</Badge>;
      },
    },
    {
      key: 'target_type',
      title: '目标类型',
      width: 100,
      nowrap: true,
      render: (value) => (
        <span className="text-ink-sub text-sm">
          {TARGET_TYPE_LABELS[value] || value}
        </span>
      ),
    },
    {
      key: 'target_id',
      title: '目标ID',
      width: 80,
      align: 'center',
      nowrap: true,
      render: (value) => (
        <span className="text-ink-muted font-mono text-xs">#{value}</span>
      ),
    },
    {
      key: 'detail',
      title: '详情',
      render: (value) => {
        if (!value) return <span className="text-ink-muted">—</span>;
        // detail 可能是 JSON 字符串，尝试解析后友好展示
        let display = value;
        try {
          const parsed = JSON.parse(value);
          if (typeof parsed === 'object' && parsed !== null) {
            display = Object.entries(parsed)
              .map(([k, v]) => `${k}: ${v}`)
              .join('  ');
          }
        } catch {
          // 非 JSON，直接显示原文
        }
        return (
          <p className="text-ink-sub text-sm line-clamp-2 break-words">{display}</p>
        );
      },
    },
    {
      key: 'ip_address',
      title: 'IP',
      width: 120,
      nowrap: true,
      render: (value) => (
        <span className="text-xs text-ink-muted font-mono">{value || '—'}</span>
      ),
    },
    {
      key: 'created_at',
      title: '时间',
      width: 150,
      nowrap: true,
      render: (value) => (
        <span className="text-xs text-ink-sub">{formatDateTime(value)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold text-ink">操作日志</h1>
        <p className="text-ink-sub text-sm mt-1">共 {total} 条记录</p>
      </div>

      {/* 筛选栏 */}
      <Card variant="outlined" padding="md">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink flex items-center gap-1.5">
              <Search size={15} />
              筛选条件
            </h3>
            {hasFilter && (
              <button
                onClick={handleClearFilter}
                className="text-xs text-ink-muted hover:text-danger flex items-center gap-1"
              >
                <RotateCcw size={12} />
                清空
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
            {/* 管理员 ID */}
            <div>
              <label className="block text-xs text-ink-muted mb-1">管理员 ID</label>
              <input
                type="text"
                value={filterAdminId}
                onChange={(e) => setFilterAdminId(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleApplyFilter()}
                placeholder="如：1"
                className="w-full px-2.5 py-1.5 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
              />
            </div>
            {/* 操作类型 */}
            <div>
              <label className="block text-xs text-ink-muted mb-1">操作类型</label>
              <select
                value={filterAction}
                onChange={(e) => setFilterAction(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
              >
                <option value="">全部</option>
                {Object.entries(ACTION_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>
            {/* 目标类型 */}
            <div>
              <label className="block text-xs text-ink-muted mb-1">目标类型</label>
              <select
                value={filterTargetType}
                onChange={(e) => setFilterTargetType(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
              >
                <option value="">全部</option>
                {Object.entries(TARGET_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            {/* 起始日期 */}
            <div>
              <label className="block text-xs text-ink-muted mb-1">起始日期</label>
              <input
                type="date"
                value={filterDateFrom}
                onChange={(e) => setFilterDateFrom(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
              />
            </div>
            {/* 结束日期 */}
            <div>
              <label className="block text-xs text-ink-muted mb-1">结束日期</label>
              <input
                type="date"
                value={filterDateTo}
                onChange={(e) => setFilterDateTo(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
              />
            </div>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button size="sm" variant="text" onClick={handleClearFilter} disabled={!hasFilter}>
              重置
            </Button>
            <Button size="sm" variant="primary" onClick={handleApplyFilter}>
              <Search size={14} className="mr-1" />
              查询
            </Button>
          </div>
        </div>
      </Card>

      {/* 当前筛选摘要 */}
      {Object.keys(applied).length > 0 && (
        <div className="flex items-center gap-2 text-sm text-ink-muted">
          <span>当前筛选：</span>
          {applied.admin_id && (
            <Badge variant="default">管理员 #{applied.admin_id}</Badge>
          )}
          {applied.action && (
            <Badge variant="info">
              {ACTION_LABELS[applied.action]?.label || applied.action}
            </Badge>
          )}
          {applied.target_type && (
            <Badge variant="default">
              {TARGET_TYPE_LABELS[applied.target_type] || applied.target_type}
            </Badge>
          )}
          {applied.date_from && (
            <Badge variant="default">起 {applied.date_from}</Badge>
          )}
          {applied.date_to && (
            <Badge variant="default">止 {applied.date_to}</Badge>
          )}
          <button
            onClick={handleClearFilter}
            className="ml-1 text-ink-muted hover:text-danger"
            title="清空筛选"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* 表格 */}
      {logs.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <ScrollText size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无日志记录</p>
        </Card>
      ) : (
        <Table<AdminLog>
          columns={columns}
          data={logs}
          loading={loading}
          emptyText="暂无日志记录"
        />
      )}

      {/* 分页 */}
      <Pagination
        page={page}
        pageSize={PAGE_SIZE}
        total={total}
        totalPages={totalPages}
        onChange={(p) => setPage(p)}
      />

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50">
          <div
            className={`px-4 py-3 rounded-lg shadow-lg text-sm ${
              toast.type === 'success' ? 'bg-grass text-paper' : 'bg-danger text-paper'
            }`}
          >
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminLogsPage;
