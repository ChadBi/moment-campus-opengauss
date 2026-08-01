import React from 'react';

interface StateLayoutProps {
  testId: string;
  icon: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  compact?: boolean;
  role?: 'status' | 'alert';
}

export const StateLayout: React.FC<StateLayoutProps> = ({
  testId,
  icon,
  title,
  description,
  action,
  compact = false,
  role = 'status',
}) => (
  <div
    data-testid={testId}
    role={role}
    aria-live={role === 'alert' ? 'assertive' : 'polite'}
    className={`flex flex-col items-center justify-center text-center ${compact ? 'px-4 py-6' : 'px-6 py-12'}`}
  >
    <div className={`grid place-items-center rounded-[16px] bg-mist text-lake ${compact ? 'w-10 h-10 mb-3' : 'w-14 h-14 mb-4'}`}>
      {icon}
    </div>
    <h3 className={`font-display font-bold text-ink ${compact ? 'text-[15px]' : 'text-lg'}`}>
      {title}
    </h3>
    {description ? (
      <p className={`text-ink-muted leading-[1.6] max-w-md ${compact ? 'text-xs mt-1' : 'text-sm mt-1.5'}`}>
        {description}
      </p>
    ) : null}
    {action ? <div className={compact ? 'mt-3' : 'mt-5'}>{action}</div> : null}
  </div>
);
