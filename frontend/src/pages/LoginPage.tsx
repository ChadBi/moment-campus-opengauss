import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { authApi } from '../services/auth';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Toast } from '../components/ui/Toast';
import { ArrowLeft, Lock, MessageSquare, Phone } from 'lucide-react';

const maskPhone = (phone: string) => phone.replace(/^(\d{3})\d{4}(\d{4})$/, '$1****$2');

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  const [mode, setMode] = useState<'sms' | 'password'>('sms');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [smsCode, setSmsCode] = useState('');
  const [cooldown, setCooldown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);
  const redirectTo = searchParams.get('redirect') || '/';

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [cooldown]);

  const sendCode = async () => {
    if (!/^1\d{10}$/.test(phone)) {
      setError('请输入有效的 11 位手机号');
      return;
    }
    try {
      const response = await authApi.sendSms(phone, 'login');
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
    if (!/^1\d{10}$/.test(phone)) {
      setError('请输入有效的 11 位手机号');
      return;
    }
    if (mode === 'sms' && !/^\d{6}$/.test(smsCode)) {
      setError('请输入 6 位短信验证码');
      return;
    }
    if (mode === 'password' && !password) {
      setError('请输入密码');
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.login(mode === 'sms' ? { phone, sms_code: smsCode } : { phone, password });
      setAuth(response.user, response.access_token, response.refresh_token);
      setToast({ message: `登录成功，欢迎回来 ${maskPhone(phone)}`, type: 'success' });
      const isAdmin = response.user.role === 'admin' || response.user.role === 'super_admin';
      navigate(redirectTo !== '/' ? redirectTo : isAdmin ? '/admin' : '/');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || '登录失败，请检查手机号和凭证');
      setToast({ message: '登录失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-mist px-4 py-10">
      <div className="w-full max-w-[400px]">
        <div className="flex flex-col items-center mb-7">
          <div className="w-[44px] h-[44px] rounded-[12px] bg-paper grid place-items-center shadow-sm mb-4">
            <span className="font-display font-bold text-[22px] text-lake leading-none">此</span>
          </div>
          <h1 className="font-display font-bold text-[24px] text-lake tracking-wide leading-none">欢迎回来</h1>
          <p className="text-ink-muted text-sm mt-2">手机号登录，进入此刻校园</p>
        </div>

        <Card variant="elevated" padding="lg">
          <div className="grid grid-cols-2 gap-1 p-1 mb-5 rounded-[10px] bg-mist" role="tablist" aria-label="登录方式">
            <button type="button" className={`py-2 rounded-[8px] text-sm ${mode === 'sms' ? 'bg-paper text-lake shadow-sm font-medium' : 'text-ink-muted'}`} onClick={() => { setMode('sms'); setError(null); }}>短信验证码</button>
            <button type="button" className={`py-2 rounded-[8px] text-sm ${mode === 'password' ? 'bg-paper text-lake shadow-sm font-medium' : 'text-ink-muted'}`} onClick={() => { setMode('password'); setError(null); }}>密码登录</button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <Input label="手机号" name="phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 11))} placeholder="请输入 11 位手机号" icon={<Phone size={16} />} autoComplete="tel" inputMode="numeric" required />
            {mode === 'sms' ? (
              <div className="flex gap-2 items-end">
                <Input label="短信验证码" name="smsCode" type="text" value={smsCode} onChange={(e) => setSmsCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="6 位验证码" icon={<MessageSquare size={16} />} inputMode="numeric" required />
                <Button type="button" variant="secondary" size="md" disabled={cooldown > 0} onClick={sendCode} className="shrink-0 min-w-[104px]">{cooldown > 0 ? `${cooldown}s 后重发` : '获取验证码'}</Button>
              </div>
            ) : (
              <Input label="密码" name="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="请输入密码" icon={<Lock size={16} />} autoComplete="current-password" required />
            )}
            {error && <div role="alert" className="text-danger text-sm text-center bg-danger/8 rounded-[10px] py-2 px-3">{error}</div>}
            <Button type="submit" variant="primary" size="lg" loading={loading} className="w-full">{loading ? '登录中...' : '登录'}</Button>
          </form>

          <div className="mt-5 flex items-center justify-between text-sm">
            <Link to="/register" className="text-lake font-medium hover:underline">还没有账号？立即注册</Link>
            <span className="text-ink-muted text-xs">手机号是唯一登录凭证</span>
          </div>
          <button type="button" onClick={() => navigate('/')} className="mt-4 w-full flex items-center justify-center gap-1.5 text-sm text-ink-muted hover:text-ink py-2"><ArrowLeft size={14} />以访客身份继续浏览</button>
        </Card>
      </div>
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};

export default LoginPage;
