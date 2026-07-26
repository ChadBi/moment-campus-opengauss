import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { notificationsApi } from '../services/notifications';
import type { Notification } from '../types';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Loading } from '../components/ui/Loading';
import { Toast } from '../components/ui/Toast';
import { Bell, Check, CheckCheck, LogIn } from 'lucide-react';
import { logger } from '../utils/logger';
import { formatRelativeTime } from '../utils/date';

const NotificationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  // FND-01.4: 函数声明移到 useEffect 之前，避免 access-before-declaration
  const loadNotifications = async () => {
    try {
      const response = await notificationsApi.getNotifications();
      setNotifications(response.items as Notification[]);
    } catch (error) {
      logger.error('加载通知失败:', error);
      setToast({ message: '加载通知失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAuthenticated) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadNotifications();
  }, [isAuthenticated]);

  if (!isAuthenticated) {
    return (
      <div className="max-w-2xl mx-auto py-4">
        <header className="mb-5 px-1">
          <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">通知消息</h1>
          <p className="text-ink-muted text-sm mt-1">登录后查看通知消息</p>
        </header>
        <div className="bg-paper rounded-[16px] border border-line/60 p-10 text-center shadow-sm">
          <div className="w-20 h-20 mx-auto rounded-[16px] bg-mist grid place-items-center mb-5">
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
      </div>
    );
  }

  const handleMarkAsRead = async (id: number) => {
    try {
      await notificationsApi.markAsRead(id);
      void loadNotifications();
      setToast({ message: '已标记为已读', type: 'success' });
    } catch {
      setToast({ message: '操作失败', type: 'error' });
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      void loadNotifications();
      setToast({ message: '已全部标记为已读', type: 'success' });
    } catch {
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

  const formatDate = (dateString: string) => formatRelativeTime(dateString);
  // P3-003: formatDate 已抽取到 utils/date，这里保留别名避免大范围改名

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
      // SUB-01.2: 四类订阅通知（新内容/更新/过期/冲突）
      case 'subscription_new':
        return '🔔';
      case 'subscription_update':
        return '🔄';
      case 'subscription_expired':
        return '⌛';
      case 'subscription_conflict':
        return '⚠️';
      default:
        return '📩';
    }
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <div className="max-w-2xl mx-auto py-4">
      <div className="flex items-end justify-between mb-5 gap-3 px-1">
        <div>
          <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">通知消息</h1>
          <p className="text-ink-muted text-sm mt-1">
            {unreadCount > 0 ? `${unreadCount} 条未读通知` : '暂无未读通知'}
          </p>
        </div>
        {unreadCount > 0 && (
          <Button
            variant="secondary"
            size="sm"
            onClick={handleMarkAllAsRead}
            icon={<CheckCheck size={14} />}
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
        <div className="bg-paper rounded-[16px] border border-line/60 p-10 text-center shadow-sm">
          <div className="text-[48px] leading-none mb-4">🔔</div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">暂无通知</h3>
          <p className="text-ink-sub text-sm">新的消息会在这里出现</p>
        </div>
      ) : (
        <div className="bg-paper rounded-[16px] border border-line/60 shadow-sm overflow-hidden">
          {notifications.map((notification, idx) => (
            <div
              key={notification.id}
              className={`relative px-5 py-4 cursor-pointer hover:bg-paper-hover transition-colors ${
                idx > 0 ? 'border-t border-ink-divider/60' : ''
              } ${!notification.is_read ? 'bg-lake/[0.02]' : ''}`}
              onClick={() => handleNotificationClick(notification)}
            >
              {!notification.is_read && (
                <span className="absolute left-0 top-0 bottom-0 w-1 bg-lake" />
              )}
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-[10px] bg-mist grid place-items-center text-lg flex-shrink-0">
                  {getNotificationIcon(notification.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1 gap-2">
                    <h3 className="font-semibold text-ink text-sm truncate">
                      {notification.title}
                    </h3>
                    {!notification.is_read && (
                      <Badge variant="info">未读</Badge>
                    )}
                  </div>
                  <p className="text-ink-sub text-[14px] mb-2 leading-[1.6]">
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
                        icon={<Check size={13} />}
                      >
                        标记已读
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>
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
