import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';
import { useCampusStore } from '../store/useCampusStore';
import { logger } from '../utils/logger';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// 不需要 X-School-Code 头的路径（公开学校目录、登录、刷新等）
// ACC-01.2: /auth/register 不再 bypass，需要注入 X-School-Code 以支持动态选校
const SCHOOL_CODE_BYPASS_PATHS = [
  '/schools',
  '/auth/login',
  '/auth/sms/send',
  '/auth/refresh',
  '/auth/logout',
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
  timeout: 15000,
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
//
// P2-006: 并发 401 加锁 — 多个请求同时收到 401 时，只发起 1 次 /auth/refresh，
// 其余请求等待同一个 promise 完成后复用结果，避免并发刷新导致 refresh_token 被多次消费
// （后端 refresh 接口会签发新 refresh_token 并使旧的失效，并发刷新会导致后续请求拿到已失效 token）
let refreshPromise: Promise<string> | null = null;

// 网络错误/5xx 自动重试（仅 GET 请求，最多重试 2 次，指数退避）
const RETRY_MAX = 2;
const RETRY_BASE_DELAY = 800;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // GET 请求网络错误或 5xx 自动重试（在 401 处理之前）
    if (originalRequest) {
      const isGetRequest = (originalRequest.method || 'get').toLowerCase() === 'get';
      const isNetworkError = !error.response; // 无 response = 网络层错误（超时/DNS/连接断开）
      const isServerError = error.response?.status >= 500 && error.response?.status < 600;
      const retryCount = (originalRequest as any)._retryCount ?? 0;

      if (isGetRequest && (isNetworkError || isServerError) && retryCount < RETRY_MAX) {
        (originalRequest as any)._retryCount = retryCount + 1;
        const delay = RETRY_BASE_DELAY * (retryCount + 1); // 800ms, 1600ms
        logger.warn(`请求失败(${error.code || error.response?.status})，${delay}ms 后第${retryCount + 1}次重试: ${originalRequest.url}`);
        await new Promise((resolve) => setTimeout(resolve, delay));
        return api(originalRequest);
      }
    }

    // 401 错误：尝试刷新 Token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = useAuthStore.getState().refreshToken;
      if (refreshToken) {
        // P2-006: 若已有 refresh 进行中，复用其 promise；否则发起新的 refresh
        if (!refreshPromise) {
          refreshPromise = (async () => {
            const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
              refresh_token: refreshToken,
            });
            const { access_token, refresh_token: new_refresh_token } = response.data;
            const user = useAuthStore.getState().user;
            if (user) {
              useAuthStore.getState().setAuth(user, access_token, new_refresh_token);
            }
            return access_token;
          })().finally(() => {
            // 无论成功失败，清空 promise，让后续 401 可再次触发刷新
            refreshPromise = null;
          });
        } else {
          logger.debug('并发 401 复用 refresh promise');
        }

        try {
          const access_token = await refreshPromise;
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
