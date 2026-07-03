import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
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
        <p className="text-ink-sub">加载统计数据失败</p>
      </div>
    );
  }

  // 颜色全部回归设计系统：lake / sun / grass / lake-dark / danger / lamp / info
  const statCards = [
    {
      title: '总信息数',
      value: stats.total_posts,
      icon: FileText,
      color: 'text-lake',
      bgColor: 'bg-lake/10',
    },
    {
      title: '待审核信息',
      value: stats.pending_posts,
      icon: Calendar,
      color: 'text-sun',
      bgColor: 'bg-sun/15',
    },
    {
      title: '总用户数',
      value: stats.total_users,
      icon: Users,
      color: 'text-grass',
      bgColor: 'bg-grass/15',
    },
    {
      title: '活跃用户',
      value: stats.active_users,
      icon: TrendingUp,
      color: 'text-lake-dark',
      bgColor: 'bg-lake/10',
    },
    {
      title: '总举报数',
      value: stats.total_reports,
      icon: Flag,
      color: 'text-danger',
      bgColor: 'bg-danger/10',
    },
    {
      title: '待处理举报',
      value: stats.pending_reports,
      icon: Flag,
      color: 'text-lamp',
      bgColor: 'bg-lamp/10',
    },
    {
      title: '总评论数',
      value: stats.total_comments,
      icon: MessageCircle,
      color: 'text-info',
      bgColor: 'bg-info/10',
    },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ink">仪表盘</h1>
        <p className="text-ink-sub text-sm mt-1">系统概览</p>
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
                  <p className="text-ink-sub text-sm">{card.title}</p>
                  <p className="text-2xl font-bold text-ink">
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
          <h2 className="text-lg font-semibold text-ink mb-4">
            快速操作
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              to="/admin/review"
              className="flex items-center gap-3 p-4 bg-mist rounded-lg hover:bg-mist/70 transition-colors"
            >
              <FileText className="text-lake" size={24} />
              <div>
                <p className="font-medium text-ink">内容审核</p>
                <p className="text-sm text-ink-sub">
                  {stats.pending_posts} 条待审核
                </p>
              </div>
            </Link>
            <Link
              to="/admin/reports"
              className="flex items-center gap-3 p-4 bg-mist rounded-lg hover:bg-mist/70 transition-colors"
            >
              <Flag className="text-danger" size={24} />
              <div>
                <p className="font-medium text-ink">举报管理</p>
                <p className="text-sm text-ink-sub">
                  {stats.pending_reports} 条待处理
                </p>
              </div>
            </Link>
            <Link
              to="/admin/users"
              className="flex items-center gap-3 p-4 bg-mist rounded-lg hover:bg-mist/70 transition-colors"
            >
              <Users className="text-grass" size={24} />
              <div>
                <p className="font-medium text-ink">用户管理</p>
                <p className="text-sm text-ink-sub">
                  {stats.total_users} 个用户
                </p>
              </div>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default AdminHomePage;
