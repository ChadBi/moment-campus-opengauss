import { api } from './api';

interface LoginRequest {
  email: string;
  password: string;
}

interface RegisterRequest {
  email: string;
  nickname: string;
  password: string;
  // 2026-08-01 起：注册时用户自由选择初始加入的学校（注册页下拉选择）
  school_id: number;
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
