import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import {
  adminApi,
  type GovernanceReportBrief,
  type GovernanceHandleRequest,
} from '../../services/admin';
import { useUIStore } from '../../store/useUIStore';
import { ShieldCheck, Clock, AlertTriangle, Lightbulb, Gavel } from 'lucide-react';

const PAGE_SIZE = 10;

/** 报告类型 → 中文标签 + 图标 + Badge 颜色 */
const TYPE_META: Record<string, { label: string; icon: React.ComponentType<{ size?: number; className?: string }>; variant: 'warning' | 'danger' | 'info' }> = {
  expiration_report: { label: '过期报告', icon: Clock, variant: 'warning' },
  conflict_report: { label: '冲突报告', icon: AlertTriangle, variant: 'danger' },
  update: { label: '更新建议', icon: Lightbulb, variant: 'info' },
};

/** 状态 → 中文标签 + Badge 颜色 */
const STATUS_META: Record<string, { label: string; variant: 'warning' | 'info' | 'success' | 'default' }> = {
  open: { label: '待处理', variant: 'warning' },
  in_review: { label: '处理中', variant: 'info' },
  resolved: { label: '已解决', variant: 'success' },
  dismissed: { label: '已驳回', variant: 'default' },
};

/** 处理动作 → 中文标签（按报告类型过滤可用动作） */
const ACTION_OPTIONS: Array<{ value: GovernanceHandleRequest['action']; label: string; desc: string }> = [
  { value: 'resolve', label: '标记已解决', desc: '报告结案，帖子状态不变' },
  { value: 'dismiss', label: '驳回报告', desc: '报告不成立，帖子状态不变' },
  { value: 'mark_expired', label: '确认过期', desc: '帖子转为「已过期」并通知作者' },
  { value: 'mark_conflict', label: '确认冲突', desc: '帖子转为「冲突中」并通知作者' },
];

const AdminGovernancePage: React.FC = () => {
  const showToast = useUIStore((s) => s.showToast);
  const [searchParams, setSearchParams] = useSearchParams();

  // 从 URL 读取筛选参数（待办卡片跳转入口：/admin/governance?type=xxx&status=open）
  const reportType = searchParams.get('type') || '';
  const status = searchParams.get('status') || '';

  const [reports, setReports] = useState<GovernanceReportBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  // 处理弹窗
  const [handleTarget, setHandleTarget] = useState<GovernanceReportBrief | null>(null);
  const [handleAction, setHandleAction] = useState<GovernanceHandleRequest['action']>('resolve');
  const [handleReason, setHandleReason] = useState('');
  const [handling, setHandling] = useState(false);

  const loadReports = useCallback(async (p: number) => {
    try {
      const data = await adminApi.getGovernanceReports({
        page: p,
        page_size: PAGE_SIZE,
        report_type: reportType || undefined,
        status: status || undefined,
      });
      setReports(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error('加载治理报告失败:', error);
      showToast('加载治理报告失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [reportType, status, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadReports(page);
  }, [page, loadReports]);

  const updateFilter = (key: 'type' | 'status', value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    setSearchParams(next);
    setPage(1);
    setLoading(true);
  };

  const openHandleModal = (report: GovernanceReportBrief) => {
    setHandleTarget(report);
    // 按报告类型预选推荐动作
    if (report.report_type === 'expiration_report') {
      setHandleAction('mark_expired');
    } else if (report.report_type === 'conflict_report') {
      setHandleAction('mark_conflict');
    } else {
      setHandleAction('resolve');
    }
    setHandleReason('');
  };

  const submitHandle = async () => {
    if (!handleTarget) return;
    if (!handleReason.trim()) {
      showToast('请填写处理说明', 'warning');
      return;
    }
    setHandling(true);
    try {
      await adminApi.handleGovernanceReport(handleTarget.id, {
        action: handleAction,
        reason: handleReason.trim(),
      });
      showToast('处理完成', 'success');
      setHandleTarget(null);
      void loadReports(page);
    } catch (error) {
      const message = error instanceof Error ? error.message : '处理失败';
      showToast(message, 'error');
    } finally {
      setHandling(false);
    }
  };

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });

  const columns: Column<GovernanceReportBrief>[] = [
    {
      key: 'report_type',
      title: '类型',
      width: 110,
      render: (value) => {
        const meta = TYPE_META[value] || { label: value, icon: Lightbulb, variant: 'info' as const };
        const Icon = meta.icon;
        return (
          <Badge variant={meta.variant}>
            <Icon size={12} className="mr-1" />
            {meta.label}
          </Badge>
        );
      },
    },
    {
      key: 'post_title',
      title: '关联帖子',
      render: (value, row) => (
        <div className="min-w-0">
          <p className="font-medium text-ink line-clamp-1">{value || `帖子 #${row.post_id}`}</p>
          <p className="text-xs text-ink-muted line-clamp-1 mt-0.5">{row.description || '无说明'}</p>
        </div>
      ),
    },
    {
      key: 'post_status',
      title: '帖子状态',
      width: 90,
      render: (value) => <Badge variant="default">{value || '-'}</Badge>,
    },
    {
      key: 'reporter_name',
      title: '报告人',
      width: 100,
      nowrap: true,
      render: (value) => value || '匿名',
    },
    {
      key: 'status',
      title: '状态',
      width: 90,
      render: (value) => {
        const meta = STATUS_META[value] || { label: value, variant: 'default' as const };
        return <Badge variant={meta.variant}>{meta.label}</Badge>;
      },
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
      width: 110,
      nowrap: true,
      render: (_, row) =>
        row.status === 'open' || row.status === 'in_review' ? (
          <Button size="sm" variant="primary" onClick={() => openHandleModal(row)}>
            <Gavel size={13} className="mr-1" />
            处理
          </Button>
        ) : (
          <span className="text-xs text-ink-muted" title={row.handler_note || ''}>
            {row.handler_name || '管理员'} 已处理
          </span>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold text-ink">治理工作台</h1>
        <p className="text-ink-sub text-sm mt-1">
          处理用户提交的过期报告 / 冲突报告 / 更新建议，共 {total} 条
        </p>
      </div>

      {/* 筛选栏 */}
      <Card variant="outlined" padding="sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-muted mr-1">类型：</span>
          {[
            { value: '', label: '全部' },
            { value: 'expiration_report', label: '过期报告' },
            { value: 'conflict_report', label: '冲突报告' },
            { value: 'update', label: '更新建议' },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => updateFilter('type', opt.value)}
              className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                reportType === opt.value
                  ? 'bg-lake text-paper'
                  : 'bg-mist text-ink-sub hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          ))}
          <span className="text-xs text-ink-muted ml-3 mr-1">状态：</span>
          {[
            { value: '', label: '全部' },
            { value: 'open', label: '待处理' },
            { value: 'in_review', label: '处理中' },
            { value: 'resolved', label: '已解决' },
            { value: 'dismissed', label: '已驳回' },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => updateFilter('status', opt.value)}
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
      {reports.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <ShieldCheck size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无治理报告</p>
        </Card>
      ) : (
        <Table<GovernanceReportBrief>
          columns={columns}
          data={reports}
          loading={loading}
          emptyText="暂无治理报告"
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

      {/* 处理弹窗 */}
      <Modal
        isOpen={handleTarget !== null}
        onClose={() => setHandleTarget(null)}
        title={`处理${TYPE_META[handleTarget?.report_type || '']?.label || '报告'} #${handleTarget?.id}`}
      >
        {handleTarget && (
          <div className="space-y-4">
            <div className="bg-mist/60 rounded-md p-3 text-sm">
              <p className="font-medium text-ink">{handleTarget.post_title || `帖子 #${handleTarget.post_id}`}</p>
              <p className="text-xs text-ink-muted mt-1">
                报告人：{handleTarget.reporter_name || '匿名'} · {formatDate(handleTarget.created_at)}
              </p>
              {handleTarget.description && (
                <p className="text-sm text-ink-sub mt-2">{handleTarget.description}</p>
              )}
              {handleTarget.evidence_url && (
                <a
                  href={handleTarget.evidence_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-lake hover:underline mt-1 inline-block"
                >
                  查看证据材料
                </a>
              )}
            </div>

            <div>
              <p className="text-sm font-medium text-ink mb-2">处理动作</p>
              <div className="space-y-2">
                {ACTION_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className={`flex items-start gap-2.5 p-2.5 rounded-md border cursor-pointer transition-colors ${
                      handleAction === opt.value
                        ? 'border-lake bg-lake/5'
                        : 'border-line hover:border-lake/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="governance-action"
                      checked={handleAction === opt.value}
                      onChange={() => setHandleAction(opt.value)}
                      className="mt-0.5"
                    />
                    <span>
                      <span className="text-sm font-medium text-ink">{opt.label}</span>
                      <span className="block text-xs text-ink-muted mt-0.5">{opt.desc}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="text-sm font-medium text-ink mb-1.5">处理说明（必填）</p>
              <textarea
                value={handleReason}
                onChange={(e) => setHandleReason(e.target.value)}
                rows={3}
                maxLength={500}
                placeholder="说明处理依据，将通知报告人与相关作者"
                className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink focus:border-lake focus:outline-none"
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="text" onClick={() => setHandleTarget(null)}>
                取消
              </Button>
              <Button variant="primary" onClick={submitHandle} loading={handling}>
                确认处理
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default AdminGovernancePage;
