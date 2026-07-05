import React from 'react';

type CardVariant = 'elevated' | 'outlined' | 'filled';

interface CardProps {
  variant?: CardVariant;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  className?: string;
  children: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}

const variantStyles: Record<CardVariant, string> = {
  elevated:
    'bg-paper border border-line/60 shadow-md rounded-[16px] hover:shadow-lg hover:-translate-y-0.5',
  outlined:
    'bg-paper border border-line rounded-[16px] hover:shadow-sm hover:-translate-y-0.5 hover:border-lake/30',
  filled:
    'bg-paper-hover rounded-[16px] hover:shadow-sm hover:-translate-y-0.5',
};

const paddingStyles: Record<NonNullable<CardProps['padding']>, string> = {
  none: '',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
};

export const Card: React.FC<CardProps> = ({
  variant = 'elevated',
  padding = 'md',
  className = '',
  children,
  onClick,
  style,
}) => {
  const baseStyles =
    'transition-[transform,box-shadow,border-color] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)]';
  const variantStyle = variantStyles[variant];
  const paddingStyle = paddingStyles[padding];
  const clickable = onClick ? 'cursor-pointer' : '';

  return (
    <div
      className={`${baseStyles} ${variantStyle} ${paddingStyle} ${clickable} ${className}`}
      onClick={onClick}
      style={style}
    >
      {children}
    </div>
  );
};
