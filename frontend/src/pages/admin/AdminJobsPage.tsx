import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi, type JobRunRecord } from '../../services/admin';
import { useUIStore } from '../../store/useUIStore';
import { Wrench, Play, FlaskConical } from 'lucide-react';
import { logger } from '../../utils/logger';
import { formatShortDateTime } from '../../utils/date';

const PAGE_SIZE = 10;

/** 状态 → 中文标签 + Badge 颜色 */
const STATUS_META: Record<string, { label: string; variant: 'success' | 'danger' | 'info' }> = {
  success: { label: '成功', variant: 'success' },
  failed: { label: '失败', variant: 'danger' },
  running: { label: '运行中', variant: 'info' },
};

/** GOV-02.2: 任务运行记录（待办卡片入口 /admin/jobs?status=failed） */
const AdminJobsPage: React.FC = () => {
  const showToast = useUIStore((s) => s.showToast);
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get('status') || '';

  const [records, setRecords] = useState<JobRunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [triggering, setTriggering] = useState(false);

  const loadRecords = useCallback(async (p: number) => {
    try {
      const data = await adminApi.getJobRecords({
        page: p,
        page_size: PAGE_SIZE,
        status: status || undefined,
      });
      setRecords(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      logger.error('加载任务记录失败:', error);
      showToast('加载任务记录失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [status, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadRecords(page);
  }, [page, loadRecords]);

  const updateFilter = (value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set('status', value);
    } else {
      next.delete('status');
    }
    setSearchParams(next);
    setPage(1);
    setLoading(true);
  };

  const handleTrigger = async (dryRun: boolean) => {
    setTriggering(true);
    try {
      const record = await adminApi.triggerExpirePostsJob(dryRun);
      showToast(
        dryRun
          ? `预演完成：将处理 ${record.processed_count} 条（未写库）`
          : `任务完成：处理 ${record.processed_count} 条，失败 ${record.failed_count} 条`,
        record.status === 'failed' ? 'error' : 'success',
      );
      void loadRecords(page);
    } catch (error) {
      const message = error instanceof Error ? error.message : '触发任务失败';
      showToast(message, 'error');
    } finally {
      setTriggering(false);
    }
  };

  const formatDate = (dateString: string | null) =>
    dateString ? formatShortDateTime(dateString) : '—';

  const columns: Column<JobRunRecord>[] = [
    {
      key: 'job_name',
      title: '任务',
      width: 130,
      render: (value, row) => (
        <div>
          <span className="font-medium text-ink">{value}</span>
          {row.dry_run && (
            <Badge variant="info" className="ml-1.5">预演</Badge>
          )}
        </div>
      ),
    },
    {
      key: 'status',
      title: '状态',
      width: 90,
      render: (value) => {
        const meta = STATUS_META[value] || { label: value, variant: 'info' as const };
        return <Badge variant={meta.variant}>{meta.label}</Badge>;
      },
    },
    {
      key: 'processed_count',
      title: '处理/失败',
      width: 100,
      nowrap: true,
      render: (_, row) => (
        <span>
          <span className="text-grass font-medium">{row.processed_count}</span>
          {' / '}
          <span className={row.failed_count > 0 ? 'text-danger font-medium' : 'text-ink-muted'}>
            {row.failed_count}
          </span>
        </span>
      ),
    },
    {
      key: 'triggered_by',
      title: '触发方式',
      width: 90,
      render: (value) => (value === 'manual' ? '手动' : '系统'),
    },
    {
      key: 'duration_seconds',
      title: '耗时',
      width: 80,
      nowrap: true,
      render: (value) => (value != null ? `${value.toFixed(1)}s` : '—'),
    },
    {
      key: 'started_at',
      title: '开始时间',
      width: 130,
      nowrap: true,
      render: (value) => formatDate(value),
    },
    {
      key: 'error_message',
      title: '备注',
      render: (value) => (
        <span className="text-xs text-ink-muted line-clamp-1" title={value || ''}>
          {value || '—'}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">任务记录</h1>
          <p className="text-ink-sub text-sm mt-1">
            自动过期任务（published → expired）运行记录，共 {total} 条
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            loading={triggering}
            onClick={() => handleTrigger(true)}
          >
            <FlaskConical size={14} className="mr-1" />
            预演（不写库）
          </Button>
          <Button
            size="sm"
            variant="primary"
            loading={triggering}
            onClick={() => handleTrigger(false)}
          >
            <Play size={14} className="mr-1" />
            手动执行
          </Button>
        </div>
      </div>

      {/* 筛选栏 */}
      <Card variant="outlined" padding="sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-muted mr-1">状态：</span>
          {[
            { value: '', label: '全部' },
            { value: 'success', label: '成功' },
            { value: 'failed', label: '失败' },
            { value: 'running', label: '运行中' },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => updateFilter(opt.value)}
              className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                status === opt.value
                  ? 'bg-lake text-paper'
                  : 'bg-mist text-ink-sub hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </Card>

      {/* 表格 */}
      {records.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <Wrench size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无任务运行记录</p>
        </Card>
      ) : (
        <Table<JobRunRecord>
          columns={columns}
          data={records}
          loading={loading}
          emptyText="暂无任务运行记录"
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
    </div>
  );
};

export default AdminJobsPage;
