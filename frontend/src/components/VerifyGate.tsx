import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, LogIn } from 'lucide-react';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import { useAuthStore } from '../store/useAuthStore';

interface VerifyGateProps {
  children: React.ReactNode;
  /** 自定义引导文案（默认：完成校园身份认证后即可发布） */
  message?: string;
  /** 紧凑模式（行内卡片，用于评论框/评分区等局部区域） */
  compact?: boolean;
}

/**
 * D4: 写操作认证门禁（未认证全站只读）。
 *
 * 包裹发帖/评论/评价/协同验证等写入区域：
 * - 未登录 → 引导登录
 * - 已登录但未完成校园认证 → 引导前往个人中心认证
 * - 已认证 → 正常渲染 children
 */
export const VerifyGate: React.FC<VerifyGateProps> = ({
  children,
  message = '完成校园身份认证后即可发布内容',
  compact = false,
}) => {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const campusVerified = useAuthStore((s) => Boolean(s.user?.campus_verified));

  if (isAuthenticated && campusVerified) {
    return <>{children}</>;
  }

  if (compact) {
    return (
      <div className="rounded-[10px] border border-lake/25 bg-lake/[0.04] px-3 py-2.5 flex items-center gap-2">
        <ShieldCheck size={15} className="text-lake flex-shrink-0" />
        <p className="text-xs text-ink-sub flex-1">{message}</p>
        <Button
          variant="text"
          size="sm"
          onClick={() => navigate(isAuthenticated ? '/profile' : '/login?redirect=/profile')}
          icon={isAuthenticated ? undefined : <LogIn size={12} />}
        >
          {isAuthenticated ? '去认证' : '去登录'}
        </Button>
      </div>
    );
  }

  return (
    <Card variant="elevated" padding="lg" className="text-center py-12">
      <div className="w-16 h-16 mx-auto rounded-[16px] bg-lake/10 grid place-items-center mb-5">
        <ShieldCheck size={30} className="text-lake" />
      </div>
      <h3 className="text-lg font-display font-bold text-ink mb-2">
        {isAuthenticated ? '完成校园身份认证后即可发布' : '登录后即可发布'}
      </h3>
      <p className="text-sm text-ink-sub mb-6">{message}</p>
      <Button
        variant="primary"
        onClick={() => navigate(isAuthenticated ? '/profile' : '/login?redirect=/profile')}
        icon={isAuthenticated ? undefined : <LogIn size={16} />}
      >
        {isAuthenticated ? '前往个人中心认证' : '去登录'}
      </Button>
    </Card>
  );
};
