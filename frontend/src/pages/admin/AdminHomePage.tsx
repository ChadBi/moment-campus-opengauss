import React, { useState, useEffect } from 'react';
import { Card } from '../../components/ui/Card';
import { Loading } from '../../components/ui/Loading';
import { api } from '../../services/api';
import { 
  FileText, 
  Users, 
  Flag, 
  MessageCircle, 
  TrendingUp,
  Calendar
} from 'lucide-react';

interface DashboardStats {
  total_posts: number;
  pending_posts: number;
  total_users: number;
  active_users: number;
  total_reports: number;
  pending_reports: number;
  total_comments: number;
}

const AdminHomePage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/stats');
      setStats(response.data);
    } catch (error) {
      console.error('加载统计数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="py-12">
        <Loading text="加载中..." />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="py-12 text-center">
        <p className="text-text-sub">加载统计数据失败</p>
      </div>
    );
  }

  const statCards = [
    {
      title: '总信息数',
      value: stats.total_posts,
      icon: FileText,
      color: 'text-blue-500',
      bgColor: 'bg-blue-50',
    },
    {
      title: '待审核信息',
      value: stats.pending_posts,
      icon: Calendar,
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-50',
    },
    {
      title: '总用户数',
      value: stats.total_users,
      icon: Users,
      color: 'text-green-500',
      bgColor: 'bg-green-50',
    },
    {
      title: '活跃用户',
      value: stats.active_users,
      icon: TrendingUp,
      color: 'text-purple-500',
      bgColor: 'bg-purple-50',
    },
    {
      title: '总举报数',
      value: stats.total_reports,
      icon: Flag,
      color: 'text-red-500',
      bgColor: 'bg-red-50',
    },
    {
      title: '待处理举报',
      value: stats.pending_reports,
      icon: Flag,
      color: 'text-orange-500',
      bgColor: 'bg-orange-50',
    },
    {
      title: '总评论数',
      value: stats.total_comments,
      icon: MessageCircle,
      color: 'text-indigo-500',
      bgColor: 'bg-indigo-50',
    },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-main">仪表盘</h1>
        <p className="text-text-sub text-sm mt-1">系统概览</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {statCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <Card key={index} padding="md">
              <div className="flex items-center gap-4">
                <div className={`${card.bgColor} p-3 rounded-lg`}>
                  <Icon className={card.color} size={24} />
                </div>
                <div>
                  <p className="text-text-sub text-sm">{card.title}</p>
                  <p className="text-2xl font-bold text-text-main">
                    {card.value}
                  </p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="mt-8">
        <Card padding="md">
          <h2 className="text-lg font-semibold text-text-main mb-4">
            快速操作
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <a
              href="/admin/review"
              className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <FileText className="text-blue-500" size={24} />
              <div>
                <p className="font-medium text-text-main">内容审核</p>
                <p className="text-sm text-text-sub">
                  {stats.pending_posts} 条待审核
                </p>
              </div>
            </a>
            <a
              href="/admin/reports"
              className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <Flag className="text-red-500" size={24} />
              <div>
                <p className="font-medium text-text-main">举报管理</p>
                <p className="text-sm text-text-sub">
                  {stats.pending_reports} 条待处理
                </p>
              </div>
            </a>
            <a
              href="/admin/users"
              className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <Users className="text-green-500" size={24} />
              <div>
                <p className="font-medium text-text-main">用户管理</p>
                <p className="text-sm text-text-sub">
                  {stats.total_users} 个用户
                </p>
              </div>
            </a>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default AdminHomePage;
