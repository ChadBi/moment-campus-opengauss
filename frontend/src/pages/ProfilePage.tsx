import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { usersApi } from '../services/users';
import { postsApi } from '../services/posts';
import type { User, Post } from '../types';
import { Card } from '../components/ui/Card';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Loading } from '../components/ui/Loading';
import { Toast } from '../components/ui/Toast';
import { Edit, LogOut, FileText, LogIn, UserCircle, CheckCircle, Award } from 'lucide-react';

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuthStore();
  const [userInfo, setUserInfo] = useState<User | null>(null);
  const [myPosts, setMyPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    loadUserInfo();
    loadMyPosts();
  }, [isAuthenticated]);

  // 未登录状态
  if (!isAuthenticated) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="mb-6">
          <span className="eyebrow">PROFILE</span>
          <h1 className="text-2xl font-display font-bold text-lake mt-2">我的</h1>
        </div>
        <Card variant="elevated" padding="lg" className="text-center py-16 relative overflow-hidden">
          <div className="pointer-events-none absolute -top-10 -right-10 w-40 h-40 rounded-full border-[18px] border-mist/60" />
          <div className="relative">
            <div className="w-20 h-20 mx-auto rounded-2xl bg-mist grid place-items-center mb-5">
              <UserCircle size={40} className="text-lake" />
            </div>
            <h3 className="text-lg font-display font-bold text-ink mb-2">登录后查看个人信息</h3>
            <p className="text-ink-sub text-sm mb-6">登录账号，记录你的校园贡献与足迹</p>
            <Button
              variant="primary"
              icon={<LogIn size={16} />}
              onClick={() => navigate('/login')}
            >
              去登录
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const loadUserInfo = async () => {
    try {
      const response = await usersApi.getCurrentUser();
      setUserInfo(response.data);
    } catch (error) {
      console.error('加载用户信息失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMyPosts = async () => {
    try {
      const response = await postsApi.getMyPosts();
      setMyPosts(response.items as Post[]);
    } catch (error) {
      console.error('加载我的帖子失败:', error);
    }
  };

  const handleLogout = () => {
    logout();
    setToast({ message: '已退出登录', type: 'success' });
    setTimeout(() => navigate('/login'), 1000);
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-6">
        <Loading text="加载中..." />
      </div>
    );
  }

  if (!userInfo) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-6 text-center text-ink-sub">
        <p>用户信息加载失败</p>
      </div>
    );
  }

  const stats = [
    { label: '已发布', value: myPosts.length, icon: <FileText size={16} />, color: 'text-lake' },
    { label: '确认有效', value: 0, icon: <CheckCircle size={16} />, color: 'text-grass' },
    { label: '贡献值', value: 0, icon: <Award size={16} />, color: 'text-sun' },
  ];

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* Hero 区域 */}
      <Card variant="elevated" padding="none" className="mb-6 overflow-hidden">
        <div className="relative px-7 pt-7 pb-6 bg-gradient-to-br from-lake to-lake-light text-white overflow-hidden">
          {/* 装饰圆 */}
          <div className="pointer-events-none absolute -top-16 -right-12 w-56 h-56 rounded-full border-[34px] border-white/10" />
          <div className="pointer-events-none absolute -bottom-20 -left-12 w-48 h-48 rounded-full border-[28px] border-white/8" />
          <div className="relative flex items-center gap-4">
            <Avatar
              src={userInfo.avatar_url}
              fallback={userInfo.nickname?.[0] || '?'}
              size="xl"
              className="!ring-4 !ring-white/30"
            />
            <div className="flex-1 min-w-0">
              <span className="eyebrow !text-white/70">CAMPUS MEMBER</span>
              <h1 className="text-xl font-display font-bold mt-1 truncate">{userInfo.nickname}</h1>
              <p className="text-white/75 text-xs mt-0.5 truncate">{userInfo.email}</p>
              {userInfo.bio && (
                <p className="text-white/85 text-sm mt-2 line-clamp-2">{userInfo.bio}</p>
              )}
            </div>
          </div>
          {/* 校园贡献值小卡 */}
          <div className="relative mt-5 inline-flex items-center gap-2 bg-white/15 backdrop-blur-sm rounded-full pl-2 pr-4 py-1.5">
            <span className="w-7 h-7 rounded-full bg-lamp grid place-items-center">
              <Award size={15} className="text-white" />
            </span>
            <span className="text-xs text-white/85">校园贡献值</span>
            <span className="font-data font-bold text-base text-white">0</span>
          </div>
        </div>
        <div className="px-7 py-4 flex gap-2 bg-paper">
          <Button variant="secondary" size="sm" icon={<Edit size={16} />}>
            编辑资料
          </Button>
          <Button variant="danger" size="sm" onClick={handleLogout} icon={<LogOut size={16} />}>
            退出登录
          </Button>
        </div>
      </Card>

      {/* 统计卡片网格 */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {stats.map(stat => (
          <Card key={stat.label} variant="elevated" padding="sm" className="text-center">
            <div className={`mx-auto w-8 h-8 rounded-lg bg-mist grid place-items-center mb-2 ${stat.color}`}>
              {stat.icon}
            </div>
            <div className="font-data font-bold text-xl text-ink leading-none">{stat.value}</div>
            <div className="text-[11px] text-ink-muted mt-1.5">{stat.label}</div>
          </Card>
        ))}
      </div>

      {/* 我的发布列表 */}
      <Card variant="elevated" padding="md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display font-semibold text-ink flex items-center gap-2">
            <FileText size={18} className="text-lake" />
            我的发布
          </h2>
          <span className="hand-tag !bg-mist !text-ink-sub">{myPosts.length} 篇</span>
        </div>
        <div className="space-y-2.5">
          {myPosts.length === 0 ? (
            <div className="text-center py-10">
              <div className="text-[40px] leading-none mb-3">📝</div>
              <p className="text-ink-sub text-sm">还没有发布过帖子</p>
              <Button
                variant="text"
                size="sm"
                className="mt-3"
                onClick={() => navigate('/publish')}
              >
                去发布第一条
              </Button>
            </div>
          ) : (
            myPosts.map(post => (
              <div
                key={post.id}
                className="p-3 bg-mist/60 rounded-lg cursor-pointer hover:bg-mist hover:-translate-y-0.5 transition-all"
                onClick={() => navigate(`/posts/${post.id}`)}
              >
                <div className="flex items-center justify-between mb-1.5 gap-2">
                  <h3 className="font-medium text-ink text-sm line-clamp-1 flex-1 min-w-0">
                    {post.title}
                  </h3>
                  <Badge variant="default">{post.status}</Badge>
                </div>
                <p className="text-ink-sub text-xs line-clamp-2">{post.content}</p>
              </div>
            ))
          )}
        </div>
      </Card>

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

export default ProfilePage;
