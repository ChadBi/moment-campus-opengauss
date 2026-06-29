import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ToastProps {
  message: string;
  type?: ToastType;
  duration?: number;
  onClose: () => void;
}

const iconMap: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle size={20} className="text-grass" />,
  error: <AlertCircle size={20} className="text-danger" />,
  warning: <AlertTriangle size={20} className="text-sun" />,
  info: <Info size={20} className="text-lamp" />,
};

export const Toast: React.FC<ToastProps> = ({
  message,
  type = 'info',
  duration = 3000,
  onClose,
}) => {
  useEffect(() => {
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  return (
    <div
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 rounded-md shadow-lg max-w-[90vw] animate-fade-in bg-ink text-white border border-white/10`}
    >
      {iconMap[type]}
      <p className="text-sm text-paper flex-1 font-sans">{message}</p>
      <button
        onClick={onClose}
        className="p-1 rounded text-paper/60 hover:text-paper hover:bg-white/10 transition-colors"
        aria-label="关闭"
      >
        <X size={16} />
      </button>
    </div>
  );
};
