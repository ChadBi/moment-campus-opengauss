import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Avatar } from '../../components/ui/Avatar';
import { Loading } from '../../components/ui/Loading';
import { Toast } from '../../components/ui/Toast';
import { api } from '../../services/api';
import { Check, X, Eye, Calendar } from 'lucide-react';

interface PendingPost {
  id: number;
  title: string;
  content: string;
  status: string;
  created_at: string;
  author?: {
    id: number;
    nickname: string;
    avatar_url?: string;
  };
  category?: {
    id: number;
    name: string;
  };
}

const AdminReviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [posts, setPosts] = useState<PendingPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    loadPendingPosts();
  }, []);

  const loadPendingPosts = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/posts/pending');
      setPosts(response.data);
    } catch (error) {
      console.error('加载待审核帖子失败:', error);
      setToast({ message: '加载待审核帖子失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (postId: number) => {
    try {
      await api.put(`/admin/posts/${postId}/approve`);
      setPosts(posts.filter(p => p.id !== postId));
      setToast({ message: '审核通过', type: 'success' });
    } catch (error) {
      console.error('审核通过失败:', error);
      setToast({ message: '审核通过失败', type: 'error' });
    }
  };

  const handleReject = async (postId: number) => {
    const reason = prompt('请输入拒绝原因：');
    if (!reason) return;

    try {
      await api.put(`/admin/posts/${postId}/reject`, { reason });
      setPosts(posts.filter(p => p.id !== postId));
      setToast({ message: '已拒绝', type: 'success' });
    } catch (error) {
      console.error('拒绝失败:', error);
      setToast({ message: '拒绝失败', type: 'error' });
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="py-12">
        <Loading text="加载中..." />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ink">内容审核</h1>
        <p className="text-ink-sub text-sm mt-1">
          待审核信息：{posts.length} 条
        </p>
      </div>

      {posts.length === 0 ? (
        <Card padding="lg" className="text-center py-12">
          <Check size={48} className="mx-auto text-grass mb-4" />
          <p className="text-ink-sub">暂无待审核内容</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {posts.map(post => (
            <Card key={post.id} padding="md">
              <div className="flex items-start gap-4">
                <Avatar
                  src={post.author?.avatar_url}
                  fallback={post.author?.nickname?.[0] || '?'}
                  size="md"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-ink text-sm">
                      {post.author?.nickname || '匿名用户'}
                    </span>
                    <Badge variant="default" className="text-xs">
                      {post.category?.name || '未分类'}
                    </Badge>
                    <Badge variant="warning" className="text-xs">
                      待审核
                    </Badge>
                  </div>
                  <h3 className="font-semibold text-ink mb-2">
                    {post.title}
                  </h3>
                  <p className="text-ink-sub text-sm mb-3 line-clamp-2">
                    {post.content}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-ink-sub mb-3">
                    <span className="flex items-center gap-1">
                      <Calendar size={14} />
                      {formatDate(post.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => navigate(`/posts/${post.id}`)}
                    >
                      <Eye size={16} className="mr-1" />
                      查看详情
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => handleApprove(post.id)}
                    >
                      <Check size={16} className="mr-1" />
                      通过
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => handleReject(post.id)}
                    >
                      <X size={16} className="mr-1" />
                      拒绝
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};

export default AdminReviewPage;
