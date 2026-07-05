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
  const user = useAuthStore((s) => s.user);

  return (
    <div className="min-h-screen bg-mist md:grid md:grid-cols-[72px_minmax(0,1fr)]">
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

        <main className="flex-1 px-3 md:px-6 py-3 pb-20 md:pb-6">
          <div className="max-w-[1680px] mx-auto">
            <Outlet />
          </div>
        </main>
      </div>

      <MobileNav />
    </div>
  );
};
