import React from 'react';
import { Loader2 } from 'lucide-react';

type ButtonVariant = 'primary' | 'secondary' | 'text' | 'danger';
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
    'bg-lamp text-white shadow-lamp hover:-translate-y-0.5 hover:bg-lamp-dark active:translate-y-0 active:bg-lamp-dark',
  secondary:
    'bg-mist text-lake hover:-translate-y-0.5 hover:bg-line active:translate-y-0',
  text:
    'bg-transparent text-lake hover:bg-mist/60 active:bg-mist/80',
  danger:
    'bg-danger text-white shadow-sm hover:-translate-y-0.5 hover:bg-danger/90 active:translate-y-0',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'h-9 px-4 text-xs gap-1.5',
  md: 'h-11 px-5 text-sm gap-2',
  lg: 'h-[52px] px-6 text-base gap-2.5',
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
    'inline-flex items-center justify-center rounded-md font-medium font-sans transition-[transform,background-color,box-shadow,border-color] duration-[180ms] ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-lamp/40';
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
        <Loader2 className="animate-spin" size={size === 'sm' ? 14 : size === 'md' ? 16 : 20} />
      ) : icon ? (
        <span className="flex-shrink-0">{icon}</span>
      ) : null}
      <span>{children}</span>
    </button>
  );
};
