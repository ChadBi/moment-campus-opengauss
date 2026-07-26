import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import {
  adminApi,
  type CategoryAdmin,
  type CategoryCreateRequest,
  type CategoryUpdateRequest,
} from '../../services/admin';
import { FolderTree, Plus, Pencil, Ban } from 'lucide-react';
import { logger } from '../../utils/logger';

const PAGE_SIZE = 20;

const AdminCategoriesPage: React.FC = () => {
  const [categories, setCategories] = useState<CategoryAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // 编辑/新建面板状态
  const [editingId, setEditingId] = useState<number | null>(null); // null = 新建模式
  const [panelOpen, setPanelOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState<CategoryCreateRequest>({
    name: '',
    code: '',
    icon: '',
    description: '',
    default_validity_days: 30,
    sort_order: 0,
    is_active: true,
  });

  const loadCategories = useCallback(async (p: number, active?: boolean) => {
    try {
      const data = await adminApi.getCategories({ page: p, page_size: PAGE_SIZE, is_active: active });
      setCategories(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      logger.error('加载分类列表失败:', error);
      setToast({ message: '加载分类列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadCategories(page, filterActive);
  }, [page, filterActive, loadCategories]);

  /** 打开新建面板 */
  const openCreatePanel = () => {
    setEditingId(null);
    setFormData({
      name: '',
      code: '',
      icon: '',
      description: '',
      default_validity_days: 30,
      sort_order: 0,
      is_active: true,
    });
    setPanelOpen(true);
  };

  /** 打开编辑面板 */
  const openEditPanel = (cat: CategoryAdmin) => {
    setEditingId(cat.id);
    setFormData({
      name: cat.name,
      code: cat.code, // 编辑时保留原值（code 不可修改，提交时不会用到）
      icon: cat.icon,
      description: cat.description || '',
      default_validity_days: cat.default_validity_days,
      sort_order: cat.sort_order,
      is_active: cat.is_active,
    });
    setPanelOpen(true);
  };

  /** 关闭面板 */
  const closePanel = () => {
    setPanelOpen(false);
    setEditingId(null);
  };

  /** 提交表单 */
  const handleSubmit = async () => {
    if (!formData.name.trim() || !formData.icon.trim()) {
      setToast({ message: '请填写名称和图标', type: 'warning' });
      return;
    }
    if (editingId === null && !formData.code.trim()) {
      setToast({ message: '请填写分类编码', type: 'warning' });
      return;
    }

    setSubmitting(true);
    try {
      if (editingId === null) {
        // 新建
        await adminApi.createCategory({
          name: formData.name.trim(),
          code: formData.code.trim(),
          icon: formData.icon.trim(),
          description: formData.description?.trim() || undefined,
          default_validity_days: formData.default_validity_days,
          sort_order: formData.sort_order,
          is_active: formData.is_active,
        });
        setToast({ message: '分类创建成功', type: 'success' });
      } else {
        // 更新
        const updateData: CategoryUpdateRequest = {
          name: formData.name.trim(),
          icon: formData.icon.trim(),
          description: formData.description?.trim() || undefined,
          default_validity_days: formData.default_validity_days,
          sort_order: formData.sort_order,
          is_active: formData.is_active,
        };
        await adminApi.updateCategory(editingId, updateData);
        setToast({ message: '分类更新成功', type: 'success' });
      }
      closePanel();
      loadCategories(page, filterActive);
    } catch (error: unknown) {
      logger.error('保存分类失败:', error);
      const e = error as { response?: { data?: { detail?: string } } };
      const msg = e?.response?.data?.detail || '保存分类失败';
      setToast({ message: msg, type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  /** 禁用分类 */
  const handleDisable = async (cat: CategoryAdmin) => {
    if (!window.confirm(`确定要禁用分类「${cat.name}」吗？\n\n禁用后该分类不再出现在前台选项中，但历史帖子仍保留该分类关联。`)) return;
    try {
      await adminApi.deleteCategory(cat.id);
      setToast({ message: `分类「${cat.name}」已禁用`, type: 'success' });
      loadCategories(page, filterActive);
    } catch (error: unknown) {
      logger.error('禁用分类失败:', error);
      const e = error as { response?: { data?: { detail?: string } } };
      const msg = e?.response?.data?.detail || '禁用分类失败';
      setToast({ message: msg, type: 'error' });
    }
  };

  // 表格列配置
  const columns: Column<CategoryAdmin>[] = [
    {
      key: 'name',
      title: '分类',
      render: (value, row) => (
        <div className="flex items-center gap-2.5">
          <span className="text-xl">{row.icon}</span>
          <div>
            <p className="font-medium text-ink">{value}</p>
            <p className="text-xs text-ink-muted font-mono">{row.code}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'description',
      title: '描述',
      render: (value) => (
        <span className="text-ink-sub text-sm line-clamp-1">{value || '—'}</span>
      ),
    },
    {
      key: 'default_validity_days',
      title: '有效期',
      width: 80,
      align: 'center',
      nowrap: true,
      render: (value) => `${value}天`,
    },
    {
      key: 'sort_order',
      title: '排序',
      width: 70,
      align: 'center',
      nowrap: true,
    },
    {
      key: 'post_count',
      title: '信息数',
      width: 80,
      align: 'center',
      nowrap: true,
      render: (value) => (
        <span className={value > 0 ? 'text-ink font-medium' : 'text-ink-muted'}>
          {value}
        </span>
      ),
    },
    {
      key: 'is_active',
      title: '状态',
      width: 80,
      nowrap: true,
      render: (value) => (
        <Badge variant={value ? 'success' : 'danger'}>
          {value ? '启用' : '禁用'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      title: '操作',
      width: 120,
      nowrap: true,
      render: (_, row) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => openEditPanel(row)}
            className="p-1.5 rounded-md text-ink-sub hover:bg-mist hover:text-lake transition-colors"
            title="编辑"
          >
            <Pencil size={15} />
          </button>
          {row.is_active && (
            <button
              onClick={() => handleDisable(row)}
              className="p-1.5 rounded-md text-ink-sub hover:bg-danger/10 hover:text-danger transition-colors"
              title="禁用"
            >
              <Ban size={15} />
            </button>
          )}
        </div>
      ),
    },
  ];

  const filterOptions: Array<{ label: string; value: boolean | undefined }> = [
    { label: '全部', value: undefined },
    { label: '启用', value: true },
    { label: '禁用', value: false },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">分类管理</h1>
          <p className="text-ink-sub text-sm mt-1">共 {total} 个分类</p>
        </div>
        <div className="flex items-center gap-3">
          {/* 筛选 */}
          <div className="flex items-center gap-1 bg-paper border border-line rounded-md p-0.5">
            {filterOptions.map((opt) => (
              <button
                key={String(opt.label)}
                onClick={() => {
                  setFilterActive(opt.value);
                  setPage(1);
                }}
                className={`px-3 py-1.5 rounded text-sm transition-colors ${
                  filterActive === opt.value
                    ? 'bg-lake text-paper'
                    : 'text-ink-sub hover:bg-mist'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Button size="sm" variant="primary" onClick={openCreatePanel}>
            <Plus size={14} className="mr-1" />
            新建分类
          </Button>
        </div>
      </div>

      {/* 表格 */}
      {categories.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <FolderTree size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无分类</p>
        </Card>
      ) : (
        <Table<CategoryAdmin>
          columns={columns}
          data={categories}
          loading={loading}
          emptyText="暂无分类"
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

      {/* 新建/编辑面板 */}
      {panelOpen && (
        <Card variant="outlined" padding="md">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-ink">
                {editingId === null ? '新建分类' : `编辑分类 #${editingId}`}
              </h3>
              <button onClick={closePanel} className="text-ink-muted hover:text-ink">
                取消
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* 名称 */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1">
                  分类名称 <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="如：失物招领"
                  className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
                />
              </div>

              {/* 编码（仅新建可编辑） */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1">
                  分类编码 <span className="text-danger">*</span>
                  {editingId !== null && <span className="text-xs text-ink-muted ml-1">（不可修改）</span>}
                </label>
                <input
                  type="text"
                  value={editingId !== null ? (categories.find(c => c.id === editingId)?.code || '') : formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toLowerCase() })}
                  placeholder="如：lost_found"
                  disabled={editingId !== null}
                  className="w-full px-3 py-2 border border-line rounded-md text-sm font-mono text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake disabled:bg-mist/50 disabled:text-ink-muted"
                />
              </div>

              {/* 图标 */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1">
                  图标 emoji <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  value={formData.icon}
                  onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                  placeholder="如：📦"
                  maxLength={10}
                  className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
                />
              </div>

              {/* 有效天数 */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1">默认有效天数</label>
                <input
                  type="number"
                  value={formData.default_validity_days}
                  onChange={(e) => setFormData({ ...formData, default_validity_days: parseInt(e.target.value) || 30 })}
                  min={1}
                  max={3650}
                  className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
                />
              </div>

              {/* 排序 */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1">排序权重</label>
                <input
                  type="number"
                  value={formData.sort_order}
                  onChange={(e) => setFormData({ ...formData, sort_order: parseInt(e.target.value) || 0 })}
                  min={0}
                  className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
                />
              </div>

              {/* 启用状态 */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1">状态</label>
                <button
                  onClick={() => setFormData({ ...formData, is_active: !formData.is_active })}
                  className={`w-full px-3 py-2 rounded-md text-sm border transition-colors ${
                    formData.is_active
                      ? 'border-grass bg-grass/10 text-grass'
                      : 'border-danger bg-danger/10 text-danger'
                  }`}
                >
                  {formData.is_active ? '启用' : '禁用'}
                </button>
              </div>
            </div>

            {/* 描述 */}
            <div>
              <label className="block text-sm font-medium text-ink mb-1">描述</label>
              <textarea
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="分类描述（可选）"
                rows={2}
                maxLength={200}
                className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake resize-none"
              />
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center justify-end gap-2">
              <Button size="sm" variant="text" onClick={closePanel}>取消</Button>
              <Button size="sm" variant="primary" onClick={handleSubmit} loading={submitting}>
                {editingId === null ? '创建' : '保存'}
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

export default AdminCategoriesPage;
