import React, { useState, useEffect } from 'react';
import { useNavigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { authApi } from '../../services/auth';
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
  ScrollText,
  ChevronRight,
  Gauge,
  Package,
  School,
  Upload,
  TrendingUp,
  MapPin,
  Wrench,
  Globe,
  BarChart3,
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
  /** 仅超级管理员可见 */
  superAdminOnly?: boolean;
}

const MENU_ITEMS: MenuItem[] = [
  { path: '/admin', label: '仪表盘', icon: LayoutDashboard, crumb: '仪表盘' },
  { path: '/admin/review', label: '内容审核', icon: FileText, crumb: '内容审核' },
  { path: '/admin/users', label: '用户管理', icon: Users, crumb: '用户管理' },
  { path: '/admin/reports', label: '举报管理', icon: Flag, crumb: '举报管理' },
  { path: '/admin/locations', label: '地点核验', icon: MapPin, crumb: '地点核验' },
  { path: '/admin/categories', label: '分类管理', icon: FolderTree, crumb: '分类管理' },
  { path: '/admin/jobs', label: '任务记录', icon: Wrench, crumb: '任务记录' },
  { path: '/admin/logs', label: '操作日志', icon: ScrollText, crumb: '操作日志' },
  { path: '/admin/usage', label: '用量与套餐', icon: Gauge, crumb: '用量与套餐' },
  // ANA-02.2: 校级数据分析（漏斗/留存/搜索/内容/治理 SLA/AI 用量/零结果洞察）
  { path: '/admin/analytics', label: '数据分析', icon: BarChart3, crumb: '数据分析' },
  { path: '/admin/settings', label: '系统设置', icon: Settings, crumb: '系统设置' },
  // super_admin 专属：平台运营
  { path: '/admin/platform/overview', label: '平台首页', icon: Globe, crumb: '平台首页', superAdminOnly: true },
  { path: '/admin/platform/plans', label: '平台套餐', icon: Package, crumb: '平台套餐', superAdminOnly: true },
  { path: '/admin/platform/schools', label: '学校管理', icon: School, crumb: '学校管理', superAdminOnly: true },
  { path: '/admin/import', label: '开通向导', icon: Upload, crumb: '开通向导', superAdminOnly: true },
  { path: '/admin/funnel', label: '激活漏斗', icon: TrendingUp, crumb: '激活漏斗', superAdminOnly: true },
];

const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!user || !isAdminRole(user.role)) {
      navigate('/login');
      return;
    }
    // super_admin 访问校级管理路径时，自动重定向到平台运营首页
    if (user.role === 'super_admin') {
      const isPlatformRoute = location.pathname.startsWith('/admin/platform') ||
        location.pathname === '/admin/import' ||
        location.pathname === '/admin/funnel';
      if (!isPlatformRoute) {
        navigate('/admin/platform/overview', { replace: true });
      }
    }
  }, [user, navigate, location.pathname]);

  // 路由变化时关闭移动端侧边栏（UI 同步需求，需在 effect 中 setState）
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSidebarOpen(false);
  }, [location.pathname]);

  // P2-005: 登出先调后端 /auth/logout（让后端有机会失效 refresh token / 写黑名单），
  // 再清本地 state；后端调用失败不阻塞前端登出
  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // 后端登出失败不阻塞本地登出
    }
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

  const isSuperAdmin = user.role === 'super_admin';
  // 按角色过滤菜单项：
  // - super_admin：仅显示平台运营菜单
  // - admin：仅显示校级管理菜单
  const adminItems = isSuperAdmin
    ? []
    : MENU_ITEMS.filter((item) => !item.superAdminOnly);
  const platformItems = isSuperAdmin
    ? MENU_ITEMS.filter((item) => item.superAdminOnly)
    : [];

  return (
    <div className="min-h-screen bg-mist">
      {/* UX-01.7: 无障碍跳转链接（键盘 Tab 聚焦时显示） */}
      <a
        href="#admin-main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[200] focus:px-4 focus:py-2 focus:bg-lake focus:text-white focus:rounded-[8px] focus:shadow-lamp focus:outline-none"
      >
        跳转到后台主内容
      </a>

      {/* ============ 移动端顶栏（含汉堡菜单） ============ */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-paper border-b border-line px-4 py-3 flex items-center justify-between">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 hover:bg-mist/70 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-lake"
          aria-label="切换菜单"
          aria-expanded={sidebarOpen}
          aria-controls="admin-sidebar"
        >
          <Menu size={24} aria-hidden="true" />
        </button>
        <h1 className="text-base font-bold text-ink">
          {currentMenu?.label || '管理后台'}
        </h1>
        <div className="w-10" />
      </div>

      {/* ============ 侧边栏（纯浅色 bg-paper） ============ */}
      <aside
        id="admin-sidebar"
        className={`fixed top-0 left-0 z-40 h-screen w-64 bg-paper border-r border-line transition-transform lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="管理后台导航"
      >
        {/* 品牌区 */}
        <div className="flex items-center justify-between p-4 border-b border-line">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-lake grid place-items-center" aria-hidden="true">
              <span className="font-display font-bold text-paper text-sm">此</span>
            </div>
            <div>
              <h1 className="text-base font-bold text-ink leading-tight">管理后台</h1>
              <p className="text-xs text-ink-muted">此刻校园 · Admin</p>
            </div>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1.5 hover:bg-mist/70 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-lake"
            aria-label="关闭菜单"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {/* 导航菜单 */}
        <nav
          className="p-3 space-y-0.5 overflow-y-auto"
          style={{ maxHeight: 'calc(100vh - 220px)' }}
          aria-label="后台功能菜单"
        >
          {adminItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                aria-current={active ? 'page' : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-1 ${
                  active
                    ? 'bg-lake text-paper font-medium'
                    : 'text-ink-sub hover:bg-mist hover:text-ink'
                }`}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
          {platformItems.length > 0 && (
            <>
              <div className="pt-3 pb-1 px-3">
                <span className="text-[10px] font-semibold text-ink-muted uppercase tracking-wider">
                  平台运营
                </span>
              </div>
              {platformItems.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.path);
                return (
                  <button
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    aria-current={active ? 'page' : undefined}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-1 ${
                      active
                        ? 'bg-lamp text-paper font-medium'
                        : 'text-ink-sub hover:bg-mist hover:text-ink'
                    }`}
                  >
                    <Icon size={18} aria-hidden="true" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </>
          )}
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
            <LogOut size={14} className="mr-1.5" aria-hidden="true" />
            退出登录
          </Button>
        </div>
      </aside>

      {/* 移动端遮罩 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ============ 主内容区 ============ */}
      <main
        id="admin-main-content"
        className="lg:ml-64 pt-14 lg:pt-0 min-h-screen flex flex-col"
        tabIndex={-1}
      >
        {/* 桌面端顶栏：面包屑 */}
        <header className="hidden lg:flex items-center justify-between px-6 py-3 bg-paper border-b border-line sticky top-0 z-20">
          <nav className="flex items-center gap-2 text-sm" aria-label="面包屑">
            <span className="text-ink-muted">管理后台</span>
            <ChevronRight size={14} className="text-ink-muted" aria-hidden="true" />
            <span className="text-ink font-medium" aria-current="page">
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
