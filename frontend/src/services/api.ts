import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';
import { useCampusStore } from '../store/useCampusStore';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// 不需要 X-School-Code 头的路径（公开学校目录、登录、刷新等）
// ACC-01.2: /auth/register 不再 bypass，需要注入 X-School-Code 以支持动态选校
const SCHOOL_CODE_BYPASS_PATHS = [
  '/schools',
  '/auth/login',
  '/auth/refresh',
  '/auth/logout',
  '/auth/forgot-password',
  '/auth/reset-password',
];

function shouldBypassSchoolCode(url: string | undefined): boolean {
  if (!url) return false;
  // url 可能是相对路径（如 '/schools/current'）或绝对 URL
  const path = url.startsWith('http') ? new URL(url).pathname : url;
  // 精确匹配 /schools（公开目录）但放行 /schools/current /schools/{code}/join
  // 公开目录调用方法为 GET /schools，简化处理：以 '/schools' 起始且长度等于 '/schools' 的视为公开目录
  if (path === '/schools' || path === '/schools/') return true;
  return SCHOOL_CODE_BYPASS_PATHS.some((p) => path === p || path === p + '/');
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 Token + X-School-Code
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // TEN-03.2：注入当前学校 code 到 X-School-Code 头
    // 公开学校目录/认证接口跳过（避免循环依赖：拉学校目录前还没有 currentSchoolCode）
    if (!shouldBypassSchoolCode(config.url)) {
      const schoolCode = useCampusStore.getState().currentSchoolCode;
      if (schoolCode) {
        config.headers['X-School-Code'] = schoolCode;
      }
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
        // 无 refreshToken：token 过期或未登录，清登录态 + 提示
        // logout() 后：受保护页面的 ProtectedRoute 会自动跳转 /login；
        // 公开页面的操作则只显示 Toast，不跳转（符合"操作只提醒不跳转"原则）
        useAuthStore.getState().logout();
        useUIStore.getState().showToast('请先登录', 'warning');
      }
    }

    return Promise.reject(error);
  }
);
