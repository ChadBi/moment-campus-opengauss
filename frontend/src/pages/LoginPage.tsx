import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { authApi, getInviteContext, clearInviteContext } from '../services/auth';
import { schoolsApi } from '../services/schools';
import { useCampusStore } from '../store/useCampusStore';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Toast } from '../components/ui/Toast';
import { Mail, Lock, ArrowLeft } from 'lucide-react';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  const { currentSchoolCode, setMemberships } = useCampusStore();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  // ACC-01.1: 读取登录后回跳目标
  const redirectTo = searchParams.get('redirect') || '/';

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError(null);
  };

  // ACC-01.2: 登录成功后若短期上下文有 invite_code，自动调用 join API 消费邀请码
  // 邀请码与当前学校 code 绑定（后端 /schools/{code}/join 会校验 school_id 匹配）
  const consumeInviteAfterLogin = async (): Promise<void> => {
    const inviteCode = getInviteContext();
    if (!inviteCode) return;
    if (!currentSchoolCode) {
      // 无学校上下文无法 join，保留 invite 上下文等待下次时机
      return;
    }
    try {
      await schoolsApi.joinSchool(currentSchoolCode, inviteCode);
      // 消费成功后刷新 memberships 列表（确保首页切换器看到新学校）
      try {
        const memberships = await schoolsApi.listMyMemberships();
        setMemberships(memberships);
      } catch {
        // 刷新 memberships 失败不阻塞登录主流程
      }
    } catch {
      // 消费失败不阻塞登录（邀请码可能已过期/已使用/不匹配当前学校）
      // 保留 invite 上下文让用户在注册流程或个人中心手动处理
      return;
    }
    clearInviteContext();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.email || !formData.password) {
      setError('请填写所有必填项');
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.login({ email: formData.email, password: formData.password });
      setAuth(response.user, response.access_token, response.refresh_token);
      // ACC-01.2: 登录后自动消费短期上下文中的邀请码（失败不阻塞登录主流程）
      await consumeInviteAfterLogin();
      setToast({ message: '登录成功', type: 'success' });
      // ACC-01.1: 优先回跳到原目标页；admin 角色且无明确回跳目标时进后台
      const role = response.user?.role;
      const isAdmin = role === 'admin' || role === 'super_admin';
      const target = redirectTo !== '/' ? redirectTo : (isAdmin ? '/admin' : '/');
      // 保留 URL 中的 school 参数（如果存在），确保登录后仍在同一学校上下文
      if (searchParams.get('school')) {
        const sep = target.includes('?') ? '&' : '?';
        navigate(`${target}${sep}school=${searchParams.get('school')}`);
      } else {
        navigate(target);
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const message = e?.response?.data?.detail || '登录失败，请检查邮箱和密码';
      setError(message);
      setToast({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-mist px-4 py-10">
      <div className="w-full max-w-[400px]">
        {/* UX-01.7: 页面顶部 SkipLink，键盘用户可跳过品牌区直达表单 */}
        <a
          href="#login-form"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[200] focus:px-4 focus:py-2 focus:bg-lake focus:text-white focus:rounded-[8px] focus:shadow-lamp"
        >
          跳转到登录表单
        </a>

        <div className="flex flex-col items-center mb-7">
          <div className="relative w-[44px] h-[44px] rounded-[12px] bg-paper grid place-items-center shadow-sm overflow-hidden mb-4">
            <span
              className="font-display font-bold text-[22px] text-lake leading-none"
              aria-hidden="true"
            >
              此
            </span>
          </div>
          <h1 className="font-display font-bold text-[24px] text-lake tracking-wide leading-none">
            欢迎回来
          </h1>
          <p className="text-ink-muted text-sm mt-2">把会消失的校园经验留下来</p>
        </div>

        <Card variant="elevated" padding="lg">
          <form
            id="login-form"
            onSubmit={handleSubmit}
            className="space-y-4"
            aria-labelledby="login-heading"
            noValidate
          >
            <h2 id="login-heading" className="sr-only">
              账号登录
            </h2>

            <Input
              label="邮箱"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="请输入邮箱"
              icon={<Mail size={16} />}
              autoComplete="email"
              inputMode="email"
              required
              aria-required="true"
            />

            <Input
              label="密码"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入密码"
              icon={<Lock size={16} />}
              autoComplete="current-password"
              required
              aria-required="true"
            />

            {error && (
              <div
                role="alert"
                aria-live="assertive"
                className="text-danger text-sm text-center bg-danger/8 rounded-[10px] py-2 px-3"
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full"
              aria-busy={loading}
            >
              {loading ? '登录中...' : '登录'}
            </Button>
          </form>

          <div className="mt-5 flex items-center justify-between text-sm">
            <Link
              to="/register"
              className="text-lake font-medium hover:underline focus:outline-none focus-visible:underline"
            >
              还没有账号？立即注册
            </Link>
            {/* ACC-01.3: 找回密码入口 */}
            <Link
              to="/forgot-password"
              className="text-ink-muted hover:text-lake hover:underline focus:outline-none focus-visible:underline"
            >
              忘记密码？
            </Link>
          </div>

          <button
            type="button"
            onClick={() => navigate('/')}
            className="mt-4 w-full flex items-center justify-center gap-1.5 text-sm text-ink-muted hover:text-ink transition-colors py-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2 focus-visible:rounded-[8px]"
          >
            <ArrowLeft size={14} aria-hidden="true" />
            以访客身份继续浏览
          </button>
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

export default LoginPage;
