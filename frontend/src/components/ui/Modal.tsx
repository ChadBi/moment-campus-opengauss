import React, { useEffect } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}

const sizeStyles: Record<NonNullable<ModalProps['size']>, string> = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-2xl',
};

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
}) => {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in">
      <div
        className="absolute inset-0 bg-[rgba(21,38,41,0.45)]"
        onClick={onClose}
      />
      <div
        className={`relative bg-paper rounded-[16px] shadow-modal w-full ${sizeStyles[size]} max-h-[90vh] overflow-hidden flex flex-col animate-modal-in border border-line/50`}
      >
        {title && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-ink-divider">
            <h2 className="text-lg font-bold text-ink font-display tracking-wide">{title}</h2>
            <button
              onClick={onClose}
              className="p-1.5 rounded-[10px] text-ink-muted hover:bg-paper-hover hover:text-ink transition-colors"
              aria-label="关闭"
            >
              <X size={18} />
            </button>
          </div>
        )}
        <div className="overflow-y-auto flex-1 px-6 py-5">
          {children}
        </div>
      </div>
    </div>
  );
};
