import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import {
  adminApi,
  type TagAdmin,
  type TagUpdateRequest,
  type BatchOperationResult,
} from '../../services/admin';
import {
  Tags,
  Search,
  Pencil,
  Trash2,
  GitMerge,
  Star,
  StarOff,
  X,
} from 'lucide-react';

const PAGE_SIZE = 20;

/** 筛选维度：官方状态 + 删除状态 */
type FilterKey = 'all' | 'official' | 'unofficial' | 'deleted';

const FILTER_OPTIONS: Array<{ label: string; value: FilterKey }> = [
  { label: '全部', value: 'all' },
  { label: '官方', value: 'official' },
  { label: '非官方', value: 'unofficial' },
  { label: '已删除', value: 'deleted' },
];

const AdminTagsPage: React.FC = () => {
  const [tags, setTags] = useState<TagAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [searchInput, setSearchInput] = useState('');
  const [searchApplied, setSearchApplied] = useState('');
  const [selectedKeys, setSelectedKeys] = useState<Array<string | number>>([]);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // 编辑面板
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editPanelOpen, setEditPanelOpen] = useState(false);
  const [editForm, setEditForm] = useState<TagUpdateRequest>({ name: '', is_official: false });
  const [submitting, setSubmitting] = useState(false);

  // 合并面板
  const [mergePanelOpen, setMergePanelOpen] = useState(false);
  const [mergeTargetId, setMergeTargetId] = useState<number | null>(null);
  const [allTagsForMerge, setAllTagsForMerge] = useState<TagAdmin[]>([]);
  const [mergeLoading, setMergeLoading] = useState(false);

  const loadTags = useCallback(async (p: number, f: FilterKey, name: string) => {
    try {
      setLoading(true);
      const params: Record<string, unknown> = { page: p, page_size: PAGE_SIZE };
      if (f === 'official') params.is_official = true;
      else if (f === 'unofficial') params.is_official = false;
      else if (f === 'deleted') params.is_deleted = true;
      if (name) params.name = name;
      const data = await adminApi.getTags(params);
      setTags(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setSelectedKeys([]);
    } catch (error) {
      console.error('加载标签列表失败:', error);
      setToast({ message: '加载标签列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTags(page, filter, searchApplied);
  }, [page, filter, searchApplied, loadTags]);

  /** 触发搜索 */
  const handleSearch = () => {
    setSearchApplied(searchInput.trim());
    setPage(1);
  };

  /** 清空搜索 */
  const handleClearSearch = () => {
    setSearchInput('');
    setSearchApplied('');
    setPage(1);
  };

  /** 打开编辑面板 */
  const openEditPanel = (tag: TagAdmin) => {
    setEditingId(tag.id);
    setEditForm({ name: tag.name, is_official: tag.is_official });
    setEditPanelOpen(true);
  };

  /** 提交编辑 */
  const handleEditSubmit = async () => {
    if (!editForm.name?.trim()) {
      setToast({ message: '请填写标签名称', type: 'warning' });
      return;
    }
    if (editingId === null) return;
    setSubmitting(true);
    try {
      await adminApi.updateTag(editingId, {
        name: editForm.name.trim(),
        is_official: editForm.is_official,
      });
      setToast({ message: '标签更新成功', type: 'success' });
      setEditPanelOpen(false);
      setEditingId(null);
      loadTags(page, filter, searchApplied);
    } catch (error: any) {
      console.error('更新标签失败:', error);
      const msg = error.response?.data?.detail || '更新标签失败';
      setToast({ message: msg, type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  /** 快速切换官方标记 */
  const handleToggleOfficial = async (tag: TagAdmin) => {
    try {
      await adminApi.updateTag(tag.id, { is_official: !tag.is_official });
      setToast({
        message: `已${tag.is_official ? '取消' : '设为'}官方标签`,
        type: 'success',
      });
      loadTags(page, filter, searchApplied);
    } catch (error: any) {
      console.error('切换官方标记失败:', error);
      const msg = error.response?.data?.detail || '操作失败';
      setToast({ message: msg, type: 'error' });
    }
  };

  /** 软删除标签 */
  const handleDelete = async (tag: TagAdmin) => {
    if (tag.is_deleted) {
      setToast({ message: '该标签已删除', type: 'warning' });
      return;
    }
    if (!window.confirm(`确定要删除标签「${tag.name}」吗？\n\n删除后该标签不再出现在前台标签库，但历史帖子关联仍保留。`)) return;
    try {
      await adminApi.deleteTag(tag.id);
      setToast({ message: `标签「${tag.name}」已删除`, type: 'success' });
      loadTags(page, filter, searchApplied);
    } catch (error: any) {
      console.error('删除标签失败:', error);
      const msg = error.response?.data?.detail || '删除失败';
      setToast({ message: msg, type: 'error' });
    }
  };

  /** 打开合并面板 */
  const openMergePanel = async () => {
    if (selectedKeys.length < 2) {
      setToast({ message: '请至少选择 2 个标签进行合并', type: 'warning' });
      return;
    }
    setMergeTargetId(null);
    setMergePanelOpen(true);
    // 加载全部启用标签作为目标候选（排除当前选中项）
    try {
      const data = await adminApi.getTags({ page: 1, page_size: 200, is_deleted: false });
      setAllTagsForMerge(data.items.filter((t) => !selectedKeys.includes(t.id)));
    } catch (error) {
      console.error('加载标签候选失败:', error);
      setToast({ message: '加载标签候选失败', type: 'error' });
    }
  };

  /** 提交合并 */
  const handleMergeSubmit = async () => {
    if (mergeTargetId === null) {
      setToast({ message: '请选择目标标签', type: 'warning' });
      return;
    }
    const sourceIds = selectedKeys as number[];
    if (sourceIds.includes(mergeTargetId)) {
      setToast({ message: '目标标签不能在源标签中', type: 'warning' });
      return;
    }
    if (!window.confirm(`将合并 ${sourceIds.length} 个标签到目标标签，源标签将被删除，确定继续吗？`)) return;

    setMergeLoading(true);
    try {
      const result: BatchOperationResult = await adminApi.mergeTags({
        source_tag_ids: sourceIds,
        target_tag_id: mergeTargetId,
      });
      setToast({
        message: result.message || `合并完成（成功 ${result.success}/${result.total}）`,
        type: result.failed > 0 ? 'warning' : 'success',
      });
      setMergePanelOpen(false);
      setSelectedKeys([]);
      loadTags(page, filter, searchApplied);
    } catch (error: any) {
      console.error('合并失败:', error);
      const msg = error.response?.data?.detail || '合并失败';
      setToast({ message: msg, type: 'error' });
    } finally {
      setMergeLoading(false);
    }
  };

  // 表格列配置
  const columns: Column<TagAdmin>[] = [
    {
      key: 'name',
      title: '标签名称',
      render: (value, row) => (
        <div className="flex items-center gap-2 min-w-0">
          {row.is_official && (
            <Star size={14} className="text-sun flex-shrink-0" fill="currentColor" />
          )}
          <span className="font-medium text-ink truncate">{value}</span>
        </div>
      ),
    },
    {
      key: 'slug',
      title: 'Slug',
      width: 160,
      nowrap: true,
      render: (value) => (
        <span className="text-xs text-ink-muted font-mono">{value || '—'}</span>
      ),
    },
    {
      key: 'usage_count',
      title: '使用次数',
      width: 100,
      align: 'center',
      nowrap: true,
      render: (value) => (
        <span className={value > 0 ? 'text-ink font-medium' : 'text-ink-muted'}>
          {value}
        </span>
      ),
    },
    {
      key: 'is_official',
      title: '官方',
      width: 90,
      align: 'center',
      nowrap: true,
      render: (value) => (
        <Badge variant={value ? 'warning' : 'default'}>
          {value ? '官方' : '普通'}
        </Badge>
      ),
    },
    {
      key: 'is_deleted',
      title: '状态',
      width: 90,
      nowrap: true,
      render: (value) => (
        <Badge variant={value ? 'danger' : 'success'}>
          {value ? '已删除' : '正常'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      title: '操作',
      width: 140,
      nowrap: true,
      render: (_, row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => openEditPanel(row)}
            className="p-1.5 rounded-md text-ink-sub hover:bg-mist hover:text-lake transition-colors"
            title="编辑"
            disabled={row.is_deleted}
          >
            <Pencil size={15} />
          </button>
          <button
            onClick={() => handleToggleOfficial(row)}
            className={`p-1.5 rounded-md transition-colors ${
              row.is_official
                ? 'text-sun hover:bg-sun/10'
                : 'text-ink-sub hover:bg-mist hover:text-sun'
            }`}
            title={row.is_official ? '取消官方' : '设为官方'}
            disabled={row.is_deleted}
          >
            {row.is_official ? <StarOff size={15} /> : <Star size={15} />}
          </button>
          {!row.is_deleted && (
            <button
              onClick={() => handleDelete(row)}
              className="p-1.5 rounded-md text-ink-sub hover:bg-danger/10 hover:text-danger transition-colors"
              title="删除"
            >
              <Trash2 size={15} />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">标签管理</h1>
          <p className="text-ink-sub text-sm mt-1">共 {total} 个标签</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* 搜索框 */}
          <div className="relative">
            <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="搜索标签名称"
              className="pl-8 pr-7 py-1.5 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake w-48"
            />
            {searchInput && (
              <button
                onClick={handleClearSearch}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
                title="清空"
              >
                <X size={14} />
              </button>
            )}
          </div>
          {/* 筛选 */}
          <div className="flex items-center gap-1 bg-paper border border-line rounded-md p-0.5">
            {FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setFilter(opt.value);
                  setPage(1);
                }}
                className={`px-3 py-1.5 rounded text-sm transition-colors ${
                  filter === opt.value
                    ? 'bg-lake text-paper'
                    : 'text-ink-sub hover:bg-mist'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 批量操作栏（选中时显示） */}
      {selectedKeys.length > 0 && (
        <Card variant="filled" padding="sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink">
              已选择 <span className="font-semibold text-lake">{selectedKeys.length}</span> 个标签
            </span>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={openMergePanel}
                disabled={selectedKeys.length < 2}
              >
                <GitMerge size={14} className="mr-1" />
                合并标签
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
      {tags.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <Tags size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无标签</p>
        </Card>
      ) : (
        <Table<TagAdmin>
          columns={columns}
          data={tags}
          loading={loading}
          selectable
          selectedRowKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
          emptyText="暂无标签"
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

      {/* 编辑面板 */}
      {editPanelOpen && editingId !== null && (
        <Card variant="outlined" padding="md">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-ink">编辑标签 #{editingId}</h3>
              <button
                onClick={() => {
                  setEditPanelOpen(false);
                  setEditingId(null);
                }}
                className="text-ink-muted hover:text-ink"
              >
                取消
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* 名称 */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1">
                  标签名称 <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  value={editForm.name || ''}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  placeholder="标签名称"
                  className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
                />
              </div>
              {/* 官方标记 */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1">官方标记</label>
                <button
                  onClick={() => setEditForm({ ...editForm, is_official: !editForm.is_official })}
                  className={`w-full px-3 py-2 rounded-md text-sm border transition-colors ${
                    editForm.is_official
                      ? 'border-sun bg-sun/10 text-sun'
                      : 'border-line bg-paper text-ink-sub'
                  }`}
                >
                  {editForm.is_official ? '★ 官方标签' : '☆ 普通标签'}
                </button>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button
                size="sm"
                variant="text"
                onClick={() => {
                  setEditPanelOpen(false);
                  setEditingId(null);
                }}
              >
                取消
              </Button>
              <Button size="sm" variant="primary" onClick={handleEditSubmit} loading={submitting}>
                保存
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 合并面板 */}
      {mergePanelOpen && (
        <Card variant="outlined" padding="md">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-ink flex items-center gap-2">
                <GitMerge size={18} />
                合并标签
              </h3>
              <button
                onClick={() => setMergePanelOpen(false)}
                className="text-ink-muted hover:text-ink"
              >
                取消
              </button>
            </div>

            {/* 源标签摘要 */}
            <div className="bg-mist/50 rounded-md p-3 text-sm">
              <p className="text-ink-muted">源标签（将删除并迁移关联）：</p>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {selectedKeys.map((k) => {
                  const t = tags.find((x) => x.id === k);
                  return t ? (
                    <Badge key={k} variant="danger">
                      {t.name}
                    </Badge>
                  ) : null;
                })}
              </div>
              <p className="text-ink-muted mt-2">共 {selectedKeys.length} 个</p>
            </div>

            {/* 目标标签选择 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-2">
                目标标签 <span className="text-danger">*</span>
                <span className="text-xs text-ink-muted ml-2">（保留该标签，关联迁移到此）</span>
              </label>
              {allTagsForMerge.length === 0 ? (
                <p className="text-sm text-ink-muted italic">无可选目标标签</p>
              ) : (
                <div className="max-h-60 overflow-y-auto border border-line rounded-md p-2 space-y-1 bg-paper">
                  {allTagsForMerge.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setMergeTargetId(t.id)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded text-sm transition-colors ${
                        mergeTargetId === t.id
                          ? 'border border-lake bg-lake/5 ring-1 ring-lake/30'
                          : 'border border-transparent hover:bg-mist'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        {t.is_official && (
                          <Star size={12} className="text-sun" fill="currentColor" />
                        )}
                        <span className="text-ink font-medium">{t.name}</span>
                      </span>
                      <span className="text-xs text-ink-muted">
                        使用 {t.usage_count} 次
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2">
              <Button
                size="sm"
                variant="text"
                onClick={() => setMergePanelOpen(false)}
              >
                取消
              </Button>
              <Button
                size="sm"
                variant="primary"
                onClick={handleMergeSubmit}
                loading={mergeLoading}
                disabled={mergeTargetId === null}
              >
                确认合并
              </Button>
            </div>
          </div>
        </Card>
      )}

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

export default AdminTagsPage;
