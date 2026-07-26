import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { useCampusStore } from '../store/useCampusStore';
import { authApi, setInviteContext, getInviteContext, clearInviteContext } from '../services/auth';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Toast } from '../components/ui/Toast';
import { Mail, Lock, User, School as SchoolIcon, Ticket } from 'lucide-react';

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  const { currentSchoolName, currentSchoolCode } = useCampusStore();
  const [formData, setFormData] = useState({
    email: '',
    nickname: '',
    password: '',
    confirmPassword: '',
    inviteCode: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  // ACC-01.1: 读取注册后回跳目标
  const redirectTo = searchParams.get('redirect') || '/';

  // ACC-01.2: URL 参数 ?invite=xxx 自动填入邀请码并写入短期上下文
  useEffect(() => {
    const urlInvite = searchParams.get('invite');
    if (urlInvite) {
      setInviteContext(urlInvite);
      // 用 microtask 延迟同步 setState，避免 react-hooks/set-state-in-effect 规则告警
      void Promise.resolve().then(() => {
        setFormData((prev) => (prev.inviteCode ? prev : { ...prev, inviteCode: urlInvite }));
      });
      return;
    }
    // URL 无 invite 参数时，回填短期上下文中的邀请码（跨页跳转保留）
    const ctxInvite = getInviteContext();
    if (ctxInvite) {
      // 用 microtask 延迟同步 setState，避免 react-hooks/set-state-in-effect 规则告警
      void Promise.resolve().then(() => {
        setFormData((prev) => (prev.inviteCode ? prev : { ...prev, inviteCode: ctxInvite }));
      });
    }
  }, [searchParams]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.email || !formData.nickname || !formData.password || !formData.confirmPassword) {
      setError('请填写所有必填项');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    if (formData.password.length < 6) {
      setError('密码长度至少为6位');
      return;
    }

    // ACC-01.2: 不再固定 school_id=1，由 Axios 拦截器注入 X-School-Code 头
    // 后端 register 端点优先使用 X-School-Code 头解析 school_id
    if (!currentSchoolCode) {
      setError('无法确定注册学校，请先选择学校');
      return;
    }

    setLoading(true);
    try {
      // ACC-01.2: 若用户填了邀请码，同步写入短期上下文（确保跨刷新保留），
      // 同时作为请求参数传给后端 register 端点进行校验与消费
      const trimmedInvite = formData.inviteCode.trim();
      if (trimmedInvite) {
        setInviteContext(trimmedInvite);
      }
      const response = await authApi.register({
        email: formData.email,
        nickname: formData.nickname,
        password: formData.password,
        // ACC-01.2: 不传 school_id，由 X-School-Code 头注入（Axios 拦截器自动处理）
        invite_code: trimmedInvite || undefined,
      });
      setAuth(response.user, response.access_token, response.refresh_token);
      // ACC-01.2: 注册成功后清除邀请码短期上下文（已被后端消费）
      clearInviteContext();
      setToast({ message: '注册成功', type: 'success' });
      // ACC-01.1: 注册后回跳到原目标页
      setTimeout(() => navigate(redirectTo), 1000);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const message = e?.response?.data?.detail || '注册失败，请稍后重试';
      setError(message);
      setToast({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-mist px-4 py-10">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-7">
          <div className="relative w-[44px] h-[44px] rounded-[12px] bg-paper grid place-items-center shadow-sm mb-4 overflow-hidden">
            <span className="font-display font-bold text-[22px] text-lake leading-none">此</span>
          </div>
          <h1 className="text-xl font-display font-bold text-lake tracking-wide">加入此刻校园</h1>
          <p className="text-ink-muted text-sm mt-1.5">分享你的校园生活每一刻</p>
        </div>

        <Card variant="elevated" padding="lg">
          {/* ACC-01.2: 显示当前选择的学校 */}
          {currentSchoolName && (
            <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-[10px] bg-lake/5 border border-lake/20">
              <SchoolIcon size={14} className="text-lake flex-shrink-0" />
              <span className="text-sm text-ink">
                将加入：<span className="font-medium">{currentSchoolName}</span>
              </span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="邮箱"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="请输入邮箱"
              icon={<Mail size={16} />}
              required
            />

            <Input
              label="昵称"
              name="nickname"
              type="text"
              value={formData.nickname}
              onChange={handleChange}
              placeholder="请输入昵称"
              icon={<User size={16} />}
              required
            />

            <Input
              label="密码"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入密码（至少6位）"
              icon={<Lock size={16} />}
              required
            />

            <Input
              label="确认密码"
              name="confirmPassword"
              type="password"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="请再次输入密码"
              icon={<Lock size={16} />}
              required
            />

            {/* ACC-01.2: 邀请码输入框（可选）；URL ?invite=xxx 自动填入 */}
            <Input
              label="邀请码（可选）"
              name="inviteCode"
              type="text"
              value={formData.inviteCode}
              onChange={handleChange}
              placeholder="如有邀请码请填写，可加入对应学校"
              icon={<Ticket size={16} />}
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
              注册
            </Button>
          </form>

          <div className="mt-5 text-center text-sm">
            <span className="text-ink-muted">已有账号？</span>
            <Link to="/login" className="text-lake font-medium ml-1 hover:underline">
              立即登录
            </Link>
          </div>
        </Card>
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

export default RegisterPage;
