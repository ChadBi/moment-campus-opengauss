import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, Map, Search, User, Bell, X } from 'lucide-react';

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
  { path: '/', label: '首页', icon: Home },
  { path: '/map', label: '地图', icon: Map },
  { path: '/search', label: '搜索', icon: Search },
  { path: '/notifications', label: '通知', icon: Bell },
  { path: '/profile', label: '我的', icon: User },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const location = useLocation();

  return (
    <>
      {/* 遮罩层 - 移动端 */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-ink/40 backdrop-blur-sm z-40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* 侧边栏：88px 窄边栏，深湖蓝底 */}
      <aside
        className={`fixed top-0 left-0 h-full w-[88px] bg-lake text-white z-50 flex flex-col items-center py-[18px] px-3 border-r border-white/10 transform transition-transform duration-300 md:sticky md:top-0 md:h-screen md:translate-x-0 md:z-30 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* 品牌标志：52x52 白色圆角方块 + 楷体"此"字 + 灯笼橙弧线装饰 */}
        <div className="relative mb-7">
          <Link
            to="/"
            onClick={onClose}
            className="block w-[52px] h-[52px] rounded-[17px] bg-paper grid place-items-center text-lake overflow-hidden relative"
            style={{ boxShadow: 'inset 0 -4px 0 rgba(23,77,94,.08)' }}
            aria-label="此刻校园首页"
          >
            <span
              className="font-display font-bold leading-none"
              style={{ fontSize: '27px', transform: 'translateY(-3px)' }}
            >
              此
            </span>
            {/* 灯笼橙弧线装饰 */}
            <span
              className="absolute pointer-events-none"
              style={{
                width: '30px',
                height: '10px',
                border: '2px solid #ff8a4c',
                borderColor: '#ff8a4c transparent transparent transparent',
                borderRadius: '50%',
                transform: 'rotate(-12deg)',
                top: '30px',
                left: '12px',
              }}
            />
          </Link>
          {/* 关闭按钮 - 移动端 */}
          <button
            onClick={onClose}
            className="md:hidden absolute -top-2 -right-2 w-6 h-6 rounded-full bg-white/20 grid place-items-center"
            aria-label="关闭菜单"
          >
            <X size={14} />
          </button>
        </div>

        {/* 导航按钮：垂直排列，图标+小字 */}
        <nav className="w-full grid gap-2.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onClose}
                aria-label={item.label}
                className={`grid place-items-center gap-[3px] rounded-2xl min-h-[58px] py-2 px-1 transition-colors ${
                  isActive
                    ? 'bg-paper text-lake shadow-sm'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`}
              >
                <Icon size={22} />
                <span className="text-[11px] tracking-[0.04em]">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="flex-1" />

        {/* 底部头像按钮：灯笼橙圆形 */}
        <Link
          to="/profile"
          onClick={onClose}
          className="w-[42px] h-[42px] rounded-[14px] bg-lamp text-white font-extrabold grid place-items-center transition-transform hover:-translate-y-0.5"
          style={{ boxShadow: '0 8px 20px rgba(0,0,0,.16)' }}
          title="个人中心"
        >
          我
        </Link>
      </aside>
    </>
  );
};
