import React from 'react';
import { Link } from 'react-router-dom';
import { Bell, Menu, Plus, School } from 'lucide-react';
import { Avatar } from '../ui';
import { useCampusStore } from '../../store/useCampusStore';

interface HeaderProps {
  onMenuClick?: () => void;
  user?: {
    nickname: string;
    avatar_url?: string;
  } | null;
  notificationCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  onMenuClick,
  user,
  notificationCount = 0,
}) => {
  const currentSchoolName = useCampusStore((s) => s.currentSchoolName);

  return (
    <header
      className="sticky top-0 z-30 bg-paper/95 backdrop-blur-sm border-b border-line/60"
      role="banner"
    >
      <div className="max-w-[1680px] mx-auto px-3 md:px-6 py-2.5 md:py-3">
        <div className="flex items-center justify-between gap-3 md:gap-5">
          <div className="flex items-center gap-2.5 whitespace-nowrap min-w-0">
            <h1 className="font-display font-bold text-[20px] md:text-[24px] tracking-wide text-lake leading-none flex-shrink-0">
              此刻校园
            </h1>
            {currentSchoolName && (
              <div className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1 rounded-[8px] bg-lake/8 text-lake border border-lake/10">
                <School size={13} aria-hidden="true" />
                <span className="text-[12px] font-semibold tracking-wide leading-none">
                  {currentSchoolName}
                </span>
              </div>
            )}
            <small className="hidden lg:inline text-ink-muted text-xs flex-shrink-0">
              把会消失的校园经验留下来
            </small>
          </div>

          <div className="flex justify-end items-center gap-1 md:gap-1.5">
            {user && (
              <Link
                to="/notifications"
                className="relative w-10 h-10 rounded-[10px] bg-paper border border-line/80 grid place-items-center hover:bg-paper-hover transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2"
                aria-label={notificationCount > 0 ? `通知（${notificationCount} 条未读）` : '通知'}
              >
                <Bell size={17} className="text-ink-sub" aria-hidden="true" />
                {notificationCount > 0 && (
                  <span
                    className="absolute -top-1 -right-1 min-w-[17px] h-[17px] px-1 bg-danger text-white text-[10px] font-bold rounded-full grid place-items-center"
                    aria-hidden="true"
                  >
                    {notificationCount > 99 ? '99+' : notificationCount}
                  </span>
                )}
              </Link>
            )}

            <Link
              to="/publish"
              className="h-10 px-4 rounded-[10px] bg-lamp text-white font-medium text-sm inline-flex items-center gap-1.5 shadow-lamp hover:bg-lamp-dark transition-colors active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-lamp focus-visible:ring-offset-2"
            >
              <Plus size={17} aria-hidden="true" />
              <span className="hidden md:inline">发布此刻</span>
            </Link>

            {user ? (
              <Link
                to="/profile"
                className="w-10 h-10 rounded-[10px] overflow-hidden border border-line/80 bg-paper grid place-items-center hover:bg-paper-hover transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2"
                aria-label={`个人中心：${user.nickname}`}
              >
                <Avatar
                  src={user.avatar_url}
                  fallback={user.nickname.charAt(0)}
                  size="sm"
                />
              </Link>
            ) : (
              <Link
                to="/login"
                className="h-10 px-4 rounded-[10px] bg-lake text-white font-medium text-sm inline-flex items-center hover:bg-lake-dark transition-colors active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2"
              >
                登录
              </Link>
            )}

            <button
              onClick={onMenuClick}
              className="md:hidden w-10 h-10 rounded-[10px] bg-paper border border-line/80 grid place-items-center hover:bg-paper-hover transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2"
              aria-label="打开菜单"
              aria-haspopup="menu"
            >
              <Menu size={18} className="text-ink" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
