import React from 'react';
import { Link } from 'react-router-dom';
import { Bell, Menu, Plus } from 'lucide-react';
import { Avatar } from '../ui';

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
  return (
    <header className="sticky top-0 z-30 bg-paper/95 backdrop-blur-sm border-b border-line/60">
      <div className="max-w-[1680px] mx-auto px-3 md:px-6 py-2.5 md:py-3">
        <div className="flex items-center justify-between gap-3 md:gap-5">
          <div className="flex items-baseline gap-2.5 whitespace-nowrap">
            <h1 className="font-display font-bold text-[20px] md:text-[24px] tracking-wide text-lake leading-none">
              此刻校园
            </h1>
            <small className="hidden lg:inline text-ink-muted text-xs">
              把会消失的校园经验留下来
            </small>
          </div>

          <div className="flex justify-end items-center gap-1 md:gap-1.5">
            {user && (
              <Link
                to="/notifications"
                className="relative w-10 h-10 rounded-[10px] bg-paper border border-line/80 grid place-items-center hover:bg-paper-hover transition-colors"
                aria-label="通知"
              >
                <Bell size={17} className="text-ink-sub" />
                {notificationCount > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[17px] h-[17px] px-1 bg-danger text-white text-[10px] font-bold rounded-full grid place-items-center">
                    {notificationCount > 99 ? '99+' : notificationCount}
                  </span>
                )}
              </Link>
            )}

            <Link
              to="/publish"
              className="h-10 px-4 rounded-[10px] bg-lamp text-white font-medium text-sm inline-flex items-center gap-1.5 shadow-lamp hover:bg-lamp-dark transition-colors active:scale-[0.98]"
            >
              <Plus size={17} />
              <span className="hidden md:inline">发布此刻</span>
            </Link>

            {user ? (
              <Link
                to="/profile"
                className="w-10 h-10 rounded-[10px] overflow-hidden border border-line/80 bg-paper grid place-items-center hover:bg-paper-hover transition-colors"
                aria-label={user.nickname}
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
                className="h-10 px-4 rounded-[10px] bg-lake text-white font-medium text-sm inline-flex items-center hover:bg-lake-dark transition-colors active:scale-[0.98]"
              >
                登录
              </Link>
            )}

            <button
              onClick={onMenuClick}
              className="md:hidden w-10 h-10 rounded-[10px] bg-paper border border-line/80 grid place-items-center hover:bg-paper-hover transition-colors"
              aria-label="打开菜单"
            >
              <Menu size={18} className="text-ink" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
