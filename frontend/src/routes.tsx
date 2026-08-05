import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { MainLayout } from './components/layout';
import { Loading } from './components/ui';
import { useAuthStore } from './store/useAuthStore';
import { useSchoolSync } from './hooks/useSchoolSync';

// ACC-01.1: 保留当前路径作为登录后回跳目标
function buildLoginRedirect(): string {
  const loc = window.location;
  const params = new URLSearchParams(loc.search);
  params.set('redirect', loc.pathname + loc.search);
  return `/login?${params.toString()}`;
}

// Lazy load pages
const loadHomePage = () => import('./pages/HomePage');
const loadMapPage = () => import('./pages/MapPage');
const loadSearchPage = () => import('./pages/SearchPage');
const loadPostDetailPage = () => import('./pages/PostDetailPage');
const loadPublishPage = () => import('./pages/PublishPage');
const loadProfilePage = () => import('./pages/ProfilePage');
const loadNotificationsPage = () => import('./pages/NotificationsPage');
const loadLoginPage = () => import('./pages/LoginPage');
const loadRegisterPage = () => import('./pages/RegisterPage');
const loadForgotPasswordPage = () => import('./pages/ForgotPasswordPage');
const loadNotFoundPage = () => import('./pages/NotFoundPage');
// TOPIC-01.1: 用户端专题
const loadTopicListPage = () => import('./pages/TopicListPage');
const loadTopicDetailPage = () => import('./pages/TopicDetailPage');
// A-05: 校园地点页（附近 + 设施评分评价）
const loadLocationPage = () => import('./pages/LocationPage');
// B-01: 校园身份认证验证链接落地页
const loadVerifyLinkPage = () => import('./pages/VerifyLinkPage');

const HomePage = lazy(loadHomePage);
const MapPage = lazy(loadMapPage);
const SearchPage = lazy(loadSearchPage);
const PostDetailPage = lazy(loadPostDetailPage);
const PublishPage = lazy(loadPublishPage);
const ProfilePage = lazy(loadProfilePage);
const NotificationsPage = lazy(loadNotificationsPage);
const LoginPage = lazy(loadLoginPage);
const RegisterPage = lazy(loadRegisterPage);
const ForgotPasswordPage = lazy(loadForgotPasswordPage);
const NotFoundPage = lazy(loadNotFoundPage);
const TopicListPage = lazy(loadTopicListPage);
const TopicDetailPage = lazy(loadTopicDetailPage);
const LocationPage = lazy(loadLocationPage);
const VerifyLinkPage = lazy(loadVerifyLinkPage);

// Admin pages
const loadAdminDashboard = () => import('./pages/admin/AdminDashboard');
const loadAdminHomePage = () => import('./pages/admin/AdminHomePage');
const loadAdminReviewPage = () => import('./pages/admin/AdminReviewPage');
const loadAdminReportsPage = () => import('./pages/admin/AdminReportsPage');
const loadAdminUsersPage = () => import('./pages/admin/AdminUsersPage');
const loadAdminCategoriesPage = () => import('./pages/admin/AdminCategoriesPage');
const loadAdminLocationsPage = () => import('./pages/admin/AdminLocationsPage');
const loadAdminTopicsPage = () => import('./pages/admin/AdminTopicsPage');
const loadAdminJobsPage = () => import('./pages/admin/AdminJobsPage');
const loadAdminLogsPage = () => import('./pages/admin/AdminLogsPage');
const loadAdminSettingsPage = () => import('./pages/admin/AdminSettingsPage');
const loadUsagePage = () => import('./pages/admin/UsagePage');
// ANA-02.2: 校级数据分析页（admin 及以上）
const loadAnalyticsPage = () => import('./pages/admin/AnalyticsPage');
const loadPlatformOverviewPage = () => import('./pages/admin/PlatformOverviewPage');
const loadPlatformPlansPage = () => import('./pages/admin/PlatformPlansPage');
const loadPlatformSchoolsPage = () => import('./pages/admin/PlatformSchoolsPage');
const loadSchoolImportPage = () => import('./pages/admin/SchoolImportPage');
const loadActivationFunnelPage = () => import('./pages/admin/ActivationFunnelPage');

const AdminDashboard = lazy(loadAdminDashboard);
const AdminHomePage = lazy(loadAdminHomePage);
const AdminReviewPage = lazy(loadAdminReviewPage);
const AdminReportsPage = lazy(loadAdminReportsPage);
const AdminUsersPage = lazy(loadAdminUsersPage);
const AdminCategoriesPage = lazy(loadAdminCategoriesPage);
const AdminLocationsPage = lazy(loadAdminLocationsPage);
const AdminTopicsPage = lazy(loadAdminTopicsPage);
const AdminJobsPage = lazy(loadAdminJobsPage);
const AdminLogsPage = lazy(loadAdminLogsPage);
const AdminSettingsPage = lazy(loadAdminSettingsPage);
const UsagePage = lazy(loadUsagePage);
const AnalyticsPage = lazy(loadAnalyticsPage);
const PlatformOverviewPage = lazy(loadPlatformOverviewPage);
const PlatformPlansPage = lazy(loadPlatformPlansPage);
const PlatformSchoolsPage = lazy(loadPlatformSchoolsPage);
const SchoolImportPage = lazy(loadSchoolImportPage);
const ActivationFunnelPage = lazy(loadActivationFunnelPage);

const commonRouteLoaders = [
  loadHomePage,
  loadSearchPage,
  loadPostDetailPage,
  loadPublishPage,
  loadProfilePage,
  loadNotificationsPage,
];

const adminRouteLoaders = [
  loadAdminDashboard,
  loadAdminHomePage,
  loadAdminReviewPage,
  loadAdminReportsPage,
  loadAdminUsersPage,
  loadAdminCategoriesPage,
  loadAdminLocationsPage,
  loadAdminTopicsPage,
  loadAdminJobsPage,
  loadAdminLogsPage,
  loadAdminSettingsPage,
  loadUsagePage,
  loadAnalyticsPage,
];

const superAdminRouteLoaders = [
  loadPlatformOverviewPage,
  loadPlatformPlansPage,
  loadPlatformSchoolsPage,
  loadSchoolImportPage,
  loadActivationFunnelPage,
];

const prefetchRouteLoaders = (loaders: Array<() => Promise<unknown>>) => {
  loaders.forEach((loadPage) => {
    void loadPage();
  });
};

// Protected Route
const ProtectedRoute: React.FC<{ children: React.ReactNode; requireAdmin?: boolean; requireSuperAdmin?: boolean }> = ({ children, requireAdmin, requireSuperAdmin }) => {
  // 同时检查 isAuthenticated 和 accessToken，防止 zustand persist 残留状态
  // （isAuthenticated=true 但 accessToken 已过期/被清空时仍跳转登录）
  const { isAuthenticated, accessToken, user } = useAuthStore();

  // 增强检查：确保 accessToken 不为 null/undefined/空字符串
  const hasValidToken = !!accessToken && accessToken.trim().length > 0;

  if (!isAuthenticated || !hasValidToken) {
    // ACC-01.1: 记录回跳目标，登录后返回原页面
    return <Navigate to={buildLoginRedirect()} replace />;
  }

  if (requireAdmin && user?.role !== 'admin' && user?.role !== 'super_admin') {
    return <Navigate to="/" replace />;
  }

  if (requireSuperAdmin && user?.role !== 'super_admin') {
    return <Navigate to="/admin" replace />;
  }

  return <>{children}</>;
};

const RouteChunkPrefetcher: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const isSuperAdmin = user?.role === 'super_admin';

  useEffect(() => {
    const commonTimer = window.setTimeout(() => {
      prefetchRouteLoaders(commonRouteLoaders);
    }, 1200);
    const mapTimer = window.setTimeout(() => {
      prefetchRouteLoaders([loadMapPage]);
    }, 3500);

    return () => {
      window.clearTimeout(commonTimer);
      window.clearTimeout(mapTimer);
    };
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }

    const adminTimer = window.setTimeout(() => {
      prefetchRouteLoaders(adminRouteLoaders);
    }, 1800);

    return () => window.clearTimeout(adminTimer);
  }, [isAdmin]);

  useEffect(() => {
    if (!isSuperAdmin) {
      return;
    }

    const superAdminTimer = window.setTimeout(() => {
      prefetchRouteLoaders(superAdminRouteLoaders);
    }, 2400);

    return () => window.clearTimeout(superAdminTimer);
  }, [isSuperAdmin]);

  return null;
};

const AnimatedRoutes: React.FC = () => {
  const location = useLocation();
  return (
    <Suspense fallback={<Loading fullScreen />}>
      <Routes location={location}>
        {/* Public Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        {/* B-01: 校园身份认证验证链接落地页（无需登录） */}
        <Route path="/verify-campus" element={<VerifyLinkPage />} />

        {/* Protected Routes with MainLayout */}
        <Route element={<MainLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/posts/:id" element={<PostDetailPage />} />
          {/* TOPIC-01.1: 用户端专题（列表 + 详情，仅展示已发布） */}
          <Route path="/topics" element={<TopicListPage />} />
          <Route path="/topics/:id" element={<TopicDetailPage />} />
          {/* A-05: 校园地点页（附近 + 设施评分评价） */}
          <Route path="/locations" element={<LocationPage />} />

          {/* Protected Routes */}
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <NotificationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/publish"
            element={
              <ProtectedRoute>
                <PublishPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* Admin Routes (require admin role) */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute requireAdmin>
              <AdminDashboard />
            </ProtectedRoute>
          }
        >
          <Route index element={<AdminHomePage />} />
          <Route path="review" element={<AdminReviewPage />} />
          <Route path="governance" element={<Navigate to="/admin/reports" replace />} />
          <Route path="reports" element={<AdminReportsPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="categories" element={<AdminCategoriesPage />} />
          <Route path="tags" element={<Navigate to="/admin" replace />} />
          <Route path="locations" element={<AdminLocationsPage />} />
          {/* TOPIC-01.2: 专题管理（CRUD/排序/上下线/编排，仅 admin 及以上） */}
          <Route path="topics" element={<AdminTopicsPage />} />
          <Route path="jobs" element={<AdminJobsPage />} />
          <Route path="logs" element={<AdminLogsPage />} />
          <Route path="settings" element={<AdminSettingsPage />} />
          <Route path="usage" element={<UsagePage />} />
          {/* ANA-02.2: 校级数据分析（admin 及以上） */}
          <Route path="analytics" element={<AnalyticsPage />} />
          {/* super_admin 专属：平台首页/套餐/学校/导入/激活漏斗 */}
          {/* Bug#2 修复：/admin/platform 自动重定向到 /admin/platform/overview */}
          <Route path="platform" element={<Navigate to="/admin/platform/overview" replace />} />
          <Route
            path="platform/overview"
            element={
              <ProtectedRoute requireSuperAdmin>
                <PlatformOverviewPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="platform/plans"
            element={
              <ProtectedRoute requireSuperAdmin>
                <PlatformPlansPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="platform/schools"
            element={
              <ProtectedRoute requireSuperAdmin>
                <PlatformSchoolsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="import"
            element={
              <ProtectedRoute requireSuperAdmin>
                <SchoolImportPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="funnel"
            element={
              <ProtectedRoute requireSuperAdmin>
                <ActivationFunnelPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
};

const AppRoutes: React.FC = () => {
  return (
    <BrowserRouter>
      <RouteChunkPrefetcher />
      <SchoolAwareRoot />
      <AnimatedRoutes />
    </BrowserRouter>
  );
};

/**
 * TEN-03.2: 学校感知根组件
 *
 * 在 BrowserRouter 内层调用 useSchoolSync，启用：
 * - 学校目录 / memberships 自动加载
 * - URL ?school=code 深链接解析
 * - 切换学校时取消进行中请求 + 清除旧缓存
 */
const SchoolAwareRoot: React.FC = () => {
  useSchoolSync();
  return null;
};

export default AppRoutes;
