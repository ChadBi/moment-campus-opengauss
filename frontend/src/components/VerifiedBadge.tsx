import React from 'react';
import { BadgeCheck } from 'lucide-react';

interface VerifiedBadgeProps {
  className?: string;
}

/**
 * B-01: 校园身份认证徽标。
 * 显示在已认证用户的昵称旁，提升内容真实性与信任感。
 */
export const VerifiedBadge: React.FC<VerifiedBadgeProps> = ({ className = '' }) => {
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-lake text-xs font-medium ${className}`}
      title="已通过校园身份认证"
      aria-label="已认证"
    >
      <BadgeCheck size={13} className="shrink-0" aria-hidden />
      <span className="hidden sm:inline whitespace-nowrap">已认证</span>
    </span>
  );
};