import React, { useState, useEffect } from 'react';
import { useNavigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { Avatar } from '../../components/ui/Avatar';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import {
  LayoutDashboard,
  FileText,
  Flag,
  Users,
  Settings,
  LogOut,
  Menu,
  X,
  FolderTree,
  Tags,
  ScrollText,
  ChevronRight,
} from 'lucide-react';

/** 管理员角色判断：admin 或 super_admin */
const isAdminRole = (role: string | undefined): boolean => {
  return role === 'admin' || role === 'super_admin';
};

/** 菜单项配置 */
interface MenuItem {
  path: string;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  /** 面包屑短名 */
  crumb: string;
}

const MENU_ITEMS: MenuItem[] = [
  { path: '/admin', label: '仪表盘', icon: LayoutDashboard, crumb: '仪表盘' },
  { path: '/admin/review', label: '内容审核', icon: FileText, crumb: '内容审核' },
  { path: '/admin/users', label: '用户管理', icon: Users, crumb: '用户管理' },
  { path: '/admin/reports', label: '举报管理', icon: Flag, crumb: '举报管理' },
  { path: '/admin/categories', label: '分类管理', icon: FolderTree, crumb: '分类管理' },
  { path: '/admin/tags', label: '标签管理', icon: Tags, crumb: '标签管理' },
  { path: '/admin/logs', label: '操作日志', icon: ScrollText, crumb: '操作日志' },
  { path: '/admin/settings', label: '系统设置', icon: Settings, crumb: '系统设置' },
];

const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!user || !isAdminRole(user.role)) {
      navigate('/login');
    }
  }, [user, navigate]);

  // 路由变化时关闭移动端侧边栏
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path: string) => {
    if (path === '/admin') {
      return location.pathname === '/admin';
    }
    return location.pathname.startsWith(path);
  };

  /** 获取当前菜单项（用于顶栏标题） */
  const currentMenu = MENU_ITEMS.find((item) => isActive(item.path));

  if (!user || !isAdminRole(user.role)) {
    return null;
  }

  return (
    <div className="min-h-screen bg-mist">
      {/* ============ 移动端顶栏（含汉堡菜单） ============ */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-paper border-b border-line px-4 py-3 flex items-center justify-between">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 hover:bg-mist/70 rounded-lg"
          aria-label="切换菜单"
        >
          <Menu size={24} />
        </button>
        <h1 className="text-base font-bold text-ink">
          {currentMenu?.label || '管理后台'}
        </h1>
        <div className="w-10" />
      </div>

      {/* ============ 侧边栏（纯浅色 bg-paper） ============ */}
      <aside
        className={`fixed top-0 left-0 z-40 h-screen w-64 bg-paper border-r border-line transition-transform lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* 品牌区 */}
        <div className="flex items-center justify-between p-4 border-b border-line">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-lake grid place-items-center">
              <span className="font-display font-bold text-paper text-sm">此</span>
            </div>
            <div>
              <h1 className="text-base font-bold text-ink leading-tight">管理后台</h1>
              <p className="text-xs text-ink-muted">此刻校园 · Admin</p>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1.5 hover:bg-mist/70 rounded-md"
            aria-label="关闭菜单"
          >
            <X size={18} />
          </button>
        </div>

        {/* 导航菜单 */}
        <nav className="p-3 space-y-0.5 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 220px)' }}>
          {MENU_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                  active
                    ? 'bg-lake text-paper font-medium'
                    : 'text-ink-sub hover:bg-mist hover:text-ink'
                }`}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* 底部用户区 */}
        <div className="absolute bottom-0 left-0 right-0 p-3 border-t border-line bg-paper">
          <div className="flex items-center gap-2.5 mb-2.5">
            <Avatar
              src={user.avatar_url}
              fallback={user.nickname?.[0] || 'A'}
              size="sm"
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-ink truncate">
                {user.nickname}
              </p>
              <Badge variant={user.role === 'super_admin' ? 'warning' : 'info'} className="text-[10px] mt-0.5">
                {user.role === 'super_admin' ? '超级管理员' : '管理员'}
              </Badge>
            </div>
          </div>
          <Button
            variant="text"
            size="sm"
            className="w-full text-ink-muted hover:text-danger"
            onClick={handleLogout}
          >
            <LogOut size={14} className="mr-1.5" />
            退出登录
          </Button>
        </div>
      </aside>

      {/* 移动端遮罩 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ============ 主内容区 ============ */}
      <main className="lg:ml-64 pt-14 lg:pt-0 min-h-screen flex flex-col">
        {/* 桌面端顶栏：面包屑 */}
        <header className="hidden lg:flex items-center justify-between px-6 py-3 bg-paper border-b border-line sticky top-0 z-20">
          <nav className="flex items-center gap-2 text-sm">
            <span className="text-ink-muted">管理后台</span>
            <ChevronRight size={14} className="text-ink-muted" />
            <span className="text-ink font-medium">
              {currentMenu?.crumb || '仪表盘'}
            </span>
          </nav>
          <div className="flex items-center gap-3">
            <span className="text-sm text-ink-sub">{user.nickname}</span>
            <Avatar
              src={user.avatar_url}
              fallback={user.nickname?.[0] || 'A'}
              size="sm"
            />
          </div>
        </header>

        {/* 页面内容 */}
        <div className="flex-1 p-4 lg:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default AdminDashboard;
