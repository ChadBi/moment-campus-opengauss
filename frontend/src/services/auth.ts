import { api } from './api';

interface LoginRequest {
  email: string;
  password: string;
}

interface RegisterRequest {
  email: string;
  nickname: string;
  password: string;
  // ACC-01.2: school_id 改为可选，优先通过 X-School-Code 头注入
  school_id?: number;
  // ACC-01.2: 邀请码可选；前端通过 URL ?invite=xxx 写入短期上下文后回传
  // 后端校验有效性（存在/未过期/未使用/邮箱匹配/学校匹配）并消费，同时创建 membership
  invite_code?: string;
}

// ACC-01.3: 找回密码响应类型
interface ForgotPasswordResponse {
  message: string;
  reset_token?: string; // 仅本地开发环境返回
}

interface ResetPasswordResponse {
  message: string;
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: {
    id: number;
    email: string;
    nickname: string;
    avatar_url?: string;
    school_id: number;
    role: string;
    bio?: string;
  };
}

// ============================================================
// ACC-01.2: 邀请码短期上下文工具
// ============================================================
// 设计：URL ?invite=xxx 携带邀请码进入站点时，写入 localStorage 短期上下文；
// 后续登录或注册时自动消费并清除；24 小时未消费自动过期清理。
const INVITE_CONTEXT_KEY = 'invite_context';
const INVITE_CONTEXT_TTL_MS = 24 * 60 * 60 * 1000; // 24 小时

interface InviteContextPayload {
  code: string;
  saved_at: number;
}

/** 写入邀请码到短期上下文（来自 URL ?invite=xxx） */
export const setInviteContext = (code: string): void => {
  if (!code) return;
  try {
    const payload: InviteContextPayload = { code, saved_at: Date.now() };
    localStorage.setItem(INVITE_CONTEXT_KEY, JSON.stringify(payload));
  } catch {
    // localStorage 不可用时静默失败，不阻塞主流程
  }
};

/** 读取短期上下文中的邀请码；过期或不存在返回 null 并清理 */
export const getInviteContext = (): string | null => {
  try {
    const raw = localStorage.getItem(INVITE_CONTEXT_KEY);
    if (!raw) return null;
    const payload = JSON.parse(raw) as InviteContextPayload;
    if (!payload || typeof payload.code !== 'string' || typeof payload.saved_at !== 'number') {
      localStorage.removeItem(INVITE_CONTEXT_KEY);
      return null;
    }
    // 24 小时 TTL
    if (Date.now() - payload.saved_at > INVITE_CONTEXT_TTL_MS) {
      localStorage.removeItem(INVITE_CONTEXT_KEY);
      return null;
    }
    return payload.code;
  } catch {
    return null;
  }
};

/** 清除短期上下文中的邀请码（消费成功或失败后调用） */
export const clearInviteContext = (): void => {
  try {
    localStorage.removeItem(INVITE_CONTEXT_KEY);
  } catch {
    // 静默
  }
};

export const authApi = {
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await api.post('/auth/login', data);
    return response.data;
  },

  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  refresh: async (refreshToken: string): Promise<{ access_token: string; refresh_token: string }> => {
    const response = await api.post('/auth/refresh', { refresh_token: refreshToken });
    return response.data;
  },

  // ACC-01.3: 找回密码
  forgotPassword: async (email: string): Promise<ForgotPasswordResponse> => {
    const response = await api.post('/auth/forgot-password', { email });
    return response.data;
  },

  resetPassword: async (token: string, newPassword: string): Promise<ResetPasswordResponse> => {
    const response = await api.post('/auth/reset-password', {
      token,
      new_password: newPassword,
    });
    return response.data;
  },
};
