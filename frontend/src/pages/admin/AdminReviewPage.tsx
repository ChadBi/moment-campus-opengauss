import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi, type PostBrief } from '../../services/admin';
import { Check, X, Eye, FileText } from 'lucide-react';

const PAGE_SIZE = 10;

const AdminReviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [posts, setPosts] = useState<PostBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [selectedKeys, setSelectedKeys] = useState<Array<string | number>>([]);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);

  const loadPosts = useCallback(async (p: number) => {
    try {
      setLoading(true);
      const data = await adminApi.getPendingPosts({ page: p, page_size: PAGE_SIZE });
      setPosts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setSelectedKeys([]);
    } catch (error) {
      console.error('加载待审核帖子失败:', error);
      setToast({ message: '加载待审核帖子失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPosts(page);
  }, [page, loadPosts]);

  /** 单条通过 */
  const handleApprove = async (postId: number) => {
    try {
      await adminApi.approvePost(postId);
      setToast({ message: '审核通过', type: 'success' });
      loadPosts(page);
    } catch (error) {
      console.error('审核通过失败:', error);
      setToast({ message: '审核通过失败', type: 'error' });
    }
  };

  /** 单条拒绝 */
  const handleReject = async (postId: number) => {
    const reason = window.prompt('请输入拒绝原因：');
    if (!reason) return;

    try {
      await adminApi.rejectPost(postId, { reason });
      setToast({ message: '已拒绝', type: 'success' });
      loadPosts(page);
    } catch (error) {
      console.error('拒绝失败:', error);
      setToast({ message: '拒绝失败', type: 'error' });
    }
  };

  /** 批量通过 */
  const handleBatchApprove = async () => {
    if (selectedKeys.length === 0) return;
    setBatchLoading(true);
    try {
      const result = await adminApi.batchApprovePosts({
        post_ids: selectedKeys as number[],
      });
      setToast({ message: result.message, type: result.failed > 0 ? 'warning' : 'success' });
      loadPosts(page);
    } catch (error) {
      console.error('批量通过失败:', error);
      setToast({ message: '批量通过失败', type: 'error' });
    } finally {
      setBatchLoading(false);
    }
  };

  /** 批量拒绝 */
  const handleBatchReject = async () => {
    if (selectedKeys.length === 0) return;
    const reason = window.prompt(`将拒绝 ${selectedKeys.length} 条帖子，请输入拒绝原因：`);
    if (!reason) return;

    setBatchLoading(true);
    try {
      const result = await adminApi.batchRejectPosts({
        post_ids: selectedKeys as number[],
        reason,
      });
      setToast({ message: result.message, type: result.failed > 0 ? 'warning' : 'success' });
      loadPosts(page);
    } catch (error) {
      console.error('批量拒绝失败:', error);
      setToast({ message: '批量拒绝失败', type: 'error' });
    } finally {
      setBatchLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 表格列配置
  const columns: Column<PostBrief>[] = [
    {
      key: 'title',
      title: '标题',
      render: (value, row) => (
        <div className="min-w-0">
          <button
            onClick={() => navigate(`/posts/${row.id}`)}
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
            onClick={() => navigate(`/posts/${row.id}`)}
            className="p-1.5 rounded-md text-ink-sub hover:bg-mist hover:text-lake transition-colors"
            title="查看详情"
          >
            <Eye size={15} />
          </button>
          <button
            onClick={() => handleApprove(row.id)}
            className="p-1.5 rounded-md text-grass hover:bg-grass/10 transition-colors"
            title="通过"
          >
            <Check size={15} />
          </button>
          <button
            onClick={() => handleReject(row.id)}
            className="p-1.5 rounded-md text-danger hover:bg-danger/10 transition-colors"
            title="拒绝"
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
                onClick={handleBatchApprove}
                loading={batchLoading}
              >
                <Check size={14} className="mr-1" />
                批量通过
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={handleBatchReject}
                loading={batchLoading}
              >
                <X size={14} className="mr-1" />
                批量拒绝
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
