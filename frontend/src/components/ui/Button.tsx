import React from 'react';
import { Loader2 } from 'lucide-react';

type ButtonVariant = 'primary' | 'secondary' | 'text' | 'danger' | 'success' | 'info';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    'bg-lamp text-white shadow-lamp hover:bg-lamp-dark active:scale-[0.98] active:bg-lamp-dark',
  secondary:
    'bg-paper-hover text-lake hover:bg-line active:scale-[0.98]',
  text:
    'bg-transparent text-ink-sub hover:bg-paper-hover hover:text-ink active:bg-paper-hover/80',
  danger:
    'bg-danger text-white shadow-sm hover:bg-danger/90 active:scale-[0.98]',
  success:
    'bg-grass text-white shadow-sm hover:bg-grass/90 active:scale-[0.98]',
  info:
    'bg-lake text-white shadow-sm hover:bg-lake/90 active:scale-[0.98]',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'h-9 px-4 text-xs gap-1.5 rounded-[10px]',
  md: 'h-10 px-5 text-sm gap-2 rounded-[10px]',
  lg: 'h-12 px-6 text-base gap-2.5 rounded-[10px]',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center font-medium font-sans transition-[transform,background-color,box-shadow,border-color] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-lamp/40';
  const variantStyle = variantStyles[variant];
  const sizeStyle = sizeStyles[size];
  const disabledStyle = (disabled || loading)
    ? 'opacity-50 cursor-not-allowed pointer-events-none'
    : '';

  return (
    <button
      className={`${baseStyles} ${variantStyle} ${sizeStyle} ${disabledStyle} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="animate-spin" size={size === 'sm' ? 14 : size === 'md' ? 16 : 18} />
      ) : icon ? (
        <span className="flex-shrink-0">{icon}</span>
      ) : null}
      <span>{children}</span>
    </button>
  );
};
