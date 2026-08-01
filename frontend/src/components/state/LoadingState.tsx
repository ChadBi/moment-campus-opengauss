import React from 'react';
import { Loader2 } from 'lucide-react';
import { StateLayout } from './StateLayout';

interface LoadingStateProps {
  title?: string;
  description?: string;
  compact?: boolean;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  title = '正在加载',
  description,
  compact = false,
}) => (
  <StateLayout
    testId="state-loading"
    icon={<Loader2 className="animate-spin" size={compact ? 20 : 26} />}
    title={title}
    description={description}
    compact={compact}
  />
);
