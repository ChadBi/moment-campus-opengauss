import React from 'react';

interface AvatarProps {
  src?: string;
  alt?: string;
  fallback?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

const sizeStyles: Record<NonNullable<AvatarProps['size']>, string> = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-12 h-12 text-base',
  xl: 'w-16 h-16 text-lg',
};

export const Avatar: React.FC<AvatarProps> = ({
  src,
  alt = '',
  fallback,
  size = 'md',
  className = '',
}) => {
  const [hasError, setHasError] = React.useState(false);

  if (src && !hasError) {
    return (
      <img
        src={src}
        alt={alt}
        className={`rounded-md object-cover ring-1 ring-line ${sizeStyles[size]} ${className}`}
        onError={() => setHasError(true)}
      />
    );
  }

  return (
    <div
      className={`rounded-md bg-mist text-lake flex items-center justify-center font-semibold font-sans ring-1 ring-line ${sizeStyles[size]} ${className}`}
    >
      {fallback || alt?.charAt(0)?.toUpperCase() || '?'}
    </div>
  );
};
