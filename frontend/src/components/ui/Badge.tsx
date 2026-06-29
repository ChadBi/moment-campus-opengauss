import React from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-mist text-ink-sub',
  success: 'bg-grass/15 text-grass',
  warning: 'bg-sun/18 text-sun',
  danger: 'bg-danger/12 text-danger',
  info: 'bg-info/12 text-info',
};

export const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  children,
  className = '',
}) => {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold font-data tracking-wide ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
};
