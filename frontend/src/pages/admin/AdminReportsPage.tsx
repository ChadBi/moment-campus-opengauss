import React, { useState, useEffect } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Avatar } from '../../components/ui/Avatar';
import { Loading } from '../../components/ui/Loading';
import { Toast } from '../../components/ui/Toast';
import { api } from '../../services/api';
import { Flag, Check, X } from 'lucide-react';

interface Report {
  id: number;
  post_id?: number;
  comment_id?: number;
  report_type: string;
  description: string;
  status: string;
  created_at: string;
  reporter?: {
    id: number;
    nickname: string;
    avatar_url?: string;
  };
  post?: {
    id: number;
    title: string;
  };
}

const AdminReportsPage: React.FC = () => {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    loadReports();
  }, [filter]);

  const loadReports = async () => {
    try {
      setLoading(true);
      const params = filter !== 'all' ? { status: filter } : {};
      const response = await api.get('/admin/reports', { params });
      setReports(response.data);
    } catch (error) {
      console.error('加载举报列表失败:', error);
      setToast({ message: '加载举报列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (reportId: number, action: string) => {
    const result = prompt(`请输入处理结果（${action}）：`);
    if (!result) return;

    try {
      await api.put(`/admin/reports/${reportId}/handle`, {
        status: action,
        result,
      });
      setReports(reports.filter(r => r.id !== reportId));
      setToast({ message: '处理成功', type: 'success' });
    } catch (error) {
      console.error('处理失败:', error);
      setToast({ message: '处理失败', type: 'error' });
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return <Badge variant="warning">待处理</Badge>;
      case 'resolved':
        return <Badge variant="success">已解决</Badge>;
      case 'dismissed':
        return <Badge variant="default">已驳回</Badge>;
      default:
        return <Badge variant="default">{status}</Badge>;
    }
  };

  const getReportTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      spam: '垃圾信息',
      harassment: '骚扰',
      false_info: '虚假信息',
      inappropriate: '不当内容',
      other: '其他',
    };
    return labels[type] || type;
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
        <h1 className="text-2xl font-bold text-ink">举报管理</h1>
        <p className="text-ink-sub text-sm mt-1">
          共 {reports.length} 条举报
        </p>
      </div>

      <div className="mb-4 flex gap-2">
        <Button
          size="sm"
          variant={filter === 'all' ? 'primary' : 'secondary'}
          onClick={() => setFilter('all')}
        >
          全部
        </Button>
        <Button
          size="sm"
          variant={filter === 'pending' ? 'primary' : 'secondary'}
          onClick={() => setFilter('pending')}
        >
          待处理
        </Button>
        <Button
          size="sm"
          variant={filter === 'resolved' ? 'primary' : 'secondary'}
          onClick={() => setFilter('resolved')}
        >
          已解决
        </Button>
        <Button
          size="sm"
          variant={filter === 'dismissed' ? 'primary' : 'secondary'}
          onClick={() => setFilter('dismissed')}
        >
          已驳回
        </Button>
      </div>

      {reports.length === 0 ? (
        <Card padding="lg" className="text-center py-12">
          <Flag size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无举报记录</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {reports.map(report => (
            <Card key={report.id} padding="md">
              <div className="flex items-start gap-4">
                <Avatar
                  src={report.reporter?.avatar_url}
                  fallback={report.reporter?.nickname?.[0] || '?'}
                  size="md"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-medium text-ink text-sm">
                      {report.reporter?.nickname || '匿名举报'}
                    </span>
                    {getStatusBadge(report.status)}
                    <Badge variant="default" className="text-xs">
                      {getReportTypeLabel(report.report_type)}
                    </Badge>
                  </div>
                  {report.post && (
                    <p className="text-ink-sub text-sm mb-2">
                      举报内容：{report.post.title}
                    </p>
                  )}
                  <p className="text-ink text-sm mb-3">
                    {report.description}
                  </p>
                  <div className="text-xs text-ink-sub mb-3">
                    举报时间：{new Date(report.created_at).toLocaleString('zh-CN')}
                  </div>
                  {report.status === 'pending' && (
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => handleResolve(report.id, 'resolved')}
                      >
                        <Check size={16} className="mr-1" />
                        解决
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => handleResolve(report.id, 'dismissed')}
                      >
                        <X size={16} className="mr-1" />
                        驳回
                      </Button>
                    </div>
                  )}
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

export default AdminReportsPage;
