import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Map, PlusCircle, User } from 'lucide-react';

const navItems = [
  { path: '/', label: '首页', icon: Home },
  { path: '/map', label: '地图', icon: Map },
  { path: '/publish', label: '发布', icon: PlusCircle },
  { path: '/profile', label: '我的', icon: User },
];

export const MobileNav: React.FC = () => {
  const location = useLocation();

  return (
    <nav
      className="fixed left-3 right-3 bottom-3 z-30 md:hidden"
      aria-label="移动端导航"
    >
      <div
        className="grid grid-cols-4 gap-2 bg-lake/[0.94] backdrop-blur-lg border border-white/[0.15] rounded-[20px] p-2"
        style={{ boxShadow: '0 16px 46px rgba(20,55,63,.28)' }}
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              aria-label={item.label}
              className={`grid place-items-center gap-[3px] rounded-[13px] py-1.5 transition-colors ${
                isActive
                  ? 'bg-paper text-lake'
                  : 'text-white/70'
              }`}
            >
              <Icon size={19} />
              <span className="text-[10px]">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
};
