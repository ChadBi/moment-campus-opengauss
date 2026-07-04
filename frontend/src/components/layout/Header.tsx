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
    <header className="sticky top-0 z-30 bg-mist/80 backdrop-blur-lg border-b border-line/60">
      <div className="max-w-[1680px] mx-auto px-3 md:px-6 py-3 md:py-4">
        <div className="flex items-center justify-between gap-3 md:gap-5">
          {/* 品牌文字：楷体"此刻校园" + 副标题 */}
          <div className="flex items-baseline gap-2.5 whitespace-nowrap">
            <h1 className="font-display font-extrabold text-[22px] md:text-[28px] tracking-[0.08em] text-lake leading-none">
              此刻校园
            </h1>
            <small className="hidden lg:inline text-ink-muted text-xs">
              把会消失的校园经验留下来
            </small>
          </div>

          {/* 右侧操作区 */}
          <div className="flex justify-end items-center gap-1.5 md:gap-2">
            {/* 通知按钮（图标按钮 44x44 圆角14px） */}
            {user && (
              <Link
                to="/notifications"
                className="relative w-11 h-11 rounded-[14px] bg-white/[0.74] border border-line grid place-items-center lift-on-hover"
                aria-label="通知"
              >
                <Bell size={19} className="text-ink-sub" />
                {notificationCount > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 bg-danger text-white text-[10px] font-bold rounded-full grid place-items-center">
                    {notificationCount > 99 ? '99+' : notificationCount}
                  </span>
                )}
              </Link>
            )}

            {/* 发布按钮：灯笼橙 */}
            <Link
              to="/publish"
              className="h-11 px-4 rounded-[14px] bg-lamp text-white font-bold inline-flex items-center gap-2 shadow-lamp lift-on-hover"
            >
              <Plus size={19} />
              <span className="hidden md:inline">发布此刻</span>
            </Link>

            {/* 用户头像 / 登录按钮 */}
            {user ? (
              <Link
                to="/profile"
                className="w-11 h-11 rounded-[14px] overflow-hidden border border-line bg-white/[0.74] grid place-items-center lift-on-hover"
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
                className="h-11 px-4 rounded-[14px] bg-lake text-white font-bold inline-flex items-center lift-on-hover"
              >
                登录
              </Link>
            )}

            {/* 移动端菜单按钮 */}
            <button
              onClick={onMenuClick}
              className="md:hidden w-11 h-11 rounded-[14px] bg-white/[0.74] border border-line grid place-items-center"
              aria-label="打开菜单"
            >
              <Menu size={20} className="text-ink" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
