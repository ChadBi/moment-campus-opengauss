import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: number;
  email: string;
  nickname: string;
  avatar_url?: string;
  school_id: number;
  /** 注册时选择的学校；切换学校后保持不变 */
  registration_school_id?: number | null;
  role: string;
  bio?: string;
  // ACC-01.4: 首次使用引导标记（后端 User.onboarding_completed）
  onboarding_completed?: boolean;
  // B-01: 校园身份认证状态（后端 User.campus_verified）
  campus_verified?: boolean;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  /** ACC-01.4: 局部更新 user 字段（如 onboarding_completed），不替换整个 user 对象 */
  updateUser: (partial: Partial<User>) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      setAuth: (user, accessToken, refreshToken) =>
        set({
          user,
          accessToken,
          refreshToken,
          isAuthenticated: true,
        }),
      setUser: (user) => set({ user }),
      updateUser: (partial) =>
        set((state) => (state.user ? { user: { ...state.user, ...partial } } : {})),
      logout: () =>
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
