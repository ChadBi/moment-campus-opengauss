import React from 'react';
import { Inbox } from 'lucide-react';
import { Button } from '../ui/Button';
import { StateLayout } from './StateLayout';

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  compact?: boolean;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon = <Inbox size={24} />,
  actionLabel,
  onAction,
  compact = false,
}) => (
  <StateLayout
    testId="state-empty"
    icon={icon}
    title={title}
    description={description}
    compact={compact}
    action={actionLabel && onAction ? (
      <Button variant="secondary" size="sm" onClick={onAction}>
        {actionLabel}
      </Button>
    ) : undefined}
  />
);
