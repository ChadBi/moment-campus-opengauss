import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { BadgeCheck, LogIn, ArrowRight } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useAuthStore } from '../store/useAuthStore';

/**
 * B-01: 校园身份认证验证链接落地页（/verify-campus?token=xxx）
 *
 * - 从 URL 提取一次性 token，存入 sessionStorage.pending_verify_token
 * - 已登录：跳转个人中心，认证卡片自动读取 token 完成确认
 * - 未登录：提示登录后完成认证（回跳个人中心）
 */
const VerifyLinkPage: React.FC = () => {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    const token = params.get('token');
    if (token) {
      sessionStorage.setItem('pending_verify_token', token);
    }
  }, [params]);

  const handleGo = () => {
    if (isAuthenticated) {
      navigate('/profile');
    } else {
      navigate('/login?redirect=/profile');
    }
  };

  return (
    <div className="max-w-md mx-auto py-16 px-4">
      <Card variant="elevated" padding="lg" className="text-center py-12">
        <div className="w-16 h-16 mx-auto rounded-[16px] bg-grass/10 grid place-items-center mb-5">
          <BadgeCheck size={32} className="text-grass" />
        </div>
        <h1 className="text-xl font-display font-bold text-ink mb-2">
          校园身份认证
        </h1>
        <p className="text-sm text-ink-sub leading-relaxed mb-6">
          验证链接已识别。完成认证后，你的昵称旁将显示「已认证」徽标。
        </p>
        <Button
          variant="primary"
          onClick={handleGo}
          icon={isAuthenticated ? <ArrowRight size={16} /> : <LogIn size={16} />}
        >
          {isAuthenticated ? '前往个人中心完成认证' : '登录后完成认证'}
        </Button>
      </Card>
    </div>
  );
};

export default VerifyLinkPage;
