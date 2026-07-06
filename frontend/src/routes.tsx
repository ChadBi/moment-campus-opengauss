import React, { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { MainLayout } from './components/layout';
import { Loading } from './components/ui';
import { useAuthStore } from './store/useAuthStore';

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
const loadNotFoundPage = () => import('./pages/NotFoundPage');

const HomePage = lazy(loadHomePage);
const MapPage = lazy(loadMapPage);
const SearchPage = lazy(loadSearchPage);
const PostDetailPage = lazy(loadPostDetailPage);
const PublishPage = lazy(loadPublishPage);
const ProfilePage = lazy(loadProfilePage);
const NotificationsPage = lazy(loadNotificationsPage);
const LoginPage = lazy(loadLoginPage);
const RegisterPage = lazy(loadRegisterPage);
const NotFoundPage = lazy(loadNotFoundPage);

// Admin pages
const loadAdminDashboard = () => import('./pages/admin/AdminDashboard');
const loadAdminHomePage = () => import('./pages/admin/AdminHomePage');
const loadAdminReviewPage = () => import('./pages/admin/AdminReviewPage');
const loadAdminReportsPage = () => import('./pages/admin/AdminReportsPage');
const loadAdminUsersPage = () => import('./pages/admin/AdminUsersPage');
const loadAdminCategoriesPage = () => import('./pages/admin/AdminCategoriesPage');
const loadAdminLogsPage = () => import('./pages/admin/AdminLogsPage');
const loadAdminSettingsPage = () => import('./pages/admin/AdminSettingsPage');

const AdminDashboard = lazy(loadAdminDashboard);
const AdminHomePage = lazy(loadAdminHomePage);
const AdminReviewPage = lazy(loadAdminReviewPage);
const AdminReportsPage = lazy(loadAdminReportsPage);
const AdminUsersPage = lazy(loadAdminUsersPage);
const AdminCategoriesPage = lazy(loadAdminCategoriesPage);
const AdminLogsPage = lazy(loadAdminLogsPage);
const AdminSettingsPage = lazy(loadAdminSettingsPage);

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
  loadAdminLogsPage,
  loadAdminSettingsPage,
];

const prefetchRouteLoaders = (loaders: Array<() => Promise<unknown>>) => {
  loaders.forEach((loadPage) => {
    void loadPage();
  });
};

// Protected Route
const ProtectedRoute: React.FC<{ children: React.ReactNode; requireAdmin?: boolean }> = ({ children, requireAdmin }) => {
  // 同时检查 isAuthenticated 和 accessToken，防止 zustand persist 残留状态
  // （isAuthenticated=true 但 accessToken 已过期/被清空时仍跳转登录）
  const { isAuthenticated, accessToken, user } = useAuthStore();

  if (!isAuthenticated || !accessToken) {
    return <Navigate to="/login" replace />;
  }

  if (requireAdmin && user?.role !== 'admin' && user?.role !== 'super_admin') {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

const RouteChunkPrefetcher: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

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

        {/* Protected Routes with MainLayout */}
        <Route element={<MainLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/posts/:id" element={<PostDetailPage />} />

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
          <Route path="reports" element={<AdminReportsPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="categories" element={<AdminCategoriesPage />} />
          <Route path="tags" element={<Navigate to="/admin" replace />} />
          <Route path="logs" element={<AdminLogsPage />} />
          <Route path="settings" element={<AdminSettingsPage />} />
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
      <AnimatedRoutes />
    </BrowserRouter>
  );
};

export default AppRoutes;
