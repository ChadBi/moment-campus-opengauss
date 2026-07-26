import React, { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileNav } from './MobileNav';
import { SkipLink } from './SkipLink';
import { FirstUseGuide } from '../FirstUseGuide';
import { useAuthStore } from '../../store/useAuthStore';
import { notificationsApi } from '../../services/notifications';

interface MainLayoutProps {
  categories?: Array<{
    id: number;
    name: string;
    icon: string;
  }>;
}

/**
 * PRF-01.2: MainLayout 拉取未读通知数量并通过 Header 显示角标
 *
 * 设计要点：
 * - 仅登录用户拉取（游客无通知）
 * - 路由切换时刷新（用户可能在通知页标记已读后回到主页，需重新计算）
 * - 标记已读 / 发布评论触发新通知等场景由各页面自行调用 invalidate
 * - 拉取失败静默处理（角标缺省为 0，不阻塞主流程）
 */
export const MainLayout: React.FC<MainLayoutProps> = ({
  categories = [],
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) {
      setUnreadCount(0);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const resp = await notificationsApi.getUnreadCount();
        if (!cancelled) {
          setUnreadCount(resp.unread_count);
        }
      } catch {
        // 静默处理：角标缺省为 0，不阻塞主流程
        if (!cancelled) setUnreadCount(0);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, location.pathname]);

  return (
    <div className="min-h-screen bg-mist md:grid md:grid-cols-[72px_minmax(0,1fr)]">
      {/* UX-01.7: 无障碍跳转链接（键盘 Tab 聚焦时显示） */}
      <SkipLink />

      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        categories={categories}
      />

      <div className="min-w-0 min-h-screen flex flex-col">
        <Header
          onMenuClick={() => setSidebarOpen(true)}
          user={user}
          notificationCount={unreadCount}
        />

        <main
          id="main-content"
          className="flex-1 px-3 md:px-6 py-3 pb-20 md:pb-6"
          tabIndex={-1}
        >
          <div className="max-w-[1680px] mx-auto">
            <Outlet />
          </div>
        </main>
      </div>

      <MobileNav />

      {/* ACC-01.4: 三步首用引导（仅未完成引导的登录用户可见） */}
      <FirstUseGuide />
    </div>
  );
};
