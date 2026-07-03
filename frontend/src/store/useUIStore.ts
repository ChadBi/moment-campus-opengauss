import { create } from 'zustand';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

interface UIState {
  sidebarOpen: boolean;
  toast: ToastItem | null;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  showToast: (message: string, type?: ToastType) => void;
  clearToast: () => void;
}

// 全局 toast 计数器，确保每次 showToast 生成唯一 id 触发重渲染
let _toastId = 0;

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: false,
  toast: null,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  showToast: (message, type = 'info') =>
    set({ toast: { id: ++_toastId, message, type } }),
  clearToast: () => set({ toast: null }),
}));
