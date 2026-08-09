import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi, type ReportBrief, type HandleReportRequest } from '../../services/admin';
import { Flag } from 'lucide-react';
import { logger } from '../../utils/logger';
import { formatShortDateTime as formatDate } from '../../utils/date';

const PAGE_SIZE = 10;

/** 举报类型 → 中文标签 */
const REPORT_TYPE_LABELS: Record<string, string> = {
  spam: '垃圾信息',
  harassment: '骚扰',
  false_info: '虚假信息',
  inappropriate: '不当内容',
  other: '其他',
};

/** 处理动作配置 */
const ACTION_OPTIONS: Array<{
  value: HandleReportRequest['action'];
  label: string;
  variant: 'default' | 'warning' | 'danger';
  desc: string;
}> = [
  { value: 'dismiss', label: '驳回', variant: 'default', desc: '举报不成立，驳回' },
  { value: 'warn', label: '警告', variant: 'warning', desc: '警告帖子作者' },
  { value: 'delete_post', label: '删除帖子', variant: 'danger', desc: '删除被举报的帖子' },
  { value: 'ban_user', label: '封禁用户', variant: 'danger', desc: '禁用帖子作者账号' },
];

const AdminReportsPage: React.FC = () => {
  const [reports, setReports] = useState<ReportBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // 处理面板状态
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [processAction, setProcessAction] = useState<HandleReportRequest['action']>('dismiss');
  const [processReason, setProcessReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadReports = useCallback(async (p: number, status?: string) => {
    try {
      const data = await adminApi.getReports({ page: p, page_size: PAGE_SIZE, status });
      setReports(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      logger.error('加载举报列表失败:', error);
      setToast({ message: '加载举报列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadReports(page, filterStatus);
  }, [page, filterStatus, loadReports]);

  /** 打开处理面板 */
  const openProcessPanel = (reportId: number) => {
    setProcessingId(reportId);
    setProcessAction('dismiss');
    setProcessReason('');
  };

  /** 关闭处理面板 */
  const closeProcessPanel = () => {
    setProcessingId(null);
    setProcessReason('');
  };

  /** 提交处理 */
  const handleSubmit = async (reportId: number) => {
    if (!processReason.trim()) {
      setToast({ message: '请输入处理说明', type: 'warning' });
      return;
    }
    setSubmitting(true);
    try {
      await adminApi.handleReport(reportId, {
        action: processAction,
        reason: processReason.trim(),
      });
      setToast({ message: '举报已处理', type: 'success' });
      closeProcessPanel();
      loadReports(page, filterStatus);
    } catch (error) {
      logger.error('处理失败:', error);
      setToast({ message: '处理失败', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  // 表格列配置
  const columns: Column<ReportBrief>[] = [
    {
      key: 'post_title',
      title: '举报内容',
      render: (value, row) => (
        <div className="min-w-0">
          {value ? (
            <p className="font-medium text-ink line-clamp-1">{value}</p>
          ) : (
            <p className="text-ink-muted italic">（无关联帖子）</p>
          )}
          <p className="text-xs text-ink-muted line-clamp-1 mt-0.5">
            {row.description || '无描述'}
          </p>
        </div>
      ),
    },
    {
      key: 'reporter_name',
      title: '举报人',
      width: 110,
      nowrap: true,
      render: (value) => value || '匿名',
    },
    {
      key: 'report_type',
      title: '类型',
      width: 100,
      nowrap: true,
      render: (value) => (
        <Badge variant="default">
          {REPORT_TYPE_LABELS[value] || value}
        </Badge>
      ),
    },
    {
      key: 'status',
      title: '状态',
      width: 90,
      nowrap: true,
      render: (value) => {
        if (value === 'pending') return <Badge variant="warning">待处理</Badge>;
        if (value === 'handled') return <Badge variant="success">已处理</Badge>;
        return <Badge variant="default">{value}</Badge>;
      },
    },
    {
      key: 'created_at',
      title: '举报时间',
      width: 130,
      nowrap: true,
      render: (value) => formatDate(value),
    },
    {
      key: 'actions',
      title: '操作',
      width: 100,
      nowrap: true,
      render: (_, row) => {
        if (row.status !== 'pending') {
          return <span className="text-xs text-ink-muted inline-block w-12 text-center">已处理</span>;
        }
        if (processingId === row.id) {
          return (
            <button
              onClick={closeProcessPanel}
              className="text-sm text-ink-muted hover:text-ink inline-flex items-center justify-center w-12 h-8"
            >
              收起
            </button>
          );
        }
        return (
          <Button size="sm" variant="primary" onClick={() => openProcessPanel(row.id)} className="w-12">
            处理
          </Button>
        );
      },
    },
  ];

  // 筛选选项
  const filterOptions: Array<{ label: string; value: string | undefined }> = [
    { label: '全部', value: undefined },
    { label: '待处理', value: 'pending' },
    { label: '已处理', value: 'handled' },
  ];

  // 当前正在处理的举报
  const processingReport = reports.find((r) => r.id === processingId);

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">举报管理</h1>
          <p className="text-ink-sub text-sm mt-1">共 {total} 条举报</p>
        </div>
        {/* 筛选 */}
        <div className="flex items-center gap-1 bg-paper border border-line rounded-md p-0.5">
          {filterOptions.map((opt) => (
            <button
              key={String(opt.label)}
              onClick={() => {
                setFilterStatus(opt.value);
                setPage(1);
              }}
              className={`px-4 py-2 rounded text-sm transition-colors min-w-[88px] text-center ${
                filterStatus === opt.value
                  ? 'bg-lake text-paper'
                  : 'text-ink-sub hover:bg-mist'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 表格 */}
      {reports.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <Flag size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无举报记录</p>
        </Card>
      ) : (
        <Table<ReportBrief>
          columns={columns}
          data={reports}
          loading={loading}
          emptyText="暂无举报记录"
        />
      )}

      {/* 处理面板（内联展开） */}
      {processingReport && (
        <Card variant="outlined" padding="md">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-ink">
                处理举报 #{processingReport.id}
              </h3>
              <button
                onClick={closeProcessPanel}
                className="text-ink-muted hover:text-ink"
              >
                收起
              </button>
            </div>

            {/* 举报摘要 */}
            <div className="bg-mist/50 rounded-md p-3 text-sm">
              <p className="text-ink">
                <span className="text-ink-muted">举报内容：</span>
                {processingReport.post_title || '无关联帖子'}
              </p>
              <p className="text-ink mt-1">
                <span className="text-ink-muted">举报理由：</span>
                {processingReport.description || '无描述'}
              </p>
            </div>

            {/* 动作选择 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-2">处理动作</label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {ACTION_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setProcessAction(opt.value)}
                    className={`p-2.5 rounded-md border text-left transition-all ${
                      processAction === opt.value
                        ? 'border-lake bg-lake/5 ring-1 ring-lake/30'
                        : 'border-line hover:border-lake/40 bg-paper'
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <Badge variant={opt.variant}>{opt.label}</Badge>
                    </div>
                    <p className="text-xs text-ink-muted mt-1">{opt.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* 处理说明 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-2">
                处理说明 <span className="text-danger">*</span>
              </label>
              <textarea
                value={processReason}
                onChange={(e) => setProcessReason(e.target.value)}
                placeholder="请输入处理说明（必填）"
                rows={3}
                className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake resize-none"
              />
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center justify-end gap-2">
              <Button size="sm" variant="text" onClick={closeProcessPanel}>
                取消
              </Button>
              <Button
                size="sm"
                variant="primary"
                onClick={() => handleSubmit(processingReport.id)}
                loading={submitting}
              >
                确认处理
              </Button>
            </div>
          </div>
        </Card>
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
              toast.type === 'success'
                ? 'bg-grass text-paper'
                : toast.type === 'warning'
                ? 'bg-sun text-ink'
                : 'bg-danger text-paper'
            }`}
          >
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminReportsPage;
