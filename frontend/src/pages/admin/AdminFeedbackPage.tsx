import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi, type FeedbackItem, type FeedbackUpdateRequest } from '../../services/admin';
import { MessageCircle } from 'lucide-react';
import { logger } from '../../utils/logger';
import { formatShortDateTime as formatDate } from '../../utils/date';

const PAGE_SIZE = 10;

/** 反馈类型 → 中文标签 */
const FEEDBACK_TYPE_LABELS: Record<string, string> = {
  suggestion: '建议',
  bug: '问题/Bug',
  complaint: '投诉',
  other: '其他',
};

const AdminFeedbackPage: React.FC = () => {
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // 处理面板状态
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [newStatus, setNewStatus] = useState<FeedbackUpdateRequest['status']>('in_review');
  const [remark, setRemark] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadFeedbacks = useCallback(async (p: number, status?: string) => {
    try {
      const data = await adminApi.getAllFeedbacks({ page: p, page_size: PAGE_SIZE, status });
      setFeedbacks(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      logger.error('加载反馈列表失败:', error);
      setToast({ message: '加载反馈列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadFeedbacks(page, filterStatus);
  }, [page, filterStatus, loadFeedbacks]);

  /** 打开处理面板 */
  const openProcessPanel = (item: FeedbackItem) => {
    setProcessingId(item.id);
    setNewStatus(item.status === 'open' ? 'in_review' : 'resolved');
    setRemark(item.remark || '');
  };

  /** 关闭处理面板 */
  const closeProcessPanel = () => {
    setProcessingId(null);
    setRemark('');
  };

  /** 提交处理 */
  const handleSubmit = async (feedbackId: number) => {
    setSubmitting(true);
    try {
      await adminApi.updateFeedback(feedbackId, {
        status: newStatus,
        remark: remark.trim() || undefined,
      });
      setToast({ message: '反馈已更新', type: 'success' });
      closeProcessPanel();
      loadFeedbacks(page, filterStatus);
    } catch (error) {
      logger.error('更新反馈失败:', error);
      setToast({ message: '更新失败', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  // 表格列配置
  const columns: Column<FeedbackItem>[] = [
    {
      key: 'content',
      title: '反馈内容',
      render: (value, row) => (
        <div className="min-w-0">
          <p className="font-medium text-ink line-clamp-1">{value}</p>
          <p className="text-xs text-ink-muted line-clamp-1 mt-0.5">
            {row.user_name ? `反馈人：${row.user_name}` : `反馈人：#${row.user_id}`}
            {row.contact ? ` · 联系方式：${row.contact}` : ''}
          </p>
        </div>
      ),
    },
    {
      key: 'feedback_type',
      title: '类型',
      width: 110,
      nowrap: true,
      render: (value) => (
        <Badge variant="default">
          {FEEDBACK_TYPE_LABELS[value] || value}
        </Badge>
      ),
    },
    {
      key: 'status',
      title: '状态',
      width: 90,
      nowrap: true,
      render: (value) => {
        if (value === 'open') return <Badge variant="warning">待处理</Badge>;
        if (value === 'in_review') return <Badge variant="info">处理中</Badge>;
        return <Badge variant="success">已解决</Badge>;
      },
    },
    {
      key: 'remark',
      title: '处理备注',
      render: (value) => (
        <p className="text-xs text-ink-muted line-clamp-1">{value || '—'}</p>
      ),
    },
    {
      key: 'created_at',
      title: '提交时间',
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
        if (processingId === row.id) {
          return (
            <button
              onClick={closeProcessPanel}
              className="text-sm text-ink-muted hover:text-ink"
            >
              收起
            </button>
          );
        }
        return (
          <Button size="sm" variant="primary" onClick={() => openProcessPanel(row)}>
            处理
          </Button>
        );
      },
    },
  ];

  // 筛选选项
  const filterOptions: Array<{ label: string; value: string | undefined }> = [
    { label: '全部', value: undefined },
    { label: '待处理', value: 'open' },
    { label: '处理中', value: 'in_review' },
    { label: '已解决', value: 'resolved' },
  ];

  // 当前正在处理的反馈
  const processingFeedback = feedbacks.find((f) => f.id === processingId);

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">反馈管理</h1>
          <p className="text-ink-sub text-sm mt-1">共 {total} 条反馈</p>
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
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
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
      {feedbacks.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <MessageCircle size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无反馈记录</p>
        </Card>
      ) : (
        <Table<FeedbackItem>
          columns={columns}
          data={feedbacks}
          loading={loading}
          emptyText="暂无反馈记录"
        />
      )}

      {/* 处理面板（内联展开） */}
      {processingFeedback && (
        <Card variant="outlined" padding="md">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-ink">
                处理反馈 #{processingFeedback.id}
              </h3>
              <button
                onClick={closeProcessPanel}
                className="text-ink-muted hover:text-ink"
              >
                收起
              </button>
            </div>

            {/* 反馈摘要 */}
            <div className="bg-mist/50 rounded-md p-3 text-sm">
              <p className="text-ink">
                <span className="text-ink-muted">反馈人：</span>
                {processingFeedback.user_name || `#${processingFeedback.user_id}`}
              </p>
              <p className="text-ink mt-1">
                <span className="text-ink-muted">类型：</span>
                {FEEDBACK_TYPE_LABELS[processingFeedback.feedback_type] || processingFeedback.feedback_type}
                {processingFeedback.contact ? ` · 联系方式：${processingFeedback.contact}` : ''}
              </p>
              <p className="text-ink mt-1">
                <span className="text-ink-muted">内容：</span>
                {processingFeedback.content}
              </p>
            </div>

            {/* 状态选择 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-2">更新状态</label>
              <div className="grid grid-cols-3 gap-2">
                {([
                  { value: 'open', label: '待处理' },
                  { value: 'in_review', label: '处理中' },
                  { value: 'resolved', label: '已解决' },
                ] as Array<{ value: FeedbackUpdateRequest['status']; label: string }>).map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setNewStatus(opt.value)}
                    className={`p-2.5 rounded-md border text-center text-sm transition-all ${
                      newStatus === opt.value
                        ? 'border-lake bg-lake/5 ring-1 ring-lake/30 font-medium text-ink'
                        : 'border-line hover:border-lake/40 bg-paper text-ink-sub'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 处理备注 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-2">
                处理备注（可选）
              </label>
              <textarea
                value={remark}
                onChange={(e) => setRemark(e.target.value)}
                placeholder="请输入处理备注（可选，将展示给用户）"
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
                onClick={() => handleSubmit(processingFeedback.id)}
                loading={submitting}
              >
                确认更新
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

export default AdminFeedbackPage;