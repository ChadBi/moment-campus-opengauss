import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { notificationsApi } from '../services/notifications';
import type { Notification } from '../types';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Loading } from '../components/ui/Loading';
import { Toast } from '../components/ui/Toast';
import { Bell, Check, CheckCheck, LogIn } from 'lucide-react';

const NotificationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    loadNotifications();
  }, [isAuthenticated]);

  // 未登录状态
  if (!isAuthenticated) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="mb-6">
          <span className="eyebrow">NOTIFICATIONS</span>
          <h1 className="text-2xl font-display font-bold text-lake mt-2">通知消息</h1>
        </div>
        <Card variant="elevated" padding="lg" className="text-center py-16 relative overflow-hidden">
          <div className="pointer-events-none absolute -top-10 -right-10 w-40 h-40 rounded-full border-[18px] border-mist/60" />
          <div className="relative">
            <div className="w-20 h-20 mx-auto rounded-2xl bg-mist grid place-items-center mb-5">
              <Bell size={40} className="text-lake" />
            </div>
            <h3 className="text-lg font-display font-bold text-ink mb-2">登录后查看通知消息</h3>
            <p className="text-ink-sub text-sm mb-6">登录账号，及时接收评论、点赞与系统通知</p>
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

  const loadNotifications = async () => {
    try {
      setLoading(true);
      const response = await notificationsApi.getNotifications();
      setNotifications(response.items as Notification[]);
    } catch (error) {
      console.error('加载通知失败:', error);
      setToast({ message: '加载通知失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsRead = async (id: number) => {
    try {
      await notificationsApi.markAsRead(id);
      loadNotifications();
      setToast({ message: '已标记为已读', type: 'success' });
    } catch (error) {
      setToast({ message: '操作失败', type: 'error' });
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      loadNotifications();
      setToast({ message: '已全部标记为已读', type: 'success' });
    } catch (error) {
      setToast({ message: '操作失败', type: 'error' });
    }
  };

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.is_read) {
      handleMarkAsRead(notification.id);
    }
    if (notification.target_type === 'post' && notification.target_id) {
      navigate(`/posts/${notification.target_id}`);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    if (diff < 60000) return '刚刚';
    const minutes = Math.floor(diff / 60000);
    if (minutes < 30) return `${minutes}分钟前`;
    const hours = Math.floor(diff / 3600000);
    if (hours < 24) return `${hours}小时前`;
    const days = Math.floor(diff / 86400000);
    return `${days}天前`;
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'comment':
        return '💬';
      case 'like':
        return '❤️';
      case 'system':
        return '🔔';
      case 'audit':
        return '📋';
      default:
        return '📩';
    }
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <div className="flex items-end justify-between mb-6 gap-3">
        <div>
          <span className="eyebrow">NOTIFICATIONS</span>
          <h1 className="text-2xl font-display font-bold text-lake mt-2">通知消息</h1>
          <p className="text-ink-sub text-sm mt-1">
            {unreadCount > 0 ? `${unreadCount} 条未读通知` : '暂无未读通知'}
          </p>
        </div>
        {unreadCount > 0 && (
          <Button
            variant="secondary"
            size="sm"
            onClick={handleMarkAllAsRead}
            icon={<CheckCheck size={16} />}
          >
            全部已读
          </Button>
        )}
      </div>

      {loading ? (
        <div className="py-12">
          <Loading text="加载中..." />
        </div>
      ) : notifications.length === 0 ? (
        <Card variant="outlined" padding="lg" className="text-center py-16">
          <div className="text-[56px] leading-none mb-4">🔔</div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">暂无通知</h3>
          <p className="text-ink-sub text-sm">新的消息会在这里出现</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {notifications.map(notification => (
            <Card
              key={notification.id}
              variant="elevated"
              padding="md"
              className={`relative overflow-hidden cursor-pointer ${
                !notification.is_read ? '!border-lake/30' : ''
              }`}
              onClick={() => handleNotificationClick(notification)}
            >
              {/* 未读左侧湖蓝色边条 */}
              {!notification.is_read && (
                <span className="absolute left-0 top-0 bottom-0 w-1 bg-lake" />
              )}
              <div className="flex items-start gap-3">
                <div className="w-11 h-11 rounded-xl bg-mist grid place-items-center text-xl flex-shrink-0">
                  {getNotificationIcon(notification.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1 gap-2">
                    <h3 className="font-display font-semibold text-ink text-sm truncate">
                      {notification.title}
                    </h3>
                    {!notification.is_read && (
                      <Badge variant="info">未读</Badge>
                    )}
                  </div>
                  <p className="text-ink-sub text-sm mb-2 leading-relaxed">
                    {notification.content}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-ink-muted font-data">
                      {formatDate(notification.created_at)}
                    </span>
                    {!notification.is_read && (
                      <Button
                        variant="text"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleMarkAsRead(notification.id);
                        }}
                        icon={<Check size={14} />}
                      >
                        标记已读
                      </Button>
                    )}
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

export default NotificationsPage;
