import React from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-paper-hover text-ink-sub',
  success: 'bg-grass/12 text-grass',
  warning: 'bg-sun/16 text-sun',
  danger: 'bg-danger/10 text-danger',
  info: 'bg-info/10 text-info',
};

export const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  children,
  className = '',
  style,
}) => {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[12px] font-medium font-sans ${variantStyles[variant]} ${className}`}
      style={style}
    >
      {children}
    </span>
  );
};
