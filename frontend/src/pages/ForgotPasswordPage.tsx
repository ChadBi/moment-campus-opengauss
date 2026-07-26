import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../services/auth';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Toast } from '../components/ui/Toast';
import { Mail, ArrowLeft, KeyRound, CheckCircle } from 'lucide-react';

/**
 * ACC-01.3: 找回密码页面
 *
 * 两步流程：
 * 1. 输入邮箱 → 调用 forgot-password → 本地开发环境返回 token
 * 2. 输入 token + 新密码 → 调用 reset-password → 完成
 *
 * 本地开发环境说明：
 * - 无邮件服务，token 通过 API 响应返回供测试
 * - 生产环境 token 会通过邮件发送（未实现邮件服务时记日志）
 */
const ForgotPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  const handleSendResetEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email) {
      setError('请输入邮箱');
      return;
    }

    setLoading(true);
    try {
      const resp = await authApi.forgotPassword(email);
      // 本地开发环境：resp.reset_token 存在
      if (resp.reset_token) {
        setResetToken(resp.reset_token);
        setToast({
          message: '已生成重置 Token（本地开发环境直接返回，生产环境将发送邮件）',
          type: 'info',
        });
      } else {
        setToast({
          message: resp.message || '如该邮箱已注册，重置链接已发送',
          type: 'success',
        });
      }
      setStep(2);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const message = e?.response?.data?.detail || '操作失败，请稍后重试';
      setError(message);
      setToast({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!resetToken) {
      setError('请输入重置 Token');
      return;
    }
    if (!newPassword) {
      setError('请输入新密码');
      return;
    }
    if (newPassword.length < 6) {
      setError('密码长度至少为6位');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    setLoading(true);
    try {
      const resp = await authApi.resetPassword(resetToken, newPassword);
      setToast({ message: resp.message || '密码已重置，请使用新密码登录', type: 'success' });
      setTimeout(() => navigate('/login'), 1500);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const message = e?.response?.data?.detail || '重置失败，请稍后重试';
      setError(message);
      setToast({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-mist px-4 py-10">
      <div className="w-full max-w-[400px]">
        <div className="flex flex-col items-center mb-7">
          <div className="relative w-[44px] h-[44px] rounded-[12px] bg-paper grid place-items-center shadow-sm overflow-hidden mb-4">
            <KeyRound size={22} className="text-lake" />
          </div>
          <h1 className="font-display font-bold text-[24px] text-lake tracking-wide leading-none">
            找回密码
          </h1>
          <p className="text-ink-muted text-sm mt-2">
            {step === 1 ? '输入注册邮箱，获取重置链接' : '输入 Token 和新密码'}
          </p>
        </div>

        <Card variant="elevated" padding="lg">
          {step === 1 ? (
            <form onSubmit={handleSendResetEmail} className="space-y-4">
              <Input
                label="邮箱"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="请输入注册邮箱"
                icon={<Mail size={16} />}
                required
              />

              {error && (
                <div className="text-danger text-sm text-center bg-danger/8 rounded-[10px] py-2 px-3">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={loading}
                className="w-full"
              >
                发送重置链接
              </Button>
            </form>
          ) : (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <Input
                label="重置 Token"
                type="text"
                value={resetToken}
                onChange={(e) => setResetToken(e.target.value)}
                placeholder="请输入重置 Token"
                required
              />

              <Input
                label="新密码"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="请输入新密码（至少6位）"
                required
              />

              <Input
                label="确认新密码"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="请再次输入新密码"
                required
              />

              {error && (
                <div className="text-danger text-sm text-center bg-danger/8 rounded-[10px] py-2 px-3">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={loading}
                className="w-full"
              >
                重置密码
              </Button>
            </form>
          )}

          <div className="mt-5 flex items-center justify-between text-sm">
            <Link
              to="/login"
              className="text-ink-muted hover:text-lake hover:underline flex items-center gap-1"
            >
              <ArrowLeft size={14} />
              返回登录
            </Link>
            {step === 2 && (
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-ink-muted hover:text-lake hover:underline"
              >
                重新发送
              </button>
            )}
          </div>
        </Card>

        {step === 2 && resetToken && (
          <div className="mt-3 flex items-start gap-2 px-3 py-2 rounded-[10px] bg-info/10 border border-info/20">
            <CheckCircle size={14} className="text-info flex-shrink-0 mt-0.5" />
            <p className="text-xs text-ink-muted leading-relaxed">
              本地开发环境已自动填入 Token。生产环境 Token 将通过邮件发送，30 分钟内有效，仅可使用一次。
            </p>
          </div>
        )}
      </div>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};

export default ForgotPasswordPage;
