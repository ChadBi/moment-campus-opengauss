import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Map, Search, User, Bell, MapPin, X } from 'lucide-react';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  categories?: Array<{
    id: number;
    name: string;
    icon: string;
  }>;
}

const navItems = [
  { path: '/map', label: '地图', icon: Map },
  { path: '/', label: '首页', icon: Home },
  // A-05: 校园地点（设施资料、AI 摘要与评分评价）
  { path: '/locations', label: '地点', icon: MapPin },
  { path: '/search', label: '搜索', icon: Search },
  { path: '/notifications', label: '通知', icon: Bell },
  { path: '/profile', label: '我的', icon: User },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const location = useLocation();

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-ink/40 z-40 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 left-0 h-full w-[72px] bg-lake text-white z-50 flex flex-col items-center py-4 px-2 border-r border-lake-light transform transition-transform duration-300 md:sticky md:top-0 md:h-screen md:translate-x-0 md:z-30 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="relative mb-6">
          <Link
            to="/map"
            onClick={onClose}
            className="block w-[44px] h-[44px] rounded-[12px] bg-paper grid place-items-center text-lake overflow-hidden relative"
            aria-label="此刻校园地图主页"
          >
            <span
              className="font-display font-bold leading-none"
              style={{ fontSize: '22px' }}
            >
              此
            </span>
          </Link>
          <button
            onClick={onClose}
            className="md:hidden absolute -top-1 -right-1 w-5 h-5 rounded-full bg-white/20 grid place-items-center"
            aria-label="关闭菜单"
          >
            <X size={12} />
          </button>
        </div>

        <nav className="w-full grid gap-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onClose}
                aria-label={item.label}
                className={`grid place-items-center gap-0.5 rounded-[10px] min-h-[48px] py-1.5 px-1 transition-colors ${
                  isActive
                    ? 'bg-paper text-lake shadow-sm'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`}
              >
                <Icon size={20} />
                <span className="text-[10px]">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="flex-1" />

        <Link
          to="/profile"
          onClick={onClose}
          className="w-[36px] h-[36px] rounded-[10px] bg-lamp text-white font-bold grid place-items-center hover:bg-lamp-dark transition-colors"
          title="个人中心"
        >
          我
        </Link>
      </aside>
    </>
  );
};
