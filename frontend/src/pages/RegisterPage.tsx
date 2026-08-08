import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { useCampusStore } from '../store/useCampusStore';
import { authApi } from '../services/auth';
import { schoolsApi } from '../services/schools';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Toast } from '../components/ui/Toast';
import { KeyRound, Lock, MessageSquare, Phone, School as SchoolIcon } from 'lucide-react';

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  const { schools, setSchools, setCurrentSchool } = useCampusStore();
  const [phone, setPhone] = useState('');
  const [smsCode, setSmsCode] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [schoolId, setSchoolId] = useState<number | ''>('');
  const [cooldown, setCooldown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);
  const redirectTo = searchParams.get('redirect') || '/';

  useEffect(() => {
    if (schools.length > 0) return;
    let cancelled = false;
    schoolsApi.listSchools().then((list) => { if (!cancelled) setSchools(list); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [schools.length, setSchools]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [cooldown]);

  const sendCode = async () => {
    if (!/^1\d{10}$/.test(phone)) { setError('请输入有效的 11 位手机号'); return; }
    try {
      const response = await authApi.sendSms(phone, 'register');
      setCooldown(60);
      setToast({ message: response.code ? `${response.message}（演示验证码：${response.code}）` : response.message, type: 'success' });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || '验证码发送失败，请稍后重试');
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!/^1\d{10}$/.test(phone)) return setError('请输入有效的 11 位手机号');
    if (!/^\d{6}$/.test(smsCode)) return setError('请输入 6 位短信验证码');
    if (password.length < 6) return setError('密码长度至少为 6 位');
    if (password !== passwordConfirm) return setError('两次输入的密码不一致');
    if (typeof schoolId !== 'number') return setError('请选择注册学校');

    setLoading(true);
    try {
      const response = await authApi.register({ phone, sms_code: smsCode, password, password_confirm: passwordConfirm, school_id: schoolId });
      setAuth(response.user, response.access_token, response.refresh_token);
      const school = schools.find((item) => item.id === schoolId);
      if (school) setCurrentSchool(school);
      setToast({ message: '注册成功', type: 'success' });
      window.setTimeout(() => navigate(redirectTo), 500);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || '注册失败，请稍后重试');
      setToast({ message: '注册失败', type: 'error' });
    } finally { setLoading(false); }
  };

  const selectedSchool = schools.find((school) => school.id === schoolId);
  return (
    <div className="min-h-screen flex items-center justify-center bg-mist px-4 py-10">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-7">
          <div className="w-[44px] h-[44px] rounded-[12px] bg-paper grid place-items-center shadow-sm mb-4"><span className="font-display font-bold text-[22px] text-lake">此</span></div>
          <h1 className="text-xl font-display font-bold text-lake tracking-wide">加入此刻校园</h1>
          <p className="text-ink-muted text-sm mt-1.5">手机号注册，认证后获得校园徽标</p>
        </div>
        <Card variant="elevated" padding="lg">
          {selectedSchool && <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-[10px] bg-lake/5 border border-lake/20 text-sm text-ink"><SchoolIcon size={14} className="text-lake" />将加入：<span className="font-medium">{selectedSchool.name}</span></div>}
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <Input label="手机号" name="phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 11))} placeholder="请输入 11 位手机号" icon={<Phone size={16} />} autoComplete="tel" inputMode="numeric" required />
            <div className="flex gap-2 items-end">
              <Input label="短信验证码" name="smsCode" type="text" value={smsCode} onChange={(e) => setSmsCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="6 位验证码" icon={<MessageSquare size={16} />} inputMode="numeric" required />
              <Button type="button" variant="secondary" size="md" disabled={cooldown > 0} onClick={sendCode} className="shrink-0 min-w-[104px]">{cooldown > 0 ? `${cooldown}s 后重发` : '获取验证码'}</Button>
            </div>
            <Input label="密码" name="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="至少 6 位密码" icon={<Lock size={16} />} autoComplete="new-password" required />
            <Input label="确认密码" name="passwordConfirm" type="password" value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} placeholder="再次输入密码" icon={<KeyRound size={16} />} autoComplete="new-password" required />
            <div><label htmlFor="register-school" className="block text-sm font-medium text-ink mb-1.5">注册学校<span className="text-danger ml-1">*</span></label><select id="register-school" value={schoolId} onChange={(e) => setSchoolId(e.target.value ? Number(e.target.value) : '')} className="w-full px-3 py-2.5 rounded-[10px] border border-line/60 bg-paper text-sm focus:border-lake focus:outline-none" required><option value="">请选择学校</option>{schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}</select></div>
            {error && <div role="alert" className="text-danger text-sm text-center bg-danger/8 rounded-[10px] py-2 px-3">{error}</div>}
            <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full">{loading ? '注册中...' : '注册'}</Button>
          </form>
          <p className="mt-5 text-center text-sm text-ink-muted">已有账号？<Link to="/login" className="text-lake font-medium hover:underline ml-1">立即登录</Link></p>
        </Card>
      </div>
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};

export default RegisterPage;
