import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Map, PlusCircle, User } from 'lucide-react';

const navItems = [
  { path: '/map', label: '地图', icon: Map },
  // /home 为原帖子信息流与话题聚合页（原首页，因地图升级为主页后改叫「帖子」）
  { path: '/home', label: '帖子', icon: Home },
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
        className="grid grid-cols-4 gap-1 bg-lake/95 border border-white/10 rounded-[16px] p-1.5"
        style={{ boxShadow: '0 8px 32px rgba(20,55,63,.25)' }}
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              aria-label={item.label}
              className={`grid place-items-center gap-0.5 rounded-[10px] py-1.5 transition-colors ${
                isActive
                  ? 'bg-paper text-lake'
                  : 'text-white/70'
              }`}
            >
              <Icon size={18} />
              <span className="text-[10px]">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
};
