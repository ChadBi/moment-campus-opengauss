import React, { useState } from 'react';
import { BadgeCheck, Shield } from 'lucide-react';
import { useAuthStore } from '../store/useAuthStore';
import { usersApi } from '../services/users';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import { VerifiedBadge } from './VerifiedBadge';
import { Toast } from './ui/Toast';

type ToastState = {
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
} | null;

/**
 * B-01: 校园身份认证卡片（个人中心）。
 * 未认证：向当前登录教育邮箱发送 6 位数字验证码 → 输入并确认。
 * 已认证：展示「已认证」徽标与说明。
 */
export const CampusVerifyCard: React.FC = () => {
  const { user, updateUser } = useAuthStore();
  const campusVerified = Boolean(user?.campus_verified);

  const [step, setStep] = useState<'form' | 'code'>('form');
  const [code, setCode] = useState('');
  const [devCode, setDevCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);

  const handleSend = async () => {
    setLoading(true);
    try {
      const res = await usersApi.sendCampusVerify();
      setDevCode(res.code ?? null);
      setStep('code');
      setToast({ message: res.message, type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '发送失败，请重试', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    const credential = code.trim();
    if (!/^\d{6}$/.test(credential)) {
      setToast({ message: '请输入 6 位数字验证码', type: 'error' });
      return;
    }
    setLoading(true);
    try {
      await usersApi.confirmCampusVerify({ code: credential });
      updateUser({ campus_verified: true });
      setToast({ message: '校园身份认证成功', type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '认证失败，请重试', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card variant="elevated" padding="lg" className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-semibold text-ink flex items-center gap-2">
          <Shield size={18} className="text-lake" />
          校园身份认证
        </h2>
        {campusVerified && <VerifiedBadge />}
      </div>

      {campusVerified ? (
        <div className="flex items-start gap-3 p-3 rounded-[10px] bg-grass/5 border border-grass/20">
          <BadgeCheck size={18} className="text-grass flex-shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="text-ink font-medium">你已完成校园身份认证</p>
            <p className="text-[11px] text-ink-muted mt-1 leading-relaxed">
              昵称旁会显示「已认证」徽标，帮助同学识别你的信息更可信。
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-[12px] text-ink-muted leading-relaxed">
            通过登录邮箱验证身份，昵称旁将显示「已认证」徽标，让同学更信任你的信息。
            支持所在学校官方域名和 qq.com 邮箱注册/登录。
          </p>

          {step === 'form' ? (
            <>
              <div className="rounded-[10px] bg-lake/5 border border-lake/20 px-3 py-2 text-xs text-lake">
                <span className="font-medium">认证邮箱：</span>
                <span className="font-data">{user?.email}</span>
                <span className="block text-[10px] text-ink-muted mt-0.5">
                  验证凭证将发送至该邮箱
                </span>
              </div>
              <Button
                variant="primary"
                disabled={loading}
                onClick={handleSend}
                icon={<Shield size={14} />}
              >
                {loading ? '发送中...' : '发送验证码'}
              </Button>
            </>
          ) : (
            <>
              <label className="block">
                <span className="text-xs text-ink-sub">6 位数字验证码</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  maxLength={6}
                  placeholder="请输入邮箱中的 6 位验证码"
                  className="mt-1 w-full px-3 py-2 rounded-[10px] border border-line/60 focus:border-lake focus:outline-none text-sm"
                />
              </label>
              {devCode && (
                <div className="rounded-[8px] bg-lake/5 border border-lake/20 px-3 py-2 text-xs text-lake">
                  👇 演示环境验证码：
                  <span className="font-data font-bold tracking-wide break-all">{devCode}</span>
                  <span className="block text-[10px] text-ink-muted mt-0.5">
                    直接复制到上方输入框即可完成认证
                  </span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  disabled={loading}
                  onClick={handleConfirm}
                  icon={<BadgeCheck size={14} />}
                >
                  {loading ? '确认中...' : '确认认证'}
                </Button>
                <Button
                  variant="text"
                  disabled={loading}
                  onClick={() => setStep('form')}
                >
                  返回修改
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </Card>
  );
};
