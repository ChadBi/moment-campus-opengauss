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
    'bg-paper/86 border border-white/80 shadow-lg backdrop-blur-xl rounded-xl hover:-translate-y-0.5 hover:shadow-xl',
  outlined:
    'bg-paper border border-line rounded-lg hover:-translate-y-0.5 hover:shadow-sm hover:border-lake/40',
  filled:
    'bg-mist rounded-lg hover:-translate-y-0.5 hover:shadow-sm',
};

const paddingStyles: Record<NonNullable<CardProps['padding']>, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-7',
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
    'transition-[transform,box-shadow,border-color] duration-[200ms] ease-out';
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
