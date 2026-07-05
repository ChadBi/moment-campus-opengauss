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
  success: <CheckCircle size={18} className="text-grass" />,
  error: <AlertCircle size={18} className="text-danger" />,
  warning: <AlertTriangle size={18} className="text-[#b89230]" />,
  info: <Info size={18} className="text-lamp" />,
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
      className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-3 rounded-[10px] shadow-toast max-w-[90vw] animate-fade-in bg-paper border border-line/80`}
    >
      {iconMap[type]}
      <p className="text-sm text-ink flex-1 font-sans">{message}</p>
      <button
        onClick={onClose}
        className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-hover transition-colors"
        aria-label="关闭"
      >
        <X size={15} />
      </button>
    </div>
  );
};
