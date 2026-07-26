import React, { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import AppRoutes from './routes';
import { useUIStore } from './store/useUIStore';
import type { ToastType } from './store/useUIStore';
import { UpdatePrompt } from './components/UpdatePrompt';
import { InstallPrompt } from './components/InstallPrompt';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
    },
  },
});

const globalToastIcon: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle size={20} className="text-grass" />,
  error: <AlertCircle size={20} className="text-danger" />,
  warning: <AlertTriangle size={20} className="text-sun" />,
  info: <Info size={20} className="text-lamp" />,
};

// 全局 Toast：监听 useUIStore.toast，放顶部（页面局部 Toast 在底部，错开避免重叠）
const GlobalToast: React.FC = () => {
  const toast = useUIStore((s) => s.toast);
  const clearToast = useUIStore((s) => s.clearToast);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(clearToast, 3000);
      return () => clearTimeout(timer);
    }
  }, [toast, clearToast]);

  if (!toast) return null;

  return (
    <div
      key={toast.id}
      className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-3 px-5 py-3 rounded-md shadow-lg max-w-[90vw] bg-ink text-white border border-white/10 route-fade-enter"
    >
      {globalToastIcon[toast.type]}
      <p className="text-sm text-paper flex-1 font-sans">{toast.message}</p>
      <button
        onClick={clearToast}
        className="p-1 rounded text-paper/60 hover:text-paper hover:bg-white/10 transition-colors"
        aria-label="关闭"
      >
        <X size={16} />
      </button>
    </div>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppRoutes />
      <GlobalToast />
      <UpdatePrompt />
      <InstallPrompt />
    </QueryClientProvider>
  </React.StrictMode>
);
