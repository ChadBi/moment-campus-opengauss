import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Input } from '../../components/ui/Input';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import {
  adminApi,
  type LocationAdmin,
  type LocationFactProposalAdmin,
  type LocationSummaryAdmin,
} from '../../services/admin';
import { useUIStore } from '../../store/useUIStore';
import { MapPin, Check, X, Search, Eye, Building2, Layers, User, Clock, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import MapLocationPicker from '../../components/MapLocationPicker';
import { logger } from '../../utils/logger';
import { formatShortDateTime as formatDate } from '../../utils/date';

const PAGE_SIZE = 10;
const FACT_PAGE_SIZE = 5;

/** ADM-01.6: 地点核验队列（待办卡片入口 /admin/locations?verified=false） */
const AdminLocationsPage: React.FC = () => {
  const showToast = useUIStore((s) => s.showToast);
  const [searchParams, setSearchParams] = useSearchParams();

  // URL 筛选：verified=true/false（待办卡片跳转带 verified=false）
  const verifiedParam = searchParams.get('verified') || '';
  const isVerifiedFilter: boolean | undefined =
    verifiedParam === 'true' ? true : verifiedParam === 'false' ? false : undefined;

  const [locations, setLocations] = useState<LocationAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [actingId, setActingId] = useState<number | null>(null);
  // Task 3.6: 详情弹窗（展示地点坐标 + 地图）
  const [detailLocation, setDetailLocation] = useState<LocationAdmin | null>(null);
  const [factProposals, setFactProposals] = useState<LocationFactProposalAdmin[]>([]);
  const [factTotal, setFactTotal] = useState(0);
  const [factTotalPages, setFactTotalPages] = useState(0);
  const [factPage, setFactPage] = useState(1);
  const [summaryQueue, setSummaryQueue] = useState<LocationSummaryAdmin[]>([]);
  const [knowledgeLoading, setKnowledgeLoading] = useState(true);
  const [actingKnowledgeId, setActingKnowledgeId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState<Record<number, string>>({});
  const [expandedReject, setExpandedReject] = useState<number | null>(null);

  const loadLocations = useCallback(async (p: number) => {
    try {
      const data = await adminApi.getAdminLocations({
        page: p,
        page_size: PAGE_SIZE,
        is_verified: isVerifiedFilter,
        keyword: keyword || undefined,
      });
      setLocations(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      logger.error('加载地点列表失败:', error);
      showToast('加载地点列表失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [isVerifiedFilter, keyword, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadLocations(page);
  }, [page, loadLocations]);

  const loadKnowledgeQueues = useCallback(async (p: number = factPage) => {
    setKnowledgeLoading(true);
    try {
      const [proposals, summaries] = await Promise.all([
        adminApi.getLocationFactProposals({ status: 'pending', page: p, page_size: FACT_PAGE_SIZE }),
        adminApi.getLocationSummaries({ status: 'pending_review', page: 1, page_size: 5 }),
      ]);
      setFactProposals(proposals.items);
      setFactTotal(proposals.total);
      setFactTotalPages(proposals.total_pages);
      setSummaryQueue(summaries.items);
    } catch (error) {
      logger.error('加载地点知识审核队列失败:', error);
    } finally {
      setKnowledgeLoading(false);
    }
  }, [factPage]);

  useEffect(() => {
    void loadKnowledgeQueues(factPage);
  }, [factPage, loadKnowledgeQueues]);

  const handleKnowledgeAction = async (
    kind: 'fact' | 'summary',
    id: number,
    action: 'approve' | 'reject',
  ) => {
    const key = `${kind}:${id}`;
    setActingKnowledgeId(key);
    try {
      const reason = action === 'reject' ? (rejectReason[id] || '').trim() || undefined : undefined;
      if (kind === 'fact') {
        if (action === 'approve') await adminApi.approveLocationFactProposal(id);
        else await adminApi.rejectLocationFactProposal(id, reason);
      } else if (action === 'approve') {
        await adminApi.approveLocationSummary(id);
      } else {
        await adminApi.rejectLocationSummary(id, reason);
      }
      showToast(action === 'approve' ? '已批准' : '已驳回', 'success');
      setExpandedReject(null);
      setRejectReason((prev) => { const next = { ...prev }; delete next[id]; return next; });
      void loadKnowledgeQueues(factPage);
    } catch (error) {
      logger.error('地点知识审核失败:', error);
      showToast('审核操作失败', 'error');
    } finally {
      setActingKnowledgeId(null);
    }
  };

  const toggleRejectInput = (id: number) => {
    setExpandedReject(expandedReject === id ? null : id);
  };

  const updateVerifiedFilter = (value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set('verified', value);
    } else {
      next.delete('verified');
    }
    setSearchParams(next);
    setPage(1);
    setLoading(true);
  };

  const handleSearch = () => {
    setKeyword(searchInput);
    setPage(1);
    setLoading(true);
  };

  const handleVerify = async (loc: LocationAdmin, target: boolean) => {
    setActingId(loc.id);
    try {
      await adminApi.verifyLocation(loc.id, target);
      showToast(target ? `已核验「${loc.name}」` : `已取消「${loc.name}」核验`, 'success');
      void loadLocations(page);
    } catch (error) {
      const message = error instanceof Error ? error.message : '操作失败';
      showToast(message, 'error');
    } finally {
      setActingId(null);
    }
  };

  const columns: Column<LocationAdmin>[] = [
    {
      key: 'name',
      title: '地点名称',
      render: (value, row) => (
        <div className="min-w-0">
          <p className="font-medium text-ink line-clamp-1">{value}</p>
          <p className="text-xs text-ink-muted line-clamp-1 mt-0.5">
            {[row.building, row.floor].filter(Boolean).join(' · ') || row.description || '—'}
          </p>
        </div>
      ),
    },
    {
      key: 'latitude',
      title: '坐标',
      width: 170,
      nowrap: true,
      render: (_, row) => (
        <span className="text-xs text-ink-sub">
          {row.latitude.toFixed(6)}, {row.longitude.toFixed(6)}
        </span>
      ),
    },
    {
      key: 'post_count',
      title: '关联内容',
      width: 90,
      nowrap: true,
      render: (value) => `${value} 条`,
    },
    {
      key: 'is_verified',
      title: '核验状态',
      width: 100,
      render: (value) =>
        value ? (
          <Badge variant="success">已核验</Badge>
        ) : (
          <Badge variant="warning">待核验</Badge>
        ),
    },
    {
      key: 'created_at',
      title: '创建时间',
      width: 130,
      nowrap: true,
      render: (value) => formatDate(value),
    },
    {
      key: 'actions',
      title: '操作',
      width: 170,
      nowrap: true,
      render: (_, row) => (
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="text"
            onClick={() => setDetailLocation(row)}
          >
            <Eye size={13} className="mr-1" />
            详情
          </Button>
          {row.is_verified ? (
            <Button
              size="sm"
              variant="text"
              loading={actingId === row.id}
              onClick={() => handleVerify(row, false)}
            >
              <X size={13} className="mr-1" />
              取消
            </Button>
          ) : (
            <Button
              size="sm"
              variant="primary"
              loading={actingId === row.id}
              onClick={() => handleVerify(row, true)}
            >
              <Check size={13} className="mr-1" />
              核验
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold text-ink">地点核验</h1>
        <p className="text-ink-sub text-sm mt-1">
          用户提交的新地点需核验后才在地图/搜索中正式启用，共 {total} 个地点
        </p>
      </div>



      {/* 地点知识层审核队列 */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card variant="outlined" padding="sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-lake" />
              <h2 className="font-semibold text-ink">资料提议审核</h2>
              <Badge variant="warning">{factTotal}</Badge>
            </div>
            <span className="text-xs text-ink-muted">批准后公开展示</span>
          </div>
          {knowledgeLoading ? <p className="text-sm text-ink-muted py-4 text-center">加载中…</p> : factProposals.length === 0 ? (
            <div className="py-8 text-center">
              <Check size={32} className="mx-auto text-success/50 mb-2" />
              <p className="text-sm text-ink-muted">暂无待审核资料提议</p>
            </div>
          ) : (
            <div className="space-y-3">
              {factProposals.map((proposal) => (
                <div key={proposal.id} className="rounded-lg border border-line/60 bg-paper p-3.5">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-ink text-sm truncate">
                          <MapPin size={12} className="inline mr-1 text-lake" />
                          {proposal.location_name}
                        </span>
                        <Badge variant="info" className="text-[10px]">地点 #{proposal.location_id}</Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-ink-muted">
                        <span className="flex items-center gap-1">
                          <User size={11} />
                          {proposal.proposer_name}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock size={11} />
                          {formatDate(proposal.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="space-y-1.5 bg-mist/40 rounded-md p-2.5 mb-2">
                    {(proposal.changes_json.upserts || []).map((item) => (
                      <div key={item.fact_key} className="text-sm">
                        <span className="text-ink-muted font-medium">{item.label || item.fact_key}：</span>
                        <span className="text-ink">{item.value}</span>
                      </div>
                    ))}
                  </div>
                  {proposal.reason && (
                    <div className="text-xs text-ink-sub bg-lamp/8 rounded-md px-2.5 py-1.5 mb-2">
                      <span className="font-medium">补充说明：</span>{proposal.reason}
                    </div>
                  )}
                  {expandedReject === proposal.id && (
                    <div className="mb-2">
                      <Input
                        placeholder="请输入驳回原因（可选）"
                        value={rejectReason[proposal.id] || ''}
                        onChange={(e) => setRejectReason((prev) => ({ ...prev, [proposal.id]: e.target.value }))}
                        className="text-sm"
                      />
                    </div>
                  )}
                  <div className="flex items-center justify-between gap-2">
                    <button
                      onClick={() => toggleRejectInput(proposal.id)}
                      className="text-xs text-ink-muted hover:text-ink flex items-center gap-0.5"
                    >
                      {expandedReject === proposal.id ? <><ChevronUp size={12} />收起</> : <><ChevronDown size={12} />填写驳回原因</>}
                    </button>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="secondary"
                        loading={actingKnowledgeId === `fact:${proposal.id}`}
                        onClick={() => void handleKnowledgeAction('fact', proposal.id, 'reject')}
                        className="w-16 justify-center"
                      >
                        驳回
                      </Button>
                      <Button
                        size="sm"
                        variant="primary"
                        loading={actingKnowledgeId === `fact:${proposal.id}`}
                        onClick={() => void handleKnowledgeAction('fact', proposal.id, 'approve')}
                        className="w-16 justify-center"
                      >
                        批准
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
              {factTotalPages > 1 && (
                <div className="flex items-center justify-center pt-2">
                  <Pagination
                    page={factPage}
                    pageSize={FACT_PAGE_SIZE}
                    total={factTotal}
                    totalPages={factTotalPages}
                    onChange={(p) => setFactPage(p)}
                  />
                </div>
              )}
            </div>
          )}
        </Card>

        <Card variant="outlined" padding="sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-ink">AI 摘要待审（{summaryQueue.length}）</h2>
            <span className="text-xs text-ink-muted">审核时核对来源</span>
          </div>
          {knowledgeLoading ? <p className="text-sm text-ink-muted">加载中…</p> : summaryQueue.length === 0 ? (
            <p className="text-sm text-ink-muted">暂无待审核摘要。</p>
          ) : (
            <div className="space-y-3">
              {summaryQueue.map((summary) => (
                <div key={summary.id} className="rounded-lg bg-mist/60 p-3">
                  <div className="text-xs text-ink-muted mb-1">{summary.location_name} · v{summary.version} · {summary.source_count} 条来源</div>
                  <p className="text-sm text-ink line-clamp-3">{summary.summary_text || '暂无摘要正文（证据不足）'}</p>
                  {summary.conflicts.length > 0 && <p className="text-xs text-lamp mt-1">包含 {summary.conflicts.length} 条冲突提示</p>}
                  <div className="flex justify-end gap-2 mt-2">
                    <Button size="sm" variant="text" loading={actingKnowledgeId === `summary:${summary.id}`} onClick={() => void handleKnowledgeAction('summary', summary.id, 'reject')}>驳回</Button>
                    <Button size="sm" variant="primary" loading={actingKnowledgeId === `summary:${summary.id}`} onClick={() => void handleKnowledgeAction('summary', summary.id, 'approve')}>批准</Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* 筛选栏 */}
      <Card variant="outlined" padding="sm">
        <div className="flex flex-wrap items-center gap-2">
          {[
            { value: '', label: '全部' },
            { value: 'false', label: '待核验' },
            { value: 'true', label: '已核验' },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => updateVerifiedFilter(opt.value)}
              className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                verifiedParam === opt.value
                  ? 'bg-lake text-paper'
                  : 'bg-mist text-ink-sub hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          ))}
          <div className="flex items-center gap-2 ml-auto">
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="按名称搜索"
              className="w-44"
            />
            <Button size="sm" variant="secondary" onClick={handleSearch} className="min-w-[84px] justify-center">
              <Search size={13} className="mr-1" />
              搜索
            </Button>
          </div>
        </div>
      </Card>

      {/* 表格 */}
      {locations.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <MapPin size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无地点记录</p>
        </Card>
      ) : (
        <Table<LocationAdmin>
          columns={columns}
          data={locations}
          loading={loading}
          emptyText="暂无地点记录"
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

      {/* Task 3.6: 地点详情弹窗（含地图展示） */}
      {detailLocation && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm p-4"
          onClick={() => setDetailLocation(null)}
        >
          <div
            className="bg-paper rounded-2xl shadow-2xl border border-line w-full max-w-lg max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 弹窗头部 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-line/60">
              <div className="flex items-center gap-2 min-w-0">
                <MapPin size={18} className="text-lake flex-shrink-0" />
                <h3 className="font-display font-bold text-lg text-ink truncate">
                  {detailLocation.name}
                </h3>
                {detailLocation.is_verified ? (
                  <Badge variant="success">已核验</Badge>
                ) : (
                  <Badge variant="warning">待核验</Badge>
                )}
              </div>
              <button
                onClick={() => setDetailLocation(null)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-ink-sub hover:bg-mist transition-colors flex-shrink-0"
                aria-label="关闭"
              >
                <X size={16} />
              </button>
            </div>

            {/* 弹窗内容 */}
            <div className="px-5 py-4 space-y-4">
              {/* 地点信息 */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                {detailLocation.building && (
                  <div className="flex items-center gap-2">
                    <Building2 size={14} className="text-ink-muted flex-shrink-0" />
                    <span className="text-ink-muted">建筑：</span>
                    <span className="text-ink">{detailLocation.building}</span>
                  </div>
                )}
                {detailLocation.floor && (
                  <div className="flex items-center gap-2">
                    <Layers size={14} className="text-ink-muted flex-shrink-0" />
                    <span className="text-ink-muted">楼层：</span>
                    <span className="text-ink">{detailLocation.floor}</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="text-ink-muted">关联帖子：</span>
                  <span className="text-ink font-medium">{detailLocation.post_count} 条</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-ink-muted">创建时间：</span>
                  <span className="text-ink text-xs">{formatDate(detailLocation.created_at)}</span>
                </div>
              </div>

              {/* 描述 */}
              {detailLocation.description && (
                <div className="text-sm text-ink-sub bg-mist/60 rounded-md px-3 py-2 border border-line/60">
                  {detailLocation.description}
                </div>
              )}

              {/* 地图展示 */}
              <div>
                <div className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">
                  地图位置
                </div>
                <MapLocationPicker
                  key={detailLocation.id}
                  initialLat={detailLocation.latitude}
                  initialLng={detailLocation.longitude}
                  initialName={detailLocation.name}
                  readOnly
                  height={280}
                />
              </div>

              {/* 操作按钮 */}
              <div className="flex gap-2 pt-2">
                {detailLocation.is_verified ? (
                  <Button
                    variant="secondary"
                    className="flex-1"
                    loading={actingId === detailLocation.id}
                    onClick={() => {
                      void handleVerify(detailLocation, false);
                      setDetailLocation(null);
                    }}
                  >
                    <X size={14} className="mr-1" />
                    取消核验
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    className="flex-1"
                    loading={actingId === detailLocation.id}
                    onClick={() => {
                      void handleVerify(detailLocation, true);
                      setDetailLocation(null);
                    }}
                  >
                    <Check size={14} className="mr-1" />
                    核验通过
                  </Button>
                )}
                <Button variant="text" onClick={() => setDetailLocation(null)}>
                  关闭
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminLocationsPage;
