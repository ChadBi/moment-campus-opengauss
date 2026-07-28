import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import {
  adminApi,
  type PostBrief,
  type AdminPostDetail,
  type ReasonTemplate,
  type BatchOperationResult,
} from '../../services/admin';
import { Check, X, Eye, FileText, MapPin, User, AlertTriangle } from 'lucide-react';
import { logger } from '../../utils/logger';
import { formatShortDateTime as formatDate } from '../../utils/date';

const PAGE_SIZE = 10;

/** 审核动作弹窗模式：单条通过 / 单条驳回 / 批量通过 / 批量驳回 */
type ReviewActionMode = 'approve' | 'reject' | 'batch_approve' | 'batch_reject';

const AdminReviewPage: React.FC = () => {
  const [posts, setPosts] = useState<PostBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [selectedKeys, setSelectedKeys] = useState<Array<string | number>>([]);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // 审核详情弹窗（ADM-01.2：管理专用接口）
  const [detail, setDetail] = useState<AdminPostDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 原因模板（ADM-01.3）
  const [approveTemplates, setApproveTemplates] = useState<ReasonTemplate[]>([]);
  const [rejectTemplates, setRejectTemplates] = useState<ReasonTemplate[]>([]);

  // 审核动作弹窗（通过/驳回 + 原因模板）
  const [actionMode, setActionMode] = useState<ReviewActionMode | null>(null);
  const [actionPostId, setActionPostId] = useState<number | null>(null);
  const [actionReason, setActionReason] = useState('');
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // 批量结果弹窗（ADM-01.4：逐项成功/失败/原因）
  const [batchResult, setBatchResult] = useState<BatchOperationResult | null>(null);

  const loadPosts = useCallback(async (p: number) => {
    try {
      const data = await adminApi.getPendingPosts({ page: p, page_size: PAGE_SIZE });
      setPosts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setSelectedKeys([]);
    } catch (error) {
      logger.error('加载待审核帖子失败:', error);
      setToast({ message: '加载待审核帖子失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadPosts(page);
  }, [page, loadPosts]);

  // 加载原因模板（一次即可）
  useEffect(() => {
    adminApi
      .getReviewTemplates()
      .then((tpl) => {
        setApproveTemplates(tpl.approve);
        setRejectTemplates(tpl.reject);
      })
      .catch((err) => logger.error('加载原因模板失败:', err));
  }, []);

  /** 打开审核详情（管理专用接口，pending 帖子公开详情不可见） */
  const openDetail = async (postId: number) => {
    setDetailLoading(true);
    try {
      const data = await adminApi.getAdminPostDetail(postId);
      setDetail(data);
    } catch (error) {
      logger.error('加载审核详情失败:', error);
      setToast({ message: '加载审核详情失败', type: 'error' });
    } finally {
      setDetailLoading(false);
    }
  };

  /** 打开审核动作弹窗 */
  const openAction = (mode: ReviewActionMode, postId?: number) => {
    setActionMode(mode);
    setActionPostId(postId ?? null);
    // 预填第一个模板内容，便于快速操作
    const tpl = mode === 'approve' || mode === 'batch_approve' ? approveTemplates : rejectTemplates;
    setActionReason(tpl[0]?.text ?? '');
  };

  /** 提交审核动作（通过/驳回，单条/批量） */
  const submitAction = async () => {
    if (!actionMode) return;
    const isReject = actionMode === 'reject' || actionMode === 'batch_reject';
    if (isReject && !actionReason.trim()) {
      setToast({ message: '驳回必须填写原因', type: 'warning' });
      return;
    }
    setActionSubmitting(true);
    try {
      if (actionMode === 'approve' && actionPostId !== null) {
        await adminApi.approvePost(actionPostId, { reason: actionReason || undefined });
        setToast({ message: '审核通过', type: 'success' });
      } else if (actionMode === 'reject' && actionPostId !== null) {
        await adminApi.rejectPost(actionPostId, { reason: actionReason.trim() });
        setToast({ message: '已驳回并退回草稿', type: 'success' });
      } else if (actionMode === 'batch_approve') {
        const result = await adminApi.batchApprovePosts({
          post_ids: selectedKeys as number[],
          reason: actionReason || undefined,
        });
        setBatchResult(result);
      } else if (actionMode === 'batch_reject') {
        const result = await adminApi.batchRejectPosts({
          post_ids: selectedKeys as number[],
          reason: actionReason.trim(),
        });
        setBatchResult(result);
      }
      setActionMode(null);
      setDetail(null);
      void loadPosts(page);
    } catch (error) {
      logger.error('审核操作失败:', error);
      setToast({ message: '审核操作失败', type: 'error' });
    } finally {
      setActionSubmitting(false);
    }
  };

  const isRejectAction = actionMode === 'reject' || actionMode === 'batch_reject';
  const currentTemplates = isRejectAction ? rejectTemplates : approveTemplates;

  // 表格列配置
  const columns: Column<PostBrief>[] = [
    {
      key: 'title',
      title: '标题',
      render: (value, row) => (
        <div className="min-w-0">
          <button
            onClick={() => openDetail(row.id)}
            className="text-left font-medium text-ink hover:text-lake hover:underline line-clamp-1"
          >
            {value}
          </button>
          <p className="text-xs text-ink-muted line-clamp-1 mt-0.5">{row.content}</p>
        </div>
      ),
    },
    {
      key: 'author_name',
      title: '作者',
      width: 120,
      nowrap: true,
      render: (value) => value || '匿名用户',
    },
    {
      key: 'category_name',
      title: '分类',
      width: 100,
      render: (value) => (
        <Badge variant="default">{value || '未分类'}</Badge>
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
      width: 180,
      nowrap: true,
      render: (_, row) => (
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => openDetail(row.id)}
            className="p-1.5 rounded-md text-ink-sub hover:bg-mist hover:text-lake transition-colors"
            title="审核详情"
          >
            <Eye size={15} />
          </button>
          <button
            onClick={() => openAction('approve', row.id)}
            className="p-1.5 rounded-md text-grass hover:bg-grass/10 transition-colors"
            title="通过"
          >
            <Check size={15} />
          </button>
          <button
            onClick={() => openAction('reject', row.id)}
            className="p-1.5 rounded-md text-danger hover:bg-danger/10 transition-colors"
            title="驳回"
          >
            <X size={15} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">内容审核</h1>
          <p className="text-ink-sub text-sm mt-1">
            待审核信息：共 {total} 条
          </p>
        </div>
      </div>

      {/* 批量操作栏（选中时显示） */}
      {selectedKeys.length > 0 && (
        <Card variant="filled" padding="sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink">
              已选择 <span className="font-semibold text-lake">{selectedKeys.length}</span> 条
            </span>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="primary"
                onClick={() => openAction('batch_approve')}
              >
                <Check size={14} className="mr-1" />
                批量通过
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => openAction('batch_reject')}
              >
                <X size={14} className="mr-1" />
                批量驳回
              </Button>
              <Button
                size="sm"
                variant="text"
                onClick={() => setSelectedKeys([])}
              >
                取消选择
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 表格 */}
      {posts.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <FileText size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无待审核内容</p>
        </Card>
      ) : (
        <Table<PostBrief>
          columns={columns}
          data={posts}
          loading={loading}
          selectable
          selectedRowKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
          emptyText="暂无待审核内容"
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

      {/* ADM-01.2: 审核详情弹窗（管理专用接口） */}
      <Modal
        isOpen={detail !== null || detailLoading}
        onClose={() => setDetail(null)}
        title="审核详情"
        size="lg"
      >
        {detailLoading && !detail ? (
          <div className="py-10 flex items-center justify-center text-ink-muted text-sm">
            <div className="w-4 h-4 border-2 border-lake/30 border-t-lake rounded-full animate-spin mr-2" />
            加载详情中...
          </div>
        ) : detail ? (
          <div className="space-y-4">
            {/* 标题与状态 */}
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-lg font-bold text-ink">{detail.title}</h3>
                <Badge variant="warning">待审核</Badge>
                {detail.is_anonymous && <Badge variant="default">匿名发布</Badge>}
              </div>
              <p className="text-xs text-ink-muted mt-1">
                提交于 {formatDate(detail.created_at)}
                {detail.expire_at && ` · 有效期至 ${formatDate(detail.expire_at)}`}
              </p>
            </div>

            {/* 完整内容 */}
            <div className="bg-mist/60 rounded-md p-3">
              <p className="text-sm text-ink whitespace-pre-wrap">{detail.content}</p>
            </div>

            {/* 图片 */}
            {detail.images.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {detail.images.map((img, idx) => (
                  <img
                    key={img.id || idx}
                    src={img.image_url}
                    alt={`图片 ${idx + 1}`}
                    className="w-24 h-24 object-cover rounded-md border border-line"
                  />
                ))}
              </div>
            )}

            {/* 元信息 */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <div>
                <p className="text-xs text-ink-muted">分类</p>
                <p className="text-ink mt-0.5">
                  {detail.category_name || '未分类'}
                </p>
              </div>
              <div>
                <p className="text-xs text-ink-muted">地点</p>
                <p className="text-ink mt-0.5 flex items-center gap-1">
                  <MapPin size={12} className="text-ink-muted" />
                  {detail.location_name || '未关联'}
                  {detail.location_verified === false && (
                    <Badge variant="warning">未核验</Badge>
                  )}
                </p>
              </div>
              <div>
                <p className="text-xs text-ink-muted">联系方式</p>
                <p className="text-ink mt-0.5">{detail.contact_info || '—'}</p>
              </div>
            </div>

            {/* 作者历史与治理概况 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="border border-line rounded-md p-3">
                <p className="text-xs text-ink-muted flex items-center gap-1 mb-2">
                  <User size={12} />
                  作者历史（{detail.author_name || '匿名'} · {detail.author_email || '无邮箱'}）
                </p>
                <div className="flex gap-4 text-sm">
                  <span className="text-ink">发布 {detail.author_history.total_posts}</span>
                  <span className="text-grass">公开 {detail.author_history.published_posts}</span>
                  <span className="text-danger">被举报 {detail.author_history.report_received_count}</span>
                </div>
              </div>
              <div className="border border-line rounded-md p-3">
                <p className="text-xs text-ink-muted flex items-center gap-1 mb-2">
                  <AlertTriangle size={12} />
                  本帖治理概况
                </p>
                <div className="flex gap-4 text-sm">
                  <span className="text-danger">待处理举报 {detail.pending_user_reports}</span>
                </div>
              </div>
            </div>

            {/* 操作 */}
            <div className="flex justify-end gap-2 pt-1">
              <Button
                variant="danger"
                onClick={() => openAction('reject', detail.id)}
              >
                <X size={14} className="mr-1" />
                驳回
              </Button>
              <Button
                variant="primary"
                onClick={() => openAction('approve', detail.id)}
              >
                <Check size={14} className="mr-1" />
                通过
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      {/* ADM-01.3: 审核动作弹窗（通过/驳回 + 原因模板） */}
      <Modal
        isOpen={actionMode !== null}
        onClose={() => setActionMode(null)}
        title={
          actionMode === 'approve'
            ? '通过审核'
            : actionMode === 'reject'
            ? '驳回审核'
            : actionMode === 'batch_approve'
            ? `批量通过（${selectedKeys.length} 条）`
            : `批量驳回（${selectedKeys.length} 条）`
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-sub">
            {isRejectAction
              ? '驳回后帖子将退回作者草稿，作者可修改后重新提交。请选择或填写驳回原因：'
              : '可选择备注模板，也可直接填写备注（选填）：'}
          </p>

          {/* 原因模板 */}
          {currentTemplates.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {currentTemplates.map((tpl) => (
                <button
                  key={tpl.code}
                  onClick={() => setActionReason(tpl.text)}
                  className={`px-2.5 py-1.5 rounded-md text-xs border transition-colors ${
                    actionReason === tpl.text
                      ? 'border-lake bg-lake/5 text-lake'
                      : 'border-line text-ink-sub hover:border-lake/50'
                  }`}
                  title={tpl.text}
                >
                  {tpl.label}
                </button>
              ))}
            </div>
          )}

          <textarea
            value={actionReason}
            onChange={(e) => setActionReason(e.target.value)}
            rows={3}
            maxLength={500}
            placeholder={isRejectAction ? '驳回原因（必填）' : '审核备注（选填）'}
            className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm text-ink focus:border-lake focus:outline-none"
          />

          <div className="flex justify-end gap-2">
            <Button variant="text" onClick={() => setActionMode(null)}>
              取消
            </Button>
            <Button
              variant={isRejectAction ? 'danger' : 'primary'}
              onClick={submitAction}
              loading={actionSubmitting}
            >
              {isRejectAction ? '确认驳回' : '确认通过'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ADM-01.4: 批量操作结果弹窗（逐项成功/失败/原因） */}
      <Modal
        isOpen={batchResult !== null}
        onClose={() => setBatchResult(null)}
        title="批量操作结果"
      >
        {batchResult && (
          <div className="space-y-4">
            <div className="flex gap-4 text-sm">
              <span className="text-ink">共 {batchResult.total} 条</span>
              <span className="text-grass font-medium">成功 {batchResult.success}</span>
              <span className={batchResult.failed > 0 ? 'text-danger font-medium' : 'text-ink-muted'}>
                失败 {batchResult.failed}
              </span>
            </div>
            {batchResult.failed_items.length > 0 ? (
              <div>
                <p className="text-xs text-ink-muted mb-2">失败明细：</p>
                <ul className="space-y-1.5 max-h-64 overflow-y-auto">
                  {batchResult.failed_items.map((item) => (
                    <li
                      key={item.id}
                      className="text-sm flex items-start gap-2 border-b border-ink-divider last:border-0 pb-1.5"
                    >
                      <Badge variant="danger" className="shrink-0 mt-0.5">#{item.id}</Badge>
                      <span className="text-ink-sub">{item.reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-sm text-grass">全部处理成功</p>
            )}
            <div className="flex justify-end">
              <Button variant="primary" onClick={() => setBatchResult(null)}>
                知道了
              </Button>
            </div>
          </div>
        )}
      </Modal>

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

export default AdminReviewPage;
