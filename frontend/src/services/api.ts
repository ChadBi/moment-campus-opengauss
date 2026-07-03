import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 Token
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：处理错误和 Token 刷新
// 设计原则：操作类请求遇到 401 时只提醒"请登录"，不跳转页面（保留用户当前浏览上下文）。
// 页面级跳转由 ProtectedRoute 在路由层处理，这里只负责操作层提示。
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 401 错误：尝试刷新 Token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = useAuthStore.getState().refreshToken;
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token } = response.data;
          const user = useAuthStore.getState().user;
          if (user) {
            useAuthStore.getState().setAuth(user, access_token, refresh_token);
          }

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          // refresh 失败：清登录态 + 全局提示，不硬跳转
          useAuthStore.getState().logout();
          useUIStore.getState().showToast('登录已过期，请重新登录', 'warning');
          return Promise.reject(refreshError);
        }
      } else {
        // 无 refreshToken：未登录用户尝试需登录操作，只提示不跳转
        useUIStore.getState().showToast('请先登录', 'warning');
      }
    }

    return Promise.reject(error);
  }
);
