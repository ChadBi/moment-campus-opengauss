import React, { useState } from 'react';
import { KeyRound, Link2Off, ChevronDown, ChevronUp } from 'lucide-react';
import { useAuthStore } from '../store/useAuthStore';
import { authApi } from '../services/auth';
import { usersApi } from '../services/users';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import { Toast } from './ui/Toast';

export const AccountSecurityCard: React.FC = () => {
  const { user, updateUser } = useAuthStore();
  const [expanded, setExpanded] = useState(false); // 默认折叠，不默认展示输入框
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [unbindCode, setUnbindCode] = useState('');
  const [devCode, setDevCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  const handleSetPassword = async () => {
    if (password.length < 6 || password !== passwordConfirm) {
      setToast({ message: password.length < 6 ? '密码至少 6 位' : '两次密码不一致', type: 'error' });
      return;
    }
    setLoading(true);
    try {
      await authApi.setPassword(password, passwordConfirm);
      updateUser({ has_password: true });
      setPassword(''); setPasswordConfirm('');
      setToast({ message: '密码设置成功', type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e.response?.data?.detail || '设置密码失败', type: 'error' });
    } finally { setLoading(false); }
  };

  const sendUnbindCode = async () => {
    setLoading(true);
    try {
      const response = await usersApi.sendEducationEmailUnbindCode();
      setDevCode(response.code || null);
      setToast({ message: response.message, type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e.response?.data?.detail || '发送失败', type: 'error' });
    } finally { setLoading(false); }
  };

  const unbind = async () => {
    if (!/^\d{6}$/.test(unbindCode)) { setToast({ message: '请输入 6 位短信验证码', type: 'error' }); return; }
    setLoading(true);
    try {
      await usersApi.unbindEducationEmail(unbindCode);
      updateUser({ education_email: null, campus_verified: false });
      setUnbindCode(''); setDevCode(null);
      setToast({ message: '教育邮箱已解除绑定', type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e.response?.data?.detail || '解除绑定失败', type: 'error' });
    } finally { setLoading(false); }
  };

  if (!user || (user.has_password && !user.education_email)) return null;
  return <Card variant="outlined" padding="md" className="mb-4 opacity-90 hover:opacity-100 transition-opacity">
    <button
      type="button"
      onClick={() => setExpanded(!expanded)}
      className="w-full flex items-center justify-between text-left"
    >
      <h2 className="font-display font-semibold text-ink-sub text-sm flex items-center gap-2">
        <KeyRound size={15} className="text-ink-muted" />
        账号安全
        <span className="text-[10px] text-ink-muted font-normal">
          {!user.has_password ? '设置密码 / ' : ''}
          {user.education_email ? '解除邮箱绑定' : ''}
        </span>
      </h2>
      {expanded
        ? <ChevronUp size={16} className="text-ink-muted" />
        : <ChevronDown size={16} className="text-ink-muted" />}
    </button>
    {expanded && <div className="space-y-3 mt-3 pt-3 border-t border-line/60">
      {!user.has_password && <div className="rounded-[10px] border border-lake/20 bg-lake/5 p-3 space-y-2"><p className="text-sm text-ink flex items-center gap-2"><KeyRound size={16} className="text-lake" />设置密码</p><p className="text-xs text-ink-muted">小程序创建的账号可以设置一次密码，用于 Web 密码登录。</p><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="新密码（至少 6 位）" className="w-full px-3 py-2 rounded-[8px] border border-line/60 text-sm" /><input type="password" value={passwordConfirm} onChange={(e) => setPasswordConfirm(e.target.value)} placeholder="确认新密码" className="w-full px-3 py-2 rounded-[8px] border border-line/60 text-sm" /><Button size="sm" variant="primary" disabled={loading} onClick={handleSetPassword}>保存密码</Button></div>}
      {user.education_email && <div className="rounded-[10px] border border-danger/20 bg-danger/5 p-3 space-y-2"><p className="text-sm text-ink flex items-center gap-2"><Link2Off size={16} className="text-danger" />解除教育邮箱绑定</p><p className="text-xs text-ink-muted">当前绑定：{user.education_email}。需要当前手机号短信验证码确认。</p><Button size="sm" variant="secondary" disabled={loading} onClick={sendUnbindCode}>发送短信验证码</Button><input value={unbindCode} onChange={(e) => setUnbindCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="短信验证码" inputMode="numeric" maxLength={6} className="w-full px-3 py-2 rounded-[8px] border border-line/60 text-sm" />{devCode && <p className="text-xs text-lake">演示验证码：<span className="font-bold">{devCode}</span></p>}<Button size="sm" variant="danger" disabled={loading} onClick={unbind}>确认解除绑定</Button></div>}
    </div>}
    {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
  </Card>;
};
