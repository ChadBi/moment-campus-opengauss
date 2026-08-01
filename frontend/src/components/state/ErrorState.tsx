import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '../ui/Button';
import { StateLayout } from './StateLayout';

interface ErrorStateProps {
  title?: string;
  description?: string;
  retryLabel?: string;
  onRetry?: () => void;
  compact?: boolean;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = '暂时无法加载',
  description = '网络开了个小差，请稍后再试。',
  retryLabel = '重新加载',
  onRetry,
  compact = false,
}) => (
  <StateLayout
    testId="state-error"
    role="alert"
    icon={<AlertTriangle className="text-danger" size={compact ? 20 : 24} />}
    title={title}
    description={description}
    compact={compact}
    action={onRetry ? (
      <Button
        variant="secondary"
        size="sm"
        icon={<RefreshCw size={14} />}
        onClick={onRetry}
      >
        {retryLabel}
      </Button>
    ) : undefined}
  />
);
