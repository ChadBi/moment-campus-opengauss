import React, { useState } from 'react';
import { BadgeCheck, Mail, Shield } from 'lucide-react';
import { useAuthStore } from '../store/useAuthStore';
import { useCampusStore } from '../store/useCampusStore';
import { isRegistrationSchool } from '../utils/campus-permission';
import { usersApi } from '../services/users';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import { VerifiedBadge } from './VerifiedBadge';
import { Toast } from './ui/Toast';

export const CampusVerifyCard: React.FC = () => {
  const { user, updateUser } = useAuthStore();
  const currentSchoolId = useCampusStore((state) => state.currentSchoolId);
  const registrationSchool = isRegistrationSchool(user, currentSchoolId);
  const campusVerified = registrationSchool && Boolean(user?.campus_verified);
  const [educationEmail, setEducationEmail] = useState(user?.education_email || '');
  const [code, setCode] = useState('');
  const [devCode, setDevCode] = useState<string | null>(null);
  const [step, setStep] = useState<'email' | 'code'>('email');
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  if (!registrationSchool) return null;

  const handleSend = async () => {
    if (!educationEmail.trim() || !educationEmail.includes('@')) {
      setToast({ message: '请输入当前学校的教育邮箱', type: 'error' });
      return;
    }
    setLoading(true);
    try {
      const response = await usersApi.sendEducationEmail(educationEmail.trim().toLowerCase());
      setDevCode(response.code || null);
      setStep('code');
      setToast({ message: response.message, type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e.response?.data?.detail || '验证码发送失败，请重试', type: 'error' });
    } finally { setLoading(false); }
  };

  const handleConfirm = async () => {
    if (!/^\d{6}$/.test(code)) {
      setToast({ message: '请输入 6 位数字验证码', type: 'error' });
      return;
    }
    setLoading(true);
    try {
      await usersApi.confirmEducationEmail({ code });
      updateUser({ education_email: educationEmail.trim().toLowerCase(), campus_verified: true });
      setToast({ message: '教育邮箱认证成功', type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e.response?.data?.detail || '认证失败，请重试', type: 'error' });
    } finally { setLoading(false); }
  };

  return (
    <Card variant="elevated" padding="lg" className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-semibold text-ink flex items-center gap-2"><Shield size={18} className="text-lake" />学校认证</h2>
        {campusVerified && <VerifiedBadge />}
      </div>
      {campusVerified ? (
        <div className="flex items-start gap-3 p-3 rounded-[10px] bg-grass/5 border border-grass/20">
          <BadgeCheck size={18} className="text-grass flex-shrink-0 mt-0.5" />
          <div className="text-sm"><p className="text-ink font-medium">已认证</p><p className="text-[11px] text-ink-muted mt-1">认证邮箱：{user?.education_email}</p></div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-[12px] text-ink-muted leading-relaxed">提交当前学校教育邮箱并完成验证码校验，获得更多权限，教育邮箱只用于校园认证。</p>
          {step === 'email' ? <>
            <label className="block"><span className="text-xs text-ink-sub">教育邮箱</span><div className="relative mt-1"><Mail size={15} className="absolute left-3 top-2.5 text-ink-muted" /><input value={educationEmail} onChange={(event) => setEducationEmail(event.target.value)} type="email" placeholder="name@school.edu.cn" className="w-full pl-9 pr-3 py-2 rounded-[10px] border border-line/60 focus:border-lake focus:outline-none text-sm" /></div></label>
            <Button variant="primary" disabled={loading} onClick={handleSend} icon={<Shield size={14} />}>{loading ? '发送中...' : '发送验证码'}</Button>
          </> : <>
            <p className="rounded-[10px] bg-lake/5 border border-lake/20 px-3 py-2 text-xs text-lake">验证码已发送至 <span className="font-data">{educationEmail}</span></p>
            <input value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" maxLength={6} placeholder="请输入 6 位验证码" className="w-full px-3 py-2 rounded-[10px] border border-line/60 focus:border-lake focus:outline-none text-sm" />
            {devCode && <p className="text-xs text-lake">演示验证码：<span className="font-bold tracking-wide">{devCode}</span></p>}
            <div className="flex gap-2"><Button variant="primary" disabled={loading} onClick={handleConfirm} icon={<BadgeCheck size={14} />}>{loading ? '确认中...' : '确认认证'}</Button><Button variant="text" disabled={loading} onClick={() => setStep('email')}>返回修改</Button></div>
          </>}
        </div>
      )}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </Card>
  );
};
