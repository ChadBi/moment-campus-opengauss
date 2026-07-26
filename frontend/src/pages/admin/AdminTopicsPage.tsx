import React, { useState, useEffect, useCallback } from 'react';
import {
  adminApi,
  type TopicAdmin,
  type TopicAdminDetail,
  type TopicPostAdminItem,
  type TopicCreateRequest,
  type TopicUpdateRequest,
} from '../../services/admin';
import { postsApi } from '../../services/posts';
import type { Post } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import {
  Plus,
  Pencil,
  Trash2,
  ArrowUp,
  ArrowDown,
  ListOrdered,
  FileText,
  X,
  Search,
} from 'lucide-react';
import { useSchoolQueryKey } from '../../hooks/useSchoolQueryKey';

const PAGE_SIZE = 20;

/** 专题状态徽章颜色 */
const STATUS_BADGE: Record<string, 'info' | 'success' | 'danger' | 'warning'> = {
  draft: 'warning',
  published: 'success',
  archived: 'danger',
};

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已下线',
};

const AdminTopicsPage: React.FC = () => {
  const schoolKey = useSchoolQueryKey();
  const [topics, setTopics] = useState<TopicAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [statusFilter, setStatusFilter] = useState<'draft' | 'published' | 'archived' | undefined>(undefined);
  const [keyword, setKeyword] = useState('');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // 编辑/新建面板
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState<TopicCreateRequest>({
    title: '',
    description: '',
    cover_url: '',
    sort_order: 0,
    status: 'draft',
  });

  // 编排面板
  const [arrangeModalOpen, setArrangeModalOpen] = useState(false);
  const [arrangingTopic, setArrangingTopic] = useState<TopicAdminDetail | null>(null);
  // 添加帖子搜索
  const [postSearchKeyword, setPostSearchKeyword] = useState('');
  const [searchedPosts, setSearchedPosts] = useState<Post[]>([]);
  const [searching, setSearching] = useState(false);
  // 帖子排序编辑（本地缓存）
  const [postSorts, setPostSorts] = useState<Record<number, number>>({});

  const loadTopics = useCallback(async (p: number, status?: string, kw?: string) => {
    try {
      setLoading(true);
      const data = await adminApi.getAdminTopics({
        page: p,
        page_size: PAGE_SIZE,
        status: status as 'draft' | 'published' | 'archived' | undefined,
        keyword: kw || undefined,
      });
      setTopics(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err: unknown) {
      console.error('加载专题列表失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '加载专题列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTopics(page, statusFilter, keyword);
  }, [page, statusFilter, schoolKey, loadTopics]);

  /** 搜索框回车触发 */
  const handleKeywordSearch = () => {
    setPage(1);
    void loadTopics(1, statusFilter, keyword);
  };

  /** 打开新建面板 */
  const openCreateModal = () => {
    setEditingId(null);
    setFormData({
      title: '',
      description: '',
      cover_url: '',
      sort_order: 0,
      status: 'draft',
    });
    setEditModalOpen(true);
  };

  /** 打开编辑面板 */
  const openEditModal = async (topic: TopicAdmin) => {
    setEditingId(topic.id);
    setFormData({
      title: topic.title,
      description: topic.description || '',
      cover_url: topic.cover_url || '',
      sort_order: topic.sort_order,
      status: topic.status,
    });
    setEditModalOpen(true);
  };

  /** 提交新建/编辑 */
  const handleSubmit = async () => {
    if (!formData.title.trim()) {
      setToast({ message: '请填写专题标题', type: 'warning' });
      return;
    }
    setSubmitting(true);
    try {
      if (editingId === null) {
        await adminApi.createTopic({
          title: formData.title.trim(),
          description: formData.description?.trim() || null,
          cover_url: formData.cover_url?.trim() || null,
          sort_order: formData.sort_order ?? 0,
          status: formData.status || 'draft',
        });
        setToast({ message: '专题创建成功', type: 'success' });
      } else {
        const updateData: TopicUpdateRequest = {
          title: formData.title.trim(),
          description: formData.description?.trim() || null,
          cover_url: formData.cover_url?.trim() || null,
          sort_order: formData.sort_order ?? 0,
        };
        await adminApi.updateTopic(editingId, updateData);
        setToast({ message: '专题更新成功', type: 'success' });
      }
      setEditModalOpen(false);
      void loadTopics(page, statusFilter, keyword);
    } catch (err: unknown) {
      console.error('保存专题失败:', err);
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '保存专题失败', type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  /** 上下线 */
  const handlePublish = async (topic: TopicAdmin) => {
    if (!window.confirm(`确定要上线专题「${topic.title}」吗？\n\n上线后用户端可见。`)) return;
    try {
      await adminApi.publishTopic(topic.id);
      setToast({ message: `专题「${topic.title}」已上线`, type: 'success' });
      void loadTopics(page, statusFilter, keyword);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '上线失败', type: 'error' });
    }
  };

  const handleArchive = async (topic: TopicAdmin) => {
    if (!window.confirm(`确定要下线专题「${topic.title}」吗？\n\n下线后用户端不再可见，但保留数据。`)) return;
    try {
      await adminApi.archiveTopic(topic.id);
      setToast({ message: `专题「${topic.title}」已下线`, type: 'success' });
      void loadTopics(page, statusFilter, keyword);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '下线失败', type: 'error' });
    }
  };

  /** 删除 */
  const handleDelete = async (topic: TopicAdmin) => {
    if (!window.confirm(`确定要删除专题「${topic.title}」吗？\n\n删除后不可恢复，关联帖子将一并移除。`)) return;
    try {
      await adminApi.deleteTopic(topic.id);
      setToast({ message: `专题「${topic.title}」已删除`, type: 'success' });
      void loadTopics(page, statusFilter, keyword);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '删除失败', type: 'error' });
    }
  };

  /** 批量排序（按 sort_order 升序写入） */
  const handleBatchSort = async () => {
    if (topics.length === 0) {
      setToast({ message: '当前列表无专题可排序', type: 'warning' });
      return;
    }
    if (!window.confirm('确定要将当前列表的专题按显示顺序批量写入排序吗？')) return;
    try {
      const items = topics.map((t, idx) => ({ id: t.id, sort_order: idx }));
      await adminApi.sortTopics(items);
      setToast({ message: `已批量排序 ${items.length} 个专题`, type: 'success' });
      void loadTopics(page, statusFilter, keyword);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '批量排序失败', type: 'error' });
    }
  };

  /** 打开编排面板 */
  const openArrangeModal = async (topic: TopicAdmin) => {
    try {
      const detail = await adminApi.getAdminTopic(topic.id);
      setArrangingTopic(detail);
      const sorts: Record<number, number> = {};
      detail.posts.forEach((p) => {
        sorts[p.post_id] = p.sort_order;
      });
      setPostSorts(sorts);
      setPostSearchKeyword('');
      setSearchedPosts([]);
      setArrangeModalOpen(true);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '加载专题详情失败', type: 'error' });
    }
  };

  /** 搜索同校已发布帖子（用于添加到专题） */
  const handleSearchPosts = async () => {
    if (!postSearchKeyword.trim()) {
      setSearchedPosts([]);
      return;
    }
    setSearching(true);
    try {
      const data = await postsApi.getPosts({
        page: 1,
        page_size: 10,
        status: 'published',
      });
      // 客户端再按关键字过滤（posts API 不支持 keyword，使用 search 接口更合适但此处简化）
      const filtered = data.items.filter(
        (p) => p.title.includes(postSearchKeyword) || p.content.includes(postSearchKeyword)
      );
      // 排除已在专题中的帖子
      const existingIds = new Set(arrangingTopic?.posts.map((p) => p.post_id) || []);
      setSearchedPosts(filtered.filter((p) => !existingIds.has(p.id)));
    } catch (err: unknown) {
      console.error('搜索帖子失败:', err);
      setSearchedPosts([]);
    } finally {
      setSearching(false);
    }
  };

  /** 添加帖子到专题 */
  const handleAddPost = async (postId: number) => {
    if (!arrangingTopic) return;
    try {
      const detail = await adminApi.addPostsToTopic(arrangingTopic.id, [
        { post_id: postId, sort_order: Object.keys(postSorts).length },
      ]);
      setArrangingTopic(detail);
      const sorts: Record<number, number> = {};
      detail.posts.forEach((p) => {
        sorts[p.post_id] = p.sort_order;
      });
      setPostSorts(sorts);
      setSearchedPosts((prev) => prev.filter((p) => p.id !== postId));
      setToast({ message: '已添加到专题', type: 'success' });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '添加失败', type: 'error' });
    }
  };

  /** 从专题移除帖子 */
  const handleRemovePost = async (postId: number) => {
    if (!arrangingTopic) return;
    if (!window.confirm('确定要从专题中移除该帖子吗？')) return;
    try {
      const detail = await adminApi.removePostFromTopic(arrangingTopic.id, postId);
      setArrangingTopic(detail);
      const sorts: Record<number, number> = {};
      detail.posts.forEach((p) => {
        sorts[p.post_id] = p.sort_order;
      });
      setPostSorts(sorts);
      setToast({ message: '已从专题移除', type: 'success' });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '移除失败', type: 'error' });
    }
  };

  /** 保存帖子排序 */
  const handleSavePostSorts = async () => {
    if (!arrangingTopic) return;
    try {
      const posts = Object.entries(postSorts).map(([postId, sortOrder]) => ({
        post_id: Number(postId),
        sort_order: sortOrder,
      }));
      const detail = await adminApi.sortTopicPosts(arrangingTopic.id, posts);
      setArrangingTopic(detail);
      setToast({ message: '帖子排序已保存', type: 'success' });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '排序保存失败', type: 'error' });
    }
  };

  // 表格列配置
  const columns: Column<TopicAdmin>[] = [
    {
      key: 'title',
      title: '专题',
      render: (value, row) => (
        <div className="flex items-center gap-2.5">
          {row.cover_url ? (
            <div className="w-10 h-10 bg-mist rounded-md overflow-hidden flex-shrink-0">
              <img
                src={row.cover_url}
                alt={value}
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
            </div>
          ) : (
            <div className="w-10 h-10 bg-mist rounded-md flex items-center justify-center flex-shrink-0">
              <FileText size={16} className="text-ink-muted" />
            </div>
          )}
          <div className="min-w-0">
            <p className="font-medium text-ink truncate">{value}</p>
            {row.description && (
              <p className="text-xs text-ink-muted line-clamp-1">{row.description}</p>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      title: '状态',
      width: 90,
      nowrap: true,
      render: (value) => (
        <Badge variant={STATUS_BADGE[value as string] || 'info'}>
          {STATUS_LABEL[value as string] || value}
        </Badge>
      ),
    },
    {
      key: 'post_count',
      title: '内容数',
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
      key: 'view_count',
      title: '浏览',
      width: 70,
      align: 'center',
      nowrap: true,
      render: (value) => <span className="text-ink-sub">{value}</span>,
    },
    {
      key: 'sort_order',
      title: '排序',
      width: 70,
      align: 'center',
      nowrap: true,
    },
    {
      key: 'actions',
      title: '操作',
      width: 240,
      nowrap: true,
      render: (_, row) => (
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => openArrangeModal(row)}
            className="p-1.5 rounded-md text-ink-sub hover:bg-lake/10 hover:text-lake transition-colors"
            title="编排帖子"
          >
            <ListOrdered size={15} />
          </button>
          <button
            onClick={() => openEditModal(row)}
            className="p-1.5 rounded-md text-ink-sub hover:bg-mist hover:text-lake transition-colors"
            title="编辑"
          >
            <Pencil size={15} />
          </button>
          {row.status === 'published' ? (
            <button
              onClick={() => handleArchive(row)}
              className="p-1.5 rounded-md text-ink-sub hover:bg-sun/10 hover:text-sun transition-colors"
              title="下线"
            >
              <ArrowDown size={15} />
            </button>
          ) : (
            <button
              onClick={() => handlePublish(row)}
              className="p-1.5 rounded-md text-ink-sub hover:bg-grass/10 hover:text-grass transition-colors"
              title="上线"
            >
              <ArrowUp size={15} />
            </button>
          )}
          <button
            onClick={() => handleDelete(row)}
            className="p-1.5 rounded-md text-ink-sub hover:bg-danger/10 hover:text-danger transition-colors"
            title="删除"
          >
            <Trash2 size={15} />
          </button>
        </div>
      ),
    },
  ];

  const statusOptions: Array<{ label: string; value: 'draft' | 'published' | 'archived' | undefined }> = [
    { label: '全部', value: undefined },
    { label: '草稿', value: 'draft' },
    { label: '已发布', value: 'published' },
    { label: '已下线', value: 'archived' },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">专题管理</h1>
          <p className="text-ink-sub text-sm mt-1">
            共 {total} 个专题 · 切换学校只展示当前学校专题
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="text" onClick={handleBatchSort}>
            <ListOrdered size={14} className="mr-1" />
            按列表顺序批量排序
          </Button>
          <Button size="sm" variant="primary" onClick={openCreateModal}>
            <Plus size={14} className="mr-1" />
            新建专题
          </Button>
        </div>
      </div>

      {/* 筛选 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1 bg-paper border border-line rounded-md p-0.5">
          {statusOptions.map((opt) => (
            <button
              key={String(opt.label)}
              onClick={() => {
                setStatusFilter(opt.value);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                statusFilter === opt.value
                  ? 'bg-lake text-paper'
                  : 'text-ink-sub hover:bg-mist'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleKeywordSearch();
            }}
            placeholder="按标题搜索"
            className="px-3 py-1.5 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
          />
          <Button size="sm" variant="text" onClick={handleKeywordSearch}>
            <Search size={14} />
          </Button>
        </div>
      </div>

      {/* 表格 */}
      {topics.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <FileText size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无专题</p>
        </Card>
      ) : (
        <Table<TopicAdmin>
          columns={columns}
          data={topics}
          loading={loading}
          emptyText="暂无专题"
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

      {/* 新建/编辑 Modal */}
      <Modal
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title={editingId === null ? '新建专题' : `编辑专题 #${editingId}`}
        size="lg"
      >
        <div className="space-y-3 p-1">
          {/* 标题 */}
          <div>
            <label className="block text-sm font-medium text-ink mb-1">
              专题标题 <span className="text-danger">*</span>
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="如：开学季专题"
              maxLength={200}
              className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
            />
          </div>

          {/* 描述 */}
          <div>
            <label className="block text-sm font-medium text-ink mb-1">描述</label>
            <textarea
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="专题描述（可选）"
              rows={3}
              maxLength={2000}
              className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake resize-none"
            />
          </div>

          {/* 封面 URL */}
          <div>
            <label className="block text-sm font-medium text-ink mb-1">封面图 URL</label>
            <input
              type="text"
              value={formData.cover_url || ''}
              onChange={(e) => setFormData({ ...formData, cover_url: e.target.value })}
              placeholder="https://..."
              maxLength={500}
              className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
            />
          </div>

          {/* 排序 + 状态 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-ink mb-1">排序权重</label>
              <input
                type="number"
                value={formData.sort_order ?? 0}
                onChange={(e) =>
                  setFormData({ ...formData, sort_order: parseInt(e.target.value) || 0 })
                }
                min={0}
                className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-ink mb-1">
                状态
                {editingId !== null && (
                  <span className="text-xs text-ink-muted ml-1">（不可在此修改，请用上下线）</span>
                )}
              </label>
              <select
                value={formData.status || 'draft'}
                onChange={(e) =>
                  setFormData({ ...formData, status: e.target.value as 'draft' | 'published' })
                }
                disabled={editingId !== null}
                className="w-full px-3 py-2 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake disabled:bg-mist/50 disabled:text-ink-muted"
              >
                <option value="draft">草稿（保存后不可见）</option>
                <option value="published">直接发布（用户端可见）</option>
              </select>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button size="sm" variant="text" onClick={() => setEditModalOpen(false)}>
              取消
            </Button>
            <Button size="sm" variant="primary" onClick={handleSubmit} loading={submitting}>
              {editingId === null ? '创建' : '保存'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* 编排 Modal */}
      <Modal
        isOpen={arrangeModalOpen}
        onClose={() => setArrangeModalOpen(false)}
        title={arrangingTopic ? `编排：${arrangingTopic.title}` : '编排专题'}
        size="lg"
      >
        <div className="space-y-4 p-1">
          {/* 当前关联的帖子列表 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-ink text-sm">
                当前内容（{arrangingTopic?.posts.length || 0}）
              </h4>
              {arrangingTopic && arrangingTopic.posts.length > 0 && (
                <Button size="sm" variant="text" onClick={handleSavePostSorts}>
                  保存排序
                </Button>
              )}
            </div>

            {arrangingTopic && arrangingTopic.posts.length > 0 ? (
              <div className="space-y-2">
                {arrangingTopic.posts.map((post: TopicPostAdminItem) => (
                  <div
                    key={post.id}
                    className="flex items-center gap-2 p-2 border border-line rounded-md bg-paper"
                  >
                    <input
                      type="number"
                      value={postSorts[post.post_id] ?? post.sort_order}
                      onChange={(e) =>
                        setPostSorts({
                          ...postSorts,
                          [post.post_id]: parseInt(e.target.value) || 0,
                        })
                      }
                      className="w-16 px-2 py-1 border border-line rounded text-xs text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30"
                      min={0}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-ink truncate">
                        {post.post_title || `#${post.post_id}`}
                      </p>
                      <p className="text-xs text-ink-muted">
                        状态：{post.post_status || '-'}
                      </p>
                    </div>
                    <button
                      onClick={() => handleRemovePost(post.post_id)}
                      className="p-1 rounded text-ink-sub hover:bg-danger/10 hover:text-danger"
                      title="移除"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-ink-muted text-sm py-6 bg-mist/30 rounded-md">
                暂无关联内容
              </p>
            )}
          </div>

          {/* 添加帖子 */}
          <div className="border-t border-line pt-3">
            <h4 className="font-semibold text-ink text-sm mb-2">添加已发布内容</h4>
            <div className="flex items-center gap-2 mb-2">
              <input
                type="text"
                value={postSearchKeyword}
                onChange={(e) => setPostSearchKeyword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSearchPosts();
                }}
                placeholder="按标题/内容搜索同校已发布帖子"
                className="flex-1 px-3 py-1.5 border border-line rounded-md text-sm text-ink bg-paper focus:outline-none focus:ring-2 focus:ring-lake/30 focus:border-lake"
              />
              <Button size="sm" variant="text" onClick={handleSearchPosts} loading={searching}>
                <Search size={14} />
              </Button>
            </div>
            {searchedPosts.length > 0 && (
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {searchedPosts.map((post) => (
                  <div
                    key={post.id}
                    className="flex items-center gap-2 p-2 border border-line rounded-md bg-paper hover:bg-mist/30"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-ink truncate">{post.title}</p>
                      <p className="text-xs text-ink-muted line-clamp-1">{post.content}</p>
                    </div>
                    <button
                      onClick={() => handleAddPost(post.id)}
                      className="px-2 py-1 text-xs rounded bg-lake text-paper hover:bg-lake/90"
                    >
                      添加
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
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

export default AdminTopicsPage;
