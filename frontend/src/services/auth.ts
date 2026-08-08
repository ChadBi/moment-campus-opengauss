import { api } from './api';

export interface UserAuth {
  id: number;
  phone?: string | null;
  education_email?: string | null;
  has_password: boolean;
  nickname: string;
  avatar_url?: string;
  school_id: number;
  registration_school_id?: number | null;
  role: string;
  bio?: string;
  is_active: boolean;
  created_at: string;
  onboarding_completed?: boolean;
  campus_verified?: boolean;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserAuth;
}

export interface SmsResponse {
  message: string;
  out_id?: string;
  code?: string;
}

export const authApi = {
  sendSms: async (phone: string, purpose: 'register' | 'login' | 'set_password' | 'education_unbind'): Promise<SmsResponse> => {
    const response = await api.post('/auth/sms/send', { phone, purpose });
    return response.data;
  },

  login: async (data: { phone: string; password?: string; sms_code?: string }): Promise<AuthResponse> => {
    const response = await api.post('/auth/login', data);
    return response.data;
  },

  register: async (data: {
    phone: string;
    sms_code: string;
    password: string;
    password_confirm: string;
    school_id: number;
  }): Promise<AuthResponse> => {
    const response = await api.post('/auth/register', data);
    return response.data;
  },

  setPassword: async (password: string, passwordConfirm: string): Promise<void> => {
    await api.post('/auth/password/set', {
      password,
      password_confirm: passwordConfirm,
    });
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },

  refresh: async (refreshToken: string): Promise<{ access_token: string; refresh_token: string }> => {
    const response = await api.post('/auth/refresh', { refresh_token: refreshToken });
    return response.data;
  },
};
