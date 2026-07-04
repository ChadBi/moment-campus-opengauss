import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileNav } from './MobileNav';
import { useAuthStore } from '../../store/useAuthStore';

interface MainLayoutProps {
  notificationCount?: number;
  categories?: Array<{
    id: number;
    name: string;
    icon: string;
  }>;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  notificationCount = 0,
  categories = [],
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // 从 store 获取登录用户信息：登录后显示头像，未登录显示登录按钮
  const user = useAuthStore((s) => s.user);

  return (
    <div className="min-h-screen bg-mist md:grid md:grid-cols-[88px_minmax(0,1fr)]">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        categories={categories}
      />

      <div className="min-w-0 min-h-screen flex flex-col">
        <Header
          onMenuClick={() => setSidebarOpen(true)}
          user={user}
          notificationCount={notificationCount}
        />

        <main className="flex-1 px-3 md:px-6 py-4 md:py-6 pb-24 md:pb-8">
          <div className="max-w-[1680px] mx-auto">
            <Outlet />
          </div>
        </main>
      </div>

      <MobileNav />
    </div>
  );
};
